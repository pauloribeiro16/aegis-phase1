"""Tests for filter_implementations."""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.implementations import filter_implementations
from aegis_phase1.v2.state import V2State

from .conftest import make_empty_state


def test_aws_kms_etc_returned_for_aws_tech(mock_state: V2State) -> None:
    result = filter_implementations(mock_state, "D-04")
    names = [i["name"] for i in result]
    assert "AWS Managed Security Services" in names
    assert "AWS KMS" in names
    assert "AWS S3" in names


def test_firebase_returns_partial_adequacy(mock_state: V2State) -> None:
    result = filter_implementations(mock_state, "D-04")
    fb = next(i for i in result if "Firebase" in i["name"])
    assert fb["adequacy"] == "PARTIAL"


def test_github_actions_returns_cicd(mock_state: V2State) -> None:
    result = filter_implementations(mock_state, "D-04")
    gha = next(i for i in result if "GitHub Actions" in i["name"])
    assert "D-07.3" in gha["covers"]


def test_covers_field_is_list(mock_state: V2State) -> None:
    result = filter_implementations(mock_state, "D-04")
    for impl in result:
        assert isinstance(impl["covers"], list)
        assert all(isinstance(c, str) for c in impl["covers"])


def test_adequacy_values_are_valid(mock_state: V2State) -> None:
    result = filter_implementations(mock_state, "D-04")
    valid = {"ADEQUATE", "PARTIAL", "MISSING"}
    for impl in result:
        assert impl["adequacy"] in valid


def test_returns_empty_when_no_tech_stack(mock_state: V2State) -> None:
    mock_state["company_context"].tech_stack = []
    assert filter_implementations(mock_state, "D-04") == []


def test_returns_empty_when_no_company_context() -> None:
    state = make_empty_state()
    assert filter_implementations(state, "D-04") == []


def test_dedupes_implementations(mock_state: V2State) -> None:
    """Two tech items that map to the same impl should not duplicate."""
    mock_state["company_context"].tech_stack = ["AWS", "aws-kms-via-tag"]

    result = filter_implementations(mock_state, "D-04")
    names = [i["name"] for i in result]
    assert names.count("AWS Managed Security Services") == 1


def test_unknown_tech_returns_empty(mock_state: V2State) -> None:
    mock_state["company_context"].tech_stack = ["PunchCards", "Mainframe"]

    result = filter_implementations(mock_state, "D-04")
    assert result == []


def test_sorted_by_name(mock_state: V2State) -> None:
    result = filter_implementations(mock_state, "D-04")
    names = [i["name"] for i in result]
    assert names == sorted(names)


def test_handles_none_company_context(mock_state: V2State) -> None:
    mock_state["company_context"] = None
    assert filter_implementations(mock_state, "D-04") == []