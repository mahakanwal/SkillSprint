"""
services/consistency_service.py

SRS Steps 44-45 / xl-xli -- GenAI Consistency Check and Consistency Score.

Runs the SAME structured generation task N times with the same prompt
version, model settings and sources (controlled parameters), then compares
the STRUCTURED business content of the runs -- never the sentence wording:

    mandatory_requirements  requirement IDs covered by mandatory modules
    sources                 document IDs cited
    module_categories       requirement IDs each module is built on
    assessment_topics       requirement IDs tested by quiz + assessments

Score = mean pairwise Jaccard similarity across the four dimensions x 100.
A dimension below 70 % is a "major difference" and is flagged.
Runs are not saved as plans (they only measure the model's stability).
"""

from itertools import combinations

from sqlalchemy.orm import Session

from config.settings import settings
from database.models import ConsistencyRun, Employee
from genai_pipeline.context_builder import build_role_context
from genai_pipeline.generator import GeneratorError, build_prompts, run_structured_generation
from python_validation.text_utils import normalize

MAJOR_DIFFERENCE = 0.70
DIMENSIONS = ("mandatory_requirements", "sources", "module_categories", "assessment_topics")


class ConsistencyError(Exception):
    pass


def signature(plan: dict) -> dict:
    modules = plan.get("modules") or []
    return {
        "mandatory_requirements": sorted({normalize(m.get("source_requirement_code")) for m in modules
                                          if m.get("mandatory") and m.get("source_requirement_code")}),
        "sources": sorted({normalize(i.get("source_document_code"))
                           for s in ("modules", "checklist", "quiz") for i in plan.get(s) or []
                           if i.get("source_document_code")}),
        "module_categories": sorted({normalize(m.get("source_requirement_code")) for m in modules
                                     if m.get("source_requirement_code")}),
        "assessment_topics": sorted({normalize(i.get("source_requirement_code"))
                                     for s in ("quiz", "assessments") for i in plan.get(s) or []
                                     if i.get("source_requirement_code")}),
    }


def _jaccard(a, b) -> float:
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def compare_signatures(sigs: list[dict]) -> dict:
    per_dim = {}
    differences = []
    for dim in DIMENSIONS:
        pairs = list(combinations(range(len(sigs)), 2))
        scores = [_jaccard(sigs[i][dim], sigs[j][dim]) for i, j in pairs] or [1.0]
        per_dim[dim] = round(sum(scores) / len(scores) * 100, 2)
        if min(scores) < MAJOR_DIFFERENCE:
            union = set().union(*[set(s[dim]) for s in sigs])
            common = set.intersection(*[set(s[dim]) for s in sigs]) if sigs else set()
            differences.append({"dimension": dim, "score": per_dim[dim],
                                "only_in_some_runs": sorted(union - common),
                                "in_every_run": sorted(common)})
    score = round(sum(per_dim.values()) / len(per_dim), 2)
    return {"score": score, "per_dimension": per_dim, "major_differences": differences}


def run_consistency_check(employee_id: int, runs: int, db: Session) -> dict:
    runs = max(2, min(int(runs or 2), 5))
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.role_id:
        raise ConsistencyError("Employee not found or has no role.")
    ctx = build_role_context(employee.role_id, db, employee)
    if not ctx["requirements"]:
        raise ConsistencyError("This role has no Requirement Matrix rows.")

    prompt, user_prompt = build_prompts(employee, ctx)
    sigs, models = [], set()
    for _ in range(runs):
        try:
            run = run_structured_generation(prompt["system"], user_prompt, employee.employee_code)
        except GeneratorError as e:
            raise ConsistencyError(f"A generation run failed: {e}")
        sigs.append(signature(run["parsed"]))
        models.add(run["model_used"])

    comparison = compare_signatures(sigs)
    record = ConsistencyRun(
        employee_id=employee_id, runs=runs, score=comparison["score"],
        details={"signatures": sigs, **comparison, "temperature": settings.GROQ_TEMPERATURE},
        model_used=", ".join(sorted(models)), prompt_version=prompt["label"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "employee_id": employee_id, "runs": runs, "score": comparison["score"],
            "per_dimension": comparison["per_dimension"], "major_differences": comparison["major_differences"],
            "signatures": sigs, "model_used": record.model_used, "prompt_version": record.prompt_version,
            "temperature": settings.GROQ_TEMPERATURE, "created_at": record.created_at}
