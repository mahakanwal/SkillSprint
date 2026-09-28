"""
main.py
FastAPI application entry point for SkillSprint AI.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from database.connection import init_db

from routers import (
    document_router,
    role_router,
    employee_router,
    requirement_matrix_router,
    onboarding_router,
    validation_router,
    auth_router,
    review_router,
    dashboard_router,
    report_router,
)
from security.rbac import require_roles, get_current_user

from dotenv import load_dotenv

load_dotenv()

# Applied at the router level. Three tiers:
#   _admin_only        -- documents/roles/requirements: only admin/training_manager
#                          create or touch these (source content + ground truth).
#   _onboarding_access -- onboarding: any logged-in user, because an EMPLOYEE
#                          must be able to read their own generated plan
#                          (GET /onboarding/plan/{employee_id}), and
#                          reviewers/managers also need read access here.
#                          NOTE: this means onboarding_router's internal
#                          routes are the real boundary for write actions
#                          (e.g. POST /onboarding/generate/{id}) -- if that
#                          file doesn't already restrict generation to
#                          admin/training_manager internally, add
#                          Depends(require_roles("admin","training_manager"))
#                          on that specific route.
#   _validation_access -- validation: admin/training_manager (who fix issues)
#                          plus reviewer/manager (who read the audit trail).
# employee_router is deliberately NOT included here: it manages narrower
# per-route access itself (any logged-in user can read, only
# admin/training_manager can create/delete).
_admin_only = [Depends(require_roles("admin", "training_manager"))]
_onboarding_access = [Depends(get_current_user)]
_validation_access = [Depends(require_roles("admin", "training_manager", "reviewer", "manager"))]
# review: only the roles allowed to actually make/override decisions.
# (manager is deliberately excluded -- they can SEE validation detail via
# _validation_access above, but approving/rejecting/overriding plans is a
# training_manager/reviewer/admin action, not a people-manager one.)
_review_access = [Depends(require_roles("admin", "training_manager", "reviewer"))]
# dashboards + reports: staff who oversee onboarding (not employees)
_reporting_access = [Depends(require_roles("admin", "training_manager", "reviewer", "manager"))]





app = FastAPI(
    title="SkillSprint AI",
    description="Generative AI-powered employee onboarding intelligence platform",
    version="1.0.0"
)


# Allow React frontend (localhost:5173 for Vite) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to specific origin before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Register routers

app.include_router(
    document_router.router,
    prefix="/documents",
    tags=["Documents"],
    dependencies=_admin_only,
)


app.include_router(
    role_router.router,
    prefix="/roles",
    tags=["Roles"],
    dependencies=_admin_only,
)


app.include_router(
    employee_router.router,
    prefix="/employees",
    tags=["Employees"]
)


app.include_router(
    requirement_matrix_router.router,
    prefix="/requirements",
    tags=["Requirement Matrix"],
    dependencies=_admin_only,
)


app.include_router(
    onboarding_router.router,
    prefix="/onboarding",
    tags=["Onboarding"],
    dependencies=_onboarding_access,
)


# NEW: Validation Pipeline

app.include_router(
    validation_router.router,
    prefix="/validation",
    tags=["Validation"],
    dependencies=_validation_access,
)

app.include_router(
    auth_router.router,
    prefix="/auth",
    tags=["Authentication"],
)

# NEW: Reviewer Decision + Audit Trail

app.include_router(
    review_router.router,
    prefix="/review",
    tags=["Review"],
    dependencies=_review_access,
)

# NEW: Dashboards (SRS 51-52, 60-61) + Reports/Export (SRS 62-63)

app.include_router(
    dashboard_router.router,
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=_reporting_access,
)

app.include_router(
    report_router.router,
    prefix="/reports",
    tags=["Reports"],
    dependencies=_reporting_access,
)

@app.on_event("startup")
def on_startup():

    init_db()

    print(
        "Database tables verified/created."
    )



@app.get("/")
def root():

    return {
        "status": "SkillSprint AI backend is running"
    }