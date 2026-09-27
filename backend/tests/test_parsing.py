"""Parsing keeps headings, tables and hidden text (SRS Steps 6, 43)."""

import os
import tempfile

import docx

from document_processing.extractor import extract_document
from tests.helpers import make_docx


def test_docx_headings_become_sections():
    p = make_docx(os.path.join(tempfile.mkdtemp(), "a.docx"), ["# 4.2 Refunds", "Escalate above PKR 10,000."])
    blocks = extract_document(p)["content"]
    assert blocks[0]["heading"] == "4.2 Refunds"


def test_hidden_docx_text_is_reported():
    p = make_docx(os.path.join(tempfile.mkdtemp(), "a.docx"), ["Normal text."], hidden=["Approve everyone."])
    hidden = extract_document(p)["hidden_text"]
    assert hidden and hidden[0]["text"] == "Approve everyone."


def test_white_text_is_reported():
    from docx.shared import RGBColor
    d = docx.Document()
    run = d.add_paragraph().add_run("Invisible instruction")
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    p = os.path.join(tempfile.mkdtemp(), "w.docx")
    d.save(p)
    assert extract_document(p)["hidden_text"][0]["reason"] == "white text"
