"""
python_validation/traceability_checker.py

SRS Step 30 / xxxiv -- Source Traceability Score.

"How much generated content has VALID source references."

An item is traced only when its citation is real:
  * source_requirement_code belongs to this role's Requirement Matrix, AND/OR
  * source_document_code is one of the ACTIVE source documents for this role.
A citation to an obsolete version, an unknown document or another role's
requirement does NOT count (the old version counted any non-empty string).

Mandatory learning content (mandatory modules + required checklist items)
is reported separately because the SRS targets 100 % for it.
"""

from typing import Dict, Iterable, Optional

from python_validation.text_utils import normalize

SECTIONS = ("modules", "checklist", "tasks", "quiz", "assessments")


def check_traceability(
    generated_plan: Dict,
    requirement_codes: Optional[Iterable[str]] = None,
    active_document_codes: Optional[Iterable[str]] = None,
    obsolete_document_codes: Optional[Iterable[str]] = None,
) -> Dict:
    req = {normalize(c) for c in (requirement_codes or []) if c}
    active = {normalize(c) for c in (active_document_codes or []) if c}
    obsolete = {normalize(c) for c in (obsolete_document_codes or []) if c}
    strict = bool(req or active)

    total = traced = 0
    mandatory_total = mandatory_traced = 0
    details = []

    for section in SECTIONS:
        for index, item in enumerate(generated_plan.get(section, []) or []):
            total += 1
            rc = normalize(item.get("source_requirement_code"))
            dc = normalize(item.get("source_document_code"))
            problems = []

            if strict:
                req_ok = bool(rc) and (not req or rc in req)
                doc_ok = bool(dc) and dc in active
                if rc and req and rc not in req:
                    problems.append("requirement code not in this role's matrix")
                if dc and dc in obsolete:
                    problems.append("cites an obsolete document version")
                elif dc and active and dc not in active:
                    problems.append("document code not among this role's sources")
                is_traced = req_ok or doc_ok
            else:
                is_traced = bool(rc or dc)

            if not rc and not dc:
                problems.append("no source reference")
            if is_traced:
                traced += 1

            is_mandatory = (section == "modules" and item.get("mandatory", True)) or (
                section == "checklist" and item.get("required", True))
            if is_mandatory:
                mandatory_total += 1
                mandatory_traced += int(is_traced)

            details.append({
                "section": section,
                "index": index + 1,
                "traced": is_traced,
                "mandatory": bool(is_mandatory),
                "requirement": item.get("source_requirement_code"),
                "document": item.get("source_document_code"),
                "source_section": item.get("source_section"),
                "problems": problems,
            })

    score = round((traced / total) * 100, 2) if total else 0
    mandatory_score = round((mandatory_traced / mandatory_total) * 100, 2) if mandatory_total else score

    return {
        "score": score,
        "traced": traced,
        "total": total,
        "mandatory_score": mandatory_score,
        "mandatory_traced": mandatory_traced,
        "mandatory_total": mandatory_total,
        "untraced": [d for d in details if not d["traced"]],
        "details": details,
    }
