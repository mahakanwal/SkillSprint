"""Coverage Score = covered mandatory / total mandatory x 100 (SRS Step 29)."""

from types import SimpleNamespace as R

from python_validation.coverage_checker import check_coverage


def _req(code, mandatory, policy):
    return R(requirement_code=code, mandatory=mandatory, policy_requirement=policy,
             process_requirement=None, competency=None)


REQS = [
    _req("R1", True, "Password policy"),
    _req("R2", True, "Refund escalation"),
    _req("R3", True, "Complaint logging"),
    _req("R4", False, "Newsletter subscription"),
]


def test_srs_example_three_mandatory_two_covered():
    plan = {"modules": [{"title": "a", "source_requirement_code": "R1"},
                        {"title": "b", "source_requirement_code": "R2"}]}
    result = check_coverage(REQS, plan)
    assert result["score"] == round(2 / 3 * 100, 2)
    assert result["missing"] == ["R3"]
    assert result["mandatory_total"] == 3


def test_optional_requirements_do_not_lower_the_score():
    plan = {"modules": [{"title": x, "source_requirement_code": x} for x in ("R1", "R2", "R3")]}
    result = check_coverage(REQS, plan)
    assert result["score"] == 100 and result["optional_covered"] == 0


def test_same_requirement_in_two_modules_is_a_duplicate():
    plan = {"modules": [{"title": "a", "source_requirement_code": "R1"}, {"title": "b", "source_requirement_code": "R1"}]}
    assert check_coverage(REQS, plan)["duplicates"] == [{"requirement_code": "r1", "modules": 2}]
