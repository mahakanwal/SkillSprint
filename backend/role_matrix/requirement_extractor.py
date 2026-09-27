"""
role_matrix/requirement_extractor.py

SRS Step 11 / xi -- Requirement Extraction (deterministic, no GenAI).

Reads the chunks of an uploaded document and classifies every sentence:

    Must Know          "employees must understand / be aware of ..."
    Must Complete      "must complete / submit / attend / finish ..."
    Must Demonstrate   "must demonstrate / be able to / perform ..."
    Must Acknowledge   "must acknowledge / sign / accept / confirm ..."
    Recommended        "should / recommended / encouraged ..."
    Optional           "may / optional / can choose ..."
    Not Applicable     "does not apply to / not applicable / exempt ..."
    Informational      everything else (not a requirement)

Mandatory = the four "Must" classes. The output is a list of SUGGESTED
Requirement Matrix rows (with document, section and location), which an
admin reviews before adding -- extraction never writes to the matrix
by itself.
"""

import re

from python_validation.text_utils import split_sentences

_NOT_APPLICABLE = re.compile(r"\b(not applicable|does not apply|do not apply|exempt(ed)? from|excluded from)\b", re.I)
_PROHIBITION = re.compile(r"\b(must not|must never|shall not|may not|is prohibited|are prohibited|not allowed|never)\b", re.I)
_MUST = re.compile(r"\b(must|shall|required to|is required|are required|mandatory|have to|has to|needs? to|is compulsory)\b", re.I)
_RECOMMENDED = re.compile(r"\b(should|recommended|encouraged|advised|best practice|ideally)\b", re.I)
_OPTIONAL = re.compile(r"\b(optional|may choose|can choose|if they wish|at their discretion|may)\b", re.I)

_KNOW = re.compile(r"\b(know|understand|be aware|familiar|awareness|recognise|recognize|read)\b", re.I)
_COMPLETE = re.compile(r"\b(complete|completion|submit|attend|finish|log|record|register|change|update|install|escalate|report|file|enrol|enroll)\b", re.I)
_DEMONSTRATE = re.compile(r"\b(demonstrate|be able to|perform|apply|operate|handle|resolve|use the|practise|practice)\b", re.I)
_ACKNOWLEDGE = re.compile(r"\b(acknowledge|sign|accept|confirm|agree|declare|consent)\b", re.I)

MANDATORY_CLASSES = {"Must Know", "Must Complete", "Must Demonstrate", "Must Acknowledge"}


def classify_sentence(sentence: str) -> str:
    s = sentence.strip()
    if not s:
        return "Informational"
    if _NOT_APPLICABLE.search(s):
        return "Not Applicable"
    if _MUST.search(s) or _PROHIBITION.search(s):
        if _ACKNOWLEDGE.search(s):
            return "Must Acknowledge"
        if _DEMONSTRATE.search(s):
            return "Must Demonstrate"
        if _COMPLETE.search(s):
            return "Must Complete"
        return "Must Know"
    if _RECOMMENDED.search(s):
        return "Recommended"
    if _OPTIONAL.search(s):
        return "Optional"
    return "Informational"


def _competency_hint(sentence: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z\-]+", sentence)
    stop = {"all", "every", "employees", "employee", "must", "shall", "should", "the", "their", "they", "and",
            "within", "before", "after", "with", "from", "that", "this", "are", "is", "be", "to", "of", "in", "on",
            "for", "a", "an", "by", "or", "may", "not", "never", "have", "has", "been", "will"}
    keep = [w for w in words if w.lower() not in stop and len(w) > 3][:4]
    return " ".join(keep).capitalize() if keep else ""


def extract_requirements(document, chunks) -> list[dict]:
    """Returns every classified sentence of a document with its trace info."""
    out = []
    for c in chunks:
        for sentence in split_sentences(c.content or ""):
            if len(sentence) < 12:
                continue
            cls = classify_sentence(sentence)
            if cls == "Informational":
                continue
            out.append({
                "classification": cls,
                "mandatory": cls in MANDATORY_CLASSES,
                "text": sentence,
                "document_id": document.id,
                "document_code": document.document_code,
                "document_version": document.version,
                "section": c.section,
                "chunk_code": c.chunk_code,
                "location": c.page_or_location,
                "suggested_row": {
                    "policy_requirement": sentence[:255] if cls in ("Must Know", "Must Acknowledge", "Recommended", "Optional") else None,
                    "process_requirement": sentence[:255] if cls in ("Must Complete", "Must Demonstrate") else None,
                    "competency": _competency_hint(sentence)[:255] or None,
                    "mandatory": cls in MANDATORY_CLASSES,
                    "priority": "High" if cls in MANDATORY_CLASSES else ("Medium" if cls == "Recommended" else "Low"),
                    "source_document_id": document.id,
                    "source_section": (c.section or "")[:100] or None,
                },
            })
    return out


def summarize(extracted: list[dict]) -> dict:
    counts = {}
    for e in extracted:
        counts[e["classification"]] = counts.get(e["classification"], 0) + 1
    return {
        "total": len(extracted),
        "mandatory": sum(1 for e in extracted if e["mandatory"]),
        "by_class": counts,
    }
