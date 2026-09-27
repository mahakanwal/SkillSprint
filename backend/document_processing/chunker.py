"""
document_processing/chunker.py

Splits extracted document content (from extractor.py) into traceable
chunks and saves them into the document_chunks table.

A "chunk" here = one paragraph (DOCX) or one page (PDF) — small enough
to stay traceable, with heading/section/page metadata preserved so
every piece of generated content can be traced back to its source.
"""

from sqlalchemy.orm import Session
from database.models import Document, DocumentChunk
from document_processing.extractor import extract_document, ExtractionError


class ChunkingError(Exception):
    pass


def chunk_document(document_id: int, db: Session) -> list[DocumentChunk]:
    """
    Loads a Document record by ID, re-extracts its file, builds
    DocumentChunk rows, saves them, and returns the created chunks.

    Raises ChunkingError if the document doesn't exist or extraction fails.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ChunkingError(f"No document found with id={document_id}")

    # Remove any existing chunks for this document (re-chunking case,
    # e.g. after a version update)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    db.commit()

    try:
        extraction_result = extract_document(doc.file_path)
    except ExtractionError as e:
        raise ChunkingError(f"Could not re-extract document {document_id}: {str(e)}")

    content_blocks = extraction_result["content"]
    file_type = extraction_result["file_type"]

    created_chunks = []
    chunk_counter = 1

    for block in content_blocks:
        chunk_code = f"{doc.document_code}-CH{chunk_counter:03d}"

        if file_type == "docx":
            section = block["heading"]
            heading = block["heading"]
            location = f"paragraph {block['paragraph_index']}"
            text = block["text"]
        else:  # pdf
            section = f"page {block['page_number']}"
            heading = None
            location = f"page {block['page_number']}"
            text = block["text"]

        # Skip near-empty chunks (e.g. stray whitespace pages)
        if not text or len(text.strip()) < 3:
            continue

        new_chunk = DocumentChunk(
            chunk_code=chunk_code,
            document_id=doc.id,
            section=section,
            heading=heading,
            content=text,
            page_or_location=location,
        )
        db.add(new_chunk)
        created_chunks.append(new_chunk)
        chunk_counter += 1

    if not created_chunks:
        raise ChunkingError(
            f"Document {document_id} produced zero valid chunks after filtering."
        )

    db.commit()

    for c in created_chunks:
        db.refresh(c)

    return created_chunks


if __name__ == "__main__":
    # Quick manual test: python chunker.py <document_id>
    import sys
    from database.connection import SessionLocal

    if len(sys.argv) < 2:
        print("Usage: python chunker.py <document_id>")
        sys.exit(1)

    db = SessionLocal()
    try:
        chunks = chunk_document(int(sys.argv[1]), db)
        print(f"Created {len(chunks)} chunks:\n")
        for c in chunks[:5]:
            print(f"[{c.chunk_code}] Section: {c.section}")
            print(f"  {c.content[:80]}...")
            print("---")
    finally:
        db.close()