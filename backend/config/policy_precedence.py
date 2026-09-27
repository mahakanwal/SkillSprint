"""
config/policy_precedence.py

SRS Step 34 / xxxvii -- configurable document-precedence rules.

The hierarchy lives in config/policy_precedence.json (not in code), e.g.

    0  Requirement Matrix (the approved ground truth)
    1  Latest approved Policy
    2  Department SOP / process manual
    3  Handbook / forms
    4  FAQ
    5  Informal guidance

Rules applied everywhere a conflict is resolved:
  1. An obsolete (superseded) document version never wins.
  2. Lower rank number wins.
  3. Same rank -> the most recent effective date / upload wins.
"""

import json
import os
from functools import lru_cache

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "policy_precedence.json")
UNKNOWN_RANK = 99


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def reload_rules() -> dict:
    load_rules.cache_clear()
    return load_rules()


def rank_for_doc_type(doc_type: str | None) -> int:
    rules = load_rules()
    dt = (doc_type or "").strip().lower()
    for rule in rules["rules"]:
        if dt in {t.lower() for t in rule["doc_types"]}:
            return int(rule["rank"])
    return UNKNOWN_RANK


def label_for_rank(rank: int) -> str:
    rules = load_rules()
    if rank == rules.get("requirement_matrix_rank", 0):
        return "Requirement Matrix"
    for rule in rules["rules"]:
        if int(rule["rank"]) == rank:
            return rule["label"]
    return "Unranked source"


def document_rank(doc) -> int:
    """Rank for a Document row (obsolete versions are pushed to the bottom)."""
    if doc is None:
        return UNKNOWN_RANK
    rank = rank_for_doc_type(getattr(doc, "doc_type", None))
    if load_rules().get("obsolete_versions_never_win", True) and getattr(doc, "is_active_version", True) is False:
        return UNKNOWN_RANK + 1
    return rank


def _recency_key(doc):
    ts = getattr(doc, "effective_date", None) or getattr(doc, "uploaded_at", None)
    return ts.timestamp() if ts is not None else 0.0


def governing_document(docs: list):
    """Returns the document that wins under the precedence rules."""
    candidates = [d for d in docs if d is not None]
    if not candidates:
        return None
    return sorted(candidates, key=lambda d: (document_rank(d), -_recency_key(d)))[0]


def describe_hierarchy() -> list[dict]:
    rules = load_rules()
    out = [{"rank": rules.get("requirement_matrix_rank", 0), "label": "Requirement Matrix", "doc_types": []}]
    out += sorted(rules["rules"], key=lambda r: r["rank"])
    return out
