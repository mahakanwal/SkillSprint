"""Unit tests for schema, quiz, sequence and consistency checks (SRS 21-27, 38)."""

from types import SimpleNamespace as R

from python_validation.consistency_checker import check_consistency
from python_validation.quiz_validator import validate_quiz
from python_validation.schema_validator import validate_plan_schema
from python_validation.sequence_validator import validate_sequence


def test_schema_detects_types_enums_and_duplicates():
    plan = {"modules": [{"module_code": "M1", "title": "Intro", "purpose": "Basics", "learning_objectives": ["x"],
                         "due_stage": "Day 1", "mandatory": "yes please"},
                        {"module_code": "M1", "title": "Again", "purpose": "More", "learning_objectives": ["y"],
                         "due_stage": "Week 1", "mandatory": True}],
            "checklist": [], "tasks": [],
            "quiz": [{"question_text": "Q?", "question_type": "essay", "options": [], "correct_answer": "x"}]}
    result = validate_plan_schema(plan)
    paths = {e["path"] for e in result["structural_errors"]}
    assert "modules[0].mandatory" in paths and "quiz[0].question_type" in paths
    assert not result["valid"]


def test_quiz_distractor_that_source_states_is_flagged():
    plan = {"quiz": [{"question_text": "How often must passwords change?", "question_type": "multiple_choice",
                      "options": ["Every 45 days", "Every 90 days"], "correct_answer": "Every 45 days",
                      "explanation": "policy", "difficulty": "Beginner", "source_requirement_code": "R1",
                      "source_document_code": "SEC", "source_section": "1"}]}
    corpus = "Passwords must change every 45 days. The old policy said every 90 days."
    issues = validate_quiz(plan, corpus)["issues"]
    assert issues and "Distractor" in " ".join(issues[0]["problems"])


def test_prerequisite_from_source_text_is_enforced():
    plan = {"modules": [
        {"module_code": "M1", "title": "Customer data access in the CRM", "purpose": "Access customer data in CRM",
         "due_stage": "Day 1", "mandatory": True},
        {"module_code": "M2", "title": "Information Security Basics", "purpose": "Security basics",
         "due_stage": "Week 1", "mandatory": True}]}
    corpus = "Employees must first complete the 'Information Security Basics' module before being granted CRM access."
    issues = " ".join(i["issue"] for i in validate_sequence(plan, [], corpus)["issues"])
    assert "must come first" in issues


def test_consistency_compares_fields_with_the_matrix():
    req = R(requirement_code="R1", mandatory=True, due_stage="Day 1", source_section="4.2",
            policy_requirement="p", process_requirement=None, competency=None)
    plan = {"modules": [{"module_code": "M1", "title": "t", "mandatory": False, "due_stage": "Week 1",
                         "source_requirement_code": "R1", "source_document_code": "SOP-07", "source_section": "4.2"}]}
    result = check_consistency(plan, [req], {"R1": "SOP-07"})
    fields = {c["field"]: c["result"] for c in result["comparisons"]}
    assert fields == {"Requirement ID": "Match", "Source Document": "Match", "Source Section": "Match",
                      "Mandatory": "Mismatch", "Due Stage": "Mismatch"}
    assert result["score"] < 100
