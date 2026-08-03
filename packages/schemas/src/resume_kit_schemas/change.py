"""Canonical change / diff domain models.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/schemas/models.py
#   (ResumeChange:896-920, ImproveDiffResult:923-928, ResumeFieldDiff:545-564,
#    ResumeDiffSummary:566-575)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Ported the diff/change domain models out of the HTTP-DTO file and
#   re-namespaced them canonically. ``ResumeChange`` -> ``ChangeProposal``
#   (list-``original``-only-for-reorder validator preserved exactly);
#   ``ResumeFieldDiff`` -> ``Diff``; ``ResumeDiffSummary`` preserved;
#   ``ImproveDiffResult`` -> ``ChangeSet`` (with canonical aliases retained).
#   No transport concerns (request_id/resume_id/job_id) are carried.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .common import Warning

ChangeAction = Literal["replace", "append", "reorder", "add_skill"]
ChangeType = Literal["added", "removed", "modified"]
Confidence = Literal["low", "medium", "high"]
FieldType = Literal[
    "skill",
    "description",
    "summary",
    "certification",
    "experience",
    "education",
    "project",
    "language",
    "award",
]


class ChangeProposal(BaseModel):
    """A single targeted change proposed against a resume field.

    Ported from upstream ``ResumeChange``. The ``original`` verification value
    may be a list only for the ``reorder`` action; for the text actions a list
    would silently bypass the replace-verification gate, so it is rejected at
    parse time (behavior preserved from upstream).
    """

    path: str = Field(
        description="Dot+bracket path, e.g. 'workExperience[0].description[1]'."
    )
    action: ChangeAction
    original: str | list[str] | None = Field(
        default=None,
        description=(
            "Current text at path, for verification. May be a list (the current "
            "items) only for the reorder action."
        ),
    )
    value: str | list[str] = Field(description="New content.")
    reason: str = Field(description="Why this change helps match the job.")

    @model_validator(mode="after")
    def _list_original_only_for_reorder(self) -> ChangeProposal:
        if isinstance(self.original, list) and self.action != "reorder":
            raise ValueError("'original' may be a list only for the reorder action")
        return self


class Diff(BaseModel):
    """A single realized field-level change record.

    Ported from upstream ``ResumeFieldDiff`` — describes a change that was
    computed/applied (as opposed to :class:`ChangeProposal`, which is proposed).
    """

    field_path: str = Field(description="e.g. 'workExperience[0].description[2]'.")
    field_type: FieldType
    change_type: ChangeType
    original_value: str | None = None
    new_value: str | None = None
    confidence: Confidence = "medium"


class ResumeDiffSummary(BaseModel):
    """Aggregate statistics describing a set of diffs. Ported from upstream."""

    total_changes: int
    skills_added: int
    skills_removed: int
    descriptions_modified: int
    certifications_added: int
    high_risk_changes: int


class ChangeSet(BaseModel):
    """A collection of proposed changes plus their realized diffs.

    Adapted from upstream ``ImproveDiffResult`` (which carried only the proposal
    list and strategy notes). Enriched here with the computed ``diffs``,
    ``summary``, and structured ``warnings`` so the change set is a self-
    contained domain artifact.
    """

    changes: list[ChangeProposal] = Field(default_factory=list)
    strategy_notes: str = Field(default="")
    diffs: list[Diff] = Field(default_factory=list)
    summary: ResumeDiffSummary | None = None
    warnings: list[Warning] = Field(default_factory=list)


# Canonical alias retaining the upstream name.
ResumeChange = ChangeProposal
"""Alias for :class:`ChangeProposal` using the upstream ``ResumeChange`` name."""
