"""
python_validation/coverage_checker.py

SRS Steps 28-29 / xxxii-xxxiii -- Mandatory Requirement Coverage.

    Coverage Score = Covered Mandatory Requirements / Total Mandatory Requirements x 100

A requirement counts as covered when the generated plan either
  (a) cites its Requirement ID on at least one item (structured match), or
  (b) contains at least half (and at least two) of its distinctive key
      terms (stemmed) in the plan text -- for plans where the model forgot
      the citation.
Optional requirements are reported separately and never lower the score.

Also returns required / covered / missing / duplicate requirement lists
(Step 28: "Required, Covered, Missing, Unsupported, Duplicate requirements").
"""

from collections import Counter
from typing import Dict, List

from python_validation.text_utils import normalize, stem_set

MIN_KEYWORD_MATCHES = 2
MIN_KEYWORD_SHARE = 0.5  # without an ID citation, half the requirement's key terms must appear


def extract_plan_text(plan: Dict) -> str:
    content = []
    for module in plan.get("modules", []) or []:
        content += [module.get("title", ""), module.get("purpose", "")]
        content += module.get("learning_objectives", []) or []
        content += module.get("key_concepts", []) or []
    for item in plan.get("checklist", []) or []:
        content.append(item.get("activity", ""))
    for task in plan.get("tasks", []) or []:
        content += [task.get("task_description", ""), task.get("expected_outcome", "")]
    for quiz in plan.get("quiz", []) or []:
        content.append(quiz.get("question_text", ""))
    for a in plan.get("assessments", []) or []:
        content += [a.get("title", ""), a.get("description", "") or ""]
    return normalize(" ".join(str(c) for c in content if c))


def _cited_codes(plan: Dict) -> Counter:
    counts = Counter()
    for section in ("modules", "checklist", "tasks", "quiz", "assessments"):
        for item in plan.get(section, []) or []:
            code = normalize(item.get("source_requirement_code"))
            if code:
                counts[(section, code)] += 1
    return counts


def check_coverage(requirements: List, generated_plan: Dict) -> Dict:
    if not requirements:
        return {"score": 0, "covered": 0, "total": 0, "requirements": [],
                "mandatory_total": 0, "optional_total": 0, "missing": [], "duplicates": []}

    plan_text = extract_plan_text(generated_plan)
    plan_stems = stem_set(plan_text)
    cited = _cited_codes(generated_plan)
    cited_codes = {code for (_, code) in cited}

    details = []
    for req in requirements:
        code_raw = getattr(req, "requirement_code", "") or ""
        code = normalize(code_raw)
        mandatory = bool(getattr(req, "mandatory", True))

        by_id = code in cited_codes
        req_terms = stem_set(" ".join(
            str(getattr(req, f, "") or "") for f in ("policy_requirement", "process_requirement", "competency")
        ))
        keyword_hits = len(req_terms & plan_stems)
        by_keywords = bool(req_terms) and keyword_hits >= MIN_KEYWORD_MATCHES and \
            keyword_hits / len(req_terms) >= MIN_KEYWORD_SHARE
        covered = by_id or by_keywords

        details.append({
            "requirement_code": code,
            "requirement_code_display": code_raw,
            "mandatory": mandatory,
            "covered": covered,
            "matched_by": "requirement_id" if by_id else ("keywords" if by_keywords else None),
            "keyword_hits": keyword_hits,
            "cited_in_modules": cited.get(("modules", code), 0),
        })

    mandatory = [d for d in details if d["mandatory"]]
    optional = [d for d in details if not d["mandatory"]]
    scored = mandatory or details  # a role with no mandatory rows is scored on all rows
    covered_count = sum(1 for d in scored if d["covered"])
    score = round((covered_count / len(scored)) * 100, 2)

    # Step 28 "duplicate requirements": the same requirement taught by more
    # than one MODULE (checklist/tasks/quiz citing it is expected).
    duplicates = [
        {"requirement_code": code, "modules": n}
        for (section, code), n in cited.items() if section == "modules" and n > 1
    ]

    return {
        "score": score,
        "covered": covered_count,
        "total": len(scored),
        "mandatory_total": len(mandatory),
        "mandatory_covered": sum(1 for d in mandatory if d["covered"]),
        "optional_total": len(optional),
        "optional_covered": sum(1 for d in optional if d["covered"]),
        "missing": [d["requirement_code_display"] for d in scored if not d["covered"]],
        "duplicates": duplicates,
        "requirements": details,
    }
