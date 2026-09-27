"""
genai_pipeline/generator.py

Pipeline 1 -- GenAI generation.

  1. Builds the role context (Requirement Matrix + ACTIVE source documents,
     precedence ranks, injection-redacted text) -- context_builder.py.
  2. Loads the active, versioned prompt template -- prompt_manager.py.
  3. Calls Groq with retry + model fallback -- fallback_client.py.
  4. Parses the JSON and validates it against schemas/genai_plan_schema.py.
     Invalid or incomplete JSON -> the errors are fed back and the call is
     retried, at most GENAI_SCHEMA_MAX_ATTEMPTS times (SRS Step 39).

This file never writes to the database; persistence is
services/onboarding_service.py. It also never approves anything -- the
output always goes through Pipeline 2 (Python validation) afterwards.
"""

import json
import re

from sqlalchemy.orm import Session

from config.settings import settings
from database.models import Employee
from genai_pipeline.context_builder import (
    build_role_context, format_precedence, format_requirements, format_sources,
)
from genai_pipeline.fallback_client import generate_with_fallback, AllModelsFailedError  # noqa: F401
from genai_pipeline.model_logger import log_generation_complete, log_schema_retry
from genai_pipeline.prompt_manager import get_prompt, render, PromptTemplateError
from python_validation.schema_validator import semantic_findings, structural_errors


class GeneratorError(Exception):
    """Raised for any failure in building/generating/parsing an onboarding plan."""
    pass


def _extract_json(raw_text: str) -> dict:
    """
    Groq is asked for pure JSON, but markdown fences or a stray sentence can
    slip in. Strip fences, then fall back to the outermost {...} block.
    """
    text = (raw_text or "").strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError as e:
                raise GeneratorError(f"GenAI response was not valid JSON: {e}")
        raise GeneratorError("GenAI response did not contain a JSON object.")


def _feedback(errors: list) -> str:
    lines = "\n".join(f"- {e['path']}: {e['message']}" for e in errors[:15])
    return (
        "\n\nYOUR PREVIOUS RESPONSE WAS REJECTED BY THE SCHEMA VALIDATOR:\n"
        f"{lines}\n"
        "Return the COMPLETE corrected JSON object, following the required shape exactly."
    )


def run_structured_generation(system_prompt: str, user_prompt: str, employee_code: str,
                              required_keys=("modules", "checklist", "tasks", "quiz"),
                              validate=structural_errors) -> dict:
    """
    Calls the model, parses + validates the JSON, retries with feedback on
    failure. Returns {"parsed", "model_used", "attempts", "attempt_errors"}.
    """
    max_attempts = max(1, settings.GENAI_SCHEMA_MAX_ATTEMPTS)
    feedback = ""
    attempt_errors = []
    for attempt in range(1, max_attempts + 1):
        result = generate_with_fallback(system_prompt, user_prompt + feedback, employee_code)
        try:
            parsed = _extract_json(result["content"])
            errors = validate(parsed) if validate else [
                {"path": k, "message": f"Missing required section '{k}'."} for k in required_keys if k not in parsed
            ]
        except GeneratorError as e:
            parsed, errors = None, [{"path": "$", "message": str(e), "severity": "error", "kind": "invalid_json"}]

        if not errors:
            return {"parsed": parsed, "model_used": result["model_used"], "attempts": attempt, "attempt_errors": attempt_errors}

        attempt_errors.append({"attempt": attempt, "errors": errors[:20]})
        log_schema_retry(employee_code, attempt, max_attempts, errors)
        feedback = _feedback(errors)

    last = attempt_errors[-1]["errors"] if attempt_errors else []
    raise GeneratorError(
        f"GenAI output failed schema validation after {max_attempts} attempts. "
        f"Last errors: " + "; ".join(f"{e['path']}: {e['message']}" for e in last[:5])
    )


def build_prompts(employee: Employee, ctx: dict, prompt_name: str = "onboarding_plan") -> tuple[dict, str]:
    try:
        prompt = get_prompt(prompt_name)
    except PromptTemplateError as e:
        raise GeneratorError(str(e))

    values = dict(
        employee_name=employee.full_name,
        employee_code=employee.employee_code,
        role_name=ctx["role_name"] or "Unknown role",
        department=employee.department,
        experience_level=employee.experience_level,
        joining_date=employee.joining_date.date().isoformat() if employee.joining_date else None,
        previous_experience=getattr(employee, "previous_experience", None),
        required_competencies=getattr(employee, "required_competencies", None),
        requirement_count=len(ctx["requirements"]),
        mandatory_count=len(ctx["mandatory_codes"]),
        requirements=format_requirements(ctx),
        precedence=format_precedence(),
        sources=format_sources(ctx),
        retry_feedback="",
    )
    user_template = prompt["user_template"] or "{{requirements}}\n\n{{sources}}"
    return prompt, render(user_template, **values)


def generate_onboarding_plan(employee_id: int, db: Session) -> dict:
    """
    Returns:
        {
          "model_used": str,
          "prompt_version": "onboarding_plan@v2.0",
          "raw_genai_json": dict,
          "attempts": int,
          "schema_issues": [...semantic findings...],
          "source_document_versions": [...],
          "context": <role context, for immediate validation>,
        }
    Raises GeneratorError (bad input / unusable output) or
    AllModelsFailedError (both Groq models failed).
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise GeneratorError(f"No employee found with id={employee_id}")
    if not employee.role_id:
        raise GeneratorError(f"Employee '{employee.employee_code}' has no role assigned.")

    ctx = build_role_context(employee.role_id, db, employee)
    if not ctx["requirements"]:
        raise GeneratorError(
            f"No Requirement Matrix rows found for role_id={employee.role_id}. "
            f"Add requirements for this role before generating a plan."
        )

    prompt, user_prompt = build_prompts(employee, ctx)
    run = run_structured_generation(prompt["system"], user_prompt, employee.employee_code)
    parsed = run["parsed"]

    issues = semantic_findings(
        parsed,
        role_name=ctx["role_name"],
        requirement_codes=ctx["requirement_codes"],
        active_document_codes=ctx["active_document_codes"],
        obsolete_document_codes=ctx["obsolete_document_codes"],
    )
    log_generation_complete(employee.employee_code, prompt["label"], run["model_used"], run["attempts"],
                            ctx["source_document_versions"])

    return {
        "model_used": run["model_used"],
        "prompt_version": prompt["label"],
        "raw_genai_json": parsed,
        "attempts": run["attempts"],
        "attempt_errors": run["attempt_errors"],
        "schema_issues": issues,
        "source_document_versions": ctx["source_document_versions"],
        "context": ctx,
    }
