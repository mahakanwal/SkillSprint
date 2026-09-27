"""
schemas/progress_schema.py
Pydantic schemas for updating and reporting onboarding progress (SRS liii.
"Progress Tracking" -- module, checklist, task, and assessment progress).
"""

from pydantic import BaseModel, field_validator
from typing import Literal

ItemType = Literal["module", "checklist", "task"]

# Modules get a middle "In Progress" state; checklist items and tasks are
# simple pending/completed toggles (matches their DB defaults: "Not
# Started" vs "Pending"). Quiz questions have no completion_status column
# -- "completing" a quiz means submitting answers, which is a separate,
# not-yet-built feature (quiz-taking), not a status toggle.
ALLOWED_STATUSES = {"Not Started", "In Progress", "Pending", "Completed"}


class ProgressUpdateRequest(BaseModel):
    completion_status: str

    @field_validator("completion_status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in ALLOWED_STATUSES:
            raise ValueError(f"completion_status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}")
        return v