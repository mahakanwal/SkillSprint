"""
schemas/auth_schema.py
Pydantic schemas for authentication endpoints.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class CreateStaffLoginRequest(BaseModel):
    username: str
    email: str
    role: str  # admin / training_manager / reviewer / manager


class CreateStaffLoginResponse(BaseModel):
    user: UserResponse
    temporary_password: str  # shown exactly once -- admin must copy/share it now
