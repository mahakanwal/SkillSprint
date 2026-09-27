"""
utils/export_utils.py

SRS Step 63 / lxii -- report export.

CSV is written with a UTF-8 byte-order mark and CRLF line endings, which is
what Microsoft Excel expects, so the same file serves as both "CSV" and the
"Excel-compatible format". PDF export is produced by the frontend's print
view (browser "Save as PDF"), so no extra server dependency is needed.
"""

import csv
import io
import json
from datetime import date, datetime

from fastapi.responses import Response


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def rows_to_csv(rows: list[dict], columns: list[str] | None = None) -> str:
    columns = columns or (list(rows[0].keys()) if rows else [])
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({c: _cell(r.get(c)) for c in columns})
    return "﻿" + buf.getvalue()


def csv_response(rows: list[dict], filename: str, columns: list[str] | None = None) -> Response:
    return Response(
        content=rows_to_csv(rows, columns).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
