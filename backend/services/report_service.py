"""
services/report_service.py

SRS Steps 51-52, 60-62 / li-lii, lx-lxi -- dashboards, plan comparison,
search/filtering and reports. Everything is computed from the real
database; nothing is hard-coded or estimated.
"""

from collections import defaultdict

from sqlalchemy.orm import Session

from database.models import (
    Assessment, Document, Employee, OnboardingPlan, QuizAttempt, RequirementMatrix, Role,
    SecurityFlag, ValidationResult,
)
from services.onboarding_service import attach_progress

FLAGGED = {"Unsupported", "Contradictory", "Incomplete", "Manual Review Required", "Partially Verified"}


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def latest_plans(db: Session) -> dict:
    """employee_id -> latest OnboardingPlan (progress attached)."""
    out = {}
    for p in db.query(OnboardingPlan).order_by(OnboardingPlan.generated_at.asc(), OnboardingPlan.id.asc()).all():
        out[p.employee_id] = p
    for p in out.values():
        attach_progress(p)
    return out


def _quiz_score(plan_id: int, db: Session):
    latest = {}
    for a in db.query(QuizAttempt).filter(QuizAttempt.plan_id == plan_id).order_by(QuizAttempt.id).all():
        latest[a.question_id] = a.is_correct
    return round(sum(latest.values()) / len(latest) * 100, 1) if latest else None


# ------------------------------------------------------------- dashboards
def dashboard_summary(db: Session) -> dict:
    employees = db.query(Employee).all()
    plans = db.query(OnboardingPlan).all()
    latest = latest_plans(db)
    docs = db.query(Document).all()
    reqs = db.query(RequirementMatrix).all()

    by_status, by_review = defaultdict(int), defaultdict(int)
    for p in plans:
        by_status[p.verification_status or "Unknown"] += 1
        by_review[p.review_status or "Pending Review"] += 1

    assessments = db.query(Assessment).filter(Assessment.score.isnot(None)).all()
    quiz_scores = [_quiz_score(p.id, db) for p in latest.values()]
    doc_flags = db.query(SecurityFlag).filter(SecurityFlag.document_id.isnot(None)).count()
    plan_flags = db.query(SecurityFlag).filter(SecurityFlag.plan_id.isnot(None)).count()

    recent = sorted(plans, key=lambda p: p.generated_at or 0, reverse=True)[:8]
    emp_by_id = {e.id: e for e in employees}
    return {
        "employees": len(employees),
        "employees_with_plan": len(latest),
        "roles": db.query(Role).count(),
        "documents": len(docs),
        "active_documents": sum(1 for d in docs if d.is_active_version),
        "obsolete_documents": sum(1 for d in docs if not d.is_active_version),
        "requirements": len(reqs),
        "mandatory_requirements": sum(1 for r in reqs if r.mandatory),
        "plans": len(plans),
        "plans_by_verification_status": dict(by_status),
        "plans_by_review_status": dict(by_review),
        "flagged_plans": sum(1 for p in plans if p.verification_status in FLAGGED),
        "pending_manual_reviews": sum(1 for p in plans if (p.review_status or "Pending Review") == "Pending Review"
                                      and p.verification_status in FLAGGED),
        "compliance_coverage": _avg([p.coverage_score for p in latest.values()]),
        "average_traceability": _avg([p.traceability_score for p in latest.values()]),
        "average_consistency": _avg([p.consistency_score for p in latest.values()]),
        "average_completion": _avg([p.progress_percent for p in latest.values()]),
        "average_quiz_score": _avg(quiz_scores),
        "average_assessment_score": _avg([a.score for a in assessments]),
        "security_flags_documents": doc_flags,
        "security_flags_outputs": plan_flags,
        "recent_plans": [{
            "id": p.id, "employee_id": p.employee_id,
            "employee_name": emp_by_id[p.employee_id].full_name if p.employee_id in emp_by_id else None,
            "generated_at": p.generated_at, "verification_status": p.verification_status,
            "review_status": p.review_status, "coverage_score": p.coverage_score,
        } for p in recent],
    }


