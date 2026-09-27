"""
routers/report_router.py -- SRS Steps 62-63 / lxi-lxii.

    GET /reports/                       list of available reports
    GET /reports/{name}?format=json     report rows as JSON (default)
    GET /reports/{name}?format=csv      CSV download (Excel-compatible)

PDF: the frontend's report page has a print view ("Save as PDF").
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from services.report_service import REPORTS, report_comparison
from utils.export_utils import csv_response

router = APIRouter()


@router.get("/")
def list_reports():
    return [{"name": k, "title": v[0]} for k, v in REPORTS.items()]


@router.get("/{name}")
def get_report(name: str, format: str = "json", plan_id: Optional[int] = None, db: Session = Depends(get_db)):
    if name not in REPORTS:
        raise HTTPException(status_code=404, detail=f"Unknown report '{name}'. Available: {', '.join(REPORTS)}")
    title, fn = REPORTS[name]
    rows = report_comparison(db, plan_id) if name == "genai-python-comparison" else fn(db)
    if format == "csv":
        return csv_response(rows, f"skillsprint_{name}.csv")
    if format != "json":
        raise HTTPException(status_code=422, detail="format must be json or csv")
    return {"name": name, "title": title, "count": len(rows), "rows": rows}
