"""Tests for job-aware deterministic experience trim ranking."""

from __future__ import annotations

import pytest
from resume_kit_schemas import (
    Experience,
    JobDescription,
    PersonalInfo,
    Requirement,
    ResumeDocument,
    TrimKind,
)
from resume_kit_scoring.rank_experience import rank_experience


def _job(*keywords: str) -> JobDescription:
    return JobDescription(
        title="Platform Engineer",
        requirements=[
            Requirement(text=keyword, keywords=[keyword]) for keyword in keywords
        ],
        keywords=list(keywords),
    )


def _resume(*work: Experience) -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(name="Jane Engineer", email="jane@example.com"),
        workExperience=list(work),
    )


def _experience(
    title: str,
    start: str,
    end: str,
    achievement: str,
    *,
    skills: list[str] | None = None,
) -> Experience:
    return Experience(
        company=f"{title} Co",
        title=title,
        years=f"{start}-{end}",
        description=[achievement, *(skills or [])],
    )


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (
            2,
            [
                ("workExperience[1]", TrimKind.COMPRESS),
                ("workExperience[1]", TrimKind.TRIM),
            ],
        ),
        (
            4,
            [
                ("workExperience[1]", TrimKind.COMPRESS),
                ("workExperience[1]", TrimKind.TRIM),
                ("workExperience[2]", TrimKind.COMPRESS),
                ("workExperience[2]", TrimKind.TRIM),
            ],
        ),
    ],
)
def test_rank_experience_orders_old_low_relevance_roles_first(
    count: int, expected: list[tuple[str, TrimKind]]
) -> None:
    resume = _resume(
        _experience(
            "Staff Platform Engineer",
            "2022-01",
            "present",
            "Reduced Python API latency 35% on Kubernetes.",
            skills=["Python", "Kubernetes"],
        ),
        _experience("Intern", "2011-01", "2012-01", "Updated wiki pages."),
        _experience("Engineer", "2019-01", "2020-01", "Maintained reports."),
    )

    candidates = rank_experience(resume, _job("Python", "Kubernetes"), count=count)

    assert [(candidate.path, candidate.kind) for candidate in candidates] == expected


def test_rank_experience_compresses_before_removing_same_role() -> None:
    resume = _resume(
        _experience("Staff Engineer", "2020-01", "present", "Scaled Python 40%."),
        _experience("Intern", "2011-01", "2012-01", "Updated wiki pages."),
    )

    candidates = rank_experience(resume, _job("Python"), count=2)

    assert [(candidate.path, candidate.kind) for candidate in candidates] == [
        ("workExperience[1]", TrimKind.COMPRESS),
        ("workExperience[1]", TrimKind.TRIM),
    ]


def test_rank_experience_defers_equal_score_ties_at_boundary() -> None:
    resume = _resume(
        _experience("Intern", "2011-01", "2012-01", "Updated wiki pages."),
        _experience("Intern", "2011-01", "2012-01", "Organized notes."),
    )

    candidates = rank_experience(resume, _job("Python"), count=2)

    assert [(candidate.path, candidate.kind) for candidate in candidates] == [
        ("workExperience[0]", TrimKind.DEFER),
        ("workExperience[1]", TrimKind.DEFER),
    ]
    assert all(candidate.deferred for candidate in candidates)


def test_rank_experience_notes_continuity_risk_for_selected_middle_role() -> None:
    resume = _resume(
        _experience("Staff Engineer", "2022-01", "present", "Scaled Python 40%."),
        _experience("Assistant", "2018-01", "2019-01", "Updated wiki pages."),
        _experience(
            "Principal Engineer",
            "2010-01",
            "2014-01",
            "Led Python platform used by 20 teams.",
        ),
    )

    candidates = rank_experience(resume, _job("Python"), count=2)

    assert [candidate.path for candidate in candidates] == [
        "workExperience[1]",
        "workExperience[1]",
    ]
    assert all("continuity risk" in candidate.rationale for candidate in candidates)


def test_rank_experience_is_deterministic() -> None:
    resume = _resume(
        _experience("Staff Engineer", "2020-01", "present", "Scaled Python 40%."),
        _experience("Intern", "2011-01", "2012-01", "Updated wiki pages."),
        _experience("Engineer", "2019-01", "2020-01", "Maintained reports."),
    )
    job = _job("Python")

    first = rank_experience(resume, job, count=4)
    second = rank_experience(resume, job, count=4)

    assert [candidate.model_dump() for candidate in first] == [
        candidate.model_dump() for candidate in second
    ]