def role_dashboard(db: Session) -> list[dict]:
    latest = latest_plans(db)
    out = []
    for role in db.query(Role).order_by(Role.role_name).all():
        reqs = [r for r in role.requirements]
        emps = [e for e in role.employees]
        role_plans = [latest[e.id] for e in emps if e.id in latest]
        docs = {r.source_document_id for r in reqs if r.source_document_id}
        out.append({
            "role_id": role.id,
            "role_name": role.role_name,
            "department": role.department,
            "requirements": len(reqs),
            "mandatory_requirements": sum(1 for r in reqs if r.mandatory),
            "optional_requirements": sum(1 for r in reqs if not r.mandatory),
            "source_documents": len(docs),
            "requirements_without_source": sum(1 for r in reqs if not r.source_document_id),
            "employees": len(emps),
            "employees_with_plan": len(role_plans),
            "completed_employees": sum(1 for e in emps if e.training_status == "Completed"),
            "average_completion": _avg([p.progress_percent for p in role_plans]),
            "average_coverage": _avg([p.coverage_score for p in role_plans]),
            "verified_plans": sum(1 for p in role_plans if p.verification_status == "Verified"),
            "flagged_plans": sum(1 for p in role_plans if p.verification_status in FLAGGED),
            "requirement_list": [{"code": r.requirement_code, "mandatory": r.mandatory, "priority": r.priority,
                                  "due_stage": r.due_stage, "competency": r.competency} for r in reqs],
        })
    return out


# ------------------------------------------------- search, filter, compare
def plan_rows(db: Session, latest_only: bool = True) -> list[dict]:
    employees = {e.id: e for e in db.query(Employee).all()}
    plans = list(latest_plans(db).values()) if latest_only else db.query(OnboardingPlan).all()
    if not latest_only:
        for p in plans:
            attach_progress(p)
    rows = []
    for p in plans:
        e = employees.get(p.employee_id)
        rows.append({
            "plan_id": p.id,
            "employee_id": p.employee_id,
            "employee_code": e.employee_code if e else None,
            "employee_name": e.full_name if e else None,
            "role_id": e.role_id if e else None,
            "role_name": e.role.role_name if e and e.role else None,
            "department": e.department if e else None,
            "experience_level": e.experience_level if e else None,
            "generated_at": p.generated_at,
            "prompt_version": p.prompt_version,
            "model_used": p.model_used,
            "verification_status": p.verification_status,
            "review_status": p.review_status,
            "coverage_score": p.coverage_score,
            "traceability_score": p.traceability_score,
            "consistency_score": p.consistency_score,
            "progress_percent": p.progress_percent,
            "modules": len(p.modules),
            "module_titles": [m.title for m in p.modules],
            "document_versions": [f"{s.get('document_code')}@{s.get('version')}" for s in (p.source_document_versions or [])
                                  if isinstance(s, dict)],
            "requirement_codes": sorted({m.source_requirement_code for m in p.modules if m.source_requirement_code}),
        })
    return rows


def filter_plans(rows: list[dict], search=None, role_id=None, department=None, status=None, review_status=None,
                 experience_level=None, module=None, policy=None, min_progress=None, max_progress=None) -> list[dict]:
    def ok(r):
        if search:
            s = search.lower()
            if s not in (r["employee_name"] or "").lower() and s not in (r["employee_code"] or "").lower():
                return False
        if role_id and r["role_id"] != role_id:
            return False
        if department and (r["department"] or "").lower() != department.lower():
            return False
        if status and r["verification_status"] != status:
            return False
        if review_status and r["review_status"] != review_status:
            return False
        if experience_level and (r["experience_level"] or "").lower() != experience_level.lower():
            return False
        if module and not any(module.lower() in (t or "").lower() for t in r["module_titles"]):
            return False
        if policy and not any(policy.lower() in v.lower() for v in r["document_versions"]):
            return False
        if min_progress is not None and (r["progress_percent"] or 0) < min_progress:
            return False
        if max_progress is not None and (r["progress_percent"] or 0) > max_progress:
            return False
        return True
    return [r for r in rows if ok(r)]


def compare_plans(rows: list[dict], group_by: str) -> list[dict]:
    """SRS Step 60 -- compare onboarding plans across roles, departments, levels or document versions."""
    key_of = {
        "role": lambda r: [r["role_name"] or "No role"],
        "department": lambda r: [r["department"] or "No department"],
        "experience_level": lambda r: [r["experience_level"] or "Not set"],
        "document_version": lambda r: r["document_versions"] or ["No sources"],
    }.get(group_by)
    if key_of is None:
        raise ValueError("group_by must be role, department, experience_level or document_version")
    groups = defaultdict(list)
    for r in rows:
        for k in key_of(r):
            groups[k].append(r)
    out = []
    for k, rs in sorted(groups.items()):
        codes = [set(r["requirement_codes"]) for r in rs]
        out.append({
            "group": k,
            "plans": len(rs),
            "employees": sorted({r["employee_name"] for r in rs if r["employee_name"]}),
            "average_modules": _avg([r["modules"] for r in rs]),
            "average_coverage": _avg([r["coverage_score"] for r in rs]),
            "average_traceability": _avg([r["traceability_score"] for r in rs]),
            "average_progress": _avg([r["progress_percent"] for r in rs]),
            "requirements_in_every_plan": sorted(set.intersection(*codes)) if codes else [],
            "requirements_in_some_plans": sorted(set.union(*codes) - set.intersection(*codes)) if codes else [],
            "statuses": dict(sorted({s: sum(1 for r in rs if r["verification_status"] == s)
                                     for s in {r["verification_status"] for r in rs}}.items())),
        })
    return out


