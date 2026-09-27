"""
document_validation/version_control.py

Real version-control logic for SRS x. "Document Version Control":
distinguishes current vs. obsolete versions of the same document family.

A "family" is a group of Document rows that are different versions of the
same underlying document (e.g. "Customer Support SOP" v1.0, v1.1, v2.0).
They share a `family_code` but each still has its own unique
`document_code` (e.g. CS-SOP-v1, CS-SOP-v2) so every version stays
individually addressable and traceable in RequirementMatrix/chunks.

Only one Document per family may have is_active_version=True at a time --
`supersede_version` enforces that by flipping the old one off and linking
the chain via supersedes_document_id.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database.models import Document


class VersionControlError(Exception):
    pass


def get_active_version(family_code: str, db: Session) -> Document | None:
    return (
        db.query(Document)
        .filter(Document.family_code == family_code, Document.is_active_version == True)  # noqa: E712
        .first()
    )


def get_version_history(family_code: str, db: Session) -> list[Document]:
    """Returns every version in this family, oldest first."""
    return (
        db.query(Document)
        .filter(Document.family_code == family_code)
        .order_by(Document.uploaded_at.asc())
        .all()
    )


def supersede_version(old_doc: Document, new_doc: Document, db: Session) -> None:
    """
    Marks old_doc as obsolete (is_active_version=False, expiry_date=now) and
    links new_doc back to it via supersedes_document_id. Does not touch
    old_doc's chunks/RequirementMatrix links -- those stay intact for
    historical traceability; only its "current" status changes.
    """
    old_doc.is_active_version = False
    old_doc.expiry_date = datetime.now(timezone.utc)
    new_doc.supersedes_document_id = old_doc.id
    new_doc.is_active_version = True
    db.commit()


def resolve_family_code(document_code: str, explicit_family_code: str | None) -> str:
    """
    A brand-new document (no version history yet) defaults its family_code
    to its own document_code, so it can later be looked up as the root of
    its own version family.
    """
    return (explicit_family_code or document_code).strip()
