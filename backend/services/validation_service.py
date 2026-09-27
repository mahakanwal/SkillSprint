"""
services/validation_service.py

Pipeline 2 -- the Python Ground-Truth Validation Pipeline.

Runs every deterministic check against a GenAI-generated onboarding plan,
decides the plan's verification status (SRS Step 47), stores the scores on
the plan, and writes one ValidationResult row per Requirement Matrix row --
the GenAI-vs-Python comparison the reviewer sees (SRS Step 46).

No GenAI API is used anywhere in this pipeline.

Checks (SRS Step 28 onward):
  schema          JSON structure + semantic IDs            (Step 38)
  coverage        mandatory requirement coverage           (Step 29)
  traceability    valid source references                  (Step 30)
  consistency     GenAI fields vs Requirement Matrix        (Section 1.2, Table 1)
  hallucination   unsupported generated content            (Steps 31-32)
  contradiction   conflicts with sources, with precedence  (Steps 33-34)
  duplicates      duplicated learning items                (Step 35)
  role_relevance  content irrelevant to the role           (Step 36)
  sequence        stages, prerequisites, ordering          (Steps 13, 26-27)
  quiz            answer + distractor validation           (Steps 21-22)
  security        injected instructions in the OUTPUT      (Step 42)
  outdated        citations of obsolete document versions  (Steps 8, 57)
"""

from sqlalchemy.orm import Session

from database.models import Employee, RequirementMatrix, OnboardingPlan, ValidationResult, SecurityFlag
from genai_pipeline.context_builder import build_role_context, source_text as ctx_source_text
from python_validation.coverage_checker import check_coverage
from python_validation.traceability_checker import check_traceability
from python_validation.consistency_checker import check_consistency
from python_validation.hallucination_detector import detect_hallucinations
from python_validation.contradiction_detector import detect_contradictions
from python_validation.duplicate_detector import detect_duplicates
from python_validation.role_relevance_checker import check_role_relevance
from python_validation.sequence_validator import validate_sequence
from python_validation.quiz_validator import validate_quiz
from python_validation.schema_validator import validate_plan_schema
from python_validation.text_utils import plan_items, requirement_text, normalize
from security.prompt_injection_guard import scan_items


class ValidationError(Exception):
    pass


FLAGGED_STATUSES = {"Unsupported", "Contradictory", "Incomplete", "Manual Review Required", "Partially Verified"}


# ----------------------------------------------------------------- helpers
def _security_check(generated_plan: dict) -> dict:
    findings = scan_items((it["label"], it["text"]) for it in plan_items(generated_plan))
    notes = generated_plan.get("security_notes") or [] if isinstance(generated_plan, dict) else []
    return {
        "score": 100.0 if not findings else max(0.0, 100.0 - 25 * len(findings)),
        "findings": findings,
        "model_security_notes": notes,
        "status": "passed" if not findings else "failed",
    }


def _outdated_check(generated_plan: dict, ctx: dict) -> dict:
    obsolete = {normalize(c) for c in ctx["obsolete_document_codes"]}
    items = []
    for it in plan_items(generated_plan):
        dc = normalize(it["raw"].get("source_document_code"))
        if dc and dc in obsolete:
            items.append({"label": it["label"], "document_code": it["raw"].get("source_document_code"),
                          "text": it["text"]})
    return {
        "outdated_citations": items,
        "stale_requirement_links": ctx["stale_links"],
        "status": "passed" if not items else "failed",
    }


