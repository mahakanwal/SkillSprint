"""
python_validation/text_utils.py

Shared, dependency-free text helpers for the Python Ground-Truth Validation
pipeline (Pipeline 2). No GenAI is used anywhere in here -- everything is
deterministic tokenizing, light stemming, sentence splitting, and number
extraction, so results are reproducible and explainable.
"""

import re
from typing import Dict, List, Set, Tuple

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "to", "of", "in", "on", "for", "with", "this", "that",
    "these", "those", "will", "it", "its", "as", "at", "by", "from", "into",
    "your", "their", "you", "they", "them", "we", "our", "us", "he", "she",
    "his", "her", "when", "how", "what", "which", "who", "whom", "why",
    "where", "if", "then", "than", "so", "do", "does", "did", "done", "has",
    "have", "had", "having", "about", "such", "each", "any", "all", "both",
    "some", "more", "most", "other", "also", "only", "own", "same", "too",
    "very", "just", "over", "under", "again", "there", "here", "out", "up",
    "down", "off", "through", "during", "before", "after", "above", "below",
    "between", "while", "within", "without", "via", "per", "etc", "e", "g",
    "ie", "eg", "able", "use", "using", "used", "make", "making", "made",
    "get", "getting", "ensure", "ensuring", "understand", "understanding",
    "learn", "learning", "know", "knowledge", "new", "employee", "employees",
    "role", "team", "company", "work", "working", "basic", "basics",
    "overview", "introduction", "key", "including", "include", "includes",
    "related", "relevant", "appropriate", "properly", "proper", "effectively",
    "effective", "explain", "describe", "identify", "demonstrate", "apply",
    "complete", "completed", "completion", "review", "reviewing", "module",
    "task", "quiz", "question", "following", "correct", "answer", "true",
    "false", "which", "would", "could", "should", "must", "can", "may",
    "shall", "need", "needs", "required", "requirement", "requirements",
}

# Words that carry obligation / permission meaning. They are excluded when
# measuring TOPIC similarity (two sentences about the same topic can differ
# only in these words -- that's exactly what a contradiction looks like).
POLARITY_WORDS = {
    "must", "required", "require", "requires", "mandatory", "shall",
    "always", "never", "not", "no", "optional", "prohibited", "forbidden",
    "allowed", "permitted", "may", "can", "cannot", "should", "need",
    "needs", "recommended", "necessary", "don", "doesn", "isn", "aren",
}

_SUFFIXES = (
    "ations", "ation", "itions", "ition", "ments", "ment", "ness", "ities",
    "ity", "ings", "ing", "ies", "ied", "ers", "er", "ed", "es", "ly", "s",
)


def normalize(text) -> str:
    if not text:
        return ""
    return str(text).lower().strip()


def stem(word: str) -> str:
    """
    Very light suffix stripper (Porter-lite). Good enough to treat
    "migrations"/"migrate"/"migrating" or "security"/"secure" as the same
    root, which is what makes paraphrased GenAI output match its source.
    """
    w = word.lower()
    if len(w) <= 4:
        return w
    if w.endswith(("ies", "ied")) and len(w) > 5:
        return w[:-3] + "y"
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


def tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", normalize(text))


def content_words(text: str, drop_polarity: bool = False) -> List[str]:
    out = []
    for w in tokens(text):
        if len(w) < 3 or w in STOPWORDS or w.isdigit():
            continue
        if drop_polarity and w in POLARITY_WORDS:
            continue
        out.append(w)
    return out


def stems(text: str, drop_polarity: bool = False) -> List[str]:
    return [stem(w) for w in content_words(text, drop_polarity=drop_polarity)]


def stem_set(text: str, drop_polarity: bool = False) -> Set[str]:
    return set(stems(text, drop_polarity=drop_polarity))


def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?;])\s+|\n+|\s+\|\s+", str(text))
    return [p.strip(" -•\t") for p in parts if p and len(p.strip()) > 3]


