"""Tests for the freedom 0-10 policy ladder and the F10 factual-block invariant."""

from __future__ import annotations

import pytest
from resume_kit_policy.path_policy import (
    FREEDOM_MAX,
    FREEDOM_MIN,
    evaluate_change_policy,
    is_path_allowed_at_freedom,
)
from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.results import PolicyReasonCode


def _change(path: str, action: str = "replace") -> ChangeProposal:
    return ChangeProposal(
        path=path,
        action=action,  # type: ignore[arg-type]
        original=None,
        value="new value",
        reason="test",
    )


# ---------------------------------------------------------------------------
# Freedom ladder boundaries
# ---------------------------------------------------------------------------

# (path, first freedom level at which it becomes editable)
_UNLOCK_TABLE = [
    ("additional.technicalSkills", 0),
    ("additional.languages", 2),
    ("additional.certificationsTraining", 2),
    ("additional.awards", 2),
    ("workExperience[0].description[1]", 4),
    ("personalProjects[0].description", 4),
    ("summary", 6),
    ("education[0].description", 8),
]


@pytest.mark.parametrize("path,unlock", _UNLOCK_TABLE)
def test_editable_exactly_at_and_above_unlock_level(path: str, unlock: int) -> None:
    for level in range(FREEDOM_MIN, FREEDOM_MAX + 1):
        expected = level >= unlock
        assert is_path_allowed_at_freedom(path, level) is expected


@pytest.mark.parametrize("path,unlock", _UNLOCK_TABLE)
def test_below_unlock_is_freedom_too_low(path: str, unlock: int) -> None:
    if unlock == FREEDOM_MIN:
        pytest.skip("no level below the minimum unlock")
    decision = evaluate_change_policy(_change(path), unlock - 1)
    assert decision.allowed is False
    assert decision.reason_code is PolicyReasonCode.FREEDOM_TOO_LOW


@pytest.mark.parametrize("path,unlock", _UNLOCK_TABLE)
def test_at_unlock_is_allowed(path: str, unlock: int) -> None:
    decision = evaluate_change_policy(_change(path), unlock)
    assert decision.allowed is True
    assert decision.reason_code is PolicyReasonCode.ALLOWED
    assert decision.freedom_level == unlock
    assert decision.path == path


def test_f0_is_skills_only() -> None:
    assert evaluate_change_policy(_change("additional.technicalSkills"), 0).allowed
    for path in ("additional.languages", "summary", "workExperience[0].description"):
        decision = evaluate_change_policy(_change(path), 0)
        assert decision.allowed is False
        assert decision.reason_code is PolicyReasonCode.FREEDOM_TOO_LOW


def test_f10_allows_all_editorial_paths() -> None:
    for path, _ in _UNLOCK_TABLE:
        decision = evaluate_change_policy(_change(path), FREEDOM_MAX)
        assert decision.allowed is True, path


# ---------------------------------------------------------------------------
# Invariant: factual identity fields blocked at EVERY freedom level, incl. F10
# ---------------------------------------------------------------------------

_FACTUAL_PATHS = [
    "personalInfo.name",
    "workExperience[0].company",
    "workExperience[0].title",
    "workExperience[0].years",
    "workExperience[0].location",
    "personalProjects[0].role",
    "education[0].degree",
    "education[0].institution",
    "education[0].years",
    "workExperience[0].github",
    "workExperience[0].website",
    "workExperience[0].id",
    "customSections.volunteer",
    "sectionMeta.order",
]


@pytest.mark.parametrize("path", _FACTUAL_PATHS)
def test_factual_fields_blocked_at_every_freedom_level(path: str) -> None:
    for level in range(FREEDOM_MIN, FREEDOM_MAX + 1):
        decision = evaluate_change_policy(_change(path), level)
        assert decision.allowed is False, (path, level)


@pytest.mark.parametrize("path", _FACTUAL_PATHS)
def test_factual_fields_blocked_at_f10(path: str) -> None:
    decision = evaluate_change_policy(_change(path), FREEDOM_MAX)
    assert decision.allowed is False
    assert decision.reason_code in (
        PolicyReasonCode.BLOCKED_FIELD,
        PolicyReasonCode.BLOCKED_PATH,
    )


def test_blocked_prefix_reports_blocked_field_reason() -> None:
    # personalInfo is a blocked prefix -> caught by is_path_blocked.
    decision = evaluate_change_policy(_change("personalInfo.name"), FREEDOM_MAX)
    assert decision.reason_code is PolicyReasonCode.BLOCKED_FIELD


def test_unknown_non_factual_path_is_blocked_path() -> None:
    decision = evaluate_change_policy(_change("nonexistent.field"), FREEDOM_MAX)
    assert decision.allowed is False
    assert decision.reason_code is PolicyReasonCode.BLOCKED_PATH


def test_education_description_editable_at_f10_but_degree_never() -> None:
    assert evaluate_change_policy(_change("education[0].description"), 10).allowed
    assert not evaluate_change_policy(_change("education[0].degree"), 10).allowed


def test_freedom_clamped_out_of_range() -> None:
    high = evaluate_change_policy(_change("additional.technicalSkills"), 99)
    assert high.freedom_level == FREEDOM_MAX
    low = evaluate_change_policy(_change("additional.technicalSkills"), -5)
    assert low.freedom_level == FREEDOM_MIN
    assert low.allowed is True  # skills editable at F0


def test_decision_carries_change_and_action() -> None:
    change = _change("additional.technicalSkills", action="add_skill")
    decision = evaluate_change_policy(change, 0)
    assert decision.change is change
    assert decision.action == "add_skill"
