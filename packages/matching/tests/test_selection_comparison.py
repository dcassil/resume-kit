"""Tests for deterministic resume selection and version comparison.

Original resume-kit tests for ``resume_kit_matching.selection.select_best`` and
``resume_kit_matching.comparison.compare_versions``.
"""

from __future__ import annotations

from resume_kit_matching.comparison import compare_versions
from resume_kit_matching.selection import select_best
from resume_kit_schemas import (
    JobDescription,
    Requirement,
    RequirementKind,
    ResumeComparisonResult,
    ResumeDocument,
    ResumeSelectionResult,
    ResumeVariantScore,
    ScoreDelta,
)


def _job() -> JobDescription:
    return JobDescription(
        title="Backend Engineer",
        company="Acme",
        requirements=[
            Requirement(
                text="Python experience",
                kind=RequirementKind.REQUIRED,
                keywords=["python"],
            ),
            Requirement(
                text="Docker in production",
                kind=RequirementKind.REQUIRED,
                keywords=["docker"],
            ),
        ],
        qualifications=[
            Requirement(
                text="Kubernetes",
                kind=RequirementKind.PREFERRED,
                keywords=["kubernetes"],
            ),
        ],
        keywords=["python", "docker", "kubernetes"],
    )


def _strong() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "S", "email": "s@e.com", "phone": "1"},
            "summary": "Engineer.",
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Prev",
                    "years": "2020-2023",
                    "description": ["Shipped python and docker services."],
                }
            ],
            "education": [{"institution": "Uni", "degree": "BS", "years": "2019"}],
            "additional": {"technicalSkills": ["python", "docker", "kubernetes"]},
        }
    )


def _medium() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "M", "email": "m@e.com", "phone": "1"},
            "summary": "Engineer.",
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Prev",
                    "years": "2020-2023",
                    "description": ["Built services with python."],
                }
            ],
            "additional": {"technicalSkills": ["docker"]},
        }
    )


def _weak() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "W", "email": "w@e.com", "phone": "1"},
            "summary": "Generalist with unrelated skills.",
        }
    )


def test_ranking_orders_variants_by_overall_score() -> None:
    job = _job()
    result = select_best([_weak(), _strong(), _medium()], job, labels=["w", "s", "m"])

    assert isinstance(result, ResumeSelectionResult)
    scores = [v.overall_score for v in result.ranked]
    assert scores == sorted(scores, reverse=True)
    assert result.ranked[0].label == "s"
    assert result.selected_variant_id == "s"
    assert result.explanation


def test_ties_break_deterministically_by_input_order() -> None:
    job = _job()
    # Two identical strong resumes: equal scores must tie-break on input order.
    result = select_best([_strong(), _strong()], job, labels=["first", "second"])

    assert result.ranked[0].overall_score == result.ranked[1].overall_score
    assert result.ranked[0].label == "first"
    assert result.ranked[1].label == "second"
    assert result.selected_variant_id == "first"


def test_labels_fall_back_to_positional_ids() -> None:
    job = _job()
    result = select_best([_strong(), _medium()], job)
    ids = {v.variant_id for v in result.ranked}
    assert ids == {"variant-0", "variant-1"}


def test_selection_is_deterministic_across_runs() -> None:
    job = _job()
    resumes = [_weak(), _strong(), _medium()]
    a = select_best(resumes, job, labels=["w", "s", "m"])
    b = select_best(resumes, job, labels=["w", "s", "m"])
    assert a.model_dump() == b.model_dump()


def test_selection_uses_canonical_schema_types() -> None:
    result = select_best([_strong()], _job(), labels=["only"])
    assert isinstance(result, ResumeSelectionResult)
    assert all(isinstance(v, ResumeVariantScore) for v in result.ranked)


def test_compare_versions_shows_positive_deltas_for_improvement() -> None:
    job = _job()
    result = compare_versions(_weak(), _strong(), job)

    assert isinstance(result, ResumeComparisonResult)
    assert result.variant_labels == ["base", "candidate"]
    assert all(isinstance(d, ScoreDelta) for d in result.deltas)

    overall = next(d for d in result.deltas if d.metric == "match.overall")
    assert overall.delta > 0
    assert overall.after > overall.before
    assert "improve" in result.summary.lower()


def test_compare_versions_shows_negative_deltas_for_regression() -> None:
    job = _job()
    result = compare_versions(_strong(), _weak(), job)

    overall = next(d for d in result.deltas if d.metric == "match.overall")
    assert overall.delta < 0
    assert overall.after < overall.before
    assert "regress" in result.summary.lower()


def test_compare_versions_covers_expected_metrics() -> None:
    result = compare_versions(_weak(), _strong(), _job())
    metrics = {d.metric for d in result.deltas}
    assert metrics == {"match.overall", "ats.overall", "keyword.match_pct"}
    for d in result.deltas:
        assert d.delta == round(d.after - d.before, 1)


def test_compare_versions_is_deterministic_across_runs() -> None:
    job = _job()
    a = compare_versions(_weak(), _strong(), job)
    b = compare_versions(_weak(), _strong(), job)
    assert a.model_dump() == b.model_dump()
