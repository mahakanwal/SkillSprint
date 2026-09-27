"""
routers/review_router.py

Real Reviewer Decision + Audit Trail workflow (SRS xliv-xlvii):
    GET  /review/queue                          Manual Review Queue
    GET  /review/plan/{plan_id}                  full plan + validation results, for the review screen
    POST /review/plan/{plan_id}/decision         Approve / Reject / Needs Regeneration
    POST /review/validation-result/{id}/override Reviewer Override on one requirement's result
    GET  /review/audit-trail/{plan_id}           full history of every decision + override on a plan

Every decision and every override writes an AuditLog row capturing the
BEFORE state (original_result), the AFTER state (reviewer_decision), who
did it, and why -- nothing is silently overwritten. Overriding a
ValidationResult never touches its original `validation_status` column;
the override is layered on top in separate columns so both stay visible.

Test via Swagger UI at http://localhost:8000/docs
"""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import (
    OnboardingPlan, ValidationResult, AuditLog, User, Employee,
    LearningModule, ChecklistItem, OnboardingTask, QuizQuestion,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm.attributes import flag_modified
from schemas.review_schema import (
    ReviewDecisionRequest, OverrideRequest, AuditLogResponse,
    ReviewQueueItem, ValidationResultWithOverride, VALID_DECISIONS,
)
from security.rbac import get_current_user

router = APIRouter()

# Verification statuses that genuinely need a human look, vs. ones a
# reviewer can skip past quickly if they're triaging.
FLAGGED_STATUSES = {"Unsupported", "Contradictory", "Incomplete", "Manual Review Required", "Partially Verified"}


@router.get("/queue", response_model=List[ReviewQueueItem])
def get_review_queue(flagged_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(OnboardingPlan).filter(OnboardingPlan.review_status == "Pending Review")
    if flagged_only:
        query = query.filter(OnboardingPlan.verification_status.in_(FLAGGED_STATUSES))
    plans = query.order_by(OnboardingPlan.generated_at.desc()).all()
    employees = {e.id: e for e in db.query(Employee).all()}
    for p in plans:
        emp = employees.get(p.employee_id)
        p.employee_name = emp.full_name if emp else None
        p.role_name = emp.role.role_name if emp and emp.role else None
    return plans


@router.get("/plan/{plan_id}")
def get_plan_for_review(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"No onboarding plan found with id={plan_id}")

    results = (
        db.query(ValidationResult)
        .filter(ValidationResult.plan_id == plan_id)
        .order_by(ValidationResult.requirement_code)
        .all()
    )

    return {
        "id": plan.id,
        "employee_id": plan.employee_id,
        "generated_at": plan.generated_at,
        "model_used": plan.model_used,
        "coverage_score": plan.coverage_score,
        "traceability_score": plan.traceability_score,
        "consistency_score": plan.consistency_score,
        "verification_status": plan.verification_status,
        "review_status": plan.review_status,
        "reviewed_by": plan.reviewed_by,
        "reviewed_at": plan.reviewed_at,
        "reviewer_notes": plan.reviewer_notes,
        "validation_results": [ValidationResultWithOverride.model_validate(r) for r in results],
    }


@router.post("/plan/{plan_id}/decision")
def submit_review_decision(
    plan_id: int,
    decision: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if decision.action not in VALID_DECISIONS:
        raise HTTPException(
            status_code=422,
            detail=f"action must be one of: {', '.join(sorted(VALID_DECISIONS))}"
        )

    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"No onboarding plan found with id={plan_id}")

    original_status = plan.review_status

    plan.review_status = decision.action
    plan.reviewed_by = user.username
    plan.reviewed_at = datetime.now(timezone.utc)
    plan.reviewer_notes = decision.notes
    db.commit()

    db.add(AuditLog(
        plan_id=plan.id,
        action=decision.action.lower().replace(" ", "_"),
        original_result=original_status,
        reviewer_decision=decision.action,
        reviewed_by=user.username,
        comment=decision.notes,
    ))
    db.commit()

    return {
        "message": f"Plan #{plan_id} marked '{decision.action}' by {user.username}.",
        "plan_id": plan.id,
        "review_status": plan.review_status,
    }


@router.post("/validation-result/{result_id}/override")
def override_validation_result(
    result_id: int,
    override: OverrideRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = db.query(ValidationResult).filter(ValidationResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"No validation result found with id={result_id}")

    original_status = result.validation_status  # untouched -- this stays as the Python-computed original

    result.overridden_status = override.overridden_status
    result.override_reason = override.reason
    result.overridden_by = user.username
    result.overridden_at = datetime.now(timezone.utc)
    db.commit()

    db.add(AuditLog(
        plan_id=result.plan_id,
        action="override",
        original_result=f"{result.requirement_code}: {original_status}",
        reviewer_decision=f"{result.requirement_code}: {override.overridden_status}",
        reviewed_by=user.username,
        comment=override.reason,
    ))
    db.commit()

    return {
        "message": f"Requirement '{result.requirement_code}' overridden from "
                   f"'{original_status}' to '{override.overridden_status}' by {user.username}.",
        "validation_result_id": result.id,
        "original_status": original_status,
        "overridden_status": result.overridden_status,
    }


@router.get("/audit-trail/{plan_id}", response_model=List[AuditLogResponse])
def get_audit_trail(plan_id: int, db: Session = Depends(get_db)):
    return (
        db.query(AuditLog)
        .filter(AuditLog.plan_id == plan_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )



# ---------------------------------------------------------------------
# SRS Step 48 -- Edit / Add comment / Regenerate (reviewer workflow)
# ---------------------------------------------------------------------
class CommentRequest(BaseModel):
    comment: str = Field(min_length=2)


class ItemEditRequest(BaseModel):
    fields: dict
    reason: str = Field(min_length=3)


_EDITABLE = {
    "module": (LearningModule, "modules", {"title", "purpose", "due_stage", "completion_criteria", "estimated_duration"}),
    "checklist": (ChecklistItem, "checklist", {"activity", "due_stage", "required", "responsible_person"}),
    "task": (OnboardingTask, "tasks", {"task_description", "expected_outcome", "due_stage", "completion_criteria", "difficulty"}),
    "quiz": (QuizQuestion, "quiz", {"question_text", "options", "correct_answer", "explanation", "difficulty"}),
}


@router.post("/plan/{plan_id}/comment")
def add_comment(plan_id: int, body: CommentRequest, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"No onboarding plan found with id={plan_id}")
    db.add(AuditLog(plan_id=plan_id, action="comment", original_result=plan.review_status,
                    reviewer_decision=plan.review_status, reviewed_by=user.username, comment=body.comment))
    db.commit()
    return {"message": "Comment added.", "plan_id": plan_id}


@router.patch("/plan/{plan_id}/item/{item_type}/{item_id}")
def edit_plan_item(plan_id: int, item_type: str, item_id: int, body: ItemEditRequest,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Reviewer edit of one generated item. The stored GenAI JSON is updated
    too (so re-validation sees the edit), the BEFORE/AFTER values go to the
    audit trail, and Python validation re-runs automatically.
    """
    if item_type not in _EDITABLE:
        raise HTTPException(status_code=422, detail=f"item_type must be one of: {', '.join(_EDITABLE)}")
    model, section, allowed = _EDITABLE[item_type]
    bad = set(body.fields) - allowed
    if bad:
        raise HTTPException(status_code=422, detail=f"Not editable: {', '.join(sorted(bad))}. Allowed: {', '.join(sorted(allowed))}")

    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"No onboarding plan found with id={plan_id}")
    item = db.query(model).filter(model.id == item_id, model.plan_id == plan_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"No {item_type} with id={item_id} on plan {plan_id}")

    before = {k: getattr(item, k) for k in body.fields}
    for k, v in body.fields.items():
        setattr(item, k, v)

    # keep raw_genai_json in sync (items were stored in the same order)
    siblings = db.query(model).filter(model.plan_id == plan_id).order_by(model.id).all()
    idx = next((i for i, s in enumerate(siblings) if s.id == item_id), None)
    raw = plan.raw_genai_json if isinstance(plan.raw_genai_json, dict) else None
    if raw is not None and idx is not None and idx < len(raw.get(section) or []):
        raw[section][idx].update(body.fields)
        plan.raw_genai_json = dict(raw)
        flag_modified(plan, "raw_genai_json")

    plan.review_status = "Pending Review"
    db.add(AuditLog(plan_id=plan_id, action="edit",
                    original_result=f"{item_type} #{item_id}: {before}",
                    reviewer_decision=f"{item_type} #{item_id}: {body.fields}",
                    reviewed_by=user.username, comment=body.reason))
    db.commit()

    from services.validation_service import validate_onboarding_plan, ValidationError as PlanValidationError
    try:
        result = validate_onboarding_plan(plan.employee_id, plan.raw_genai_json, db, plan_id=plan.id)
        new_status = result["validation_status"]
    except PlanValidationError:
        new_status = plan.verification_status
    return {"message": f"{item_type} #{item_id} updated and re-validated.", "verification_status": new_status}


@router.post("/plan/{plan_id}/regenerate")
def regenerate_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Generates a NEW plan for the same employee (old one is kept for the audit trail)."""
    if user.role not in ("admin", "training_manager", "reviewer"):
        raise HTTPException(status_code=403, detail="Only admins, training managers and reviewers can regenerate plans.")
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"No onboarding plan found with id={plan_id}")

    from services.onboarding_service import create_onboarding_plan, OnboardingServiceError
    from routers.onboarding_router import run_validation_for_plan
    try:
        new_plan = create_onboarding_plan(plan.employee_id, db)
    except OnboardingServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    new_plan = run_validation_for_plan(new_plan, db)

    original = plan.review_status
    plan.review_status = "Needs Regeneration"
    db.add(AuditLog(plan_id=plan.id, action="regenerate", original_result=original,
                    reviewer_decision=f"Regenerated as plan #{new_plan.id} ({new_plan.verification_status})",
                    reviewed_by=user.username, comment=None))
    db.commit()
    return {"message": f"Plan #{plan_id} regenerated as plan #{new_plan.id}.", "new_plan_id": new_plan.id,
            "verification_status": new_plan.verification_status}
