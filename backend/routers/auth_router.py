"""
routers/auth_router.py
Real authentication -- no public self-signup. Matches how a real company
portal works: HR/Admin creates accounts, people don't create their own.

    POST /auth/bootstrap-first-admin   only works while the users table is
                                        empty -- creates account #1 (admin),
                                        so someone can log in for the first
                                        time. Refuses once any user exists.
    POST /auth/login                   email + password -> JWT
    GET  /auth/me                      current logged-in user's info
    POST /auth/create-staff-login      admin-only: create a login for a
                                        non-employee staff role (training
                                        manager, reviewer, manager, another
                                        admin). Employee logins are instead
                                        created automatically by
                                        POST /employees/ (see employee_router.py)
                                        since every employee login must be
                                        linked to an Employee record.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import User
from schemas.auth_schema import LoginRequest, TokenResponse, UserResponse, CreateStaffLoginRequest, CreateStaffLoginResponse
from security.auth import hash_password, verify_password, create_access_token, generate_temporary_password
from security.rbac import get_current_user, require_roles

router = APIRouter()

VALID_ROLES = {"admin", "training_manager", "reviewer", "manager", "employee"}


@router.post("/bootstrap-first-admin", response_model=TokenResponse)
def bootstrap_first_admin(data: LoginRequest, db: Session = Depends(get_db)):
    """
    One-time setup endpoint. Only works if the users table is completely
    empty -- this is how the very first admin account gets created, since
    there's no admin yet to create one the normal way. Immediately useless
    after account #1 exists (returns 403).
    """
    if db.query(User).count() > 0:
        raise HTTPException(
            status_code=403,
            detail="An admin account already exists. Ask an existing admin "
                   "to create your account via /auth/create-staff-login.",
        )

    user = User(
        username="Admin",
        email=data.email,
        hashed_password=hash_password(data.password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email, user.role)
    return TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    employee_id = user.employee.id if user.employee else None
    token = create_access_token(user.id, user.email, user.role, employee_id=employee_id)
    return TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/create-staff-login",
    response_model=CreateStaffLoginResponse,
    dependencies=[Depends(require_roles("admin"))],
)
def create_staff_login(data: CreateStaffLoginRequest, db: Session = Depends(get_db)):
    """
    Admin-only. Creates a login for a staff role that isn't a regular
    Employee onboarding record (training_manager, reviewer, manager, or
    another admin). System generates the temporary password -- returned
    exactly once here so the admin can share it; it is never retrievable
    again after this response.
    """
    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of: {', '.join(sorted(VALID_ROLES))}")
    if data.role == "employee":
        raise HTTPException(
            status_code=400,
            detail="Employee logins are created automatically via POST /employees/, not here.",
        )

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A user with email '{data.email}' already exists.")

    temp_password = generate_temporary_password()
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(temp_password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return CreateStaffLoginResponse(
        user=UserResponse.model_validate(user),
        temporary_password=temp_password,
    )