_UNIT_MAP = {
    "day": "day", "days": "day", "business day": "day", "business days": "day",
    "working day": "day", "working days": "day",
    "week": "week", "weeks": "week", "month": "month", "months": "month",
    "year": "year", "years": "year", "hour": "hour", "hours": "hour",
    "hrs": "hour", "hr": "hour", "minute": "minute", "minutes": "minute",
    "mins": "minute", "min": "minute", "character": "character",
    "characters": "character", "chars": "character", "%": "percent",
    "percent": "percent", "times": "times", "attempts": "attempt",
    "attempt": "attempt", "digits": "digit", "digit": "digit",
}

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
    "forty-five": 45, "sixty": 60, "ninety": 90,
}

_NUM_UNIT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?|" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) + r")"
    r"\s*(%|percent|(?:business |working )?days?|weeks?|months?|years?|hours?|hrs?|"
    r"minutes?|mins?|characters?|chars|times|attempts?|digits?)\b",
    re.IGNORECASE,
)


def numbers_with_units(text: str) -> List[Tuple[float, str]]:
    """Returns [(value, unit)] e.g. 'every 90 days' -> [(90.0, 'day')]."""
    out = []
    for raw_num, raw_unit in _NUM_UNIT_RE.findall(normalize(text)):
        num = _WORD_NUMBERS.get(raw_num.lower())
        if num is None:
            try:
                num = float(raw_num)
            except ValueError:
                continue
        unit = _UNIT_MAP.get(raw_unit.lower().strip())
        if unit:
            out.append((float(num), unit))
    return out


def fmt_num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def requirement_text(req) -> str:
    """All human-readable ground-truth text on one Requirement Matrix row."""
    fields = (
        "policy_requirement", "process_requirement", "competency",
        "assessment_requirement", "source_section", "due_stage",
    )
    return " ".join(str(getattr(req, f, "") or "") for f in fields)


def _join(parts) -> str:
    """Joins text fields as separate sentences (so they aren't read as one run-on sentence)."""
    out = []
    for p in parts:
        p = str(p or "").strip()
        if p:
            out.append(p if p[-1] in ".!?:;" else p + ".")
    return " ".join(out)


def plan_items(plan: Dict) -> List[Dict]:
    """
    Flattens a GenAI plan into one entry per generated item, combining all
    of that item's text fields (so a module is judged as a whole, the way a
    human reviewer would read it). Each entry keeps a readable label and
    the item's own citations.
    """
    items = []

    for i, m in enumerate(plan.get("modules", []) or [], 1):
        title = m.get("title") or f"Module {i}"
        parts = [
            m.get("title", ""), m.get("purpose", ""),
            *(m.get("learning_objectives", []) or []),
            ", ".join(m.get("key_concepts", []) or []),
        ]
        items.append({"section": "modules", "index": i, "label": f"Module {i}: {title}",
                      "text": _join(parts), "raw": m})

    for i, c in enumerate(plan.get("checklist", []) or [], 1):
        items.append({"section": "checklist", "index": i, "label": f"Checklist item {i}",
                      "text": (c.get("activity") or "").strip(), "raw": c})

    for i, t in enumerate(plan.get("tasks", []) or [], 1):
        parts = [t.get("task_description", ""), t.get("scenario", ""), t.get("expected_outcome", "")]
        items.append({"section": "tasks", "index": i, "label": f"Task {i}",
                      "text": _join(parts), "raw": t})

    for i, q in enumerate(plan.get("quiz", []) or [], 1):
        ans = q.get("correct_answer", "")
        ans = "; ".join(str(a) for a in ans) if isinstance(ans, list) else ans
        parts = [q.get("question_text", ""), ans, q.get("explanation", "")]
        items.append({"section": "quiz", "index": i, "label": f"Quiz question {i}",
                      "text": _join(parts), "raw": q})

    for i, a in enumerate(plan.get("assessments", []) or [], 1):
        parts = [a.get("title", ""), a.get("description", "")]
        items.append({"section": "assessments", "index": i, "label": f"Assessment {i}: {a.get('title') or ''}".strip(),
                      "text": _join(parts), "raw": a})

    return [it for it in items if it["text"]]
