"""Tests for the data-only canonical resume shape policy."""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_policy import (
    InformationalShapeBudgets,
    ResumeShapePolicy,
    default_shape_policy,
    load_shape_policy,
)
from resume_kit_schemas.canonical import CanonicalSection


def test_default_shape_policy_loads() -> None:
    policy = default_shape_policy()

    assert isinstance(policy, ResumeShapePolicy)
    assert policy.section_order == [
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
    ]
    assert policy.allow_other is True
    assert policy.fallback_section is CanonicalSection.OTHER
    assert policy.informational_budgets.enforcement == "informational_only"
    assert isinstance(policy.informational_budgets, InformationalShapeBudgets)


def test_alias_table_maps_known_headings() -> None:
    policy = default_shape_policy()

    assert policy.section_aliases["technical skills"] is CanonicalSection.SKILLS
    assert (
        policy.canonical_section_for_heading("Technical Skills")
        is CanonicalSection.SKILLS
    )
    assert (
        policy.canonical_section_for_heading("Certifications")
        is CanonicalSection.CERTIFICATIONS
    )


def test_unknown_heading_resolves_to_other() -> None:
    policy = default_shape_policy()

    assert (
        policy.canonical_section_for_heading("Domains & Industries")
        is CanonicalSection.OTHER
    )


def test_missing_project_config_loads_default_policy(tmp_path: Path) -> None:
    assert load_shape_policy(tmp_path) == default_shape_policy()


def test_project_override_overlays_default_policy(tmp_path: Path) -> None:
    config = tmp_path / "resume-kit" / "config.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "shape_policy": {
                    "section_order": ["basics", "skills", "work", "other"],
                    "section_aliases": {
                        "Domains & Industries": "interests",
                        "Technical Skills": "projects",
                    },
                    "informational_budgets": {
                        "max_skills": 45,
                        "max_summary_words": 70,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    policy = load_shape_policy(tmp_path)

    assert policy.section_order == [
        CanonicalSection.BASICS,
        CanonicalSection.SKILLS,
        CanonicalSection.WORK,
        CanonicalSection.OTHER,
    ]
    assert (
        policy.canonical_section_for_heading("Domains & Industries")
        is CanonicalSection.INTERESTS
    )
    assert (
        policy.canonical_section_for_heading("Technical Skills")
        is CanonicalSection.PROJECTS
    )
    assert (
        policy.canonical_section_for_heading("Certifications")
        is CanonicalSection.CERTIFICATIONS
    )
    assert policy.informational_budgets.max_skills == 45
    assert policy.informational_budgets.max_summary_words == 70
    assert policy.informational_budgets.enforcement == "informational_only"
