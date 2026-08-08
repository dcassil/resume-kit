"""Tests for budget violation schema contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import BudgetViolation


def test_budget_violation_round_trips_through_dump() -> None:
    violation = BudgetViolation(
        dimension="skills",
        limit=2,
        actual=4,
        overage=2,
    )

    restored = BudgetViolation.model_validate(violation.model_dump())

    assert restored == violation
    assert restored.model_dump(mode="json") == {
        "dimension": "skills",
        "location": None,
        "limit": 2,
        "actual": 4,
        "overage": 2,
    }


def test_budget_violation_requires_positive_actual_minus_limit_overage() -> None:
    with pytest.raises(ValidationError):
        BudgetViolation(
            dimension="summary_words",
            limit=8,
            actual=10,
            overage=1,
        )

    with pytest.raises(ValidationError):
        BudgetViolation(
            dimension="summary_words",
            limit=10,
            actual=10,
            overage=0,
        )
