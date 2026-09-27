"""Tests for python_validation/contradiction_detector.py (run: pytest tests/)."""
from types import SimpleNamespace as R

from python_validation.contradiction_detector import detect_contradictions

SOURCE = (
    "All employees must change their system password every 45 days. "
    "Minimum password length is 12 characters. "
    "Company laptops must have antivirus software installed and updated daily. "
    "Optional: join the monthly security newsletter."
)


def test_value_conflict_detected():
    plan = {"modules": [{"title": "Passwords", "purpose": "Employees must change their system password every 90 days."}]}
    result = detect_contradictions(plan, SOURCE)
    assert any(c["conflict_type"] == "Value conflict" for c in result["contradictions"])


def test_rule_conflict_detected():
    plan = {"modules": [{"title": "Devices", "purpose": "Antivirus software on company laptops is optional."}]}
    result = detect_contradictions(plan, SOURCE)
    assert any(c["conflict_type"] == "Rule conflict" for c in result["contradictions"])


def test_unrelated_must_and_optional_do_not_conflict():
    # old bug: "must" anywhere in the plan + "optional" anywhere in the source = contradiction
    plan = {"modules": [{"title": "CRM", "purpose": "You must log every customer call in the CRM."}]}
    result = detect_contradictions(plan, SOURCE)
    assert result["contradictions"] == []


def test_matching_statement_is_clean():
    plan = {"modules": [{"title": "Passwords", "purpose": "Change your system password every 45 days; minimum length is 12 characters."}]}
    result = detect_contradictions(plan, SOURCE)
    assert result["contradictions"] == []


def test_optional_item_for_mandatory_requirement():
    reqs = [R(requirement_code="R001", policy_requirement="Complete information security training",
              process_requirement=None, competency=None, assessment_requirement=None, mandatory=True)]
    plan = {"checklist": [{"activity": "Complete information security training", "required": False,
                           "source_requirement_code": "R001"}]}
    result = detect_contradictions(plan, "", reqs)
    assert any(c["conflict_type"] == "Mandatory status conflict" for c in result["contradictions"])
