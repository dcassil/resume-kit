"""Tests for the canonical Resume schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas.canonical import (
    Achievement,
    Award,
    Basics,
    Certification,
    Education,
    Experience,
    Link,
    LinkType,
    Metric,
    Project,
    Resume,
    SkillGroup,
)


def _valid_resume() -> Resume:
    return Resume(
        basics=Basics(
            name="Daniel Cassil",
            email="daniel@example.com",
            links=[Link(type=LinkType.LINKEDIN, url="https://example.com/in/daniel")],
        ),
        work=[
            Experience(
                organization="Example Co",
                title="Senior Engineer",
                startDate="2020",
                endDate="present",
                achievements=[
                    Achievement(
                        text="Built reliable Python services.",
                        metrics=[
                            Metric(type="count", value=12, unit="services"),
                            Metric(type="duration", value=6, unit="months"),
                        ],
                    )
                ],
            )
        ],
        skills=[SkillGroup(name="Languages", keywords=["Python", "TypeScript"])],
        projects=[
            Project(
                name="Resume Kit",
                description="Open-source resume tooling.",
                technologies=["Python"],
            )
        ],
        education=[Education(institution="State U", degree="BS Computer Science")],
        certifications=[Certification(name="AWS Certified Developer")],
        awards=[Award(name="Engineering Excellence")],
    )


def test_canonical_resume_round_trips_through_dump() -> None:
    resume = _valid_resume()
    restored = Resume.model_validate(resume.model_dump())
    assert restored == resume
    assert restored.work[0].achievements[0].metrics[1].unit == "months"


def test_achievement_accepts_text_only() -> None:
    achievement = Achievement(text="Shipped a canonical schema.")
    assert achievement.action == ""
    assert achievement.result == ""
    assert achievement.metrics == []
    assert achievement.skills == []
    assert achievement.keywords == []


def test_resume_requires_basics() -> None:
    with pytest.raises(ValidationError):
        Resume.model_validate({})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "email": "person@example.com"},
        {"name": "Person"},
        {"name": "Person", "email": "", "phone": ""},
    ],
)
def test_basics_cardinality(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Basics(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "organization": "Example Co",
            "title": "",
            "achievements": [Achievement(text="Built APIs.")],
        },
        {"organization": "Example Co", "title": "Engineer"},
    ],
)
def test_experience_cardinality(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Experience(**kwargs)


def test_experience_allows_empty_organization() -> None:
    """RIT-T-0156 B1: empty ``organization`` is legal (mirrors the source
    schema's ``company: str = ""`` for date-grouped umbrella headings). Only
    ``title`` is required-non-empty."""
    entry = Experience(
        organization="",
        title="Ventures & Consulting",
        achievements=[Achievement(text="Advised early-stage teams.")],
    )
    assert entry.organization == ""


def test_achievement_requires_text() -> None:
    with pytest.raises(ValidationError):
        Achievement(text="")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "keywords": ["Python"]},
        {"name": "Languages", "keywords": []},
    ],
)
def test_skill_group_cardinality(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SkillGroup(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "description": "A project."},
        {"name": "Project"},
    ],
)
def test_project_cardinality(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Project(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"institution": "", "degree": "BS"},
        {"institution": "State U"},
    ],
)
def test_education_cardinality(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Education(**kwargs)


def test_certification_requires_name() -> None:
    with pytest.raises(ValidationError):
        Certification(name="")


def test_link_requires_url() -> None:
    with pytest.raises(ValidationError):
        Link(type=LinkType.GITHUB, url="")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "currency", "value": 1000},
        {"type": "duration", "value": 3},
        {"type": "percentage", "value": 50, "unit": "%"},
    ],
)
def test_metric_shape_rules(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Metric(**kwargs)


def test_named_optional_sections_require_name() -> None:
    with pytest.raises(ValidationError):
        Award(name="")
