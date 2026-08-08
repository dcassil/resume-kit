"""Tests for job-aware deterministic achievement-bullet trim ranking."""

from __future__ import annotations

import pytest
from resume_kit_schemas import JobDescription, Requirement, TrimKind
from resume_kit_schemas.canonical import Achievement, Basics, Experience, Resume
from resume_kit_scoring.rank_bullets import rank_bullets


def _job(*keywords: str) -> JobDescription:
    return JobDescription(
        title="Platform Engineer",
        requirements=[
            Requirement(text=keyword, keywords=[keyword]) for keyword in keywords
        ],
        keywords=list(keywords),
    )


def _resume(*bullets: str) -> Resume:
    return Resume(
        basics=Basics(name="Jane Engineer", email="jane@example.com"),
        work=[
            Experience(
                organization="Acme",
                title="Staff Engineer",
                achievements=[Achievement(text=bullet) for bullet in bullets],
            )
        ],
    )


@pytest.mark.parametrize(
    ("count", "expected_paths"),
    [
        (1, ["work[0].achievements[1]"]),
        (
            3,
            [
                "work[0].achievements[1]",
                "work[0].achievements[2]",
                "work[0].achievements[3]",
            ],
        ),
    ],
)
def test_rank_bullets_orders_tool_weak_and_low_relevance_first(
    count: int, expected_paths: list[str]
) -> None:
    resume = _resume(
        "Reduced Python API latency 35% by architecting the platform.",
        "Used Jira, Slack, email.",
        "Responsible for documentation.",
        "Built Docker services.",
    )

    candidates = rank_bullets(resume, _job("Python"), count=count)

    assert [candidate.path for candidate in candidates] == expected_paths
    assert [candidate.kind for candidate in candidates] == [TrimKind.TRIM] * count


def test_rank_bullets_keeps_alias_relevant_bullet_above_unmatched_bullet() -> None:
    resume = _resume(
        "Built Kubernetes deployment automation.",
        "Built Docker services.",
    )

    candidates = rank_bullets(resume, _job("k8s"), count=1)

    assert [candidate.path for candidate in candidates] == ["work[0].achievements[1]"]


def test_rank_bullets_defers_equal_score_ties_at_boundary() -> None:
    resume = _resume("Updated docs.", "Updated docs.")

    candidates = rank_bullets(resume, _job("Python"), count=1)

    assert [candidate.path for candidate in candidates] == [
        "work[0].achievements[0]",
        "work[0].achievements[1]",
    ]
    assert [candidate.kind for candidate in candidates] == [
        TrimKind.DEFER,
        TrimKind.DEFER,
    ]
    assert all(candidate.deferred for candidate in candidates)


def test_rank_bullets_is_deterministic() -> None:
    resume = _resume(
        "Reduced Python API latency 35% by architecting the platform.",
        "Used Jira, Slack, email.",
        "Responsible for documentation.",
        "Built Docker services.",
    )
    job = _job("Python")

    first = rank_bullets(resume, job, count=3)
    second = rank_bullets(resume, job, count=3)

    assert [candidate.model_dump() for candidate in first] == [
        candidate.model_dump() for candidate in second
    ]
