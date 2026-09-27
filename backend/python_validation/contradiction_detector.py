"""
python_validation/contradiction_detector.py

Checks generated onboarding content against the approved sources to find
statements that CONFLICT with them (SRS Pipeline 2: "Contradictory
instructions").

Why the old version was wrong:
  It checked "does the generated item contain the word 'must'" AND "does the
  source contain 'not required' ANYWHERE" -- two unrelated sentences in
  completely different topics produced a "contradiction". Almost every plan
  contains "must"/"required", so results were noise.

How it works now (deterministic, no GenAI):
  1. Split the generated item and every source (document chunks + this
     role's Requirement Matrix rows) into sentences.
  2. Pair a generated sentence only with source sentences about the SAME
     topic (enough shared key terms, ignoring must/optional/not words).
  3. Within a same-topic pair, report a contradiction when:
       a) Rule conflict: one says required/mandatory and the other says
          optional/not required, or one allows and the other prohibits.
       b) Value conflict: both give a value with the same unit but the
          numbers differ (e.g. "every 90 days" vs "every 45 days").
  Each finding includes the exact source sentence and document code, so a
  reviewer can see both sides.
"""

import re
from typing import Dict, Iterable, List, Optional, Tuple

from config.policy_precedence import label_for_rank
from python_validation.text_utils import (
    fmt_num, normalize, numbers_with_units, plan_items, requirement_text,
    split_sentences, stem_set,
)

MIN_SHARED_TERMS = 3
MIN_TOPIC_SIMILARITY = 0.30

_PROHIBIT = re.compile(
    r"\b(must not|must never|should not|shall not|cannot|can not|may not|never|"
    r"not allowed|not permitted|prohibited|forbidden|do not|don't|is not allowed)\b"
)
_OPTIONAL = re.compile(r"\b(optional|not required|not mandatory|not necessary|no need to|is not compulsory)\b")
_REQUIRED = re.compile(r"\b(must|required|mandatory|shall|compulsory|always|need to|needs to)\b")
_ALLOWED = re.compile(r"\b(allowed|permitted|may|can)\b")


def _polarity(sentence: str) -> Optional[str]:
    s = normalize(sentence)
    if _PROHIBIT.search(s):
        return "prohibited"
    if _OPTIONAL.search(s):
        return "optional"
    if _REQUIRED.search(s):
        return "required"
    if _ALLOWED.search(s):
        return "allowed"
    return None


_CONFLICTING = {
    frozenset({"required", "optional"}),
    frozenset({"required", "prohibited"}),
    frozenset({"allowed", "prohibited"}),
}


def _topic_match(a: set, b: set) -> Tuple[bool, int, float]:
    if not a or not b:
        return False, 0, 0.0
    shared = len(a & b)
    sim = shared / min(len(a), len(b))
    return (shared >= MIN_SHARED_TERMS and sim >= MIN_TOPIC_SIMILARITY), shared, sim


def _build_source_sentences(source_text: str, source_segments, requirements) -> List[Dict]:
    sentences = []
    if source_segments:
        for seg in source_segments:
            for s in split_sentences(seg.get("text", "")):
                sentences.append({"text": s, "origin": seg.get("document_code") or "Source document",
                                  "section": seg.get("section"), "rank": seg.get("rank", 50),
                                  "doc_type": seg.get("doc_type")})
    elif source_text:
        for s in split_sentences(source_text):
            sentences.append({"text": s, "origin": "Source document", "section": None})

    for r in requirements:
        code = getattr(r, "requirement_code", "") or "Requirement"
        for field in ("policy_requirement", "process_requirement", "competency", "assessment_requirement"):
            val = getattr(r, field, None)
            if val:
                for s in split_sentences(val):
                    sentences.append({"text": s, "origin": f"Requirement Matrix {code}", "section": field, "rank": 0})
        # the mandatory flag is itself a ground-truth rule
        mandatory = getattr(r, "mandatory", None)
        topic = " ".join(str(getattr(r, f, "") or "") for f in ("policy_requirement", "process_requirement"))
        if mandatory is not None and topic.strip():
            flag = "Mandatory" if mandatory else "Optional"
            sentences.append({"text": f"Marked {flag} in the Requirement Matrix: {topic.strip()}",
                              "origin": f"Requirement Matrix {code}",
                              "section": "mandatory flag", "flag_only": True, "rank": 0})

    for s in sentences:
        s.setdefault("rank", 50)
        s["stems"] = stem_set(s["text"], drop_polarity=True)
        s["polarity"] = _polarity(s["text"])
        s["values"] = numbers_with_units(s["text"])
    return sentences


