"""
services/onboarding_service.py
Persistence layer for GenAI-generated onboarding plans. Calls
genai_pipeline.generator to get the parsed plan from Groq, then writes it
into OnboardingPlan + LearningModule + ChecklistItem + OnboardingTask +
QuizQuestion.

Note: coverage_score / traceability_score / consistency_score are left at
their DB defaults (0.0) here -- calculating them is the python_validation
pipeline's job (a separate, not-yet-built feature), not the generator's.
"""

from sqlalchemy.orm import Session

from database.models import (
    OnboardingPlan, LearningModule, ChecklistItem, OnboardingTask,
    QuizQuestion, Document, Assessment,
)
from genai_pipeline.generator import generate_onboarding_plan, GeneratorError
from genai_pipeline.fallback_client import AllModelsFailedError


class OnboardingServiceError(Exception):
    """Raised for any failure generating or saving an onboarding plan."""
    pass


def _document_code_map(db: Session) -> dict:
    return {d.document_code: d.id for d in db.query(Document).all()}


def create_onboarding_plan(employee_id: int, db: Session) -> OnboardingPlan:
    """
    Generates a fresh onboarding plan for the employee via Groq and saves it
    to the database. Returns the saved OnboardingPlan with its relationships
    populated (plan.modules / plan.checklist_items / plan.tasks / plan.quizzes).
    """
    try:
        result = generate_onboarding_plan(employee_id, db)
    except GeneratorError as e:
        raise OnboardingServiceError(str(e))
    except AllModelsFailedError as e:
        raise OnboardingServiceError(f"GenAI generation failed: {e}")

    plan = persist_plan(employee_id, result, db)
    return plan


def _answers(q: dict) -> list[str]:
    ans = q.get("correct_answer")
    items = ans if isinstance(ans, list) else [ans]
    return [str(a).strip() for a in items if a is not None and str(a).strip()]


def add_plan_items(plan: OnboardingPlan, plan_json: dict, db: Session, doc_map: dict | None = None) -> None:
    """Writes modules / checklist / tasks / quiz / assessments rows for a plan."""
    doc_map = doc_map if doc_map is not None else _document_code_map(db)

    for m in plan_json.get("modules", []) or []:
        db.add(LearningModule(
            plan_id=plan.id,
            module_code=m.get("module_code"),
            title=m.get("title"),
            purpose=m.get("purpose"),
            learning_objectives=m.get("learning_objectives"),
            key_concepts=m.get("key_concepts"),
            estimated_duration=m.get("estimated_duration"),
            due_stage=m.get("due_stage"),
            mandatory=m.get("mandatory", True),
            source_document_id=doc_map.get(m.get("source_document_code")),
            source_section=m.get("source_section"),
            source_requirement_code=m.get("source_requirement_code"),
            learning_activities=m.get("learning_activities"),
            assessment=m.get("assessment"),
            completion_criteria=m.get("completion_criteria"),
            prerequisites=m.get("prerequisites"),
        ))

    for c in plan_json.get("checklist", []) or []:
        db.add(ChecklistItem(
            plan_id=plan.id,
            activity=c.get("activity"),
            required=c.get("required", True),
            due_stage=c.get("due_stage"),
            source_document_id=doc_map.get(c.get("source_document_code")),
            responsible_person=c.get("responsible_person"),
            source_requirement_code=c.get("source_requirement_code"),
            source_section=c.get("source_section"),
        ))

    for t in plan_json.get("tasks", []) or []:
        db.add(OnboardingTask(
            plan_id=plan.id,
            task_description=t.get("task_description"),
            expected_outcome=t.get("expected_outcome"),
            source_requirement_code=t.get("source_requirement_code"),
            difficulty=t.get("difficulty"),
            due_stage=t.get("due_stage"),
            completion_criteria=t.get("completion_criteria"),
            task_type=t.get("task_type"),
            scenario=t.get("scenario"),
        ))

    for q in plan_json.get("quiz", []) or []:
        answers = _answers(q)
        db.add(QuizQuestion(
            plan_id=plan.id,
            question_text=q.get("question_text"),
            question_type=q.get("question_type"),
            options=q.get("options"),
            correct_answer="; ".join(answers)[:255] if answers else None,
            correct_answers=answers,
            explanation=q.get("explanation"),
            difficulty=q.get("difficulty"),
            source_document_id=doc_map.get(q.get("source_document_code")),
            source_section=q.get("source_section"),
            source_requirement_code=q.get("source_requirement_code"),
        ))

    for a in plan_json.get("assessments", []) or []:
        db.add(Assessment(
            plan_id=plan.id,
            title=a.get("title"),
            assessment_type=a.get("assessment_type"),
            description=a.get("description"),
            due_stage=a.get("due_stage"),
            difficulty=a.get("difficulty"),
            source_requirement_code=a.get("source_requirement_code"),
            rubric=a.get("rubric"),
        ))


