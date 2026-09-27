"""
document_validation/validator.py

Real, deterministic checks run on every document BEFORE it's saved to the
DB or disk -- no LLM involved. Covers SRS vi. "Document Validation":
    - File type must be an allowed extension
    - File size must be under the limit
    - File content must not be a byte-for-byte duplicate of an already
      uploaded document (detected by SHA-256 hash of the file content,
      not by filename -- catches re-uploads under a different name)
    - Metadata (document_code, title, doc_type, department, version) must
      be present and well-formed

Raises ValidationError with a clear, specific reason on the first failing
check -- callers (document_router.py) turn that into an HTTP 422/400.
"""

import os
import re
import hashlib
from sqlalchemy.orm import Session
from database.models import Document

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_DOC_TYPES = {"Policy", "SOP", "FAQ", "Handbook", "Guideline", "Manual", "Form", "Role Description", "Compliance", "Informal"}
MAX_FILE_SIZE_MB = 20
VERSION_PATTERN = re.compile(r"^\d+(\.\d+)?$")  # e.g. "1", "1.0", "2.3"


class ValidationError(Exception):
    """Raised when a document fails any validation check."""
    pass


def validate_file_type(filename: str) -> str:
    """Returns the lowercase extension if valid, else raises ValidationError."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext or '(none)'}'. "
            f"Only {', '.join(sorted(ALLOWED_EXTENSIONS))} are allowed."
        )
    return ext


def validate_file_size(file_path: str, max_mb: int = MAX_FILE_SIZE_MB) -> float:
    """Returns file size in MB if within limit, else raises ValidationError."""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > max_mb:
        raise ValidationError(f"File too large ({size_mb:.1f} MB). Max allowed: {max_mb} MB.")
    if size_mb <= 0:
        raise ValidationError("File is empty (0 bytes).")
    return round(size_mb, 3)


def compute_file_hash(file_path: str) -> str:
    """Returns the SHA-256 hex digest of the file's content."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def check_duplicate_content(file_hash: str, db: Session) -> Document | None:
    """
    Returns the existing Document with this exact file content (if any),
    regardless of what filename or document_code it was uploaded under.
    Catches "same file, re-uploaded under a new code" duplicates that a
    filename or document_code check alone would miss.
    """
    return db.query(Document).filter(Document.file_hash == file_hash).first()


def validate_metadata(document_code: str, title: str, doc_type: str, department: str, version: str) -> None:
    """Raises ValidationError listing every problem found (not just the first)."""
    problems = []

    if not document_code or not document_code.strip():
        problems.append("document_code is required.")
    if not title or not title.strip():
        problems.append("title is required.")
    if not department or not department.strip():
        problems.append("department is required.")

    if not doc_type or not doc_type.strip():
        problems.append("doc_type is required.")
    elif doc_type not in ALLOWED_DOC_TYPES:
        problems.append(
            f"doc_type '{doc_type}' is not recognized. Use one of: {', '.join(sorted(ALLOWED_DOC_TYPES))}."
        )

    if not version or not version.strip():
        problems.append("version is required.")
    elif not VERSION_PATTERN.match(version.strip()):
        problems.append(f"version '{version}' is not a valid format. Use e.g. '1.0', '2', '2.3'.")

    if problems:
        raise ValidationError(" | ".join(problems))


def validate_document_code_unique(document_code: str, db: Session) -> None:
    """A document_code must be globally unique -- each version gets its own code
    (e.g. SOP-07-v1, SOP-07-v2), grouped together by family_code instead."""
    existing = db.query(Document).filter(Document.document_code == document_code).first()
    if existing:
        raise ValidationError(
            f"document_code '{document_code}' is already in use (by document id={existing.id}). "
            f"Each version needs its own unique document_code."
        )
