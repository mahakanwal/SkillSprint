"""
python_validation/role_relevance_checker.py

Checks whether each generated item actually belongs to the employee's role
(SRS Pipeline 2: "Role relevance" / "Task-role alignment").

Fixes vs the old version:
- A module's title and purpose were checked as two separate items, so one
  module could be counted twice (or half-flagged). Each item is now judged
  as a whole.
- It used raw substring search ("data" matched inside "database"), and
  exact word forms only. Now uses stemmed key-term overlap.
- It ignored the item's own citation. An item that cites a requirement code
  from a DIFFERENT role is now flagged as a wrong-role assignment, which is
  the strongest signal available.
- Every flagged item now includes the reason.
"""

from typing import Dict, Iterable, List, Optional

from python_validation.text_utils import normalize, plan_items, requirement_text, stem_set, stems

MIN_SHARED_TERMS = 2
MIN_RATIO = 0.20


def check_role_relevance(
    generated_plan: Dict,
    role_requirements: List,
    role_name: str = "",
    source_text: str = "",
    other_role_requirement_codes: Optional[Iterable[str]] = None,
) -> Dict:
    role_requirements = list(role_requirements or [])
    items = plan_items(generated_plan)
    total = len(items)

    role_text = " ".join(requirement_text(r) for r in role_requirements) + " " + (role_name or "") + " " + (source_text or "")
    role_stems = stem_set(role_text)
    role_codes = {normalize(getattr(r, "requirement_code", "")) for r in role_requirements}
    other_codes = {normalize(c) for c in (other_role_requirement_codes or []) if c}

    if not role_stems:
        return {
            "score": None, "total_items": total, "relevant_items": 0, "irrelevant_items": [],
            "status": "insufficient_source",
            "message": "No Requirement Matrix text is available for this role.",
        }

    irrelevant = []
    for item in items:
        raw = item["raw"]
        cited = normalize(raw.get("source_requirement_code"))

        if cited and cited in other_codes and cited not in role_codes:
            irrelevant.append({
                "label": item["label"], "text": item["text"],
                "reason": f"Cites requirement '{raw.get('source_requirement_code')}', which belongs to a different role.",
            })
            continue

        if cited and cited in role_codes:
            continue  # explicitly tied to one of this role's requirements

        terms = list(dict.fromkeys(stems(item["text"])))
        shared = [t for t in terms if t in role_stems]
        ratio = len(shared) / len(terms) if terms else 1.0
        if terms and len(shared) < MIN_SHARED_TERMS and ratio < MIN_RATIO:
            irrelevant.append({
                "label": item["label"], "text": item["text"],
                "reason": (
                    f"Not linked to any of this role's requirements and only {len(shared)} of its "
                    f"{len(terms)} key terms relate to the role's requirements."
                ),
            })

    relevant = total - len(irrelevant)
    score = 100.0 if total == 0 else round((relevant / total) * 100, 2)

    return {
        "score": score,
        "total_items": total,
        "relevant_items": relevant,
        "irrelevant_items": irrelevant,
        "status": "passed" if not irrelevant else ("warning" if score >= 80 else "failed"),
    }
