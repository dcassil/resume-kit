"""Candidate-evidence domain models.

New resume-kit subsystem (no upstream equivalent). ``CandidateEvidence`` is the
grounding record that resume claims are checked against by the truth-validation
engine and the provenance classifier.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EvidenceKind(StrEnum):
    """The kind of source a piece of candidate evidence came from."""

    MASTER_RESUME = "master_resume"
    WORK_HISTORY = "work_history"
    PROJECT = "project"
    CERTIFICATION = "certification"
    EDUCATION = "education"
    SKILL = "skill"
    USER_STATEMENT = "user_statement"
    OTHER = "other"


class CandidateEvidence(BaseModel):
    """A single piece of ground-truth evidence about the candidate.

    Evidence is the substrate the truth-validation engine uses to classify
    :class:`~resume_kit_schemas.provenance.ClaimProvenance`. Each record is
    independently addressable via ``id`` so provenance records can reference it.
    """

    id: str = Field(description="Stable identifier for cross-referencing from claims.")
    kind: EvidenceKind = Field(description="What sort of source this evidence is.")
    content: str = Field(description="The evidence text (what the candidate can attest to).")
    source: str | None = Field(
        default=None, description="Where the evidence came from, e.g. a document name."
    )
    tags: list[str] = Field(
        default_factory=list, description="Free-form labels, e.g. skill names or employers."
    )
    user_confirmed: bool = Field(
        default=False,
        description="True when the candidate has explicitly attested to this evidence.",
    )
    recorded_at: datetime | None = Field(
        default=None, description="When the evidence was captured, if known."
    )
