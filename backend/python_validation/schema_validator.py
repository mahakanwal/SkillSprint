"""
python_validation/schema_validator.py

SRS Step 38 / xvi -- Python validation of the GenAI JSON response.

Two levels of findings:

  STRUCTURAL errors (the JSON does not match schemas/genai_plan_schema.py):
    missing fields, invalid data types, invalid enum values, missing
    mandatory status, missing top-level sections. These make the output
    unusable, so the generator retries (bounded) with the errors fed back.

  SEMANTIC findings (valid JSON, but wrong against our data):
    invalid source requirement IDs, unknown or obsolete document IDs,
    wrong role, duplicate module IDs, correct answer not among the options,
    rubric weights not adding up to 100. These are kept and reported by the
    validation pipeline rather than retried.
"""

from typing import Iterable, Optional

from pydantic import ValidationError as PydanticValidationError

from schemas.genai_plan_schema import GenPlan, REQUIRED_TOP_LEVEL


def _loc(loc: tuple) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def structural_errors(plan) -> list[dict]:
    if not isinstance(plan, dict):
        return [{"path": "$", "message": "Output is not a JSON object.", "severity": "error", "kind": "structure"}]
    errors = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in plan:
            errors.append({"path": key, "message": f"Missing required section '{key}'.", "severity": "error", "kind": "missing_field"})
    try:
        GenPlan.model_validate(plan)
    except PydanticValidationError as e:
        for err in e.errors():
            kind = "missing_field" if err["type"] == "missing" else (
                "invalid_value" if "literal" in err["type"] or "enum" in err["type"] else "invalid_type")
            path = _loc(err["loc"])
            msg = err["msg"]
            if path.endswith(".mandatory") and err["type"] == "missing":
                msg = "Missing mandatory status (true/false)."
                kind = "missing_mandatory_status"
            errors.append({"path": path, "message": msg, "severity": "error", "kind": kind})
    # de-duplicate (missing top-level is also reported by pydantic)
    seen, unique = set(), []
    for e in errors:
        key = (e["path"], e["message"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def semantic_findings(
    plan: dict,
    role_name: Optional[str] = None,
    requirement_codes: Iterable[str] = (),
    active_document_codes: Iterable[str] = (),
    obsolete_document_codes: Iterable[str] = (),
) -> list[dict]:
    if not isinstance(plan, dict):
        return []
    req = {c.lower() for c in requirement_codes if c}
    active = {c.lower() for c in active_document_codes if c}
    obsolete = {c.lower() for c in obsolete_document_codes if c}
    out = []

    def add(path, message, kind, severity="warning"):
        out.append({"path": path, "message": message, "severity": severity, "kind": kind})

    if role_name and plan.get("role") and plan["role"].strip().lower() != role_name.strip().lower():
        add("role", f"Plan is for role '{plan['role']}' but the employee's role is '{role_name}'.", "invalid_role", "error")

    for section in ("modules", "checklist", "tasks", "quiz", "assessments"):
        for i, item in enumerate(plan.get(section) or []):
            if not isinstance(item, dict):
                continue
            path = f"{section}[{i}]"
            rc = (item.get("source_requirement_code") or "").strip()
            if rc and req and rc.lower() not in req:
                add(f"{path}.source_requirement_code", f"'{rc}' is not a requirement of this role.", "invalid_source_id", "error")
            dc = (item.get("source_document_code") or "").strip()
            if dc:
                if dc.lower() in obsolete:
                    add(f"{path}.source_document_code", f"'{dc}' is an obsolete document version.", "outdated_source", "error")
                elif active and dc.lower() not in active:
                    add(f"{path}.source_document_code", f"'{dc}' is not one of the source documents provided.", "invalid_source_id", "error")

    codes = [m.get("module_code") for m in plan.get("modules") or [] if isinstance(m, dict) and m.get("module_code")]
    dupes = sorted({c for c in codes if codes.count(c) > 1})
    for c in dupes:
        add("modules", f"Duplicate module_code '{c}'.", "duplicate_id", "error")
    known = set(codes)
    for i, m in enumerate(plan.get("modules") or []):
        if isinstance(m, dict):
            for pre in m.get("prerequisites") or []:
                if pre not in known:
                    add(f"modules[{i}].prerequisites", f"Prerequisite '{pre}' does not exist in this plan.", "invalid_reference")

    for i, q in enumerate(plan.get("quiz") or []):
        if not isinstance(q, dict):
            continue
        options = [str(o).strip() for o in q.get("options") or []]
        answers = q.get("correct_answer")
        answers = answers if isinstance(answers, list) else [answers]
        answers = [str(a).strip() for a in answers if a is not None and str(a).strip()]
        if q.get("question_type") in ("multiple_choice", "multiple_response", "true_false") and not options:
            add(f"quiz[{i}].options", "Question has no options.", "invalid_value", "error")
        if options and any(a not in options for a in answers):
            add(f"quiz[{i}].correct_answer", "Correct answer is not one of the options.", "invalid_value", "error")
        if q.get("question_type") == "multiple_response" and len(answers) < 2:
            add(f"quiz[{i}].correct_answer", "Multiple-response question has fewer than two correct answers.", "invalid_value")

    for i, a in enumerate(plan.get("assessments") or []):
        if isinstance(a, dict) and a.get("rubric"):
            try:
                total = sum(float(r.get("weight") or 0) for r in a["rubric"] if isinstance(r, dict))
            except (TypeError, ValueError):
                continue
            if abs(total - 100) > 1 and abs(total - 1) > 0.01:
                add(f"assessments[{i}].rubric", f"Rubric weights add up to {total:g}, expected 100.", "invalid_value")

    return out


def validate_plan_schema(plan, **context) -> dict:
    structural = structural_errors(plan)
    semantic = semantic_findings(plan, **context) if not structural or isinstance(plan, dict) else []
    total_items = sum(len(plan.get(s) or []) for s in ("modules", "checklist", "tasks", "quiz", "assessments")) if isinstance(plan, dict) else 0
    problems = len(structural) + len([f for f in semantic if f["severity"] == "error"])
    score = 100.0 if total_items == 0 and not structural else round(max(0.0, 100.0 * (1 - problems / max(total_items, 1))), 2)
    return {
        "valid": not structural,
        "score": score,
        "structural_errors": structural,
        "semantic_findings": semantic,
        "status": "passed" if not structural and not semantic else ("failed" if structural else "warning"),
    }


def structural_errors_partial(plan) -> list[dict]:
    """
    Same checks as structural_errors, but for a PARTIAL plan (selective
    regeneration / extra quiz): sections may be absent or empty, yet every
    item that IS present must match its schema.
    """
    from schemas.genai_plan_schema import GenAssessment, GenChecklistItem, GenModule, GenQuizQuestion, GenTask

    if not isinstance(plan, dict):
        return [{"path": "$", "message": "Output is not a JSON object.", "severity": "error", "kind": "structure"}]
    models = {"modules": GenModule, "checklist": GenChecklistItem, "tasks": GenTask,
              "quiz": GenQuizQuestion, "assessments": GenAssessment}
    errors, total = [], 0
    for section, model in models.items():
        items = plan.get(section) or []
        if not isinstance(items, list):
            errors.append({"path": section, "message": "Must be a list.", "severity": "error", "kind": "invalid_type"})
            continue
        for i, item in enumerate(items):
            total += 1
            try:
                model.model_validate(item)
            except PydanticValidationError as e:
                for err in e.errors():
                    errors.append({"path": f"{section}[{i}]" + ("." + _loc(err["loc"]) if err["loc"] else ""),
                                   "message": err["msg"], "severity": "error",
                                   "kind": "missing_field" if err["type"] == "missing" else "invalid_type"})
    if total == 0:
        errors.append({"path": "$", "message": "No items were returned.", "severity": "error", "kind": "missing_field"})
    return errors