# ------------------------------------------------------------------ reports
def report_employee_progress(db: Session) -> list[dict]:
    from services.progress_service import assess_progress
    rows = []
    employees = {e.id: e for e in db.query(Employee).all()}
    for emp_id, plan in latest_plans(db).items():
        e = employees.get(emp_id)
        pa = assess_progress(plan, db)
        rows.append({
            "employee_code": e.employee_code if e else None, "employee_name": e.full_name if e else None,
            "role": e.role.role_name if e and e.role else None, "department": e.department if e else None,
            "plan_id": plan.id, "outcome": pa["outcome"], "progress_percent": pa["progress_percent"],
            "modules_completed": f"{pa['module_completion']['completed']}/{pa['module_completion']['total']}",
            "checklist_completed": f"{pa['checklist_completion']['completed']}/{pa['checklist_completion']['total']}",
            "tasks_completed": f"{pa['task_completion']['completed']}/{pa['task_completion']['total']}",
            "quiz_score": pa["quiz"]["score"], "assessment_average": pa["assessment_average"],
            "overdue_items": len(pa["overdue_items"]),
            "weak_areas": "; ".join(sorted({w["topic"] for w in pa["weak_areas"] if w.get("topic")})),
        })
    return rows


def report_role_coverage(db: Session) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "requirement_list"} for r in role_dashboard(db)]


def report_mandatory_training(db: Session) -> list[dict]:
    rows = []
    employees = {e.id: e for e in db.query(Employee).all()}
    for emp_id, plan in latest_plans(db).items():
        e = employees.get(emp_id)
        results = {r.requirement_code: r for r in db.query(ValidationResult).filter(ValidationResult.plan_id == plan.id).all()}
        modules_by_req = defaultdict(list)
        for m in plan.modules:
            if m.source_requirement_code:
                modules_by_req[m.source_requirement_code].append(m)
        for req in (e.role.requirements if e and e.role else []):
            if not req.mandatory:
                continue
            mods = modules_by_req.get(req.requirement_code, [])
            vr = results.get(req.requirement_code)
            rows.append({
                "employee_code": e.employee_code, "employee_name": e.full_name, "role": e.role.role_name,
                "requirement_code": req.requirement_code, "requirement": req.policy_requirement or req.process_requirement,
                "covered_in_plan": "Yes" if vr and vr.coverage_status == "Covered" else ("Yes" if mods else "No"),
                "module_completed": "Yes" if mods and all(m.completion_status == "Completed" for m in mods) else "No",
                "validation_status": (vr.overridden_status or vr.validation_status) if vr else None,
                "due_stage": req.due_stage,
            })
    return rows


def report_assessment_results(db: Session) -> list[dict]:
    rows = []
    employees = {e.id: e for e in db.query(Employee).all()}
    for emp_id, plan in latest_plans(db).items():
        e = employees.get(emp_id)
        rows.append({"employee_name": e.full_name if e else None, "plan_id": plan.id, "type": "Quiz",
                     "title": "Plan quiz", "score": _quiz_score(plan.id, db),
                     "status": None, "evaluated_by": None})
        for a in plan.assessments:
            rows.append({"employee_name": e.full_name if e else None, "plan_id": plan.id,
                         "type": (a.assessment_type or "").title(), "title": a.title, "score": a.score,
                         "status": a.status, "evaluated_by": a.evaluated_by})
    return rows


def report_source_traceability(db: Session) -> list[dict]:
    rows = []
    for plan in latest_plans(db).values():
        rep = plan.last_validation_report or {}
        for d in (rep.get("traceability") or {}).get("details", []):
            rows.append({"plan_id": plan.id, "section": d.get("section"), "item": d.get("index"),
                         "mandatory": d.get("mandatory"), "requirement": d.get("requirement"),
                         "document": d.get("document"), "source_section": d.get("source_section"),
                         "traced": "Yes" if d.get("traced") else "No",
                         "problems": "; ".join(d.get("problems") or [])})
    return rows