def _determine_verification_status(checks: dict) -> tuple[str, list[str]]:
    """
    SRS Step 47 + Section 1.2: "Verified" only when all mandatory
    requirements are covered, valid source references exist, and no
    unresolved contradictions or unsupported requirements remain.
    Returns (status, reasons).
    """
    reasons = []
    coverage = checks["coverage"]
    trace = checks["traceability"]
    halluc = checks["hallucination"]
    contra = checks["contradiction"]
    schema = checks["schema"]

    if checks["security"]["findings"]:
        reasons.append("Generated content contains instruction-like text (possible prompt injection).")
        return "Manual Review Required", reasons
    if not schema["valid"]:
        reasons.append("Plan JSON does not match the required schema.")
        return "Manual Review Required", reasons
    if contra.get("contradictions"):
        reasons.append(f"{len(contra['contradictions'])} contradiction(s) with approved sources.")
        return "Contradictory", reasons

    if checks["outdated"]["outdated_citations"]:
        reasons.append("Plan cites obsolete (superseded) document versions.")
        return "Manual Review Required", reasons

    missing = coverage.get("missing") or []
    if coverage.get("score", 0) < 60:
        reasons.append(f"Only {coverage.get('score')}% of mandatory requirements are covered.")
        return "Incomplete", reasons

    total = halluc.get("total_items") or 0
    unsupported = halluc.get("unsupported_items") or []
    if total and len(unsupported) / total > 0.20:
        reasons.append(f"{len(unsupported)} of {total} generated items are not supported by the sources.")
        return "Unsupported", reasons

    if halluc.get("status") == "insufficient_source" or contra.get("status") == "insufficient_source":
        reasons.append("No source text is available to verify this plan.")
        return "Manual Review Required", reasons

    if missing:
        reasons.append(f"Missing mandatory requirement(s): {', '.join(missing)}.")
        return "Incomplete", reasons

    warnings = []
    if unsupported:
        warnings.append(f"{len(unsupported)} unsupported item(s).")
    if trace.get("mandatory_score", 0) < 100:
        warnings.append(f"Mandatory traceability is {trace.get('mandatory_score')}% (target 100%).")
    if checks["consistency"].get("score", 0) < 100:
        warnings.append(f"Requirement consistency is {checks['consistency'].get('score')}%.")
    for key in ("duplicates", "role_relevance", "sequence", "quiz"):
        if checks[key].get("status") not in (None, "passed"):
            warnings.append(f"{key.replace('_', ' ').title()} check reported issues.")
    if schema["semantic_findings"]:
        warnings.append(f"{len(schema['semantic_findings'])} schema finding(s).")
    if checks["stale_links"]:
        warnings.append("Requirement Matrix still links obsolete document versions.")

    if not warnings:
        return "Verified", ["All mandatory requirements covered, traced and consistent."]
    if trace.get("mandatory_score", 0) >= 80 and len(unsupported) <= max(1, total // 10):
        return "Verified with Warning", warnings
    return "Partially Verified", warnings


def _persist_validation_results(plan_id, ctx, checks, generated_plan, db):
    """
    One ValidationResult row per Requirement Matrix row (SRS Step 46):
    Requirement ID | Role | Source | Python expected | GenAI result |
    Match/Mismatch | Coverage status | Traceability status | Validation
    status | Explanation of disagreement.
    Rows are updated in place so reviewer overrides survive re-validation.
    """
    requirements = ctx["requirements"]
    coverage_by_code = {d["requirement_code"]: d for d in checks["coverage"]["requirements"]}
    items = plan_items(generated_plan)
    code_by_label = {it["label"]: normalize(it["raw"].get("source_requirement_code")) for it in items}

    items_by_code = {}
    for it in items:
        code = normalize(it["raw"].get("source_requirement_code"))
        if code:
            items_by_code.setdefault(code, []).append(it)

    unsupported = {}
    for u in checks["hallucination"].get("unsupported_items", []):
        code = normalize(u.get("source_requirement_code")) or code_by_label.get(u.get("label"), "")
        unsupported.setdefault(code, []).append(u)
    contradictions = {}
    for c in checks["contradiction"].get("contradictions", []):
        contradictions.setdefault(code_by_label.get(c.get("label"), ""), []).append(c)
    outdated = {}
    for o in checks["outdated"]["outdated_citations"]:
        outdated.setdefault(code_by_label.get(o["label"], ""), []).append(o)
    stale = {normalize(code) for link in ctx["stale_links"] for code in link["requirement_codes"]}
    comparisons = {}
    for row in checks["consistency"].get("comparisons", []):
        comparisons.setdefault(normalize(row["requirement_code"]), []).append(row)

    trace_by_code = {}
    for d in checks["traceability"]["details"]:
        code = normalize(d.get("requirement"))
        if code:
            trace_by_code.setdefault(code, []).append(d)

    existing = {
        normalize(r.requirement_code): r
        for r in db.query(ValidationResult).filter(ValidationResult.plan_id == plan_id).all()
    }

    for req in requirements:
        code = (req.requirement_code or "").strip()
        key = normalize(code)
        cov = coverage_by_code.get(key, {})
        covered = bool(cov.get("covered"))
        mismatched = [c for c in comparisons.get(key, []) if c["result"] == "Mismatch"]
        traces = trace_by_code.get(key, [])

        if not covered:
            status = "Requirement Missing" if req.mandatory else "Partially Verified"
            why = "No generated item covers this requirement."
        elif key in contradictions:
            c = contradictions[key][0]
            status = "Contradiction Detected"
            why = f"{c['label']}: {c.get('detail')} Source: {c.get('source_origin')}."
        elif key in outdated:
            status = "Outdated Source"
            why = f"Cites obsolete document {outdated[key][0]['document_code']}."
        elif key in unsupported:
            u = unsupported[key][0]
            status = "Unsupported Requirement"
            why = f"{u['label']}: " + "; ".join(u.get("reasons", [])[:2])
        elif not ctx["requirement_doc_code"].get(code):
            status = "Source Support Missing"
            why = "Covered, but the requirement has no active source document linked."
        elif mismatched:
            status = "Verified"
            why = "Covered and grounded; field differences: " + "; ".join(
                f"{m['field']} (GenAI '{m['genai']}' vs '{m['python']}')" for m in mismatched[:3])
        else:
            status = "Verified"
            why = "Covered, grounded in its sources and consistent with the matrix."
        if key in stale:
            why += " Note: the matrix row still links an obsolete document version."

        if traces and all(t["traced"] for t in traces):
            trace_status = "Traced"
        elif key in outdated:
            trace_status = "Outdated"
        elif traces:
            trace_status = "Partially traced"
        else:
            trace_status = "Untraced"

        expected = req.policy_requirement or req.process_requirement or req.competency or ""
        genai_items = items_by_code.get(key) or []
        genai_text = genai_items[0]["text"] if genai_items else "No generated item cites this requirement code."
        doc_code = ctx["requirement_doc_code"].get(code)

        row = existing.get(key) or ValidationResult(plan_id=plan_id, requirement_code=code)
        row.genai_result = genai_text[:255]
        row.python_expected_result = expected[:255]
        row.match_status = "Match" if status == "Verified" and not mismatched else "Mismatch"
        row.validation_status = status
        row.explanation = f"Requirement '{code}' ({'mandatory' if req.mandatory else 'optional'}): {why}"
        row.role_name = ctx["role_name"]
        row.source_reference = (f"{doc_code} §{req.source_section}" if doc_code and req.source_section
                                else (doc_code or None))
        row.coverage_status = "Covered" if covered else "Missing"
        row.traceability_status = trace_status
        row.field_comparison = comparisons.get(key, [])
        if key not in existing:
            db.add(row)

    # security findings in the OUTPUT are stored against the plan
    db.query(SecurityFlag).filter(SecurityFlag.plan_id == plan_id).delete()
    for f in checks["security"]["findings"]:
        db.add(SecurityFlag(plan_id=plan_id, category=f["category"], severity=f["severity"],
                            matched_text=f["sentence"], location=f.get("label_item")))
    db.commit()


# -------------------------------------------------------------------- main
def validate_onboarding_plan(employee_id: int, generated_plan: dict, db: Session,
                             plan_id: int = None, context: dict = None) -> dict:
    """
    Runs every Python check on generated_plan and returns the full report.
    If plan_id is given, scores + status are stored on the OnboardingPlan
    row and per-requirement ValidationResult rows are written.
    """
    try:
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            raise ValidationError("Employee not found")
        if not employee.role_id:
            raise ValidationError("Employee role missing")
        if not isinstance(generated_plan, dict):
            raise ValidationError("This plan has no stored GenAI output to validate.")

        ctx = context or build_role_context(employee.role_id, db, employee)
        requirements = ctx["requirements"]
        if not requirements:
            raise ValidationError("Requirement matrix not found")

        source_text = ctx_source_text(ctx)
        ground_truth_text = source_text + " " + " ".join(requirement_text(r) for r in requirements)
        other_role_codes = [
            code for (code,) in db.query(RequirementMatrix.requirement_code)
            .filter(RequirementMatrix.role_id != employee.role_id).all()
        ]

        checks = {
            "schema": validate_plan_schema(
                generated_plan, role_name=ctx["role_name"], requirement_codes=ctx["requirement_codes"],
                active_document_codes=ctx["active_document_codes"],
                obsolete_document_codes=ctx["obsolete_document_codes"]),
            "coverage": check_coverage(requirements, generated_plan),
            "traceability": check_traceability(
                generated_plan, ctx["requirement_codes"], ctx["active_document_codes"], ctx["obsolete_document_codes"]),
            "consistency": check_consistency(generated_plan, requirements, ctx["requirement_doc_code"]),
            "hallucination": detect_hallucinations(
                generated_plan, source_text, requirements, ctx["active_document_codes"], ctx["obsolete_document_codes"]),
            "contradiction": detect_contradictions(generated_plan, source_text, requirements, ctx["segments"]),
            "duplicates": detect_duplicates(generated_plan),
            "role_relevance": check_role_relevance(generated_plan, requirements, ctx["role_name"], source_text, other_role_codes),
            "sequence": validate_sequence(generated_plan, requirements, source_text),
            "quiz": validate_quiz(generated_plan, ground_truth_text),
            "security": _security_check(generated_plan),
            "outdated": _outdated_check(generated_plan, ctx),
            "stale_links": ctx["stale_links"],
        }

        report_holder = {}
        status, reasons = _determine_verification_status(checks)
        cov, trace, cons = checks["coverage"], checks["traceability"], checks["consistency"]
        overall_score = round((cov.get("score", 0) + trace.get("score", 0) + cons.get("score", 0)) / 3, 2)

        metrics = {
            "required_requirements": cov.get("total", 0),
            "covered_requirements": cov.get("covered", 0),
            "missing_requirement_count": len(cov.get("missing") or []),
            "unsupported_requirement_count": len(checks["hallucination"].get("unsupported_items") or []),
            "duplicate_requirement_count": len(cov.get("duplicates") or []) + checks["duplicates"].get("duplicate_count", 0),
            "contradiction_count": len(checks["contradiction"].get("contradictions") or []),
            "mandatory_coverage_score": cov.get("score", 0),
            "source_traceability_score": trace.get("score", 0),
            "requirement_consistency_score": cons.get("score", 0),
        }

        if plan_id is not None:
            plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
            if plan:
                plan.coverage_score = cov.get("score", 0)
                plan.traceability_score = trace.get("score", 0)
                plan.consistency_score = cons.get("score", 0)
                plan.verification_status = status
                db.commit()
                _persist_validation_results(plan_id, ctx, checks, generated_plan, db)
                report_holder["plan"] = plan

        halluc, contra = checks["hallucination"], checks["contradiction"]
        report = {
            "employee_id": employee_id,
            "plan_id": plan_id,
            "validation_status": status,
            "status_reasons": reasons,
            "overall_score": overall_score,
            "metrics": metrics,
            "coverage": {
                "score": cov.get("score", 0),
                "covered": cov.get("covered", 0),
                "total": cov.get("total", 0),
                "mandatory_total": cov.get("mandatory_total", 0),
                "optional_total": cov.get("optional_total", 0),
                "optional_covered": cov.get("optional_covered", 0),
                "missing": cov.get("missing", []),
                "duplicates": cov.get("duplicates", []),
                "details": cov.get("requirements", []),
            },
            "traceability": {
                "score": trace.get("score", 0),
                "mandatory_score": trace.get("mandatory_score", 0),
                "total_items": trace.get("total", 0),
                "untraced": trace.get("untraced", []),
                "details": trace.get("details", []),
            },
            "consistency": {
                "score": cons.get("score", 0),
                "issues": cons.get("issues", []),
                "comparisons": cons.get("comparisons", []),
            },
            "schema": checks["schema"],
            "hallucination": {
                "score": halluc.get("score") if halluc.get("score") is not None else 0,
                "total_items": halluc.get("total_items", 0),
                "unsupported_items": halluc.get("unsupported_items", []),
                "status": halluc.get("status"),
                "message": halluc.get("message"),
            },
            "contradiction": {
                "score": contra.get("score") if contra.get("score") is not None else 0,
                "total_items": contra.get("total_items", 0),
                "contradictions": contra.get("contradictions", []),
                "resolved_by_precedence": contra.get("resolved_by_precedence", []),
                "status": contra.get("status"),
                "message": contra.get("message"),
            },
            "duplicates": {
                "score": checks["duplicates"].get("score", 0),
                "total_items": checks["duplicates"].get("total_items", 0),
                "duplicate_count": checks["duplicates"].get("duplicate_count", 0),
                "details": checks["duplicates"].get("duplicates", {}),
                "status": checks["duplicates"].get("status"),
            },
            "role_relevance": {
                "score": checks["role_relevance"].get("score") if checks["role_relevance"].get("score") is not None else 0,
                "total_items": checks["role_relevance"].get("total_items", 0),
                "irrelevant_items": checks["role_relevance"].get("irrelevant_items", []),
                "status": checks["role_relevance"].get("status"),
                "message": checks["role_relevance"].get("message"),
            },
            "sequence": {
                "score": checks["sequence"].get("score", 0),
                "total_items": checks["sequence"].get("total_modules", 0),
                "issues": checks["sequence"].get("issues", []),
                "status": checks["sequence"].get("status"),
            },
            "quiz": checks["quiz"],
            "security": checks["security"],
            "outdated": checks["outdated"],
            "sources_used": ctx["source_document_versions"],
            "redacted_sentences": ctx["redactions"],
        }
        if report_holder.get("plan") is not None:
            import json as _json
            from datetime import datetime, timezone
            p = report_holder["plan"]
            p.last_validation_report = _json.loads(_json.dumps(report, default=str))
            p.validated_at = datetime.now(timezone.utc)
            db.commit()
        return report

    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError(f"Validation failed: {str(error)}")