def detect_contradictions(
    generated_plan: Dict,
    source_text: str,
    requirements: Optional[Iterable] = None,
    source_segments: Optional[List[Dict]] = None,
) -> Dict:
    requirements = list(requirements or [])
    items = plan_items(generated_plan)
    total = len(items)

    source_sentences = _build_source_sentences(source_text or "", source_segments, requirements)

    if not source_sentences:
        return {
            "score": None,
            "total_items": total,
            "contradictions": [],
            "status": "insufficient_source",
            "message": (
                "No source document text or Requirement Matrix text is available for this role, "
                "so contradiction checking was skipped rather than reporting a false all-clear."
            ),
        }

    conflicts = []
    resolved = []  # conflicts with a lower-precedence source that a higher one overrules
    flagged_items = set()

    for item in items:
        raw = item["raw"]
        gen_sentences = split_sentences(item["text"])

        # A plan item explicitly marked optional while it cites a mandatory requirement
        cited = normalize(raw.get("source_requirement_code"))
        is_optional_flag = raw.get("mandatory") is False or raw.get("required") is False
        if cited and is_optional_flag:
            for r in requirements:
                if normalize(getattr(r, "requirement_code", "")) == cited and getattr(r, "mandatory", False):
                    conflicts.append({
                        "label": item["label"],
                        "generated_text": item["text"],
                        "source_text": f"{r.requirement_code} is marked Mandatory in the Requirement Matrix",
                        "source_origin": f"Requirement Matrix {r.requirement_code}",
                        "conflict_type": "Mandatory status conflict",
                        "detail": "The plan marks this item as optional, but its source requirement is mandatory.",
                    })
                    flagged_items.add(item["label"])

        for gs in gen_sentences:
            g_stems = stem_set(gs, drop_polarity=True)
            g_pol = _polarity(gs)
            g_vals = numbers_with_units(gs)
            if len(g_stems) < MIN_SHARED_TERMS:
                continue

            sentence_conflicts = []
            agree_ranks = []
            for ss in source_sentences:
                ok, shared, sim = _topic_match(g_stems, ss["stems"])
                if not ok:
                    continue

                finding = None

                # a) rule / obligation conflict
                pair = frozenset({g_pol, ss["polarity"]})
                if ss.get("flag_only") and pair != frozenset({"required", "optional"}):
                    pair = None  # the synthetic mandatory flag only conflicts with "optional"
                if g_pol and ss["polarity"] and pair in _CONFLICTING:
                    finding = (
                        "Rule conflict",
                        f"The plan says this is {g_pol}, but the source says it is {ss['polarity']}.",
                    )

                # b) value conflict (same unit, different number)
                if not finding and g_vals and ss["values"]:
                    src_by_unit = {}
                    for v, u in ss["values"]:
                        src_by_unit.setdefault(u, set()).add(v)
                    for v, u in g_vals:
                        if u in src_by_unit and v not in src_by_unit[u]:
                            src_vals = ", ".join(fmt_num(x) for x in sorted(src_by_unit[u]))
                            finding = (
                                "Value conflict",
                                f"The plan says {fmt_num(v)} {u}(s), but the source says {src_vals} {u}(s).",
                            )
                            break

                if finding:
                    sentence_conflicts.append((ss, finding))
                else:
                    same_rule = g_pol and ss["polarity"] == g_pol
                    same_value = bool(set(g_vals) & set(ss["values"]))
                    if same_rule or same_value:
                        agree_ranks.append(ss["rank"])

            # Policy precedence (config/policy_precedence.json): if a HIGHER
            # precedence source agrees with the plan, a conflicting LOWER
            # precedence source (e.g. an FAQ vs the policy) does not make the
            # plan contradictory -- the plan followed the governing source.
            best_agree = min(agree_ranks) if agree_ranks else None
            for ss, finding in sentence_conflicts:
                entry = {
                    "label": item["label"],
                    "generated_text": gs,
                    "full_item_text": item["text"],
                    "source_text": ss["text"],
                    "source_origin": ss["origin"] + (f" (section {ss['section']})" if ss.get("section") and not str(ss["origin"]).startswith("Requirement") else ""),
                    "source_rank": ss["rank"],
                    "source_precedence": label_for_rank(ss["rank"]),
                    "conflict_type": finding[0],
                    "detail": finding[1],
                    "_g": gs,
                }
                if best_agree is not None and best_agree < ss["rank"]:
                    entry["resolution"] = (
                        f"Plan follows a higher-precedence source ({label_for_rank(best_agree)}); "
                        f"this {label_for_rank(ss['rank'])} statement is overruled."
                    )
                    resolved.append(entry)
                    continue
                key = (item["label"], gs, ss["text"])
                if any((c["label"], c.get("_g"), c["source_text"]) == key for c in conflicts):
                    continue
                conflicts.append(entry)
                flagged_items.add(item["label"])

    for c in conflicts + resolved:
        c.pop("_g", None)

    score = 100.0 if total == 0 else round(((total - len(flagged_items)) / total) * 100, 2)

    return {
        "score": score,
        "total_items": total,
        "contradictions": conflicts,
        "resolved_by_precedence": resolved,
        "status": "passed" if not conflicts else "failed",
    }
