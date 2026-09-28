"""
main.py
FastAPI application entry point for SkillSprint AI.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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


load_dotenv()


app = FastAPI(
    title="SkillSprint AI",
    description="Generative AI-powered employee onboarding intelligence platform",
    version="1.0.0"
)


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://skill-sprint-omega-six.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_admin_only = [
    Depends(require_roles("admin", "training_manager"))
]

_onboarding_access = [
    Depends(get_current_user)
]

_validation_access = [
    Depends(
        require_roles(
            "admin",
            "training_manager",
            "reviewer",
            "manager"
        )
    )
]

_review_access = [
    Depends(
        require_roles(
            "admin",
            "training_manager",
            "reviewer"
        )
    )
]

_reporting_access = [
    Depends(
        require_roles(
            "admin",
            "training_manager",
            "reviewer",
            "manager"
        )
    )
]


# Register Routers

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
    tags=["Employees"],
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


app.include_router(
    review_router.router,
    prefix="/review",
    tags=["Review"],
    dependencies=_review_access,
)


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