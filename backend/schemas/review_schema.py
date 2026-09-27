"""
schemas/review_schema.py
Pydantic schemas for the reviewer decision + audit trail workflow.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

VALID_DECISIONS = {"Approved", "Rejected", "Needs Regeneration"}


class ReviewDecisionRequest(BaseModel):
    action: str = Field(description="One of: Approved, Rejected, Needs Regeneration")
    notes: Optional[str] = None


class OverrideRequest(BaseModel):
    overridden_status: str = Field(description="The reviewer's corrected validation_status")
    reason: str = Field(min_length=3, description="Why the original Python-computed result is being overridden")


class AuditLogResponse(BaseModel):
    id: int
    plan_id: Optional[int]
    action: str
    original_result: Optional[str]
    reviewer_decision: Optional[str]
    reviewed_by: Optional[str]
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewQueueItem(BaseModel):
    id: int
    employee_id: int
    generated_at: datetime
    verification_status: str
    review_status: str
    coverage_score: float
    traceability_score: float
    consistency_score: float
    employee_name: Optional[str] = None
    role_name: Optional[str] = None

    class Config:
        from_attributes = True


class ValidationResultWithOverride(BaseModel):
    id: int
    requirement_code: Optional[str]
    genai_result: Optional[str]
    python_expected_result: Optional[str]
    match_status: Optional[str]
    validation_status: Optional[str]
    explanation: Optional[str]
    role_name: Optional[str] = None
    source_reference: Optional[str] = None
    coverage_status: Optional[str] = None
    traceability_status: Optional[str] = None
    field_comparison: Optional[list] = None
    overridden_status: Optional[str]
    override_reason: Optional[str]
    overridden_by: Optional[str]
    overridden_at: Optional[datetime]

    class Config:
        from_attributes = True
