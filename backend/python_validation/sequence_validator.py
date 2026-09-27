"""
python_validation/sequence_validator.py

Validates the onboarding learning sequence (SRS: "Learning-plan
sequencing", "Prerequisite requirements").

Fixes vs the old version:
- Only five exact strings were accepted ("Day 1", "Week 1", ...). Stages
  used in your own Requirement Matrix (e.g. "Development Stage",
  "Implementation Stage") were reported as "Invalid or missing due stage"
  for every module. Stages are now parsed flexibly (Day 3, Week 2, First
  30 Days, Month 1, ...) and any stage that appears in this role's
  Requirement Matrix is accepted.
- It never compared a module's stage with the stage its own requirement
  specifies. It now does (ground truth check).
- Ordering is only checked between stages that have a known time order;
  named stages without a time meaning are not falsely reported as
  out-of-order.
"""

import re
from typing import Dict, Iterable, Optional

from python_validation.text_utils import normalize, stem_set

_NAMED_ORDER = {
    "pre-boarding": 0, "preboarding": 0, "pre boarding": 0,
    "orientation": 1, "induction": 1, "day 1": 1, "first day": 1,
    "week 1": 7, "first week": 7, "week 2": 14, "second week": 14,
}


def _stage_rank(stage: str) -> Optional[float]:
    s = normalize(stage)
    if not s:
        return None
    if s in _NAMED_ORDER:
        return _NAMED_ORDER[s]
    m = re.search(r"(?:day)\s*(\d+)", s)
    if m:
        return float(m.group(1))
    m = re.search(r"week\s*(\d+)", s)
    if m:
        return float(m.group(1)) * 7
    m = re.search(r"month\s*(\d+)", s)
    if m:
        return float(m.group(1)) * 30
    m = re.search(r"(?:first|within)\s*(\d+)\s*days?", s)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+)\s*days?", s)
    if m:
        return float(m.group(1))
    return None


_PREREQ_PATTERNS = [
    # "must first complete the 'Information Security Basics' module before being granted CRM access"
    re.compile(r"complete (?:the )?['\"“‘]?([^'\"”’.]{4,80}?)['\"”’]?(?: module| training| course)? before (?:being granted |accessing |starting |handling |working on )?([^.]{4,80})", re.I),
    # "X is a prerequisite for Y"
    re.compile(r"([^.]{4,80}?) is a (?:mandatory )?prerequisite (?:for|to|before) ([^.]{4,80})", re.I),
]


def source_prerequisites(corpus_text: str) -> list[dict]:
    """Prerequisite relationships stated in the source documents (SRS Step 26)."""
    found = []
    for rx in _PREREQ_PATTERNS:
        for m in rx.finditer(corpus_text or ""):
            before, after = m.group(1).strip(), m.group(2).strip()
            if before and after:
                found.append({"prerequisite": before, "dependent": after, "sentence": m.group(0).strip()})
    return found


def _item_text(m: dict) -> str:
    return " ".join(str(m.get(k) or "") for k in ("title", "purpose", "task_description")) + " " + \
        " ".join(m.get("learning_objectives") or []) + " " + " ".join(m.get("key_concepts") or [])


def _matches(text: str, phrase: str) -> bool:
    want = stem_set(phrase)
    if not want:
        return False
    have = stem_set(text)
    return len(want & have) / len(want) >= 0.6


