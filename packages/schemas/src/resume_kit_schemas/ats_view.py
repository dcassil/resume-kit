"""AtsViewReport: the read-only "what the ATS sees" report (RIT-T-0109).

A deterministic, provider-free projection of a resume's ATS view, derived
entirely from a :class:`~resume_kit_schemas.scoredoc.ScoreDoc`. It re-exposes the
canonical ATS sections, the extracted entities (name/contact/links, per-role
dates -> computed years-of-experience, degrees), and the zoned keyword breakdown
so a caller can read exactly what an ATS is likely to parse — without any
scoring, alignment, or advice attached.

Like ``ScoreDoc`` this module is **pure data**: no projection logic, no I/O, no
clock reads. All date-derived values it carries were computed by the projection
using a caller-supplied reference date, so the model is deterministic and frozen.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .scoredoc import KeywordZone, ScoreEntities, ScoreSection

#: Schema/format version for the AtsViewReport envelope.
ATS_VIEW_SCHEMA_VERSION = 1

#: Plain-language disclaimer carried on every report. A strong ATS/keyword match
#: improves parseability but is not a guarantee that a recruiter advances the
#: application — the report states this explicitly so no surface implies more.
ATS_VIEW_DISCLAIMER = (
    "This report shows what an ATS is likely to parse from your resume. A strong "
    "ATS/keyword match improves parseability and how reliably your experience is "
    "surfaced, but it does not guarantee that a recruiter will advance your "
    "application."
)


class AtsViewReport(BaseModel):
    """The read-only ATS-view report derived from a resume's ScoreDoc."""

    model_config = {"frozen": True}

    schema_version: int = ATS_VIEW_SCHEMA_VERSION
    sections: list[ScoreSection] = Field(
        default_factory=list,
        description="Canonical ATS sections segmented from the resume, in order.",
    )
    entities: ScoreEntities = Field(
        default_factory=ScoreEntities,
        description=(
            "Entities the ATS extracted: name/contact/links, per-role dates with "
            "computed years-of-experience, and degrees."
        ),
    )
    keyword_zones: dict[KeywordZone, list[str]] = Field(
        default_factory=dict,
        description="Zoned keyword breakdown: detected keyword tokens grouped by ScoreDoc zone.",
    )
    disclaimer: str = Field(
        default=ATS_VIEW_DISCLAIMER,
        description=(
            "Plain-language note that a strong ATS match aids parseability but does "
            "not guarantee a recruiter advances the application."
        ),
    )
