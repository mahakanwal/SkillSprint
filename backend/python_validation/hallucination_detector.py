"""
python_validation/hallucination_detector.py

Detects generated content that is NOT supported by the approved ground
truth (SRS Pipeline 2: "Unsupported generated requirements").

Why the old version flagged almost everything as "unsupported":

1. WRONG GROUND TRUTH. It compared the plan only against the text of the
   uploaded documents. The GenAI prompt, however, grounds the plan on the
   Requirement Matrix rows AND the document chunks. When the documents are
   short (e.g. CMS-001.docx is a single description line), every module
   built from the matrix's policy / process / competency text looked
   "unsupported". The ground-truth corpus is now: linked document text +
   this role's Requirement Matrix text.

2. EXACT-WORD MATCHING. "migration" vs "migrations" vs "migrate" counted as
   different words, so normal paraphrasing failed. Words are now stemmed.

3. NO EXPLANATION. A flagged item only showed a percentage. Each flagged
   item now carries concrete reasons: which specific numbers/values were
   invented, which cited codes don't exist, and which key terms were not
   found anywhere in the sources.

An item is flagged as unsupported when ANY of these is true:
  - it states a specific value (e.g. "within 48 hours", "5 attempts") that
    does not appear anywhere in the sources  -> fabricated detail
  - it cites a requirement code that does not belong to this role, or a
    document code that isn't linked / doesn't exist -> invalid citation
  - less than MIN_OVERLAP of its key terms appear in the sources
    -> topic not grounded
"""

from typing import Dict, Iterable, List, Optional

from python_validation.text_utils import (
    fmt_num, normalize, numbers_with_units, plan_items, requirement_text,
    stem_set, stems,
)

MIN_OVERLAP = 0.30          # below this share of key terms found -> unsupported
MIN_TERMS_FOR_RATIO = 3     # items with fewer key terms are judged on citations/values only


def detect_hallucinations(
    generated_plan: Dict,
    source_text: str,
    requirements: Optional[Iterable] = None,
    known_document_codes: Optional[Iterable[str]] = None,
    obsolete_document_codes: Optional[Iterable[str]] = None,
) -> Dict:
    requirements = list(requirements or [])
    doc_text = normalize(source_text)
    req_text = normalize(" ".join(requirement_text(r) for r in requirements))
    role_names = " ".join(
        str(getattr(getattr(r, "role", None), "role_name", "") or "") for r in requirements
    )
    corpus = f"{doc_text} {req_text} {normalize(role_names)}".strip()

    items = plan_items(generated_plan)
    total = len(items)

    if not corpus:
        return {
            "score": None,
            "total_items": total,
            "unsupported_items": [],
            "status": "insufficient_source",
            "message": (
                "No source document text and no Requirement Matrix text is available "
                "for this role, so grounding could not be checked."
            ),
        }

    corpus_stems = stem_set(corpus)
    corpus_values = {(v, u) for v, u in numbers_with_units(corpus)}

    role_req_codes = {
        normalize(getattr(r, "requirement_code", "")) for r in requirements
        if getattr(r, "requirement_code", None)
    }
    known_docs = {normalize(c) for c in (known_document_codes or []) if c}
    obsolete_docs = {normalize(c) for c in (obsolete_document_codes or []) if c}

    unsupported = []
    for item in items:
        reasons = []
        raw = item["raw"]

        # 1) Invented specific values (the most reliable hallucination signal)
        fabricated = [
            f"{fmt_num(v)} {u}{'' if v == 1 or u == 'percent' else 's'}"
            for v, u in numbers_with_units(item["text"])
            if (v, u) not in corpus_values
        ]
        if fabricated:
            reasons.append(
                "States specific value(s) not found in any source: " + ", ".join(sorted(set(fabricated)))
            )

        # 2) Citations that don't exist for this role
        cited_req = normalize(raw.get("source_requirement_code"))
        if cited_req and role_req_codes and cited_req not in role_req_codes:
            reasons.append(
                f"Cites requirement '{raw.get('source_requirement_code')}', which is not in this role's Requirement Matrix"
            )
        cited_doc = normalize(raw.get("source_document_code"))
        if cited_doc and cited_doc in obsolete_docs:
            reasons.append(
                f"Cites document '{raw.get('source_document_code')}', which is an obsolete (superseded) version"
            )
        elif cited_doc and known_docs and cited_doc not in known_docs:
            reasons.append(
                f"Cites document '{raw.get('source_document_code')}', which is not linked to this role"
            )

        # 3) Topic grounding by stemmed key-term overlap
        item_terms = stems(item["text"])
        unique_terms = list(dict.fromkeys(item_terms))
        matched = [t for t in unique_terms if t in corpus_stems]
        ratio = (len(matched) / len(unique_terms)) if unique_terms else 1.0
        if len(unique_terms) >= MIN_TERMS_FOR_RATIO and ratio < MIN_OVERLAP:
            reasons.append(
                f"Only {round(ratio * 100)}% of its key terms appear in the source documents or Requirement Matrix"
            )

        if reasons:
            unmatched_words = []
            for w in item["text"].split():
                clean = "".join(ch for ch in w.lower() if ch.isalnum())
                if clean and stems(clean) and stems(clean)[0] not in corpus_stems and clean not in unmatched_words:
                    unmatched_words.append(clean)
            unsupported.append({
                "label": item["label"],
                "section": item["section"],
                "text": item["text"],
                "overlap_ratio": round(ratio, 2),
                "reasons": reasons,
                "terms_not_in_source": unmatched_words[:12],
                "source_requirement_code": raw.get("source_requirement_code"),
                "source_document_code": raw.get("source_document_code"),
            })

    score = 100.0 if total == 0 else round(((total - len(unsupported)) / total) * 100, 2)

    result = {
        "score": score,
        "total_items": total,
        "unsupported_items": unsupported,
        "status": "passed" if not unsupported else ("warning" if score >= 80 else "failed"),
    }
    if len(doc_text) < 500:
        result["message"] = (
            "The linked source documents contain very little text "
            f"({len(doc_text)} characters), so grounding relied mostly on the Requirement Matrix. "
            "Upload fuller policy/SOP documents for stronger verification."
        )
    return result
