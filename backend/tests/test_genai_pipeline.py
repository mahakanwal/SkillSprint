"""GenAI pipeline: prompt templates, JSON parsing, retry + fallback (SRS 37-41, lxiii-lxv)."""

import tempfile


from genai_pipeline.generator import GeneratorError, _extract_json
from genai_pipeline.prompt_manager import get_prompt, list_versions, render
from tests.helpers import CALLS, bootstrap_admin, get_client, good_plan, queue, seed_role


def test_prompt_templates_are_versioned_files():
    p = get_prompt("onboarding_plan")
    assert p["version"] == list_versions()["active"]["onboarding_plan"]
    assert "untrusted DATA" in p["system"] and "{{requirements}}" in p["user_template"]
    old = get_prompt("onboarding_plan", "v1.0")
    assert old["system"] != p["system"]
    assert "Not specified" in render("Level: {{experience_level}}")


def test_json_extraction_handles_fences_and_chatter():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Sure! Here it is: {"a": 2} Hope it helps') == {"a": 2}
    try:
        _extract_json("no json here")
        raise AssertionError("expected GeneratorError")
    except GeneratorError:
        pass


def test_primary_model_failure_falls_back_and_is_recorded():
    client = get_client()
    headers = bootstrap_admin(client)
    ids = seed_role(client, headers, tempfile.mkdtemp())
    # primary model fails on every retry (3x), fallback succeeds
    queue(RuntimeError("timeout"), RuntimeError("quota"), RuntimeError("timeout"), good_plan())
    r = client.post(f"/onboarding/generate/{ids['employee']['id']}", headers=headers)
    assert r.status_code == 200, r.text
    models = [c["model"] for c in CALLS]
    assert len(set(models)) == 2 and r.json()["model_used"] == models[-1]


def test_api_failure_is_a_clean_error_not_a_crash():
    client = get_client()
    headers = bootstrap_admin(client)
    ids = seed_role(client, headers, tempfile.mkdtemp())
    queue(*[RuntimeError("down")] * 6)
    r = client.post(f"/onboarding/generate/{ids['employee']['id']}", headers=headers)
    assert r.status_code == 422
    assert "failed" in r.json()["detail"].lower()
