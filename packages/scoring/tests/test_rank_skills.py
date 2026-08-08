"""Tests for job-aware deterministic skill trim ranking."""

from __future__ import annotations

import pytest
from resume_kit_schemas import JobDescription, Requirement, TrimKind
from resume_kit_schemas.canonical import (
    Achievement,
    Basics,
    Experience,
    Resume,
    SkillGroup,
)
from resume_kit_scoring.rank_skills import rank_skills


def _job(*keywords: str) -> JobDescription:
    return JobDescription(
        title="Platform Engineer",
        requirements=[
            Requirement(text=keyword, keywords=[keyword]) for keyword in keywords
        ],
        keywords=list(keywords),
    )


def _resume(*skills: SkillGroup, summary: str = "Platform engineer.") -> Resume:
    return Resume(
        basics=Basics(
            name="Jane Engineer",
            email="jane@example.com",
            summary=summary,
        ),
        work=[
            Experience(
                organization="Acme",
                title="Staff Engineer",
                achievements=[Achievement(text="Built Python APIs for billing.")],
            )
        ],
        skills=list(skills),
    )


def _skill(name: str, *keywords: str) -> SkillGroup:
    return SkillGroup(name=name, keywords=list(keywords or (name,)))


@pytest.mark.parametrize(
    ("count", "expected_paths"),
    [
        (1, ["skills[6]"]),
        (4, ["skills[6]", "skills[4]", "skills[3]", "skills[5]"]),
    ],
)
def test_rank_skills_orders_lowest_value_rules_first(
    count: int, expected_paths: list[str]
) -> None:
    resume = _resume(
        _skill("Python"),
        _skill("Kubernetes"),
        _skill("Docker"),
        _skill("Communication"),
        _skill("Microsoft Word"),
        _skill("Programming"),
        _skill("Docker"),
    )

    candidates = rank_skills(resume, _job("Python", "Kubernetes"), count=count)

    assert [candidate.path for candidate in candidates] == expected_paths
    assert [candidate.kind for candidate in candidates] == [TrimKind.TRIM] * count


def test_rank_skills_uses_alias_aware_job_match() -> None:
    resume = _resume(_skill("Kubernetes"), _skill("Terraform"))

    candidates = rank_skills(resume, _job("k8s"), count=1)

    assert [candidate.path for candidate in candidates] == ["skills[1]"]


def test_rank_skills_defers_equal_score_ties_at_boundary() -> None:
    resume = _resume(_skill("Communication"), _skill("Teamwork"))

    candidates = rank_skills(resume, _job("Python"), count=1)

    assert [candidate.path for candidate in candidates] == ["skills[0]", "skills[1]"]
    assert [candidate.kind for candidate in candidates] == [
        TrimKind.DEFER,
        TrimKind.DEFER,
    ]
    assert all(candidate.deferred for candidate in candidates)


def test_rank_skills_is_deterministic() -> None:
    resume = _resume(
        _skill("Python"),
        _skill("Communication"),
        _skill("Microsoft Word"),
        _skill("Programming"),
    )
    job = _job("Python")

    first = rank_skills(resume, job, count=3)
    second = rank_skills(resume, job, count=3)

    assert [candidate.model_dump() for candidate in first] == [
        candidate.model_dump() for candidate in second
    ]
