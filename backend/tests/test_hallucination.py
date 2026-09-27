"""Tests for python_validation/hallucination_detector.py (run: pytest tests/)."""
from types import SimpleNamespace as R

from python_validation.hallucination_detector import detect_hallucinations

REQS = [R(requirement_code="R0022", policy_requirement="Follow content governance, security, backup, and update policies.",
          process_requirement="Handle CMS updates, migrations, troubleshooting, and performance optimization.",
          competency="CMS security, version control, debugging, SEO basics", assessment_requirement=None,
          source_section="CMS Operations", due_stage="Development Stage")]
SOURCE = "CMS security, updates, migration, troubleshooting, and performance optimization requirements."


def test_paraphrased_grounded_module_is_not_flagged():
    plan = {"modules": [{"title": "Securing and Maintaining CMS Sites",
                         "purpose": "Apply security, backup and update practices and handle migrations.",
                         "source_requirement_code": "R0022"}]}
    result = detect_hallucinations(plan, SOURCE, REQS, ["CMS-002"])
    assert result["unsupported_items"] == []


def test_invented_value_and_topic_is_flagged():
    plan = {"modules": [{"title": "Expense Claims",
                         "purpose": "Submit expense claims within 48 hours and finish payment card certification."}]}
    result = detect_hallucinations(plan, SOURCE, REQS, ["CMS-002"])
    assert len(result["unsupported_items"]) == 1
    assert any("48 hours" in r for r in result["unsupported_items"][0]["reasons"])


def test_citation_from_other_role_is_flagged():
    plan = {"checklist": [{"activity": "Handle CMS updates", "source_requirement_code": "R0023"}]}
    result = detect_hallucinations(plan, SOURCE, REQS, ["CMS-002"])
    assert len(result["unsupported_items"]) == 1


def test_no_sources_at_all_is_insufficient_not_unsupported():
    result = detect_hallucinations({"modules": [{"title": "Anything"}]}, "", [], [])
    assert result["status"] == "insufficient_source"
    assert result["unsupported_items"] == []
