"""
python_validation/consistency_checker.py

SRS "Requirement Consistency Score" (Section 1.2, Table 1) -- compares the
STRUCTURED attributes of every generated item with the Python ground truth
(the Requirement Matrix row it cites), field by field:

    Requirement ID  -> must exist for this role
    Source Document -> must equal the matrix's (active) source document
    Source Section  -> must equal the matrix's source section
    Mandatory       -> module.mandatory / checklist.required must equal matrix
    Due Stage       -> must equal the matrix's due stage

Also keeps the old completeness check (required fields present), because
an item with missing fields cannot be consistent.

Score = matching fields / compared fields x 100.
The per-field rows are exactly what the GenAI-vs-Python comparison report
shows (Validation Field | GenAI Output | Python Ground Truth | Result).
"""

from typing import Dict, List, Optional

from python_validation.text_utils import normalize

REQUIRED_FIELDS = {
    "modules": ["module_code", "title", "mandatory", "due_stage"],
    "checklist": ["activity", "required"],
    "tasks": ["task_description", "expected_outcome"],
    "quiz": ["question_text", "correct_answer"],
}


def _norm_section(v) -> str:
    s = normalize(v).replace("section", "").replace("§", "").strip(" .:")
    return s


def check_consistency(
    generated_plan: Dict,
    requirements: Optional[List] = None,
    requirement_doc_code: Optional[Dict[str, str]] = None,
) -> Dict:
    by_code = {normalize(getattr(r, "requirement_code", "")): r for r in (requirements or [])}
    doc_for = {normalize(k): v for k, v in (requirement_doc_code or {}).items()}

    compared = matched = 0
    issues = []
    comparisons = []

    # 1) completeness
    for section, fields in REQUIRED_FIELDS.items():
        for index, item in enumerate(generated_plan.get(section, []) or []):
            for field in fields:
                compared += 1
                if item.get(field) not in (None, "", []):
                    matched += 1
                else:
                    issues.append({"section": section, "index": index + 1, "field": field,
                                   "issue": f"missing '{field}'"})

    # 2) field-level comparison against the cited Requirement Matrix row
    if by_code:
        for section in ("modules", "checklist", "tasks", "quiz", "assessments"):
            for index, item in enumerate(generated_plan.get(section, []) or []):
                code = normalize(item.get("source_requirement_code"))
                if not code:
                    continue
                req = by_code.get(code)
                label = f"{section}[{index + 1}]"
                rows = []
                if req is None:
                    rows.append(("Requirement ID", item.get("source_requirement_code"), "not in this role's matrix", False))
                else:
                    rows.append(("Requirement ID", item.get("source_requirement_code"), req.requirement_code, True))
                    expected_doc = doc_for.get(code)
                    if expected_doc and "source_document_code" in item:
                        got = item.get("source_document_code")
                        rows.append(("Source Document", got, expected_doc, normalize(got) == normalize(expected_doc)))
                    if req.source_section and item.get("source_section"):
                        rows.append(("Source Section", item.get("source_section"), req.source_section,
                                     _norm_section(item.get("source_section")) == _norm_section(req.source_section)))
                    flag = item.get("mandatory") if section == "modules" else (item.get("required") if section == "checklist" else None)
                    if flag is not None and req.mandatory is not None:
                        rows.append(("Mandatory", "Yes" if flag else "No", "Yes" if req.mandatory else "No",
                                     bool(flag) == bool(req.mandatory)))
                    if section in ("modules", "checklist") and req.due_stage and item.get("due_stage"):
                        rows.append(("Due Stage", item.get("due_stage"), req.due_stage,
                                     normalize(item.get("due_stage")) == normalize(req.due_stage)))

                for field, got, expected, ok in rows:
                    compared += 1
                    matched += int(ok)
                    comparisons.append({"item": label, "requirement_code": item.get("source_requirement_code"),
                                        "field": field, "genai": got, "python": expected,
                                        "result": "Match" if ok else "Mismatch"})
                    if not ok:
                        issues.append({"section": section, "index": index + 1, "field": field,
                                       "issue": f"{field}: GenAI '{got}' vs ground truth '{expected}'"})

    score = round((matched / compared) * 100, 2) if compared else 0
    return {
        "score": score,
        "passed": matched,
        "total": compared,
        "issues": issues,
        "comparisons": comparisons,
    }
