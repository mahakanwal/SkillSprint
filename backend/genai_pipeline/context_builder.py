"""
genai_pipeline/context_builder.py

Builds the approved "ground truth" context for one role. Used by BOTH
pipelines so they look at exactly the same sources:

  - Pipeline 1 (generator.py) sends it to the GenAI model.
  - Pipeline 2 (services/validation_service.py) validates against it.

What it guarantees:
  * Obsolete document versions are never used. If a Requirement Matrix row
    still points at v1 of a document whose v2 is now active, the active
    version of the same family is used instead (SRS Step 8, Challenge 4)
    and the stale link is reported.
  * Every chunk carries document code, version, section, chunk id and
    location (SRS Steps 6-7, Source Traceability Challenge).
  * Chunks carry their precedence rank (config/policy_precedence.json).
  * Sentences flagged by the prompt-injection guard are redacted before
    they can reach the model (SRS Step 42).
"""

from sqlalchemy.orm import Session

from config.policy_precedence import document_rank, label_for_rank, describe_hierarchy
from config.settings import settings
from database.models import Document, DocumentChunk, Employee, RequirementMatrix
from security.prompt_injection_guard import redact, wrap_as_data


def resolve_active_document(doc: Document, db: Session) -> Document:
    """Returns the active version of doc's family (or doc itself)."""
    if doc is None or doc.is_active_version or not doc.family_code:
        return doc
    active = (
        db.query(Document)
        .filter(Document.family_code == doc.family_code, Document.is_active_version == True)  # noqa: E712
        .first()
    )
    return active or doc


def build_role_context(role_id: int, db: Session, employee: Employee | None = None) -> dict:
    requirements = (
        db.query(RequirementMatrix)
        .filter(RequirementMatrix.role_id == role_id)
        .order_by(RequirementMatrix.requirement_code)
        .all()
    )

    linked_ids = {r.source_document_id for r in requirements if r.source_document_id}
    linked_docs = {d.id: d for d in db.query(Document).filter(Document.id.in_(linked_ids)).all()} if linked_ids else {}

    stale_links = []
    active_by_linked_id = {}
    for doc_id, doc in linked_docs.items():
        active = resolve_active_document(doc, db)
        active_by_linked_id[doc_id] = active
        if active is not None and active.id != doc.id:
            stale_links.append({
                "requirement_codes": [r.requirement_code for r in requirements if r.source_document_id == doc_id],
                "linked_document_code": doc.document_code,
                "linked_version": doc.version,
                "active_document_code": active.document_code,
                "active_version": active.version,
            })
        elif active is not None and not active.is_active_version:
            stale_links.append({
                "requirement_codes": [r.requirement_code for r in requirements if r.source_document_id == doc_id],
                "linked_document_code": doc.document_code,
                "linked_version": doc.version,
                "active_document_code": None,
                "active_version": None,
            })

    source_docs = {}
    for active in active_by_linked_id.values():
        if active is not None and active.is_active_version:
            source_docs[active.id] = active

    # every obsolete version in the same families (used to spot outdated citations)
    families = {d.family_code for d in list(linked_docs.values()) + list(source_docs.values()) if d.family_code}
    obsolete_docs = (
        db.query(Document).filter(Document.family_code.in_(families), Document.is_active_version == False).all()  # noqa: E712
        if families else []
    )

    requirement_doc_code = {}
    for r in requirements:
        active = active_by_linked_id.get(r.source_document_id)
        requirement_doc_code[r.requirement_code] = active.document_code if active is not None and active.is_active_version else None

    segments = []
    redactions = 0
    ordered_docs = sorted(source_docs.values(), key=lambda d: (document_rank(d), d.document_code))
    for doc in ordered_docs:
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.id).all()
        for c in chunks:
            clean, n = redact(c.content or "")
            redactions += n
            segments.append({
                "document_id": doc.id,
                "document_code": doc.document_code,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "version": doc.version,
                "rank": document_rank(doc),
                "section": c.section,
                "heading": c.heading,
                "chunk_code": c.chunk_code,
                "location": c.page_or_location,
                "text": clean,
                "raw_text": c.content or "",
            })

    role_name = requirements[0].role.role_name if requirements and requirements[0].role else None
    if employee is not None and employee.role is not None:
        role_name = employee.role.role_name

    return {
        "role_id": role_id,
        "role_name": role_name,
        "requirements": requirements,
        "requirement_codes": [r.requirement_code for r in requirements],
        "mandatory_codes": [r.requirement_code for r in requirements if r.mandatory],
        "requirement_doc_code": requirement_doc_code,
        "source_documents": ordered_docs,
        "obsolete_documents": obsolete_docs,
        "active_document_codes": [d.document_code for d in ordered_docs],
        "obsolete_document_codes": [d.document_code for d in obsolete_docs],
        "stale_links": stale_links,
        "segments": segments,
        "redactions": redactions,
        "source_document_versions": [
            {"document_id": d.id, "document_code": d.document_code, "title": d.title,
             "version": d.version, "doc_type": d.doc_type, "precedence_rank": document_rank(d),
             "effective_date": d.effective_date.isoformat() if d.effective_date else None}
            for d in ordered_docs
        ],
    }


def source_text(ctx: dict) -> str:
    return " ".join(s["text"] for s in ctx["segments"])


def format_requirements(ctx: dict) -> str:
    lines = []
    for r in ctx["requirements"]:
        doc_code = ctx["requirement_doc_code"].get(r.requirement_code) or "-"
        lines.append(
            f"- {r.requirement_code} | {'MANDATORY' if r.mandatory else 'optional'} | priority: {r.priority or '-'} | "
            f"due_stage: {r.due_stage or '-'} | policy: {r.policy_requirement or '-'} | "
            f"process: {r.process_requirement or '-'} | competency: {r.competency or '-'} | "
            f"assessment: {r.assessment_requirement or '-'} | "
            f"source_document_code: {doc_code} | source_section: {r.source_section or '-'}"
        )
    return "\n".join(lines) if lines else "(none)"


def format_precedence() -> str:
    return "\n".join(
        f"- rank {h['rank']}: {h['label']}" + (f" ({', '.join(h['doc_types'])})" if h.get("doc_types") else "")
        for h in describe_hierarchy()
    )


def format_sources(ctx: dict, max_chars: int | None = None, per_chunk: int = 900) -> str:
    """Wraps every chunk as untrusted data, highest-precedence first, within a size budget."""
    budget = max_chars or settings.GENAI_MAX_SOURCE_CHARS
    wanted_sections = {(r.source_section or "").strip().lower() for r in ctx["requirements"] if r.source_section}

    def priority(seg):
        sec = (seg.get("section") or "").strip().lower()
        head = (seg.get("heading") or "").strip().lower()
        hit = any(w and (w == sec or w == head or w in head) for w in wanted_sections)
        return (0 if hit else 1, seg["rank"])

    parts, used = [], 0
    for seg in sorted(ctx["segments"], key=priority):
        text = seg["text"].strip()
        if len(text) > per_chunk:
            text = text[:per_chunk] + " ..."
        block = wrap_as_data(
            text,
            code=seg["document_code"], version=seg["version"], type=seg["doc_type"],
            precedence_rank=seg["rank"], section=seg["section"], chunk=seg["chunk_code"],
        )
        if used + len(block) > budget:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts) if parts else "(no source documents are linked to this role's requirements)"


def precedence_label(rank: int) -> str:
    return label_for_rank(rank)
