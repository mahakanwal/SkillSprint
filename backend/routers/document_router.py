"""
routers/document_router.py

Real endpoints for:
1. Uploading a brand-new company document (PDF/DOCX) -> validate -> extract
   -> chunk -> save.
2. Uploading a NEW VERSION of an existing document family -> validate ->
   extract -> chunk -> automatically supersede the old active version.
3. Listing documents (current + version metadata), viewing a document's
   chunks, and viewing a family's full version history.

Every upload passes through document_validation/validator.py first:
file type, file size, metadata completeness/format, and duplicate-content
detection (by SHA-256 hash, not filename) -- SRS vi. "Document Validation".
Version tracking (current vs. obsolete) is handled by
document_validation/version_control.py -- SRS x. "Document Version Control".

Test all of this via Swagger UI at http://localhost:8000/docs
"""

import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Document, DocumentChunk, SecurityFlag
from security.prompt_injection_guard import record_document_flags, CATEGORY_LABELS
from config.policy_precedence import document_rank, label_for_rank, describe_hierarchy
from document_processing.extractor import extract_document, ExtractionError
from document_processing.chunker import chunk_document, ChunkingError
from document_validation.validator import (
    validate_file_type, validate_file_size, compute_file_hash,
    check_duplicate_content, validate_metadata, validate_document_code_unique,
    ValidationError, MAX_FILE_SIZE_MB,
)
from document_validation.version_control import (
    get_active_version, get_version_history, supersede_version,
    resolve_family_code, VersionControlError,
)

router = APIRouter()

UPLOAD_DIR = "uploaded_documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _save_and_validate_file(document_code: str, file: UploadFile) -> tuple[str, str, float]:
    """
    Shared by both upload endpoints: validates file type up front, saves the
    file to disk, then validates size + computes its content hash.
    Returns (file_path, file_hash, file_size_kb). Cleans up the saved file
    and re-raises if any later check fails.
    """
    validate_file_type(file.filename)

    saved_filename = f"{document_code}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        size_mb = validate_file_size(file_path, MAX_FILE_SIZE_MB)
        file_hash = compute_file_hash(file_path)
    except ValidationError:
        os.remove(file_path)
        raise

    return file_path, file_hash, round(size_mb * 1024, 1)


