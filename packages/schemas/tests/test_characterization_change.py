"""Characterization tests locking upstream change/diff schema behavior.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/schemas/models.py (ResumeChange:896-920)
#   and apps/backend/tests/unit/test_resume_diff.py (diff field expectations)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Retargeted to canonical ``ChangeProposal``/``Diff`` names; locks the
#   "list ``original`` only for reorder" validator that the upstream verification
#   gate depends on.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import ChangeProposal, Diff, ResumeChange


def test_list_original_allowed_for_reorder() -> None:
    change = ChangeProposal.model_validate(
        {
            "path": "workExperience[0].description",
            "action": "reorder",
            "original": ["a", "b"],
            "value": ["b", "a"],
            "reason": "reorder for impact",
        }
    )
    assert change.original == ["a", "b"]


@pytest.mark.parametrize("action", ["replace", "append", "add_skill"])
def test_list_original_rejected_for_non_reorder(action: str) -> None:
    with pytest.raises(ValidationError, match="only for reorder/remove actions"):
        ChangeProposal.model_validate(
            {
                "path": "workExperience[0].description[0]",
                "action": action,
                "original": ["a", "b"],
                "value": "new",
                "reason": "x",
            }
        )


def test_string_original_allowed_for_replace() -> None:
    change = ResumeChange.model_validate(
        {
            "path": "summary",
            "action": "replace",
            "original": "old",
            "value": "new",
            "reason": "clearer",
        }
    )
    assert change.original == "old"


def test_diff_defaults_confidence_to_medium() -> None:
    diff = Diff.model_validate(
        {
            "field_path": "additional.technicalSkills[0]",
            "field_type": "skill",
            "change_type": "added",
        }
    )
    assert diff.confidence == "medium"


def test_diff_rejects_unknown_field_type() -> None:
    with pytest.raises(ValidationError):
        Diff.model_validate(
            {"field_path": "x", "field_type": "nonsense", "change_type": "added"}
        )


def test_resume_change_is_alias_of_change_proposal() -> None:
    assert ResumeChange is ChangeProposal
