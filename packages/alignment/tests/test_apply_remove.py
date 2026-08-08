"""Tests for explicit list-item removal in the shared apply engine."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from resume_kit_alignment.apply import apply_diffs
from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.results import PolicyReasonCode

FREEDOM_FIT = 6
FREEDOM_MAX = 10


@pytest.fixture
def sample_resume() -> dict[str, Any]:
    return {
        "summary": "Backend engineer with Python and FastAPI experience.",
        "workExperience": [
            {
                "title": "Senior Backend Engineer",
                "company": "Acme Corp",
                "description": [
                    "Built REST APIs using Python and FastAPI.",
                    "Maintained team calendar and email workflows.",
                    "Reduced API latency 35% with Postgres tuning.",
                    "Prepared weekly spreadsheet reports.",
                ],
            }
        ],
        "additional": {
            "technicalSkills": ["Python", "FastAPI", "Email", "PostgreSQL"],
        },
    }


def test_remove_one_skill_preserves_remaining_order(
    sample_resume: dict[str, Any],
) -> None:
    original = sample_resume["additional"]["technicalSkills"]
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="remove",
            original=original,
            value=["Email"],
            reason="Trim low-value skill.",
        )
    ]

    result, applied, rejected = apply_diffs(
        sample_resume, changes, freedom=FREEDOM_FIT
    )

    assert len(applied) == 1
    assert rejected == []
    assert result["additional"]["technicalSkills"] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
    ]


def test_remove_two_bullets_preserves_remaining_order(
    sample_resume: dict[str, Any],
) -> None:
    original = sample_resume["workExperience"][0]["description"]
    changes = [
        ChangeProposal(
            path="workExperience[0].description",
            action="remove",
            original=original,
            value=[
                "Maintained team calendar and email workflows.",
                "Prepared weekly spreadsheet reports.",
            ],
            reason="Trim lower-value bullets.",
        )
    ]

    result, applied, rejected = apply_diffs(
        sample_resume, changes, freedom=FREEDOM_FIT
    )

    assert len(applied) == 1
    assert rejected == []
    assert result["workExperience"][0]["description"] == [
        "Built REST APIs using Python and FastAPI.",
        "Reduced API latency 35% with Postgres tuning.",
    ]


def test_remove_rejects_original_mismatch_without_mutation(
    sample_resume: dict[str, Any],
) -> None:
    before = copy.deepcopy(sample_resume)
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="remove",
            original=["Python", "FastAPI", "PostgreSQL", "Email"],
            value=["Email"],
            reason="Mismatched original order.",
        )
    ]

    result, applied, rejected = apply_diffs(
        sample_resume, changes, freedom=FREEDOM_FIT
    )

    assert applied == []
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.ORIGINAL_MISMATCH
    assert result == before


def test_remove_rejects_missing_value_item_without_mutation(
    sample_resume: dict[str, Any],
) -> None:
    before = copy.deepcopy(sample_resume)
    original = sample_resume["additional"]["technicalSkills"]
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="remove",
            original=original,
            value=["Kubernetes"],
            reason="Missing item.",
        )
    ]

    result, applied, rejected = apply_diffs(
        sample_resume, changes, freedom=FREEDOM_FIT
    )

    assert applied == []
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.ORIGINAL_MISMATCH
    assert result == before


def test_remove_rejects_scalar_target(
    sample_resume: dict[str, Any],
) -> None:
    changes = [
        ChangeProposal(
            path="summary",
            action="remove",
            original=None,
            value=["Backend engineer with Python and FastAPI experience."],
            reason="Scalar paths cannot be removed as lists.",
        )
    ]

    _result, applied, rejected = apply_diffs(
        sample_resume, changes, freedom=FREEDOM_FIT
    )

    assert applied == []
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.UNSUPPORTED_ACTION


def test_remove_on_factual_path_is_rejected_by_policy_gate(
    sample_resume: dict[str, Any],
) -> None:
    before = copy.deepcopy(sample_resume)
    changes = [
        ChangeProposal(
            path="workExperience[0].company",
            action="remove",
            original=None,
            value=["Acme Corp"],
            reason="Blocked factual field.",
        )
    ]

    result, applied, rejected = apply_diffs(
        sample_resume, changes, freedom=FREEDOM_MAX
    )

    assert applied == []
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.BLOCKED_FIELD
    assert result == before
