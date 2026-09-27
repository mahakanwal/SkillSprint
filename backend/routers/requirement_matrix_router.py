"""
routers/requirement_matrix_router.py

Real CRUD endpoints for the Role Requirement Matrix (SRS "ground truth"
table), plus CSV bulk-upload so 150+ requirements can be added in one shot
instead of one-by-one through the UI.

Endpoints:
    POST   /requirements/                 create one requirement
    GET    /requirements/                 list requirements (optional ?role_id=)
    GET    /requirements/{id}             get one requirement
    PUT    /requirements/{id}             update one requirement
    DELETE /requirements/{id}             delete one requirement
    POST   /requirements/bulk-upload      upload a CSV of many requirements
    GET    /requirements/template/csv     download a starter CSV template

Test all of this via Swagger UI at http://localhost:8000/docs
"""

import io
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import RequirementMatrix, Role, Document
from schemas.requirement_matrix_schema import (
    RequirementMatrixCreate,
    RequirementMatrixUpdate,
    RequirementMatrixResponse,
    CSVUploadResponse,
)
from role_matrix.matrix_builder import import_requirements_csv, CSVImportError

router = APIRouter()


@router.post("/", response_model=RequirementMatrixResponse)
def create_requirement(req: RequirementMatrixCreate, db: Session = Depends(get_db)):
    existing = db.query(RequirementMatrix).filter(
        RequirementMatrix.requirement_code == req.requirement_code
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Requirement '{req.requirement_code}' already exists."
        )

    role = db.query(Role).filter(Role.id == req.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"No role found with id={req.role_id}")

    if req.source_document_id is not None:
        doc = db.query(Document).filter(Document.id == req.source_document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"No document found with id={req.source_document_id}"
            )

    new_req = RequirementMatrix(**req.dict())
    db.add(new_req)
    db.commit()
    db.refresh(new_req)
    return new_req


@router.get("/", response_model=List[RequirementMatrixResponse])
def list_requirements(role_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(RequirementMatrix)
    if role_id is not None:
        query = query.filter(RequirementMatrix.role_id == role_id)
    return query.order_by(RequirementMatrix.id).all()


@router.get("/template/csv")
def download_csv_template():
    """Downloadable starter CSV with the exact headers bulk-upload expects."""
    header = (
        "requirement_code,role_name,policy_requirement,process_requirement,"
        "competency,mandatory,priority,due_stage,source_document_code,"
        "source_section,assessment_requirement\n"
    )
    example = (
        "R001,Customer Support Executive,Must follow escalation SOP within 24 hours,"
        "Log every ticket in CRM before closing,Conflict de-escalation,true,High,Week 1,"
        "SOP-07,4.2,Explain the 3-step escalation process\n"
    )
    csv_content = header + example
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=requirement_matrix_template.csv"},
    )


@router.get("/{requirement_id}", response_model=RequirementMatrixResponse)
def get_requirement(requirement_id: int, db: Session = Depends(get_db)):
    req = db.query(RequirementMatrix).filter(RequirementMatrix.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"No requirement found with id={requirement_id}")
    return req


@router.put("/{requirement_id}", response_model=RequirementMatrixResponse)
def update_requirement(
    requirement_id: int,
    req_update: RequirementMatrixUpdate,
    db: Session = Depends(get_db),
):
    req = db.query(RequirementMatrix).filter(RequirementMatrix.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"No requirement found with id={requirement_id}")

    update_data = req_update.dict(exclude_unset=True)

    if "role_id" in update_data and update_data["role_id"] is not None:
        role = db.query(Role).filter(Role.id == update_data["role_id"]).first()
        if not role:
            raise HTTPException(
                status_code=404,
                detail=f"No role found with id={update_data['role_id']}"
            )

    if "source_document_id" in update_data and update_data["source_document_id"] is not None:
        doc = db.query(Document).filter(Document.id == update_data["source_document_id"]).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"No document found with id={update_data['source_document_id']}"
            )

    for field, value in update_data.items():
        setattr(req, field, value)

    db.commit()
    db.refresh(req)
    return req


@router.delete("/{requirement_id}")
def delete_requirement(requirement_id: int, db: Session = Depends(get_db)):
    req = db.query(RequirementMatrix).filter(RequirementMatrix.id == requirement_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"No requirement found with id={requirement_id}")
    code = req.requirement_code
    db.delete(req)
    db.commit()
    return {"message": f"Requirement '{code}' deleted."}


@router.post("/bulk-upload", response_model=CSVUploadResponse)
async def bulk_upload_requirements(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

    try:
        result = import_requirements_csv(file_bytes, db)
    except CSVImportError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return result