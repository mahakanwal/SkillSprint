"""
tests/helpers.py -- shared setup for the HTTP-level test suite.

Every test runs against a throw-away SQLite database and a FAKE GenAI
client (no network, no API key, no cost). The fake returns whatever JSON
the test queues up, so tests can simulate good plans, invalid JSON,
prompt-injected output, etc. The real Python validation pipeline runs
unchanged.

Run:  cd backend && python -m pytest tests -q
"""

import json
import os
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

_DB_FILE = os.path.join(tempfile.gettempdir(), f"skillsprint_test_{os.getpid()}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_FILE}"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-automated-tests-only")
os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")

# queue of raw model responses the fake Groq client will return, in order
FAKE_RESPONSES: list = []
CALLS: list = []


def _fake_call_groq(system_prompt, user_prompt, model):
    CALLS.append({"system": system_prompt, "user": user_prompt, "model": model})
    if not FAKE_RESPONSES:
        raise AssertionError("Fake GenAI client called but no response was queued")
    nxt = FAKE_RESPONSES.pop(0)
    if isinstance(nxt, Exception):
        from genai_pipeline.groq_client import GroqClientError
        raise GroqClientError(str(nxt))
    return nxt if isinstance(nxt, str) else json.dumps(nxt)


def queue(*responses):
    FAKE_RESPONSES.extend(responses)


_app = None


def get_client():
    """Fresh database + TestClient with the fake GenAI client installed."""
    global _app
    from fastapi.testclient import TestClient
    import genai_pipeline.groq_client as gc
    import genai_pipeline.retry_handler as rh
    gc.call_groq = _fake_call_groq
    rh.call_groq = _fake_call_groq
    rh.time.sleep = lambda s: None  # no real back-off waits in tests

    from database.connection import Base, engine, init_db
    Base.metadata.drop_all(bind=engine)
    init_db()
    FAKE_RESPONSES.clear()
    CALLS.clear()

    if _app is None:
        from main import app
        _app = app
    return TestClient(_app)


def bootstrap_admin(client, email="admin@test.com", password="Admin#12345"):
    r = client.post("/auth/bootstrap-first-admin", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_docx(path, paragraphs, hidden=None):
    """Creates a DOCX; `hidden` paragraphs are written as hidden text."""
    import docx
    d = docx.Document()
    for p in paragraphs:
        if p.startswith("# "):
            d.add_heading(p[2:], level=1)
        else:
            d.add_paragraph(p)
    for h in hidden or []:
        run = d.add_paragraph().add_run(h)
        run.font.hidden = True
    d.save(path)
    return path


def upload(client, headers, path, code, doc_type="Policy", title=None, version="1.0", department="All"):
    with open(path, "rb") as f:
        return client.post(
            "/documents/upload",
            headers=headers,
            data={"document_code": code, "title": title or code, "doc_type": doc_type,
                  "department": department, "version": version},
            files={"file": (os.path.basename(path), f, "application/octet-stream")},
        )


def upload_version(client, headers, family, path, code, version, doc_type="Policy", title=None, department="All"):
    with open(path, "rb") as f:
        return client.post(
            f"/documents/upload-version/{family}",
            headers=headers,
            data={"document_code": code, "title": title or code, "doc_type": doc_type,
                  "department": department, "version": version},
            files={"file": (os.path.basename(path), f, "application/octet-stream")},
        )


SECURITY_POLICY_V1 = [
    "# 1. Password Policy",
    "All employees must change their system password every 90 days. Minimum password length is 8 characters.",
    "# 2. Device Security",
    "Company laptops must have antivirus software installed and updated weekly.",
]

SECURITY_POLICY_V2 = [
    "# 1. Password Policy",
    "All employees must change their system password every 45 days. Minimum password length is 12 characters.",
    "# 2. Device Security",
    "Company laptops must have antivirus software installed and updated daily.",
    "# 3. Data Handling",
    "Employees must first complete the 'Information Security Basics' module before being granted CRM access.",
]

ESCALATION_SOP = [
    "# 4.2 Refund Escalation",
    "Support executives must escalate refund requests above PKR 10,000 to the Team Leader within 24 hours.",
    "# 4.3 Complaint Logging",
    "Every customer complaint must be logged in the CRM before the ticket is closed.",
]

CONFLICTING_FAQ = [
    "# Refunds",
    "Support executives must escalate refund requests above PKR 25,000 to the Team Leader within 48 hours.",
]


def good_plan(role="Customer Support Executive"):
    """A realistic, correct plan for the test role."""
    return {
        "role": role,
        "stages": ["Day 1", "Week 1", "Week 2", "First 30 Days", "First 60 Days", "First 90 Days"],
        "modules": [
            {"module_code": "M01", "title": "Password and Device Security",
             "purpose": "Change your system password every 45 days with a minimum length of 12 characters and keep antivirus software updated daily.",
             "learning_objectives": ["Apply the password policy", "Keep company laptops protected with antivirus software"],
             "key_concepts": ["password policy", "antivirus"], "learning_activities": ["Read the password policy"],
             "assessment": "Short quiz", "completion_criteria": "Quiz passed",
             "estimated_duration": "1 hour", "due_stage": "Day 1", "mandatory": True, "prerequisites": [],
             "source_requirement_code": "R001", "source_document_code": "SEC-v2", "source_section": "1. Password Policy",
             "difficulty": "Beginner"},
            {"module_code": "M02", "title": "Refund Escalation Procedure",
             "purpose": "Escalate refund requests above PKR 10,000 to the Team Leader within 24 hours.",
             "learning_objectives": ["Recognise refund requests that need escalation"],
             "key_concepts": ["refund escalation", "team leader"], "learning_activities": ["Walk through escalation examples"],
             "assessment": "Scenario task", "completion_criteria": "Scenario completed",
             "estimated_duration": "2 hours", "due_stage": "Week 1", "mandatory": True, "prerequisites": ["M01"],
             "source_requirement_code": "R002", "source_document_code": "SOP-07", "source_section": "4.2 Refund Escalation"},
        ],
        "checklist": [
            {"activity": "Log every customer complaint in the CRM before closing the ticket", "required": True,
             "due_stage": "Week 1", "source_requirement_code": "R003", "source_document_code": "SOP-07",
             "source_section": "4.3 Complaint Logging", "responsible_person": "Team Leader"},
        ],
        "tasks": [
            {"task_description": "Handle a simulated refund request of PKR 15,000 and escalate it to the Team Leader",
             "task_type": "scenario", "scenario": "A customer requests a refund of PKR 15,000.",
             "expected_outcome": "Refund escalated to the Team Leader within 24 hours",
             "completion_criteria": "Escalation logged", "difficulty": "Beginner", "due_stage": "Week 2",
             "source_requirement_code": "R002"},
        ],
        "quiz": [
            {"question_text": "How often must employees change their system password?",
             "question_type": "multiple_choice", "options": ["Every 45 days", "Every 180 days", "Never", "Once a year"],
             "correct_answer": "Every 45 days", "explanation": "The password policy requires a change every 45 days.",
             "difficulty": "Beginner", "source_requirement_code": "R001", "source_document_code": "SEC-v2",
             "source_section": "1. Password Policy"},
        ],
        "assessments": [
            {"title": "Refund escalation practical", "assessment_type": "practical",
             "description": "Escalate a refund request above PKR 10,000 to the Team Leader.",
             "due_stage": "First 30 Days", "difficulty": "Beginner", "source_requirement_code": "R002",
             "rubric": [
                 {"criterion": "Correct threshold", "weight": 60, "expected_performance": "Escalates above PKR 10,000", "pass_condition": "Threshold applied correctly"},
                 {"criterion": "Timeliness", "weight": 40, "expected_performance": "Within 24 hours", "pass_condition": "Escalated within 24 hours"},
             ]},
        ],
        "insufficient_information": [],
        "security_notes": [],
    }


def seed_role(client, headers, tmpdir):
    """Uploads documents, a role, 3 requirements and an employee. Returns ids."""
    sec = make_docx(os.path.join(tmpdir, "sec_v1.docx"), SECURITY_POLICY_V1)
    sop = make_docx(os.path.join(tmpdir, "sop.docx"), ESCALATION_SOP)
    r1 = upload(client, headers, sec, "SEC-v1", "Policy", "Information Security Policy")
    assert r1.status_code == 200, r1.text
    sec2 = make_docx(os.path.join(tmpdir, "sec_v2.docx"), SECURITY_POLICY_V2)
    r2 = upload_version(client, headers, "SEC-v1", sec2, "SEC-v2", "2.0", "Policy", "Information Security Policy")
    assert r2.status_code == 200, r2.text
    r3 = upload(client, headers, sop, "SOP-07", "SOP", "Customer Support Escalation SOP", department="Customer Support")
    assert r3.status_code == 200, r3.text

    role = client.post("/roles/", headers=headers, json={
        "role_name": "Customer Support Executive", "department": "Customer Support",
        "description": "Handles customer queries"}).json()
    other = client.post("/roles/", headers=headers, json={
        "role_name": "Finance Associate", "department": "Finance", "description": "Finance"}).json()

    docs = {d["document_code"]: d["id"] for d in client.get("/documents/list", headers=headers).json()}
    reqs = [
        # R001 intentionally still points at the OLD policy version (stale link)
        {"requirement_code": "R001", "role_id": role["id"], "policy_requirement": "Follow the password and device security policy",
         "process_requirement": "Change passwords and keep antivirus updated", "competency": "Information security",
         "mandatory": True, "priority": "High", "due_stage": "Day 1", "source_document_id": docs["SEC-v1"],
         "source_section": "1. Password Policy", "assessment_requirement": "Quiz on password policy"},
        {"requirement_code": "R002", "role_id": role["id"], "policy_requirement": "Refund escalation procedure",
         "process_requirement": "Escalate refund requests above threshold to the Team Leader", "competency": "Escalation handling",
         "mandatory": True, "priority": "High", "due_stage": "Week 1", "source_document_id": docs["SOP-07"],
         "source_section": "4.2 Refund Escalation", "assessment_requirement": "Practical escalation task"},
        {"requirement_code": "R003", "role_id": role["id"], "policy_requirement": "Complaint handling",
         "process_requirement": "Log every customer complaint in the CRM", "competency": "CRM usage",
         "mandatory": True, "priority": "Medium", "due_stage": "Week 1", "source_document_id": docs["SOP-07"],
         "source_section": "4.3 Complaint Logging", "assessment_requirement": "Checklist"},
        {"requirement_code": "F001", "role_id": other["id"], "policy_requirement": "Monthly reconciliation",
         "process_requirement": "Reconcile ledgers every month", "competency": "Accounting",
         "mandatory": True, "priority": "High", "due_stage": "Week 1", "source_document_id": None,
         "source_section": None, "assessment_requirement": None},
    ]
    for r in reqs:
        resp = client.post("/requirements/", headers=headers, json=r)
        assert resp.status_code == 200, resp.text

    emp = client.post("/employees/", headers=headers, json={
        "employee_code": "EMP-001", "full_name": "Ayesha Khan", "email": "ayesha@test.com",
        "department": "Customer Support", "experience_level": "Beginner",
        "joining_date": "2026-09-01T00:00:00", "reporting_manager": "Sarah Ahmed", "role_id": role["id"]})
    assert emp.status_code == 200, emp.text
    body = emp.json()
    return {"role": role, "other_role": other, "docs": docs, "employee": body["employee"],
            "employee_password": body["temporary_password"]}


def make_pdf(path, pages):
    """Writes a minimal, valid multi-page PDF with plain text (no extra libraries)."""
    objects = []
    def add(obj):
        objects.append(obj)
        return len(objects)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids, content_ids = [], []
    pages_id_placeholder = len(objects) + 1 + 2 * len(pages)
    for text in pages:
        lines = [l.replace("(", "[").replace(")", "]") for l in text.split("\n")]
        stream = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(f"({l}) '" for l in lines) + " ET"
        data = stream.encode("latin-1")
        cid = add(b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"\nendstream")
        pid = add(("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 842] /Contents %d 0 R "
                   "/Resources << /Font << /F1 %d 0 R >> >> >>" % (pages_id_placeholder, cid, font)).encode())
        page_ids.append(pid)
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
    assert pages_id == pages_id_placeholder
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as f:
        f.write(bytes(out))
    return path
