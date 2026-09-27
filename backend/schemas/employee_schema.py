"""
schemas/employee_schema.py
Pydantic schemas for Employee create/read.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EmployeeCreate(BaseModel):
    employee_code: str
    full_name: str
    email: str  # required -- this becomes the employee's login email too
    department: Optional[str] = None
    experience_level: Optional[str] = "Beginner"  # Beginner / Intermediate / Advanced
    location: Optional[str] = None
    joining_date: Optional[datetime] = None
    reporting_manager: Optional[str] = None
    required_competencies: Optional[str] = None
    previous_experience: Optional[str] = None
    role_id: int


class EmployeeResponse(BaseModel):
    id: int
    employee_code: str
    full_name: str
    email: str
    department: Optional[str]
    experience_level: Optional[str]
    location: Optional[str]
    joining_date: Optional[datetime]
    reporting_manager: Optional[str]
    required_competencies: Optional[str] = None
    previous_experience: Optional[str] = None
    training_status: str
    role_id: int
    user_id: Optional[int]

    class Config:
        from_attributes = True


class EmployeeCreateResponse(BaseModel):
    """
    Returned only from POST /employees/ -- includes the one-time temporary
    password for the login account that gets auto-created alongside the
    Employee record. Never retrievable again after this response.
    """
    employee: EmployeeResponse
    login_email: str
    temporary_password: str
