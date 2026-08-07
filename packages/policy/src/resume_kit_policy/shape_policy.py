"""Canonical resume shape policy data and project overlay loading.

The shape policy is configuration consumed by later structure analysis stages.
It contains section ordering, heading aliases, the ``other`` fallback contract,
and budget thresholds that are informational only. It intentionally contains no
trim, delete, rank, or fix rules.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator
from resume_kit_schemas.canonical import CanonicalSection

__all__ = [
    "InformationalShapeBudgets",
    "ResumeShapePolicy",
    "default_shape_policy",
    "load_shape_policy",
    "normalize_section_heading",
    "overlay_shape_policy",
]

_WORKING_DIR_NAME = "resume-kit"
_CONFIG_FILE_NAME = "config.json"
_SHAPE_POLICY_CONFIG_KEYS: tuple[str, ...] = ("shape_policy", "resume_shape_policy")

_HEADING_TOKEN_RE = re.compile(r"[a-z0-9]+")


class InformationalShapeBudgets(BaseModel):
    """Non-enforcing resume shape budget thresholds.

    These values are report-only inputs for downstream analysis. They do not
    authorize trimming, deletion, ranking, or automatic fixes in this policy.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    enforcement: Literal["informational_only"] = "informational_only"
    max_skills: int | None = Field(default=30, ge=1)
    max_summary_words: int | None = Field(default=80, ge=1)
    max_summary_chars: int | None = Field(default=600, ge=1)
    max_bullets_per_role: int | None = Field(default=6, ge=1)
    max_pages: int | None = Field(default=2, ge=1)


class ResumeShapePolicy(BaseModel):
    """Data-only policy for canonical resume section shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_order: list[CanonicalSection]
    section_aliases: dict[str, CanonicalSection]
    allow_other: bool = True
    fallback_section: CanonicalSection = CanonicalSection.OTHER
    informational_budgets: InformationalShapeBudgets = Field(
        default_factory=InformationalShapeBudgets
    )

    @field_validator("section_aliases", mode="before")
    @classmethod
    def _normalize_alias_keys(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        normalized: dict[str, object] = {}
        for raw_key, raw_section in value.items():
            key = normalize_section_heading(str(raw_key))
            if key:
                normalized[key] = raw_section
        return normalized

    def canonical_section_for_heading(self, heading: str) -> CanonicalSection:
        """Return the configured canonical section for ``heading`` or fallback."""

        key = normalize_section_heading(heading)
        return self.section_aliases.get(key, self.fallback_section)

    @property
    def aliases(self) -> dict[str, CanonicalSection]:
        """Alias table using the ticket's shorter terminology."""

        return self.section_aliases


def normalize_section_heading(heading: str) -> str:
    """Normalize headings for case-insensitive policy table lookup."""

    return " ".join(_HEADING_TOKEN_RE.findall(heading.casefold()))


def default_shape_policy() -> ResumeShapePolicy:
    """Return the built-in canonical resume shape policy."""

    return ResumeShapePolicy(
        section_order=[
            CanonicalSection.BASICS,
            CanonicalSection.WORK,
            CanonicalSection.SKILLS,
            CanonicalSection.PROJECTS,
            CanonicalSection.EDUCATION,
            CanonicalSection.CERTIFICATIONS,
            CanonicalSection.AWARDS,
            CanonicalSection.PUBLICATIONS,
            CanonicalSection.VOLUNTEER,
            CanonicalSection.LANGUAGES,
            CanonicalSection.INTERESTS,
            CanonicalSection.REFERENCES,
            CanonicalSection.OTHER,
        ],
        section_aliases=_default_section_aliases(),
    )


def overlay_shape_policy(
    base: ResumeShapePolicy, override: Mapping[str, object]
) -> ResumeShapePolicy:
    """Apply a ``config.json`` shape-policy overlay to ``base``.

    ``section_aliases`` are merged over the defaults; scalar fields and
    ``section_order`` replace the default value; informational budgets are
    merged field-by-field. Unknown policy keys are rejected by the model after
    overlay.
    """

    data = base.model_dump(mode="python")
    remaining = dict(override)

    shorthand_aliases_override = remaining.pop("aliases", None)
    aliases_override = remaining.pop("section_aliases", None)
    if shorthand_aliases_override is not None or aliases_override is not None:
        aliases = cast(dict[str, object], dict(data["section_aliases"]))
        if shorthand_aliases_override is not None:
            if not isinstance(shorthand_aliases_override, Mapping):
                raise ValueError("shape_policy.aliases must be a JSON object.")
            aliases.update(cast(Mapping[str, object], shorthand_aliases_override))
        if aliases_override is not None:
            if not isinstance(aliases_override, Mapping):
                raise ValueError("shape_policy.section_aliases must be a JSON object.")
            aliases.update(cast(Mapping[str, object], aliases_override))
        data["section_aliases"] = aliases

    budgets_override = remaining.pop("informational_budgets", None)
    if budgets_override is not None:
        if not isinstance(budgets_override, Mapping):
            raise ValueError("shape_policy.informational_budgets must be a JSON object.")
        budgets = base.informational_budgets.model_dump(mode="python")
        budgets.update(cast(Mapping[str, object], budgets_override))
        data["informational_budgets"] = budgets

    data.update(remaining)
    return ResumeShapePolicy.model_validate(data)


