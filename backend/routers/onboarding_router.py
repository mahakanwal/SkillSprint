"""
routers/onboarding_router.py
Endpoints to generate and view GenAI onboarding plans.

    POST  /onboarding/generate/{employee_id}   generate + save a new plan
    GET   /onboarding/plan/{plan_id}           get one full plan
    GET   /onboarding/employee/{employee_id}   list all plans for an employee
    PATCH /onboarding/plan/{plan_id}/progress/{item_type}/{item_id}
                                                mark a module/checklist item/
                                                task Completed (SRS liii)

Test via Swagger UI at http://localhost:8000/docs
"""

from typing import List

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Employee, User
from schemas.genai_output_schema import OnboardingPlanResponse, OnboardingPlanSummary
from schemas.progress_schema import ProgressUpdateRequest
from security.rbac import get_current_user, require_roles
from services.validation_service import validate_onboarding_plan, ValidationError as PlanValidationError
from services.onboarding_service import (
    create_onboarding_plan,
    get_plan_by_id,
    list_plans_for_employee,
    update_item_progress,
    OnboardingServiceError,
)

router = APIRouter()


def _assert_can_touch_plan(plan_employee_id: int, current_user: User):
    """
    Only an admin/training_manager, or the employee this plan actually
    belongs to, may update its progress -- otherwise any logged-in
    employee could mark a coworker's tasks complete just by guessing ids.
    """
    if current_user.role in ("admin", "training_manager"):
        return
    if current_user.employee and current_user.employee.id == plan_employee_id:
        return
    raise HTTPException(status_code=403, detail="You can only update your own onboarding plan's progress.")


STAFF_ROLES = ("admin", "training_manager", "reviewer")


def assert_can_view_employee(employee: Employee, current_user: User):
    """
    Read access to an employee's plans:
      admin / training_manager / reviewer -> any employee
      manager  -> only employees whose reporting_manager is this manager
      employee -> only their own record
    (Previously any logged-in user could read any plan by guessing ids.)
    """
    if current_user.role in STAFF_ROLES:
        return
    if current_user.role == "manager":
        if (employee.reporting_manager or "").strip().lower() == (current_user.username or "").strip().lower():
            return
    elif current_user.employee and current_user.employee.id == employee.id:
        return
    raise HTTPException(status_code=403, detail="You do not have access to this employee's onboarding plan.")


def run_validation_for_plan(plan, db: Session):
    """Pipeline 2 runs automatically right after Pipeline 1 (SRS Step 46)."""
    try:
        validate_onboarding_plan(plan.employee_id, plan.raw_genai_json, db, plan_id=plan.id)
    except PlanValidationError:
        # plan is still saved; its status stays "Manual Review Required"
        pass
    return get_plan_by_id(plan.id, db)


@router.post("/generate/{employee_id}", response_model=OnboardingPlanResponse,
             dependencies=[Depends(require_roles("admin", "training_manager"))])
def generate_plan(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"No employee found with id={employee_id}")

    try:
        plan = create_onboarding_plan(employee_id, db)
    except OnboardingServiceError as e:
        # bad input (no role/requirements), invalid GenAI output after the
        # bounded retries, or Groq failure -- 422, not a 500
        raise HTTPException(status_code=422, detail=str(e))

    return run_validation_for_plan(plan, db)


@router.get("/plan/{plan_id}", response_model=OnboardingPlanResponse)
def get_plan(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        plan = get_plan_by_id(plan_id, db)
    except OnboardingServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    employee = db.query(Employee).filter(Employee.id == plan.employee_id).first()
    if employee:
        assert_can_view_employee(employee, current_user)
    return plan


@router.get("/employee/{employee_id}", response_model=List[OnboardingPlanSummary])
def get_employee_plans(employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"No employee found with id={employee_id}")
    assert_can_view_employee(employee, current_user)
    return list_plans_for_employee(employee_id, db)


@router.patch("/plan/{plan_id}/progress/{item_type}/{item_id}", response_model=OnboardingPlanResponse)
def update_progress(
    plan_id: int,
    item_type: str,
    item_id: int,
    data: ProgressUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        plan = get_plan_by_id(plan_id, db)
    except OnboardingServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))

    _assert_can_touch_plan(plan.employee_id, current_user)

    try:
        return update_item_progress(plan_id, item_type, item_id, data.completion_status, db)
    except OnboardingServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))



