"""
database/models.py
SQLAlchemy ORM models for SkillSprint AI.
Covers: Users/Auth, Roles, Employees, Documents, Requirement Matrix,
Onboarding Plans (modules, checklists, tasks, quizzes), Validation results,
and Audit trail.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    ForeignKey,
    Date,
    DateTime,
    Float,
    JSON
)

from sqlalchemy.orm import relationship

from sqlalchemy.sql import func

from database.connection import Base


# ---------------------------------------------------------------------
# USERS & AUTH
# ---------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # admin, training_manager, reviewer, manager, employee
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # One login account can be linked to one Employee onboarding record
    # (only relevant when role == "employee"; admin/training_manager/
    # reviewer/manager accounts have no linked Employee row).
    employee = relationship("Employee", back_populates="user", uselist=False)

# NOTE: EmployeeProfile (a second, disconnected place to store department/
# experience/joining_date) used to live here. It duplicated what Employee
# already stores and was never linked to it -- removed. Employee is now the
# single source of truth for onboarding-record data, and Employee.user_id
# links it to the login account below.
# ---------------------------------------------------------------------
# JOB ROLES
# ---------------------------------------------------------------------
class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(150), unique=True, nullable=False)
    department = Column(String(150))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requirements = relationship("RequirementMatrix", back_populates="role")
    employees = relationship("Employee", back_populates="role")


# ---------------------------------------------------------------------
# EMPLOYEES
# ---------------------------------------------------------------------
class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False)  # also the employee's login email
    department = Column(String(150))
    experience_level = Column(String(50))  # Beginner / Intermediate / Advanced
    location = Column(String(150))
    joining_date = Column(DateTime(timezone=True))
    reporting_manager = Column(String(150))
    training_status = Column(String(50), default="Not Started")
    # SRS Step 9 -- profile fields (no sensitive personal data required)
    required_competencies = Column(Text, nullable=True)
    previous_experience = Column(Text, nullable=True)

    role_id = Column(Integer, ForeignKey("roles.id"))
    role = relationship("Role", back_populates="employees")

    # Login account for this employee. Created automatically (with a
    # system-generated temporary password) whenever an admin/training
    # manager registers a new Employee -- employees never self-signup.
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    user = relationship("User", back_populates="employee")

    onboarding_plans = relationship("OnboardingPlan", back_populates="employee")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------
# DOCUMENTS
# ---------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_code = Column(String(50), unique=True, nullable=False)  # e.g. SOP-07-v1 (each version gets its own code)
    title = Column(String(255), nullable=False)
    doc_type = Column(String(100))  # Policy, SOP, FAQ, Handbook, etc.
    department = Column(String(150))
    file_path = Column(String(500))
    version = Column(String(20), default="1.0")
    is_active_version = Column(Boolean, default=True)
    effective_date = Column(DateTime(timezone=True))
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Document Validation + Version Control ---
    file_hash = Column(String(64), index=True, nullable=True)       # SHA-256 of file content -- duplicate detection
    file_size_kb = Column(Float, nullable=True)
    family_code = Column(String(50), index=True, nullable=True)     # groups versions of the "same" document together
    supersedes_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)  # links to the version this replaced

    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_code = Column(String(50))  # e.g. CH-001
    document_id = Column(Integer, ForeignKey("documents.id"))
    section = Column(String(100))
    heading = Column(String(255))
    content = Column(Text)
    page_or_location = Column(String(100))

    document = relationship("Document", back_populates="chunks")


# ---------------------------------------------------------------------
# ROLE REQUIREMENT MATRIX (ground truth)
# ---------------------------------------------------------------------
class RequirementMatrix(Base):
    __tablename__ = "requirement_matrix"

    id = Column(Integer, primary_key=True, index=True)
    requirement_code = Column(String(50), unique=True, nullable=False)  # e.g. R001

    role_id = Column(Integer, ForeignKey("roles.id"))
    role = relationship("Role", back_populates="requirements")

    policy_requirement = Column(String(255))
    process_requirement = Column(String(255))
    competency = Column(String(255))
    mandatory = Column(Boolean, default=True)
    priority = Column(String(20))  # High / Medium / Low
    due_stage = Column(String(50))  # Day 1, Week 1, First 30 Days, etc.

    source_document_id = Column(Integer, ForeignKey("documents.id"))
    source_section = Column(String(100))

    assessment_requirement = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------
# ONBOARDING PLAN (GenAI generated, structured)
# ---------------------------------------------------------------------
class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    employee = relationship("Employee", back_populates="onboarding_plans")

    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    model_used = Column(String(100))
    prompt_version = Column(String(50))

    coverage_score = Column(Float, default=0.0)
    traceability_score = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)

    verification_status = Column(String(50), default="Manual Review Required")
    # Verified / Verified with Warning / Partially Verified / Incomplete /
    # Unsupported / Contradictory / Manual Review Required

    # --- Reviewer Decision workflow (SRS xliv-xlvii) ---
    review_status = Column(String(30), default="Pending Review")
    # Pending Review / Approved / Rejected / Needs Regeneration
    reviewed_by = Column(String(150), nullable=True)   # reviewer's username/email
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_notes = Column(Text, nullable=True)

    raw_genai_json = Column(JSON, nullable=True)  # full structured GenAI output

    # SRS Step 41 -- versions of every source document used for this plan,
    # e.g. [{"document_code": "SOP-07-v2", "version": "2.0", "document_id": 9}]
    source_document_versions = Column(JSON, nullable=True)
    generation_attempts = Column(Integer, default=1)
    schema_issues = Column(JSON, nullable=True)  # Step 38 findings kept for the report
    last_validation_report = Column(JSON, nullable=True)  # full Pipeline 2 output, for reports
    validated_at = Column(DateTime(timezone=True), nullable=True)

    modules = relationship("LearningModule", back_populates="plan")
    checklist_items = relationship("ChecklistItem", back_populates="plan")
    tasks = relationship("OnboardingTask", back_populates="plan")
    quizzes = relationship("QuizQuestion", back_populates="plan")
    assessments = relationship("Assessment", back_populates="plan")


class LearningModule(Base):
    __tablename__ = "learning_modules"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"))
    plan = relationship("OnboardingPlan", back_populates="modules")

    module_code = Column(String(50))  # e.g. M04
    title = Column(String(255))
    purpose = Column(Text)
    learning_objectives = Column(JSON)  # list of strings
    key_concepts = Column(JSON)
    estimated_duration = Column(String(50))
    due_stage = Column(String(50))
    mandatory = Column(Boolean, default=True)

    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    source_section = Column(String(100), nullable=True)

    # SRS Step 14 -- structured module fields
    source_requirement_code = Column(String(50), nullable=True)
    learning_activities = Column(JSON, nullable=True)
    assessment = Column(Text, nullable=True)
    completion_criteria = Column(Text, nullable=True)
    prerequisites = Column(JSON, nullable=True)  # list of module codes

    completion_status = Column(String(50), default="Not Started")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"))
    plan = relationship("OnboardingPlan", back_populates="checklist_items")

    activity = Column(String(255))
    required = Column(Boolean, default=True)
    due_stage = Column(String(50))
    completion_status = Column(String(50), default="Pending")
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    responsible_person = Column(String(150), nullable=True)
    source_requirement_code = Column(String(50), nullable=True)
    source_section = Column(String(100), nullable=True)


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"))
    plan = relationship("OnboardingPlan", back_populates="tasks")

    task_description = Column(Text)
    expected_outcome = Column(Text)
    source_requirement_code = Column(String(50), nullable=True)
    difficulty = Column(String(50))  # Beginner/Intermediate/Advanced
    due_stage = Column(String(50))
    completion_status = Column(String(50), default="Pending")
    # SRS Steps 18-19 -- completion criteria + scenario-based tasks
    completion_criteria = Column(Text, nullable=True)
    task_type = Column(String(30), nullable=True)  # practical / scenario
    scenario = Column(Text, nullable=True)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"))
    plan = relationship("OnboardingPlan", back_populates="quizzes")

    question_text = Column(Text)
    question_type = Column(String(50))  # multiple_choice, true_false, scenario
    options = Column(JSON, nullable=True)
    correct_answer = Column(String(255))
    explanation = Column(Text)
    difficulty = Column(String(50))

    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    source_section = Column(String(100), nullable=True)
    source_requirement_code = Column(String(50), nullable=True)
    # multiple_response questions have more than one correct option
    correct_answers = Column(JSON, nullable=True)


# ---------------------------------------------------------------------
# ASSESSMENTS (SRS Steps 23-24) -- generated with a structured rubric
# ---------------------------------------------------------------------
class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"))
    plan = relationship("OnboardingPlan", back_populates="assessments")

    title = Column(String(255))
    assessment_type = Column(String(30))  # knowledge / practical / scenario / role_specific
    description = Column(Text)
    due_stage = Column(String(50))
    difficulty = Column(String(50))
    source_requirement_code = Column(String(50), nullable=True)
    rubric = Column(JSON, nullable=True)  # [{criterion, weight, expected_performance, pass_condition}]

    score = Column(Float, nullable=True)  # 0-100, recorded by a trainer/manager
    status = Column(String(30), default="Pending")  # Pending / Passed / Failed
    evaluated_by = Column(String(150), nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------
# QUIZ ATTEMPTS (SRS Steps 50, 53, 56) -- quiz scores + weak areas
# ---------------------------------------------------------------------
class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"), index=True)
    question_id = Column(Integer, ForeignKey("quiz_questions.id"), index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), index=True)
    selected = Column(JSON)  # list of selected option strings
    is_correct = Column(Boolean, default=False)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------
# SECURITY FLAGS (SRS Steps 42-43, xlviii-xlix) -- suspicious instructions
# found inside uploaded documents or generated output
# ---------------------------------------------------------------------
class SecurityFlag(Base):
    __tablename__ = "security_flags"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id"), nullable=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"), nullable=True)
    category = Column(String(60))  # instruction_override / approval_manipulation / ...
    severity = Column(String(20))  # high / medium
    matched_text = Column(Text)
    location = Column(String(150), nullable=True)
    hidden_text = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------
# GENAI CONSISTENCY RUNS (SRS Steps 44-45)
# ---------------------------------------------------------------------
class ConsistencyRun(Base):
    __tablename__ = "consistency_runs"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    runs = Column(Integer)
    score = Column(Float)
    details = Column(JSON)
    model_used = Column(String(100))
    prompt_version = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------
# VALIDATION RESULTS (Python Ground-Truth Pipeline output)
# ---------------------------------------------------------------------
class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"))

    requirement_code = Column(String(50))
    genai_result = Column(String(255), nullable=True)
    python_expected_result = Column(String(255), nullable=True)
    match_status = Column(String(20))  # Match / Mismatch
    validation_status = Column(String(50))
    # Verified / Source Support Missing / Requirement Missing /
    # Unsupported Requirement / Outdated Source / Contradiction Detected

    explanation = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())

    # SRS Step 46 / comparison report columns
    role_name = Column(String(150), nullable=True)
    source_reference = Column(String(255), nullable=True)   # e.g. "SOP-07-v2 §4.2"
    coverage_status = Column(String(30), nullable=True)     # Covered / Missing
    traceability_status = Column(String(30), nullable=True) # Traced / Untraced / Outdated
    field_comparison = Column(JSON, nullable=True)          # [{field, genai, python, result}]

    # --- Reviewer Override (SRS xlvi-xlvii) ---
    # validation_status above is the ORIGINAL, Python-computed result and is
    # never overwritten -- the override lives in separate columns so both
    # the original and the overridden result are always visible together.
    overridden_status = Column(String(50), nullable=True)
    override_reason = Column(Text, nullable=True)
    overridden_by = Column(String(150), nullable=True)
    overridden_at = Column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------
# AUDIT TRAIL (for reviewer overrides)
# ---------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("onboarding_plans.id"), nullable=True)
    action = Column(String(100))  # approve, reject, edit, regenerate, override
    original_result = Column(Text, nullable=True)
    reviewer_decision = Column(Text, nullable=True)
    reviewed_by = Column(String(150), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())