"""
schemas/requirement_matrix_schema.py
Pydantic schemas for the Role Requirement Matrix -- create/update/read,
plus the CSV bulk-upload response shape.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class RequirementMatrixCreate(BaseModel):
    requirement_code: str
    role_id: int
    policy_requirement: Optional[str] = None
    process_requirement: Optional[str] = None
    competency: Optional[str] = None
    mandatory: Optional[bool] = True
    priority: Optional[str] = None          # High / Medium / Low
    due_stage: Optional[str] = None         # Day 1, Week 1, First 30 Days, etc.
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    assessment_requirement: Optional[str] = None


class RequirementMatrixUpdate(BaseModel):
    role_id: Optional[int] = None
    policy_requirement: Optional[str] = None
    process_requirement: Optional[str] = None
    competency: Optional[str] = None
    mandatory: Optional[bool] = None
    priority: Optional[str] = None
    due_stage: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    assessment_requirement: Optional[str] = None


class RequirementMatrixResponse(BaseModel):
    id: int
    requirement_code: str
    role_id: int
    policy_requirement: Optional[str]
    process_requirement: Optional[str]
    competency: Optional[str]
    mandatory: bool
    priority: Optional[str]
    due_stage: Optional[str]
    source_document_id: Optional[int]
    source_section: Optional[str]
    assessment_requirement: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CSVUploadRowError(BaseModel):
    row_number: int
    requirement_code: Optional[str] = None
    error: str


class CSVUploadResponse(BaseModel):
    message: str
    total_rows_in_file: int
    created_count: int
    skipped_count: int
    errors: List[CSVUploadRowError]