@router.post("/plan/{plan_id}/regenerate-affected", response_model=OnboardingPlanResponse,
             dependencies=[Depends(require_roles("admin", "training_manager"))])
def regenerate_affected_items(plan_id: int, document_id: int, db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    """
    SRS Step 59 -- regenerate ONLY the items affected by a document update
    (see GET /documents/impact/{document_id}); everything else is kept.
    Saved as a new plan and re-validated.
    """
    from services.regeneration_service import regenerate_affected, RegenerationError
    try:
        result = regenerate_affected(plan_id, document_id, db, user_name=current_user.username)
    except RegenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return run_validation_for_plan(result["new_plan"], db)



# ---------------------------------------------------------------------
# SRS Steps 50, 53-56 -- quiz taking, assessment scoring, progress
# assessment, weak areas and adaptive recommendations
# ---------------------------------------------------------------------
from pydantic import BaseModel as _BaseModel  # noqa: E402


class QuizAnswer(_BaseModel):
    question_id: int
    selected: list[str] | str


class QuizSubmission(_BaseModel):
    answers: list[QuizAnswer]


class AssessmentScore(_BaseModel):
    score: float


def _plan_or_404(plan_id: int, db: Session):
    try:
        return get_plan_by_id(plan_id, db)
    except OnboardingServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/plan/{plan_id}/quiz/submit")
def submit_quiz_answers(plan_id: int, body: QuizSubmission, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    from services.progress_service import submit_quiz, ProgressError
    plan = _plan_or_404(plan_id, db)
    _assert_can_touch_plan(plan.employee_id, current_user)
    try:
        return submit_quiz(plan, plan.employee_id, [a.model_dump() for a in body.answers], db)
    except ProgressError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/plan/{plan_id}/quiz/results")
def quiz_results(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from services.progress_service import quiz_summary
    plan = _plan_or_404(plan_id, db)
    employee = db.query(Employee).filter(Employee.id == plan.employee_id).first()
    if employee:
        assert_can_view_employee(employee, current_user)
    return quiz_summary(plan, db)


@router.post("/plan/{plan_id}/assessment/{assessment_id}/score")
def score_plan_assessment(plan_id: int, assessment_id: int, body: AssessmentScore, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    from database.models import Assessment
    from services.progress_service import score_assessment, ProgressError
    if current_user.role not in ("admin", "training_manager", "manager", "reviewer"):
        raise HTTPException(status_code=403, detail="Only trainers, managers and reviewers can score assessments.")
    plan = _plan_or_404(plan_id, db)
    employee = db.query(Employee).filter(Employee.id == plan.employee_id).first()
    if employee:
        assert_can_view_employee(employee, current_user)
    a = db.query(Assessment).filter(Assessment.id == assessment_id, Assessment.plan_id == plan_id).first()
    if not a:
        raise HTTPException(status_code=404, detail=f"No assessment {assessment_id} on plan {plan_id}")
    try:
        a = score_assessment(a, body.score, current_user.username, db)
    except ProgressError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": a.id, "score": a.score, "status": a.status, "evaluated_by": a.evaluated_by}


@router.get("/plan/{plan_id}/progress-assessment")
def progress_assessment(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from services.progress_service import assess_progress
    plan = _plan_or_404(plan_id, db)
    employee = db.query(Employee).filter(Employee.id == plan.employee_id).first()
    if employee:
        assert_can_view_employee(employee, current_user)
    return assess_progress(plan, db)


@router.post("/plan/{plan_id}/additional-quiz", response_model=OnboardingPlanResponse,
             dependencies=[Depends(require_roles("admin", "training_manager"))])
def additional_quiz(plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from services.regeneration_service import generate_additional_quiz, RegenerationError
    try:
        generate_additional_quiz(plan_id, db, user_name=current_user.username)
    except RegenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return run_validation_for_plan(_plan_or_404(plan_id, db), db)
