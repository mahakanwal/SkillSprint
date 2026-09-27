"""
routers/employee_router.py
Real CRUD endpoints for managing Employees.

Creating an Employee here ALSO creates its login account in one step --
employees never self-signup. A random temporary password is generated,
hashed and stored, and returned to the caller (the admin/training manager)
exactly once in the response, so it can be shared with the employee. It is
never retrievable again after this.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Employee, Role, User
from schemas.employee_schema import EmployeeCreate, EmployeeResponse, EmployeeCreateResponse
from security.auth import hash_password, generate_temporary_password
from security.rbac import require_roles, get_current_user

router = APIRouter()

# Reading employee data is available to anyone logged in (an employee needs
# this to see their own onboarding plan); creating/deleting employee
# records is admin/training_manager only.
_manage_dep = Depends(require_roles("admin", "training_manager"))
_read_dep = Depends(get_current_user)
# Listing every employee (names, emails) is a staff-only action; an employee
# must not be able to download the whole directory.
_list_dep = Depends(require_roles("admin", "training_manager", "reviewer", "manager"))


@router.post("/", response_model=EmployeeCreateResponse, dependencies=[_manage_dep])
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db)):
    existing_code = db.query(Employee).filter(Employee.employee_code == employee.employee_code).first()
    if existing_code:
        raise HTTPException(
            status_code=400,
            detail=f"Employee with code '{employee.employee_code}' already exists."
        )

    existing_email = db.query(User).filter(User.email == employee.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail=f"A login already exists for email '{employee.email}'.")

    role = db.query(Role).filter(Role.id == employee.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"No role found with id={employee.role_id}")

    # 1) create the login account
    temp_password = generate_temporary_password()
    user = User(
        username=employee.full_name,
        email=employee.email,
        hashed_password=hash_password(temp_password),
        role="employee",
        is_active=True,
    )
    db.add(user)
    db.flush()  # get user.id before linking

    # 2) create the Employee onboarding record, linked to that login
    new_employee = Employee(
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        email=employee.email,
        department=employee.department,
        experience_level=employee.experience_level,
        location=employee.location,
        joining_date=employee.joining_date,
        reporting_manager=employee.reporting_manager,
        required_competencies=employee.required_competencies,
        previous_experience=employee.previous_experience,
        role_id=employee.role_id,
        user_id=user.id,
    )
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)

    return EmployeeCreateResponse(
        employee=new_employee,
        login_email=employee.email,
        temporary_password=temp_password,
    )


@router.get("/", response_model=list[EmployeeResponse], dependencies=[_list_dep])
def list_employees(db: Session = Depends(get_db)):
    return db.query(Employee).all()


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"No employee found with id={employee_id}")
    if current_user.role == "employee" and emp.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Employees can only view their own record.")
    return emp


@router.delete("/{employee_id}", dependencies=[_manage_dep])
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail=f"No employee found with id={employee_id}")

    linked_user = db.query(User).filter(User.id == emp.user_id).first() if emp.user_id else None

    db.delete(emp)
    if linked_user:
        db.delete(linked_user)  # employee gone -> their login should go too
    db.commit()
    return {"message": f"Employee '{emp.full_name}' and their login account deleted."}
