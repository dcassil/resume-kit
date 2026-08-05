"""ScoreDoc: the canonical ATS-view projection of a resume (RIT-I-0017).

Per RIT-A-0002, scoring is re-seated off a derived representation instead of the
build model. ``ScoreDoc`` is that derived view — canonical ATS sections,
extracted entities (name/contact/links, per-role dates -> computed
years-of-experience, degrees), and a zoned keyword index (token -> zone). It is
produced by the pure deterministic projection ``project_scoredoc`` (RIT-T-0106,
in ``packages/scoring``); nothing authors a ``ScoreDoc`` by hand.

This module is **pure data**: no projection logic, no I/O, no clock reads. Any
date-derived values (e.g. ``duration_months``, ``total_years_experience``) are
stored as data computed by the caller from a supplied reference date, never
derived at read time — so the models are deterministic and frozen. Purely
additive: ``resume.py`` (BuildDoc), the renderer, and export are unchanged.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

#: Schema/format version for the ScoreDoc envelope.
SCOREDOC_SCHEMA_VERSION = 1


class KeywordZone(StrEnum):
    """Weighted zones a surfaced token can occupy in the ATS view.

    Scoring weights these differently (experience > skills_list > summary) so a
    skill demonstrated in experience outranks one sitting in a bare list.
    """

    EXPERIENCE = "experience"
    SKILLS_LIST = "skills_list"
    SUMMARY = "summary"
    EDUCATION = "education"
    PROJECTS = "projects"
    OTHER = "other"


class ScoreRole(BaseModel):
    """One employment role as the ATS sees it, with computed duration.

    ``start_date`` / ``end_date`` are the raw strings the projection parsed
    from; ``duration_months`` is the caller-computed span (``None`` when the
    dates could not be parsed, so the role is excluded from YoE totals).
    """

    model_config = {"frozen": True}

    title: str = ""
    company: str = ""
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None


class ScoreDegree(BaseModel):
    """One education entry as the ATS sees it."""

    model_config = {"frozen": True}

    degree: str = ""
    institution: str = ""


class ScoreEntities(BaseModel):
    """Entities extracted from the resume for ATS-view scoring/reporting."""

    model_config = {"frozen": True}

    name: str = ""
    email: str = ""
    phone: str = ""
    links: list[str] = Field(default_factory=list)
    roles: list[ScoreRole] = Field(default_factory=list)
    total_years_experience: float = 0.0
    education: list[ScoreDegree] = Field(default_factory=list)


class ScoreSection(BaseModel):
    """A canonical ATS section segmented from the resume."""

    model_config = {"frozen": True}

    name: str = ""
    zone: KeywordZone = KeywordZone.OTHER
    text: str = ""
    source_section_type: str | None = None


class ZonedKeywordIndex(BaseModel):
    """Bidirectional token<->zone index harvested from all zones.

    ``token_zones`` maps each surfaced token to the zones it appears in;
    ``zone_tokens`` maps each zone to its token list. Both directions are stored
    so keyword/skill scoring can weight by zone without re-deriving either map.
    """

    model_config = {"frozen": True}

    token_zones: dict[str, list[KeywordZone]] = Field(default_factory=dict)
    zone_tokens: dict[KeywordZone, list[str]] = Field(default_factory=dict)


class ScoreDoc(BaseModel):
    """The canonical ATS view derived from a resume (BuildDoc)."""

    model_config = {"frozen": True}

    schema_version: int = SCOREDOC_SCHEMA_VERSION
    sections: list[ScoreSection] = Field(default_factory=list)
    entities: ScoreEntities = Field(default_factory=ScoreEntities)
    zoned_index: ZonedKeywordIndex = Field(default_factory=ZonedKeywordIndex)