def report_hallucination_flags(db: Session) -> list[dict]:
    rows = []
    for plan in latest_plans(db).values():
        rep = plan.last_validation_report or {}
        for u in (rep.get("hallucination") or {}).get("unsupported_items", []):
            rows.append({"plan_id": plan.id, "type": "Unsupported content", "item": u.get("label"),
                         "text": u.get("text"), "detail": "; ".join(u.get("reasons") or [])})
        for c in (rep.get("contradiction") or {}).get("contradictions", []):
            rows.append({"plan_id": plan.id, "type": "Contradiction", "item": c.get("label"),
                         "text": c.get("generated_text"), "detail": f"{c.get('detail')} Source: {c.get('source_origin')}"})
        for f in (rep.get("security") or {}).get("findings", []):
            rows.append({"plan_id": plan.id, "type": "Injected instruction in output", "item": f.get("label_item"),
                         "text": f.get("sentence"), "detail": f.get("label")})
    return rows


def report_policy_coverage(db: Session) -> list[dict]:
    rows = []
    plans = list(latest_plans(db).values())
    for d in db.query(Document).order_by(Document.document_code).all():
        reqs = db.query(RequirementMatrix).filter(RequirementMatrix.source_document_id == d.id).all()
        citing = [p.id for p in plans if any(isinstance(s, dict) and s.get("document_code") == d.document_code
                                             for s in (p.source_document_versions or []))]
        rows.append({"document_code": d.document_code, "title": d.title, "type": d.doc_type, "version": d.version,
                     "status": "Active" if d.is_active_version else "Obsolete",
                     "linked_requirements": len(reqs), "mandatory_requirements": sum(1 for r in reqs if r.mandatory),
                     "roles": "; ".join(sorted({r.role.role_name for r in reqs if r.role})),
                     "plans_using_it": len(citing),
                     "security_flags": db.query(SecurityFlag).filter(SecurityFlag.document_id == d.id).count()})
    return rows


def report_comparison(db: Session, plan_id: int | None = None) -> list[dict]:
    """GenAI vs Python comparison (SRS deliverable 6)."""
    q = db.query(ValidationResult)
    if plan_id:
        q = q.filter(ValidationResult.plan_id == plan_id)
    rows = []
    for r in q.order_by(ValidationResult.plan_id, ValidationResult.requirement_code).all():
        rows.append({
            "plan_id": r.plan_id, "requirement_id": r.requirement_code, "role": r.role_name,
            "source": r.source_reference, "python_expected_requirement": r.python_expected_result,
            "genai_result": r.genai_result, "match": r.match_status, "coverage_status": r.coverage_status,
            "traceability_status": r.traceability_status, "validation_status": r.validation_status,
            "reviewer_override": r.overridden_status, "explanation_of_disagreement": r.explanation,
        })
    return rows


def report_validation(db: Session) -> list[dict]:
    rows = []
    employees = {e.id: e for e in db.query(Employee).all()}
    for plan in latest_plans(db).values():
        rep = plan.last_validation_report or {}
        m = rep.get("metrics") or {}
        e = employees.get(plan.employee_id)
        rows.append({
            "plan_id": plan.id, "employee_name": e.full_name if e else None,
            "role": e.role.role_name if e and e.role else None,
            "verification_status": plan.verification_status,
            "mandatory_requirements": m.get("required_requirements"),
            "covered_requirements": m.get("covered_requirements"),
            "missing_requirements": "; ".join((rep.get("coverage") or {}).get("missing") or []),
            "unsupported_items": m.get("unsupported_requirement_count"),
            "contradictions": m.get("contradiction_count"),
            "duplicate_content": m.get("duplicate_requirement_count"),
            "coverage_score": plan.coverage_score, "traceability_score": plan.traceability_score,
            "consistency_score": plan.consistency_score,
            "manual_review": "Yes" if plan.verification_status in FLAGGED else "No",
            "validated_at": plan.validated_at,
        })
    return rows


def report_security(db: Session) -> list[dict]:
    docs = {d.id: d.document_code for d in db.query(Document).all()}
    return [{"id": f.id, "document": docs.get(f.document_id), "plan_id": f.plan_id, "category": f.category,
             "severity": f.severity, "hidden_text": f.hidden_text, "text": f.matched_text, "location": f.location,
             "created_at": f.created_at}
            for f in db.query(SecurityFlag).order_by(SecurityFlag.id.desc()).all()]


REPORTS = {
    "employee-progress": ("Employee progress", report_employee_progress),
    "role-coverage": ("Role coverage", report_role_coverage),
    "mandatory-training": ("Mandatory training", report_mandatory_training),
    "assessment-results": ("Assessment results", report_assessment_results),
    "source-traceability": ("Source traceability", report_source_traceability),
    "hallucination-flags": ("Hallucination and contradiction flags", report_hallucination_flags),
    "policy-coverage": ("Policy coverage", report_policy_coverage),
    "genai-python-comparison": ("GenAI vs Python comparison", report_comparison),
    "validation": ("Validation report", report_validation),
    "security": ("Security flags", report_security),
}
