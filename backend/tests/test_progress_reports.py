"""
Quiz taking, assessment scoring, progress assessment, weak areas,
recommendations (SRS 50, 53-56), dashboards (51-52, 60-61) and reports
with CSV export (62-63).
"""

import tempfile

from tests.helpers import bootstrap_admin, get_client, good_plan, login, queue, seed_role


def _setup():
    client = get_client()
    headers = bootstrap_admin(client)
    ids = seed_role(client, headers, tempfile.mkdtemp())
    queue(good_plan())
    plan = client.post(f"/onboarding/generate/{ids['employee']['id']}", headers=headers).json()
    return client, headers, ids, plan


def test_quiz_submission_scores_and_weak_areas():
    client, headers, ids, plan = _setup()
    emp = login(client, "ayesha@test.com", ids["employee_password"])
    q = plan["quizzes"][0]
    r = client.post(f"/onboarding/plan/{plan['id']}/quiz/submit", headers=emp,
                    json={"answers": [{"question_id": q["id"], "selected": ["Never"]}]})
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["is_correct"] is False
    assert r.json()["score"] == 0

    pa = client.get(f"/onboarding/plan/{plan['id']}/progress-assessment", headers=emp).json()
    assert pa["outcome"] in ("Requires Attention", "Behind Schedule")
    assert any(w["requirement_code"] == "R001" for w in pa["weak_areas"])
    types = {r["type"] for r in pa["recommendations"]}
    assert {"Revision module", "Additional quiz"} <= types
    assert pa["milestones"] and pa["quiz"]["score"] == 0

    # answer again correctly -> score updates, repeated error is remembered only when wrong twice
    client.post(f"/onboarding/plan/{plan['id']}/quiz/submit", headers=emp,
                json={"answers": [{"question_id": q["id"], "selected": "Every 45 days"}]})
    res = client.get(f"/onboarding/plan/{plan['id']}/quiz/results", headers=emp).json()
    assert res["score"] == 100 and res["attempt_count"] == 2


def test_assessment_scoring_and_completion():
    client, headers, ids, plan = _setup()
    a = plan["assessments"][0]
    bad = client.post(f"/onboarding/plan/{plan['id']}/assessment/{a['id']}/score", headers=headers, json={"score": 140})
    assert bad.status_code == 422
    ok = client.post(f"/onboarding/plan/{plan['id']}/assessment/{a['id']}/score", headers=headers, json={"score": 85})
    assert ok.json()["status"] == "Passed"

    emp = login(client, "ayesha@test.com", ids["employee_password"])
    assert client.post(f"/onboarding/plan/{plan['id']}/assessment/{a['id']}/score", headers=emp,
                       json={"score": 100}).status_code == 403
    for kind, key in (("module", "modules"), ("checklist", "checklist_items"), ("task", "tasks")):
        for item in plan[key]:
            client.patch(f"/onboarding/plan/{plan['id']}/progress/{kind}/{item['id']}", headers=emp,
                         json={"completion_status": "Completed"})
    client.post(f"/onboarding/plan/{plan['id']}/quiz/submit", headers=emp,
                json={"answers": [{"question_id": plan["quizzes"][0]["id"], "selected": ["Every 45 days"]}]})
    pa = client.get(f"/onboarding/plan/{plan['id']}/progress-assessment", headers=emp).json()
    assert pa["outcome"] == "Completed"
    assert client.get(f"/onboarding/plan/{plan['id']}", headers=emp).json()["progress_percent"] == 100


def test_dashboards_and_filters():
    client, headers, ids, plan = _setup()
    s = client.get("/dashboard/summary", headers=headers).json()
    assert s["plans"] == 1 and s["employees_with_plan"] == 1 and s["mandatory_requirements"] == 4
    assert s["obsolete_documents"] == 1
    roles = client.get("/dashboard/roles", headers=headers).json()
    cse = next(r for r in roles if r["role_name"] == "Customer Support Executive")
    assert cse["mandatory_requirements"] == 3 and cse["employees_with_plan"] == 1
    assert client.get("/dashboard/plans?search=ayesha", headers=headers).json()[0]["plan_id"] == plan["id"]
    assert client.get("/dashboard/plans?search=nobody", headers=headers).json() == []
    assert client.get("/dashboard/plans?policy=SEC-v2", headers=headers).json()
    cmp = client.get("/dashboard/compare?group_by=document_version", headers=headers).json()
    assert {c["group"] for c in cmp} >= {"SEC-v2@2.0", "SOP-07@1.0"}
    emp = login(client, "ayesha@test.com", ids["employee_password"])
    assert client.get("/dashboard/summary", headers=emp).status_code == 403


def test_reports_json_and_csv_export():
    client, headers, ids, plan = _setup()
    names = [r["name"] for r in client.get("/reports/", headers=headers).json()]
    assert "genai-python-comparison" in names and len(names) >= 10
    for name in names:
        r = client.get(f"/reports/{name}", headers=headers)
        assert r.status_code == 200, (name, r.text)
    comp = client.get("/reports/genai-python-comparison", headers=headers).json()
    assert comp["count"] == 3
    assert {"requirement_id", "python_expected_requirement", "genai_result", "match",
            "explanation_of_disagreement"} <= set(comp["rows"][0])
    csv = client.get("/reports/validation?format=csv", headers=headers)
    assert csv.headers["content-type"].startswith("text/csv")
    assert csv.content.startswith("﻿".encode("utf-8"))
    assert b"coverage_score" in csv.content