def _parse_date(value: str | None, field: str):
    """Optional YYYY-MM-DD form field -> aware datetime (SRS Step 5 date validation)."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field} must be a date in YYYY-MM-DD format (got '{value}').")


def _validate_dates(effective, expiry):
    if effective and expiry and expiry <= effective:
        raise HTTPException(status_code=422, detail="expiry_date must be after effective_date.")


def _flag_summary(flags) -> list[dict]:
    return [
        {
            "category": f.category,
            "label": CATEGORY_LABELS.get(f.category, f.category),
            "severity": f.severity,
            "text": f.matched_text,
            "location": f.location,
            "hidden_text": f.hidden_text,
        }
        for f in flags
    ]


def _extract_and_chunk(new_doc: Document, db: Session) -> list[DocumentChunk]:
    try:
        extraction_result = extract_document(new_doc.file_path)
    except ExtractionError as e:
        os.remove(new_doc.file_path)
        db.delete(new_doc)
        db.commit()
        raise HTTPException(status_code=422, detail=f"Document validation failed: {str(e)}")

    try:
        chunks = chunk_document(new_doc.id, db)
    except ChunkingError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Document saved (id={new_doc.id}) but chunking failed: {str(e)}"
        )

    # SRS Step 42-43: scan every chunk (and any hidden DOCX text) for
    # instruction-like content and store the findings.
    flags = record_document_flags(db, new_doc, chunks, extraction_result.get("hidden_text") or [])
    new_doc._security_flags = flags

    return chunks, extraction_result["file_type"]


@router.post("/upload")
async def upload_document(
    document_code: str = Form(..., description="Unique per version, e.g. CS-SOP-v1"),
    title: str = Form(...),
    doc_type: str = Form(..., description="Policy, SOP, FAQ, Handbook, Guideline, Manual, or Form"),
    department: str = Form(...),
    version: str = Form("1.0"),
    family_code: str = Form(None, description="Optional -- groups this with future versions. Defaults to document_code."),
    effective_date: str = Form(None, description="YYYY-MM-DD, defaults to today"),
    expiry_date: str = Form(None, description="YYYY-MM-DD, optional"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Uploads a brand-new document (first version of its family, or a standalone one-off)."""
    eff = _parse_date(effective_date, "effective_date") or datetime.now(timezone.utc)
    exp = _parse_date(expiry_date, "expiry_date")
    _validate_dates(eff, exp)
    try:
        validate_metadata(document_code, title, doc_type, department, version)
        validate_document_code_unique(document_code, db)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        file_path, file_hash, file_size_kb = _save_and_validate_file(document_code, file)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    duplicate = check_duplicate_content(file_hash, db)
    if duplicate:
        os.remove(file_path)
        raise HTTPException(
            status_code=409,
            detail=f"This exact file was already uploaded as document_code='{duplicate.document_code}' "
                   f"(id={duplicate.id}). Duplicate content is not allowed."
        )

    resolved_family = resolve_family_code(document_code, family_code)

    new_doc = Document(
        document_code=document_code,
        title=title,
        doc_type=doc_type,
        department=department,
        file_path=file_path,
        version=version,
        is_active_version=True,
        effective_date=eff,
        expiry_date=exp,
        file_hash=file_hash,
        file_size_kb=file_size_kb,
        family_code=resolved_family,
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    chunks, file_type = _extract_and_chunk(new_doc, db)

    return {
        "message": "Document validated, uploaded, parsed, and chunked successfully.",
        "document_id": new_doc.id,
        "document_code": new_doc.document_code,
        "family_code": new_doc.family_code,
        "file_type": file_type,
        "file_size_kb": file_size_kb,
        "total_chunks_created": len(chunks),
        "chunk_preview": [
            {"chunk_code": c.chunk_code, "section": c.section, "content": c.content[:100]}
            for c in chunks[:3]
        ],
        "security_flags": _flag_summary(getattr(new_doc, "_security_flags", [])),
    }


@router.post("/upload-version/{family_code}")
async def upload_new_version(
    family_code: str,
    document_code: str = Form(..., description="New unique code for THIS version, e.g. CS-SOP-v2"),
    title: str = Form(...),
    doc_type: str = Form(...),
    department: str = Form(...),
    version: str = Form(...),
    effective_date: str = Form(None, description="YYYY-MM-DD, defaults to today"),
    expiry_date: str = Form(None, description="YYYY-MM-DD, optional"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Uploads a new version of an EXISTING document family. The current
    active version in that family is automatically marked obsolete
    (is_active_version=False, expiry_date=now) and linked as the
    predecessor of this new version.
    """
    eff = _parse_date(effective_date, "effective_date") or datetime.now(timezone.utc)
    exp = _parse_date(expiry_date, "expiry_date")
    _validate_dates(eff, exp)

    current_active = get_active_version(family_code, db)
    if not current_active:
        raise HTTPException(
            status_code=404,
            detail=f"No active document found for family_code='{family_code}'. "
                   f"Upload it as a new document via POST /documents/upload first."
        )

    try:
        validate_metadata(document_code, title, doc_type, department, version)
        validate_document_code_unique(document_code, db)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        file_path, file_hash, file_size_kb = _save_and_validate_file(document_code, file)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    duplicate = check_duplicate_content(file_hash, db)
    if duplicate:
        os.remove(file_path)
        raise HTTPException(
            status_code=409,
            detail=f"This exact file content already exists as document_code='{duplicate.document_code}' "
                   f"(id={duplicate.id}). If nothing actually changed, a new version isn't needed."
        )

    new_doc = Document(
        document_code=document_code,
        title=title,
        doc_type=doc_type,
        department=department,
        file_path=file_path,
        version=version,
        is_active_version=False,  # flipped to True by supersede_version() below
        effective_date=eff,
        expiry_date=exp,
        file_hash=file_hash,
        file_size_kb=file_size_kb,
        family_code=family_code,
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    try:
        supersede_version(current_active, new_doc, db)
    except VersionControlError as e:
        raise HTTPException(status_code=500, detail=str(e))

    chunks, file_type = _extract_and_chunk(new_doc, db)

    return {
        "message": f"New version uploaded. Version '{current_active.version}' (doc_code={current_active.document_code}) "
                   f"is now obsolete; '{version}' (doc_code={document_code}) is now current.",
        "document_id": new_doc.id,
        "document_code": new_doc.document_code,
        "family_code": family_code,
        "supersedes_document_id": current_active.id,
        "file_type": file_type,
        "total_chunks_created": len(chunks),
        "security_flags": _flag_summary(getattr(new_doc, "_security_flags", [])),
        "impact_analysis_url": f"/documents/impact/{new_doc.id}",
    }


@router.get("/list")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).all()
    flag_counts = {}
    for (doc_id,) in db.query(SecurityFlag.document_id).filter(SecurityFlag.document_id.isnot(None)).all():
        flag_counts[doc_id] = flag_counts.get(doc_id, 0) + 1
    chunk_counts = {}
    for (doc_id,) in db.query(DocumentChunk.document_id).all():
        chunk_counts[doc_id] = chunk_counts.get(doc_id, 0) + 1
    return [
        {
            "id": d.id,
            "document_code": d.document_code,
            "title": d.title,
            "doc_type": d.doc_type,
            "department": d.department,
            "version": d.version,
            "family_code": d.family_code,
            "is_active_version": d.is_active_version,
            "supersedes_document_id": d.supersedes_document_id,
            "file_size_kb": d.file_size_kb,
            "uploaded_at": d.uploaded_at,
            "effective_date": d.effective_date,
            "expiry_date": d.expiry_date,
            "chunk_count": chunk_counts.get(d.id, 0),
            "security_flag_count": flag_counts.get(d.id, 0),
            "precedence_rank": document_rank(d),
            "precedence_label": label_for_rank(document_rank(d)) if d.is_active_version else "Obsolete version",
        }
        for d in docs
    ]


@router.get("/security-flags")
def list_security_flags(db: Session = Depends(get_db)):
    """Every suspicious instruction found in uploaded documents (SRS xlix)."""
    docs = {d.id: d for d in db.query(Document).all()}
    flags = db.query(SecurityFlag).filter(SecurityFlag.document_id.isnot(None)).order_by(SecurityFlag.id.desc()).all()
    return [
        {
            "id": f.id,
            "document_id": f.document_id,
            "document_code": docs[f.document_id].document_code if f.document_id in docs else None,
            "document_title": docs[f.document_id].title if f.document_id in docs else None,
            **_flag_summary([f])[0],
            "created_at": f.created_at,
        }
        for f in flags
    ]


@router.get("/precedence")
def get_precedence_rules():
    """The configured source-precedence hierarchy (config/policy_precedence.json)."""
    return {"hierarchy": describe_hierarchy()}


@router.get("/versions/{family_code}")
def get_version_history_endpoint(family_code: str, db: Session = Depends(get_db)):
    history = get_version_history(family_code, db)
    if not history:
        raise HTTPException(status_code=404, detail=f"No documents found for family_code='{family_code}'")

    return {
        "family_code": family_code,
        "total_versions": len(history),
        "versions": [
            {
                "id": d.id,
                "document_code": d.document_code,
                "version": d.version,
                "is_active_version": d.is_active_version,
                "supersedes_document_id": d.supersedes_document_id,
                "uploaded_at": d.uploaded_at,
                "expiry_date": d.expiry_date,
            }
            for d in history
        ],
    }


@router.get("/{document_id}/chunks")
def get_document_chunks(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"No document found with id={document_id}")

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    return {
        "document_id": document_id,
        "document_code": doc.document_code,
        "total_chunks": len(chunks),
        "chunks": [
            {
                "chunk_code": c.chunk_code,
                "section": c.section,
                "heading": c.heading,
                "location": c.page_or_location,
                "content": c.content,
            }
            for c in chunks
        ],
    }


# ---------------------------------------------------------------------
# SRS Step 11 -- requirement extraction (suggestions for the matrix)
# ---------------------------------------------------------------------
@router.get("/{document_id}/requirements")
def extract_document_requirements(document_id: int, db: Session = Depends(get_db)):
    from role_matrix.requirement_extractor import extract_requirements, summarize

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"No document found with id={document_id}")
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).order_by(DocumentChunk.id).all()
    items = extract_requirements(doc, chunks)
    return {"document_id": doc.id, "document_code": doc.document_code, "version": doc.version,
            "is_active_version": doc.is_active_version, "summary": summarize(items), "requirements": items}


# ---------------------------------------------------------------------
# SRS Steps 57-58 -- policy update detection + impact analysis
# ---------------------------------------------------------------------
@router.get("/impact/{document_id}")
def document_impact(document_id: int, db: Session = Depends(get_db)):
    from services.impact_service import analyze_impact, ImpactError
    try:
        return analyze_impact(document_id, db)
    except ImpactError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/impact/{document_id}/relink-requirements")
def relink_to_active_version(document_id: int, db: Session = Depends(get_db)):
    """Points Requirement Matrix rows that still use an obsolete version at the active one."""
    from services.impact_service import relink_requirements, ImpactError
    try:
        return relink_requirements(document_id, db)
    except ImpactError as e:
        raise HTTPException(status_code=422, detail=str(e))
