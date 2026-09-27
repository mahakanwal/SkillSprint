"""
schemas/genai_plan_schema.py

SRS Steps 37-38 / xv-xvi -- the predefined JSON contract for GenAI output.

This describes what the MODEL must return (the raw plan), not the API
response. It is used by python_validation/schema_validator.py to detect
missing fields, wrong data types, bad enum values, and a missing
mandatory status before anything is saved.
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["Beginner", "Intermediate", "Advanced"]
QuestionType = Literal["multiple_choice", "multiple_response", "true_false", "scenario"]
TaskType = Literal["practical", "scenario"]
AssessmentType = Literal["knowledge", "practical", "scenario", "role_specific"]


class _Lenient(BaseModel):
    # Extra keys from the model are allowed (kept in raw JSON), but every
    # REQUIRED field must be present with the right type.
    model_config = ConfigDict(extra="allow")


class GenModule(_Lenient):
    module_code: str = Field(min_length=1)
    title: str = Field(min_length=3)
    purpose: str = Field(min_length=3)
    learning_objectives: List[str] = Field(min_length=1)
    key_concepts: List[str] = []
    learning_activities: List[str] = []
    assessment: Optional[str] = None
    completion_criteria: Optional[str] = None
    estimated_duration: Optional[str] = None
    due_stage: str = Field(min_length=1)
    mandatory: bool  # REQUIRED -- "missing mandatory status" is a schema error
    prerequisites: List[str] = []
    source_requirement_code: Optional[str] = None
    source_document_code: Optional[str] = None
    source_section: Optional[str] = None


class GenChecklistItem(_Lenient):
    activity: str = Field(min_length=3)
    required: bool
    due_stage: Optional[str] = None
    source_requirement_code: Optional[str] = None
    source_document_code: Optional[str] = None
    source_section: Optional[str] = None
    responsible_person: Optional[str] = None


class GenTask(_Lenient):
    task_description: str = Field(min_length=3)
    task_type: Optional[TaskType] = "practical"
    scenario: Optional[str] = None
    expected_outcome: str = Field(min_length=3)
    completion_criteria: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    due_stage: Optional[str] = None
    source_requirement_code: Optional[str] = None


class GenQuizQuestion(_Lenient):
    question_text: str = Field(min_length=3)
    question_type: QuestionType
    options: List[str] = []
    correct_answer: Union[str, List[str]]
    explanation: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    source_requirement_code: Optional[str] = None
    source_document_code: Optional[str] = None
    source_section: Optional[str] = None


class RubricCriterion(_Lenient):
    criterion: str = Field(min_length=2)
    weight: float = Field(ge=0, le=100)
    expected_performance: str = Field(min_length=2)
    pass_condition: str = Field(min_length=2)


class GenAssessment(_Lenient):
    title: str = Field(min_length=3)
    assessment_type: AssessmentType
    description: Optional[str] = None
    due_stage: Optional[str] = None
    difficulty: Optional[Difficulty] = None
    source_requirement_code: Optional[str] = None
    rubric: List[RubricCriterion] = Field(min_length=1)


class GenPlan(_Lenient):
    role: Optional[str] = None
    stages: List[str] = []
    modules: List[GenModule] = Field(min_length=1)
    checklist: List[GenChecklistItem] = []
    tasks: List[GenTask] = []
    quiz: List[GenQuizQuestion] = []
    assessments: List[GenAssessment] = []
    insufficient_information: List[str] = []
    security_notes: List[str] = []


REQUIRED_TOP_LEVEL = ("modules", "checklist", "tasks", "quiz")
