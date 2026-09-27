"""
routers/dashboard_router.py

    GET /dashboard/summary   administrator dashboard metrics      (SRS Step 51)
    GET /dashboard/roles     role dashboard                       (SRS Step 52)
    GET /dashboard/plans     search + filter latest plans         (SRS Step 61)
    GET /dashboard/compare   compare plans by role / department /
                             experience level / document version  (SRS Step 60)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from services import report_service

router = APIRouter()


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return report_service.dashboard_summary(db)


@router.get("/roles")
def roles(db: Session = Depends(get_db)):
    return report_service.role_dashboard(db)


@router.get("/plans")
def plans(
    search: Optional[str] = None, role_id: Optional[int] = None, department: Optional[str] = None,
    status: Optional[str] = None, review_status: Optional[str] = None, experience_level: Optional[str] = None,
    module: Optional[str] = None, policy: Optional[str] = None,
    min_progress: Optional[float] = None, max_progress: Optional[float] = None,
    all_versions: bool = False, db: Session = Depends(get_db),
):
    rows = report_service.plan_rows(db, latest_only=not all_versions)
    return report_service.filter_plans(rows, search, role_id, department, status, review_status,
                                       experience_level, module, policy, min_progress, max_progress)


@router.get("/compare")
def compare(group_by: str = "role", db: Session = Depends(get_db)):
    try:
        return report_service.compare_plans(report_service.plan_rows(db), group_by)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
