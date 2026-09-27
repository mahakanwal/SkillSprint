"""
role_matrix/matrix_builder.py

Real CSV bulk-import logic for the Role Requirement Matrix (the SRS "ground
truth" table). Reads an uploaded CSV file, validates every row, resolves
role_name -> role_id (and an optional source_document_code -> document id),
and inserts RequirementMatrix rows one row at a time so a single bad row
never blocks the rest of the batch.

Expected CSV columns (header row required):
    requirement_code        (required)
    role_name                (required -- must match an existing Role.role_name)
    policy_requirement
    process_requirement
    competency
    mandatory                 true/false/yes/no/1/0 -- defaults to true if blank
    priority                  High / Medium / Low
    due_stage                 e.g. Day 1, Week 1, First 30 Days
    source_document_code      optional -- must match an existing Document.document_code
    source_section
    assessment_requirement

Use case: SRS requires a minimum of 150 requirements in this table. Filling
that in one-by-one through the UI is slow, so this lets the matrix be built
in Excel/Sheets and uploaded in one shot via POST /requirements/bulk-upload.
"""

import csv
import io
from sqlalchemy.orm import Session

from database.models import RequirementMatrix, Role, Document

REQUIRED_COLUMNS = {"requirement_code", "role_name"}

TRUE_VALUES = {"true", "yes", "1", "y"}
FALSE_VALUES = {"false", "no", "0", "n"}


class CSVImportError(Exception):
    """Raised when the CSV file itself is malformed (no header, missing
    required columns, unreadable encoding, etc.) -- stops the whole import
    before any row is processed."""
    pass


def _parse_mandatory(raw_value):
    """Converts a free-text CSV cell into a bool. Blank cells default to True."""
    if raw_value is None or raw_value.strip() == "":
        return True
    val = raw_value.strip().lower()
    if val in TRUE_VALUES:
        return True
    if val in FALSE_VALUES:
        return False
    raise ValueError(f"invalid 'mandatory' value '{raw_value}' (use true/false)")


def _clean(value):
    """Trims a CSV cell and turns empty strings into None."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def import_requirements_csv(file_bytes: bytes, db: Session) -> dict:
    """
    Parses CSV bytes and inserts RequirementMatrix rows.

    Each row is committed independently (its own mini-transaction), so if
    row 47 has a bad role_name, rows 1-46 and 48+ are still saved -- the
    person just gets told which row failed and why, and can fix + re-upload
    only the bad rows.

    Returns a summary dict: message, total_rows_in_file, created_count,
    skipped_count, errors[] (each with row_number, requirement_code, error).
    """
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CSVImportError("File is not valid UTF-8 text. Please save/export the CSV as UTF-8.")

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise CSVImportError("CSV file has no header row.")

    headers = {h.strip() for h in reader.fieldnames if h}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise CSVImportError(
            f"CSV is missing required column(s): {', '.join(sorted(missing))}. "
            f"Download the template for the expected format."
        )

    # Cache lookups so we don't hit the DB once per row
    roles_by_name = {r.role_name.strip().lower(): r for r in db.query(Role).all()}
    docs_by_code = {d.document_code.strip().lower(): d for d in db.query(Document).all()}
    existing_codes = {
        code for (code,) in db.query(RequirementMatrix.requirement_code).all()
    }
    seen_codes_in_file = set()

    total_rows = 0
    created_count = 0
    skipped_count = 0
    errors = []

    for row_number, row in enumerate(reader, start=2):  # row 1 is the header
        # Skip completely blank lines (common at the end of an exported CSV)
        if row is None or all((v is None or str(v).strip() == "") for v in row.values()):
            continue

        total_rows += 1
        requirement_code = _clean(row.get("requirement_code")) or ""
        role_name = _clean(row.get("role_name")) or ""

        try:
            if not requirement_code:
                raise ValueError("requirement_code is required")
            if not role_name:
                raise ValueError("role_name is required")
            if requirement_code in existing_codes:
                raise ValueError(f"requirement_code '{requirement_code}' already exists in the database")
            if requirement_code in seen_codes_in_file:
                raise ValueError(f"requirement_code '{requirement_code}' is duplicated earlier in this CSV")

            role = roles_by_name.get(role_name.lower())
            if not role:
                raise ValueError(
                    f"role_name '{role_name}' does not match any existing Role -- create the role first"
                )

            source_document_id = None
            source_doc_code = _clean(row.get("source_document_code"))
            if source_doc_code:
                doc = docs_by_code.get(source_doc_code.lower())
                if not doc:
                    raise ValueError(
                        f"source_document_code '{source_doc_code}' does not match any existing Document"
                    )
                source_document_id = doc.id

            mandatory = _parse_mandatory(row.get("mandatory"))

            new_req = RequirementMatrix(
                requirement_code=requirement_code,
                role_id=role.id,
                policy_requirement=_clean(row.get("policy_requirement")),
                process_requirement=_clean(row.get("process_requirement")),
                competency=_clean(row.get("competency")),
                mandatory=mandatory,
                priority=_clean(row.get("priority")),
                due_stage=_clean(row.get("due_stage")),
                source_document_id=source_document_id,
                source_section=_clean(row.get("source_section")),
                assessment_requirement=_clean(row.get("assessment_requirement")),
            )
            db.add(new_req)
            db.commit()  # commit per-row so one bad row can't roll back good ones

            seen_codes_in_file.add(requirement_code)
            existing_codes.add(requirement_code)
            created_count += 1

        except Exception as e:
            db.rollback()
            skipped_count += 1
            errors.append({
                "row_number": row_number,
                "requirement_code": requirement_code or None,
                "error": str(e),
            })

    return {
        "message": f"CSV processed: {created_count} requirement(s) created, {skipped_count} skipped.",
        "total_rows_in_file": total_rows,
        "created_count": created_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }