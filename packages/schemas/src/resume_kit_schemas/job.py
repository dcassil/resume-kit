"""Canonical job-description domain models.

New resume-kit domain models. Upstream had no structured job-description domain
model — only HTTP DTOs (``JobUploadRequest``/``JobUploadResponse``) that are
intentionally excluded. These models capture the parsed structure a job posting
is analyzed against.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RequirementKind(StrEnum):
    """Whether a requirement is mandatory or preferred."""

    REQUIRED = "required"
    PREFERRED = "preferred"


class Requirement(BaseModel):
    """A single job requirement or qualification."""

    text: str = Field(description="The requirement statement as written or normalized.")
    kind: RequirementKind = Field(
        default=RequirementKind.REQUIRED,
        description="Whether this requirement is mandatory or merely preferred.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Skill/keyword terms extracted from this requirement.",
    )


class JobDescription(BaseModel):
    """A structured job description.

    Domain-only: it represents the parsed content of a posting, not any upload
    request, persistence id, or response envelope.
    """

    title: str = ""
    company: str = ""
    location: str | None = None
    raw_text: str = Field(
        default="", description="The original job-description text, if available."
    )
    summary: str = ""
    requirements: list[Requirement] = Field(
        default_factory=list,
        description="Required qualifications extracted from the posting.",
    )
    qualifications: list[Requirement] = Field(
        default_factory=list,
        description="Preferred / nice-to-have qualifications extracted from the posting.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="All salient skill/keyword terms extracted from the posting.",
    )
