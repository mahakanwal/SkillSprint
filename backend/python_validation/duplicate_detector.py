"""
python_validation/duplicate_detector.py

Detects duplicate modules, checklist items, tasks and quiz questions
(SRS Pipeline 2: "Duplicate learning content").

Previously only exact-text duplicates were caught; "Review the CMS backup
policy" and "Review CMS backup policies." counted as different. Near
duplicates (same key terms after stemming) are now caught too, and each
finding shows which earlier item it repeats.

Output shape is unchanged: duplicates = {section: [text, ...]}.
"""

from typing import Dict, List

from python_validation.text_utils import stem_set

NEAR_DUPLICATE_SIMILARITY = 0.85


def _similarity(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_duplicates(items: List[str]) -> List[str]:
    seen = []  # (original_text, normalized, stems)
    duplicates = []
    for item in items:
        text = (item or "").strip()
        if not text:
            continue
        norm = " ".join(text.lower().replace(".", "").split())
        st = stem_set(text)
        match = None
        for orig, n, s in seen:
            if norm == n or (len(st) >= 3 and _similarity(st, s) >= NEAR_DUPLICATE_SIMILARITY):
                match = orig
                break
        if match is not None:
            duplicates.append(text if match.strip().lower() == text.lower() else f"{text}  (repeats: \"{match}\")")
        else:
            seen.append((text, norm, st))
    return duplicates


def detect_duplicates(generated_plan: Dict) -> Dict:
    sections = {
        "modules": [m.get("title", "") for m in generated_plan.get("modules", []) or []],
        "checklist": [c.get("activity", "") for c in generated_plan.get("checklist", []) or []],
        "tasks": [t.get("task_description", "") for t in generated_plan.get("tasks", []) or []],
        "quiz": [q.get("question_text", "") for q in generated_plan.get("quiz", []) or []],
    }

    results = {}
    total = 0
    count = 0
    for section, items in sections.items():
        total += len(items)
        dups = find_duplicates(items)
        count += len(dups)
        results[section] = dups

    score = 100 if total == 0 else round(((total - count) / total) * 100, 2)
    return {
        "score": score,
        "total_items": total,
        "duplicate_count": count,
        "duplicates": results,
        "status": "passed" if count == 0 else ("warning" if score >= 80 else "failed"),
    }
