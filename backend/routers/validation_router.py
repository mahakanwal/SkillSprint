"""
routers/validation_router.py

Handles onboarding plan validation and re-validation.

FIX: previously read `plan.generated_content`, which does not exist on the
OnboardingPlan model (the real column is `raw_genai_json` -- see
database/models.py and services/onboarding_service.py, which both use that
name). This caused every call to /validation/revalidate/{plan_id} to raise
an AttributeError, caught by the generic except-block below, and returned
as a 500 "Validation failed: ..." error.

Now also passes plan_id through so validation_service persists the computed
scores back onto the OnboardingPlan row instead of just returning them.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import OnboardingPlan
from services.validation_service import validate_onboarding_plan, ValidationError
from security.rbac import require_roles

router = APIRouter()


@router.post("/revalidate/{plan_id}")
def revalidate_plan(plan_id: int, db: Session = Depends(get_db)):
    try:
        plan = db.query(OnboardingPlan).filter(OnboardingPlan.id == plan_id).first()

        if not plan:
            raise HTTPException(status_code=404, detail="Onboarding plan not found")

        result = validate_onboarding_plan(
            employee_id=plan.employee_id,
            generated_plan=plan.raw_genai_json,  # FIXED: was plan.generated_content
            db=db,
            plan_id=plan.id,  # lets the service persist scores back onto this plan
        )

        return {
            "success": True,
            "message": "Validation completed",
            "data": result,
        }

    except ValidationError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except HTTPException:
        raise

    except Exception as error:
        db.rollback()
        print("VALIDATION ERROR:", repr(error))
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(error)}")



# ---------------------------------------------------------------------
# SRS Steps 44-45 -- GenAI consistency check (repeated controlled runs)
# ---------------------------------------------------------------------
@router.post("/consistency/{employee_id}", dependencies=[Depends(require_roles("admin", "training_manager"))])
def run_consistency(employee_id: int, runs: int = 2, db: Session = Depends(get_db)):
    from services.consistency_service import run_consistency_check, ConsistencyError
    from genai_pipeline.fallback_client import AllModelsFailedError
    try:
        return run_consistency_check(employee_id, runs, db)
    except ConsistencyError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except AllModelsFailedError as e:
        raise HTTPException(status_code=503, detail=f"GenAI API unavailable: {e}")


@router.get("/consistency/{employee_id}")
def list_consistency_runs(employee_id: int, db: Session = Depends(get_db)):
    from database.models import ConsistencyRun
    rows = (db.query(ConsistencyRun).filter(ConsistencyRun.employee_id == employee_id)
            .order_by(ConsistencyRun.id.desc()).all())
    return [{"id": r.id, "runs": r.runs, "score": r.score, "model_used": r.model_used,
             "prompt_version": r.prompt_version, "created_at": r.created_at,
             "per_dimension": (r.details or {}).get("per_dimension"),
             "major_differences": (r.details or {}).get("major_differences")} for r in rows]


@router.get("/prompt-versions")
def prompt_versions():
    """SRS Step 40 -- the registered prompt templates and which version is active."""
    from genai_pipeline.prompt_manager import list_versions
    return list_versions()