def persist_plan(employee_id: int, result: dict, db: Session) -> OnboardingPlan:
    plan_json = result["raw_genai_json"]
    plan = OnboardingPlan(
        employee_id=employee_id,
        model_used=result["model_used"],
        prompt_version=result["prompt_version"],
        raw_genai_json=plan_json,
        source_document_versions=result.get("source_document_versions"),
        generation_attempts=result.get("attempts", 1),
        schema_issues=result.get("schema_issues"),
    )
    db.add(plan)
    db.flush()  # assigns plan.id before we attach children

    add_plan_items(plan, plan_json, db)

    db.commit()
    db.refresh(plan)
    attach_progress(plan)
    return plan


def get_plan_by_id(plan_id: int, db: Session) -> OnboardingPlan:
    plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()
    if not plan:
        raise OnboardingServiceError(f"No onboarding plan found with id={plan_id}")
    attach_progress(plan)
    return plan


def list_plans_for_employee(employee_id: int, db: Session):
    plans = (
        db.query(OnboardingPlan)
        .filter(OnboardingPlan.employee_id == employee_id)
        .order_by(OnboardingPlan.generated_at.desc())
        .all()
    )
    for plan in plans:
        attach_progress(plan)
    return plans


# ---------------------------------------------------------------------
# PROGRESS TRACKING (SRS liii) -- module, checklist, and task completion.
# ---------------------------------------------------------------------

_ITEM_MODEL_MAP = {
    "module": LearningModule,
    "checklist": ChecklistItem,
    "task": OnboardingTask,
}


def compute_progress(plan: OnboardingPlan) -> dict:
    """
    Progress = fraction of (modules + checklist items + tasks) whose
    completion_status is "Completed". Quiz questions aren't counted here --
    "completing" a quiz means submitting answers, a separate feature.
    """
    items = list(plan.modules) + list(plan.checklist_items) + list(plan.tasks)
    total = len(items)
    completed = sum(1 for i in items if i.completion_status == "Completed")
    percent = round((completed / total) * 100, 1) if total else 0.0
    return {"completed_items": completed, "total_items": total, "progress_percent": percent}


def attach_progress(plan: OnboardingPlan) -> OnboardingPlan:
    """
    Computes progress and sets it as a plain Python attribute on the ORM
    instance (not a DB column) so OnboardingPlanResponse/-Summary can read
    it via from_attributes, without storing a value that would go stale
    the moment an item's status changes.
    """
    summary = compute_progress(plan)
    plan.progress_percent = summary["progress_percent"]
    plan.completed_items = summary["completed_items"]
    plan.total_items = summary["total_items"]
    raw = plan.raw_genai_json if isinstance(plan.raw_genai_json, dict) else {}
    plan.insufficient_information = raw.get("insufficient_information") or []
    plan.security_notes = raw.get("security_notes") or []
    plan.stages = raw.get("stages") or []
    return plan


def update_item_progress(
    plan_id: int, item_type: str, item_id: int, completion_status: str, db: Session
) -> OnboardingPlan:
    """
    Updates one module/checklist item/task's completion_status. Caller
    (the router) is responsible for checking the requester is allowed to
    touch this plan -- this function only checks that the item actually
    belongs to plan_id, so nobody can update an item on someone else's plan
    just by guessing its id.
    """
    model = _ITEM_MODEL_MAP.get(item_type)
    if model is None:
        raise OnboardingServiceError(f"Unknown item_type '{item_type}'. Must be one of: module, checklist, task.")

    item = db.query(model).filter(model.id == item_id, model.plan_id == plan_id).first()
    if not item:
        raise OnboardingServiceError(
            f"No {item_type} with id={item_id} found on plan {plan_id}."
        )

    item.completion_status = completion_status
    db.commit()

    plan = get_plan_by_id(plan_id, db)  # re-fetch, already attaches fresh progress
    return plan