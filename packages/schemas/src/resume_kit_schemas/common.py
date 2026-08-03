"""Shared canonical primitives: severity, warnings, and artifact metadata.

These are New resume-kit domain primitives with no upstream equivalent. They
carry no HTTP/transport concerns: ``Warning`` is a structured diagnostic record
(the upstream code passed bare ``list[str]`` warnings through API DTOs), and
``Artifact`` is generic produced-output metadata used across analysis, change,
and evidence results.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """Diagnostic severity, ordered least-to-most serious."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Warning(BaseModel):
    """A structured, non-fatal diagnostic emitted by an analysis or change step.

    Replaces the upstream bare-string warning lists with a typed record so
    downstream consumers can filter by severity and trace the offending field.
    """

    model_config = ConfigDict(frozen=True)

    message: str = Field(description="Human-readable description of the concern.")
    severity: Severity = Field(
        default=Severity.WARNING, description="How serious the concern is."
    )
    code: str | None = Field(
        default=None,
        description="Stable machine-readable identifier for this class of warning.",
    )
    field_path: str | None = Field(
        default=None,
        description="Dot+bracket path to the resume field the warning refers to, if any.",
    )


class ArtifactKind(StrEnum):
    """The kind of produced artifact."""

    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    OUTREACH_MESSAGE = "outreach_message"
    ANALYSIS_REPORT = "analysis_report"
    CHANGE_SET = "change_set"
    OTHER = "other"


class Artifact(BaseModel):
    """Metadata describing a generated output (a produced document or report).

    Domain-only: it records *what* was produced and provenance-relevant
    metadata, never transport concerns such as URLs, HTTP status, or DB ids.
    """

    kind: ArtifactKind = Field(description="What sort of artifact this is.")
    title: str | None = Field(default=None, description="Human-facing artifact title.")
    content: str | None = Field(
        default=None,
        description="Inline artifact content when the artifact is textual (e.g. markdown).",
    )
    media_type: str = Field(
        default="text/markdown",
        description="IANA media type of ``content`` when present.",
    )
    created_at: datetime | None = Field(
        default=None, description="When the artifact was produced, if known."
    )
    warnings: list[Warning] = Field(
        default_factory=list, description="Non-fatal concerns raised while producing this artifact."
    )
