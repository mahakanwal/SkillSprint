"""Chunks keep document, chunk id, section and location (SRS Step 7)."""

import os
import tempfile

from tests.helpers import ESCALATION_SOP, bootstrap_admin, get_client, make_docx, upload


def test_chunks_are_traceable():
    c = get_client()
    h = bootstrap_admin(c)
    p = make_docx(os.path.join(tempfile.mkdtemp(), "sop.docx"), ESCALATION_SOP)
    r = upload(c, h, p, "SOP-07", "SOP")
    assert r.status_code == 200
    chunks = c.get(f"/documents/{r.json()['document_id']}/chunks", headers=h).json()["chunks"]
    assert len(chunks) == 2
    for ch in chunks:
        assert ch["chunk_code"].startswith("SOP-07-CH")
        assert ch["section"] in ("4.2 Refund Escalation", "4.3 Complaint Logging")
        assert ch["location"].startswith("paragraph")
