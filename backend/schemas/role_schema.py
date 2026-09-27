"""
schemas/role_schema.py
Pydantic schemas for Role create/read.
"""

from pydantic import BaseModel
from typing import Optional


class RoleCreate(BaseModel):
    role_name: str
    department: Optional[str] = None
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: int
    role_name: str
    department: Optional[str]
    description: Optional[str]

    class Config:
        from_attributes = True