def validate_sequence(generated_plan: Dict, requirements: Optional[Iterable] = None, corpus_text: str = "") -> Dict:
    requirements = list(requirements or [])
    modules = generated_plan.get("modules", []) or []

    if not modules:
        return {"score": 100, "total_modules": 0, "valid_modules": 0, "issues": [], "status": "passed"}

    matrix_stages = {normalize(getattr(r, "due_stage", "")) for r in requirements if getattr(r, "due_stage", None)}
    stage_by_req = {
        normalize(getattr(r, "requirement_code", "")): (getattr(r, "due_stage", "") or "")
        for r in requirements
    }

    issues = []
    problem_modules = set()
    last_rank = None
    last_title = None

    for index, module in enumerate(modules, 1):
        title = module.get("title") or f"Module {index}"
        label = f"Module {index}: {title}"
        stage = (module.get("due_stage") or "").strip()
        rank = _stage_rank(stage)

        if not stage:
            issues.append({"module": label, "issue": "No due stage was given for this module."})
            problem_modules.add(index)
            continue

        if rank is None and normalize(stage) not in matrix_stages:
            issues.append({
                "module": label,
                "issue": f"Due stage '{stage}' is not a recognised time stage and does not appear in this role's Requirement Matrix.",
            })
            problem_modules.add(index)

        # Ground-truth check: stage must match what its requirement says
        req_code = normalize(module.get("source_requirement_code"))
        expected = stage_by_req.get(req_code)
        if req_code and expected:
            exp_rank = _stage_rank(expected)
            same = normalize(expected) == normalize(stage) or (
                exp_rank is not None and rank is not None and exp_rank == rank
            )
            if not same:
                issues.append({
                    "module": label,
                    "issue": (
                        f"Scheduled for '{stage}', but requirement {module.get('source_requirement_code')} "
                        f"in the Requirement Matrix sets the due stage as '{expected}'."
                    ),
                })
                problem_modules.add(index)

        # Ordering: only between stages with a known time order
        if rank is not None:
            if last_rank is not None and rank < last_rank:
                issues.append({
                    "module": label,
                    "issue": f"Scheduled for '{stage}' but listed after '{last_title}', which is due later.",
                })
                problem_modules.add(index)
            else:
                last_rank = rank
                last_title = title

    # ---- SRS Step 13: "The plan must not assign every training requirement on Day 1"
    ranks = [_stage_rank(m.get("due_stage")) for m in modules]
    if len(modules) >= 3 and all(r is not None and r <= 1 for r in ranks):
        issues.append({"module": "Whole plan", "issue": "Every module is scheduled for Day 1; training must be spread across stages."})

    # ---- Step 27: advanced work before basic training
    items = [("module", m) for m in modules] + [("task", t) for t in generated_plan.get("tasks", []) or []]
    beginner_ranks = [(_stage_rank(x.get("due_stage")), x) for _, x in items if (x.get("difficulty") or "") == "Beginner"]
    beginner_ranks = [r for r, _ in beginner_ranks if r is not None]
    first_basic = min(beginner_ranks) if beginner_ranks else None
    for kind, x in items:
        if (x.get("difficulty") or "") != "Advanced":
            continue
        r = _stage_rank(x.get("due_stage"))
        if first_basic is not None and r is not None and r < first_basic:
            name = x.get("title") or x.get("task_description") or kind
            issues.append({"module": f"{kind.title()}: {name}",
                           "issue": f"Advanced {kind} is due '{x.get('due_stage')}', before any beginner training."})

    # ---- Step 27: assessment before its learning content
    module_rank_by_req = {}
    for m in modules:
        rc = normalize(m.get("source_requirement_code"))
        r = _stage_rank(m.get("due_stage"))
        if rc and r is not None:
            module_rank_by_req[rc] = min(r, module_rank_by_req.get(rc, r))
    for a in generated_plan.get("assessments", []) or []:
        rc = normalize(a.get("source_requirement_code"))
        r = _stage_rank(a.get("due_stage"))
        if rc in module_rank_by_req and r is not None and r < module_rank_by_req[rc]:
            issues.append({"module": f"Assessment: {a.get('title')}",
                           "issue": f"Assessment is due '{a.get('due_stage')}', before the module that teaches {a.get('source_requirement_code')}."})

    # ---- Step 26: declared prerequisites must come first
    position = {m.get("module_code"): i for i, m in enumerate(modules) if m.get("module_code")}
    for i, m in enumerate(modules):
        for pre in m.get("prerequisites") or []:
            if pre not in position:
                issues.append({"module": f"Module {i + 1}: {m.get('title')}", "issue": f"Missing prerequisite module '{pre}'."})
                problem_modules.add(i + 1)
                continue
            pre_mod = modules[position[pre]]
            pr, mr = _stage_rank(pre_mod.get("due_stage")), _stage_rank(m.get("due_stage"))
            if position[pre] > i or (pr is not None and mr is not None and pr > mr):
                issues.append({"module": f"Module {i + 1}: {m.get('title')}",
                               "issue": f"Prerequisite '{pre}' ({pre_mod.get('title')}) is scheduled after this module."})
                problem_modules.add(i + 1)

    # ---- Step 26: prerequisites stated in the SOURCE documents
    all_items = modules + (generated_plan.get("tasks", []) or [])
    for rel in source_prerequisites(corpus_text):
        pre_idx = next((i for i, m in enumerate(all_items) if _matches(_item_text(m), rel["prerequisite"])), None)
        dep_idx = next((i for i, m in enumerate(all_items) if _matches(_item_text(m), rel["dependent"])), None)
        if dep_idx is None:
            continue
        dep = all_items[dep_idx]
        dep_name = dep.get("title") or dep.get("task_description")
        if pre_idx is None:
            issues.append({"module": dep_name, "issue": f"Missing prerequisite: the source says to complete '{rel['prerequisite']}' first."})
            continue
        pre = all_items[pre_idx]
        pr, dr = _stage_rank(pre.get("due_stage")), _stage_rank(dep.get("due_stage"))
        if pr is not None and dr is not None and pr > dr:
            issues.append({"module": dep_name,
                           "issue": f"'{pre.get('title') or pre.get('task_description')}' must come first (source: \"{rel['sentence'][:120]}\")."})

    valid = len(modules) - len(problem_modules)
    score = round((valid / len(modules)) * 100, 2)
    if issues and score == 100:
        score = round(max(0.0, 100 - 10 * len(issues)), 2)

    return {
        "score": score,
        "total_modules": len(modules),
        "valid_modules": valid,
        "issues": issues,
        "status": "passed" if not issues else ("warning" if score >= 80 else "failed"),
    }
