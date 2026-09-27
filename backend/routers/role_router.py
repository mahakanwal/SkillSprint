"""
routers/role_router.py
Real CRUD endpoints for managing Job Roles.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Role
from schemas.role_schema import RoleCreate, RoleResponse

router = APIRouter()


@router.post("/", response_model=RoleResponse)
def create_role(role: RoleCreate, db: Session = Depends(get_db)):
    existing = db.query(Role).filter(Role.role_name == role.role_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Role '{role.role_name}' already exists.")

    new_role = Role(
        role_name=role.role_name,
        department=role.department,
        description=role.description,
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role


@router.get("/", response_model=list[RoleResponse])
def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).all()


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(role_id: int, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"No role found with id={role_id}")
    return role


@router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"No role found with id={role_id}")
    db.delete(role)
    db.commit()
    return {"message": f"Role '{role.role_name}' deleted."}