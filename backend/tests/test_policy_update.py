"""
Policy Update Challenge (SRS Steps 57-59, Challenge 4), requirement
extraction (Step 11) and GenAI consistency check (Steps 44-45).
"""

import copy
import os
import tempfile

from tests.helpers import (
    CALLS, SECURITY_POLICY_V2, bootstrap_admin, get_client, good_plan, make_docx, queue, seed_role,
    upload_version,
)


def _setup_with_plan_on_v2():
    client = get_client()
    headers = bootstrap_admin(client)
    tmp = tempfile.mkdtemp()
    ids = seed_role(client, headers, tmp)
    queue(good_plan())
    plan = client.post(f"/onboarding/generate/{ids['employee']['id']}", headers=headers).json()
    return client, headers, ids, tmp, plan


def test_requirement_extraction_classifies_sentences():
    client, headers, ids, tmp, _ = _setup_with_plan_on_v2()
    r = client.get(f"/documents/{ids['docs']['SEC-v2']}/requirements", headers=headers)
    assert r.status_code == 200
    body = r.json()
    classes = {x["classification"] for x in body["requirements"]}
    assert "Must Complete" in classes
    assert body["summary"]["mandatory"] >= 3
    assert all(x["section"] for x in body["requirements"])


def test_new_version_triggers_impact_analysis_and_selective_regeneration():
    client, headers, ids, tmp, plan = _setup_with_plan_on_v2()
    v3_text = [s.replace("45 days", "30 days") for s in SECURITY_POLICY_V2]
    v3 = make_docx(os.path.join(tmp, "sec_v3.docx"), v3_text)
    up = upload_version(client, headers, "SEC-v1", v3, "SEC-v3", "3.0", "Policy", "Information Security Policy")
    assert up.status_code == 200, up.text
    new_id = up.json()["document_id"]

    impact = client.get(f"/documents/impact/{new_id}", headers=headers).json()
    assert impact["previous_version"]["document_code"] == "SEC-v2"
    changed = impact["changes"]["changed"]
    assert any("45 day(s) -> 30 day(s)" in " ".join(c["value_changes"]) for c in changed)
    affected = next(p for p in impact["affected_plans"] if p["plan_id"] == plan["id"])
    assert affected["requires_regeneration"]
    assert affected["affected_counts"].get("modules", 0) >= 1
    assert affected["outdated_quiz_questions"]  # "Every 45 days" question is outdated
    assert impact["summary"]["employees_affected"] == 1

    # regenerate only the affected module + quiz question
    fresh = copy.deepcopy(good_plan())
    fresh_module = fresh["modules"][0]
    fresh_module["purpose"] = fresh_module["purpose"].replace("45 days", "30 days")
    fresh_module["source_document_code"] = "SEC-v3"
    fresh_quiz = fresh["quiz"][0]
    fresh_quiz["options"][0] = "Every 30 days"
    fresh_quiz["correct_answer"] = "Every 30 days"
    fresh_quiz["explanation"] = "The password policy requires a change every 30 days."
    fresh_quiz["source_document_code"] = "SEC-v3"
    queue({"modules": [fresh_module], "quiz": [fresh_quiz]})
    r = client.post(f"/onboarding/plan/{plan['id']}/regenerate-affected?document_id={new_id}", headers=headers)
    assert r.status_code == 200, r.text
    new_plan = r.json()
    assert new_plan["id"] != plan["id"]
    assert "ITEMS TO REPLACE" in CALLS[-1]["user"]
    titles = [m["title"] for m in new_plan["modules"]]
    assert "Refund Escalation Procedure" in titles           # unaffected module kept
    assert any("30 days" in (m["purpose"] or "") for m in new_plan["modules"])
    assert new_plan["quizzes"][0]["correct_answer"] == "Every 30 days"
    actions = [a["action"] for a in client.get(f"/review/audit-trail/{plan['id']}", headers=headers).json()]
    assert "selective_regeneration" in actions

    # relink stale matrix rows to the active version
    rl = client.post(f"/documents/impact/{new_id}/relink-requirements", headers=headers)
    assert rl.status_code == 200 and "R001" in rl.json()["relinked"]


def test_consistency_check_flags_major_differences():
    client, headers, ids, tmp, _ = _setup_with_plan_on_v2()
    second = good_plan()
    second["modules"] = second["modules"][:1]        # run 2 forgets the escalation module
    second["assessments"] = []
    queue(good_plan(), second)
    r = client.post(f"/validation/consistency/{ids['employee']['id']}?runs=2", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] < 100
    dims = {d["dimension"] for d in body["major_differences"]}
    assert "module_categories" in dims
    listed = client.get(f"/validation/consistency/{ids['employee']['id']}", headers=headers).json()
    assert listed[0]["score"] == body["score"]