def load_shape_policy(root: str | Path) -> ResumeShapePolicy:
    """Load the default shape policy plus optional ``config.json`` overlay.

    ``root`` may be a project root, a ``resume-kit`` working directory, or a
    direct path to ``config.json``. A missing config returns the default policy.
    """

    policy = default_shape_policy()
    path = _resolve_config_path(root)
    if not path.exists():
        return policy

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(raw).__name__}.")

    override = _extract_shape_policy_override(raw)
    if override is None:
        return policy
    return overlay_shape_policy(policy, override)


def _resolve_config_path(root: str | Path) -> Path:
    path = Path(root)
    if path.name == _CONFIG_FILE_NAME:
        return path
    if path.name == _WORKING_DIR_NAME:
        return path / _CONFIG_FILE_NAME
    return path / _WORKING_DIR_NAME / _CONFIG_FILE_NAME


def _extract_shape_policy_override(
    config: Mapping[str, object]
) -> Mapping[str, object] | None:
    for key in _SHAPE_POLICY_CONFIG_KEYS:
        value = config.get(key)
        if value is None:
            continue
        if not isinstance(value, Mapping):
            raise ValueError(f"{key} must be a JSON object.")
        return cast(Mapping[str, object], value)
    return None


def _default_section_aliases() -> dict[str, CanonicalSection]:
    # Seeded from resume_kit_ats.engine._CONVENTIONAL_SECTION_KEYWORDS
    # (RIT-T-0134); promoted from a flat conventional-heading keyword tuple to
    # canonical-section mappings for shape policy consumers.
    aliases: dict[str, CanonicalSection] = {
        "summary": CanonicalSection.BASICS,
        "objective": CanonicalSection.BASICS,
        "profile": CanonicalSection.BASICS,
        "about": CanonicalSection.BASICS,
        "experience": CanonicalSection.WORK,
        "employment": CanonicalSection.WORK,
        "work": CanonicalSection.WORK,
        "history": CanonicalSection.WORK,
        "education": CanonicalSection.EDUCATION,
        "academic": CanonicalSection.EDUCATION,
        "skill": CanonicalSection.SKILLS,
        "technical": CanonicalSection.SKILLS,
        "competenc": CanonicalSection.SKILLS,
        "certification": CanonicalSection.CERTIFICATIONS,
        "license": CanonicalSection.CERTIFICATIONS,
        "credential": CanonicalSection.CERTIFICATIONS,
        "project": CanonicalSection.PROJECTS,
        "portfolio": CanonicalSection.PROJECTS,
        "publication": CanonicalSection.PUBLICATIONS,
        "award": CanonicalSection.AWARDS,
        "honor": CanonicalSection.AWARDS,
        "achievement": CanonicalSection.AWARDS,
        "volunteer": CanonicalSection.VOLUNTEER,
        "leadership": CanonicalSection.VOLUNTEER,
        "activit": CanonicalSection.VOLUNTEER,
        "language": CanonicalSection.LANGUAGES,
        "interest": CanonicalSection.INTERESTS,
        "reference": CanonicalSection.REFERENCES,
        "other": CanonicalSection.OTHER,
    }

    aliases.update(
        {
            "professional summary": CanonicalSection.BASICS,
            "career profile": CanonicalSection.BASICS,
            "work experience": CanonicalSection.WORK,
            "professional experience": CanonicalSection.WORK,
            "employment history": CanonicalSection.WORK,
            "technical skills": CanonicalSection.SKILLS,
            "core skills": CanonicalSection.SKILLS,
            "skills": CanonicalSection.SKILLS,
            "technologies": CanonicalSection.SKILLS,
            "competencies": CanonicalSection.SKILLS,
            "certifications": CanonicalSection.CERTIFICATIONS,
            "licenses": CanonicalSection.CERTIFICATIONS,
            "credentials": CanonicalSection.CERTIFICATIONS,
            "projects": CanonicalSection.PROJECTS,
            "personal projects": CanonicalSection.PROJECTS,
            "portfolio projects": CanonicalSection.PROJECTS,
            "publications": CanonicalSection.PUBLICATIONS,
            "awards": CanonicalSection.AWARDS,
            "honors": CanonicalSection.AWARDS,
            "achievements": CanonicalSection.AWARDS,
            "volunteering": CanonicalSection.VOLUNTEER,
            "volunteer experience": CanonicalSection.VOLUNTEER,
            "leadership activities": CanonicalSection.VOLUNTEER,
            "activities": CanonicalSection.VOLUNTEER,
            "languages": CanonicalSection.LANGUAGES,
            "interests": CanonicalSection.INTERESTS,
            "references": CanonicalSection.REFERENCES,
        }
    )
    return aliases
