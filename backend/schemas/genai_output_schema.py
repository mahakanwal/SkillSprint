"""
schemas/genai_output_schema.py
Pydantic response schemas for GenAI-generated onboarding plans -- the
saved-to-DB shape returned by /onboarding endpoints.
"""

from pydantic import BaseModel
from typing import Any, Optional, List
from datetime import datetime


class LearningModuleResponse(BaseModel):
    id: int
    module_code: Optional[str] = None
    title: Optional[str] = None
    purpose: Optional[str] = None
    learning_objectives: Optional[List[str]] = None
    key_concepts: Optional[List[str]] = None
    estimated_duration: Optional[str] = None
    due_stage: Optional[str] = None
    mandatory: bool
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    source_requirement_code: Optional[str] = None
    learning_activities: Optional[List[str]] = None
    assessment: Optional[str] = None
    completion_criteria: Optional[str] = None
    prerequisites: Optional[List[str]] = None
    completion_status: str

    class Config:
        from_attributes = True


class ChecklistItemResponse(BaseModel):
    id: int
    activity: Optional[str] = None
    required: bool
    due_stage: Optional[str] = None
    completion_status: str
    source_document_id: Optional[int] = None
    responsible_person: Optional[str] = None
    source_requirement_code: Optional[str] = None
    source_section: Optional[str] = None

    class Config:
        from_attributes = True


class OnboardingTaskResponse(BaseModel):
    id: int
    task_description: Optional[str] = None
    expected_outcome: Optional[str] = None
    source_requirement_code: Optional[str] = None
    difficulty: Optional[str] = None
    due_stage: Optional[str] = None
    completion_status: str
    completion_criteria: Optional[str] = None
    task_type: Optional[str] = None
    scenario: Optional[str] = None

    class Config:
        from_attributes = True


class QuizQuestionResponse(BaseModel):
    id: int
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    source_document_id: Optional[int] = None
    source_section: Optional[str] = None
    source_requirement_code: Optional[str] = None
    correct_answers: Optional[List[str]] = None

    class Config:
        from_attributes = True


class AssessmentResponse(BaseModel):
    id: int
    title: Optional[str] = None
    assessment_type: Optional[str] = None
    description: Optional[str] = None
    due_stage: Optional[str] = None
    difficulty: Optional[str] = None
    source_requirement_code: Optional[str] = None
    rubric: Optional[List[Any]] = None
    score: Optional[float] = None
    status: Optional[str] = None
    evaluated_by: Optional[str] = None
    evaluated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OnboardingPlanResponse(BaseModel):
    id: int
    employee_id: int
    generated_at: datetime
    model_used: Optional[str] = None
    prompt_version: Optional[str] = None
    coverage_score: float
    traceability_score: float
    consistency_score: float
    verification_status: str
    review_status: Optional[str] = None

    # Progress is computed on read (services/onboarding_service.attach_progress).
    # These were missing from the response model before, so the employee
    # dashboard always showed 0% even after items were completed.
    progress_percent: Optional[float] = None
    completed_items: Optional[int] = None
    total_items: Optional[int] = None

    source_document_versions: Optional[List[Any]] = None
    generation_attempts: Optional[int] = None
    schema_issues: Optional[List[Any]] = None
    insufficient_information: Optional[List[str]] = None
    security_notes: Optional[List[str]] = None
    stages: Optional[List[str]] = None
    last_validation_report: Optional[dict] = None
    validated_at: Optional[datetime] = None

    modules: List[LearningModuleResponse] = []
    checklist_items: List[ChecklistItemResponse] = []
    tasks: List[OnboardingTaskResponse] = []
    quizzes: List[QuizQuestionResponse] = []
    assessments: List[AssessmentResponse] = []

    class Config:
        from_attributes = True


class OnboardingPlanSummary(BaseModel):
    id: int
    employee_id: int
    generated_at: datetime
    model_used: Optional[str] = None
    prompt_version: Optional[str] = None
    verification_status: str
    review_status: Optional[str] = None
    progress_percent: Optional[float] = None

    class Config:
        from_attributes = True