"""Tests for build_ats_view over a projected ScoreDoc (RIT-T-0109)."""

from __future__ import annotations

from datetime import date

from resume_kit_schemas import (
    ATS_VIEW_DISCLAIMER,
    AdditionalInfo,
    Experience,
    PersonalInfo,
    ResumeDocument,
)
from resume_kit_scoring import build_ats_view, project_scoredoc

_REF = date(2025, 1, 1)


def _resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Daniel Cassil",
            email="me@example.com",
            phone="555-1234",
        ),
        summary="Built Python services with Docker.",
        workExperience=[
            Experience(
                id=1,
                title="Staff Engineer",
                company="Acme",
                years="2019 - Present",
                description=["Led the billing platform."],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "Docker"]),
    )


def test_build_ats_view_mirrors_scoredoc() -> None:
    scoredoc = project_scoredoc(_resume(), reference_date=_REF)
    report = build_ats_view(scoredoc)

    assert report.sections == list(scoredoc.sections)
    assert report.entities == scoredoc.entities
    assert report.keyword_zones == dict(scoredoc.zoned_index.zone_tokens)


def test_build_ats_view_carries_disclaimer() -> None:
    report = build_ats_view(project_scoredoc(_resume(), reference_date=_REF))
    assert report.disclaimer == ATS_VIEW_DISCLAIMER


def test_build_ats_view_is_deterministic() -> None:
    first = build_ats_view(project_scoredoc(_resume(), reference_date=_REF))
    second = build_ats_view(project_scoredoc(_resume(), reference_date=_REF))
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_build_ats_view_years_experience_from_reference_date() -> None:
    """An open-ended ('Present') role's YoE tracks the supplied reference date."""
    early = build_ats_view(project_scoredoc(_resume(), reference_date=date(2021, 1, 1)))
    late = build_ats_view(project_scoredoc(_resume(), reference_date=date(2025, 1, 1)))
    assert (
        late.entities.total_years_experience > early.entities.total_years_experience
    )
