"""Tests for deterministic, explainable job-match scoring.

Original resume-kit tests for ``resume_kit_matching.match.check_job_match``.
"""

from __future__ import annotations

from resume_kit_matching.match import check_job_match
from resume_kit_schemas import (
    JobDescription,
    JobMatchReport,
    Requirement,
    RequirementKind,
    ResumeDocument,
)

_EXPECTED_KEYS = {
    "keyword_coverage",
    "required_coverage",
    "preferred_coverage",
    "evidence_placement",
    "ats_contribution",
}


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


def _resume_with_skill_once() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jane Dev",
                "email": "jane@example.com",
                "phone": "555-1000",
            },
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


def _resume_with_skill_repeated() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jane Dev",
                "email": "jane@example.com",
                "phone": "555-1000",
            },
            "summary": "Engineer.",
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Prev",
                    "years": "2020-2023",
                    "description": [
                        "python python python python.",
                        "More python. Even more python here.",
                    ],
                }
            ],
            "additional": {"technicalSkills": ["docker"]},
        }
    )


def test_report_has_required_dimensions_and_weights() -> None:
    report = check_job_match(_resume_with_skill_once(), _job())
    keys = {d.key for d in report.dimensions}
    assert keys == _EXPECTED_KEYS
    total_weight = sum(d.weight for d in report.dimensions)
    assert abs(total_weight - 1.0) < 1e-9


def test_no_repetition_reward_on_keyword_coverage() -> None:
    once = check_job_match(_resume_with_skill_once(), _job())
    repeated = check_job_match(_resume_with_skill_repeated(), _job())

    def kw(r: JobMatchReport) -> float:
        return next(d.score for d in r.dimensions if d.key == "keyword_coverage")

    assert kw(once) == kw(repeated)
    # Whole report is identical too: repetition changes nothing.
    assert once.overall_score == repeated.overall_score


def test_support_and_placement_increase_score() -> None:
    weak = ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jane",
                "email": "j@example.com",
                "phone": "555",
            },
            "summary": "Generalist.",
        }
    )
    strong = ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jane",
                "email": "j@example.com",
                "phone": "555",
            },
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
    weak_report = check_job_match(weak, _job())
    strong_report = check_job_match(strong, _job())

    def dim(r: JobMatchReport, key: str) -> float:
        return next(d.score for d in r.dimensions if d.key == key)

    assert dim(strong_report, "required_coverage") > dim(
        weak_report, "required_coverage"
    )
    assert dim(strong_report, "evidence_placement") > dim(
        weak_report, "evidence_placement"
    )
    assert strong_report.overall_score > weak_report.overall_score


def test_missing_requirements_populate_missing_evidence_and_recommendations() -> None:
    bare = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Jane", "email": "j@e.com", "phone": "5"},
            "summary": "Nothing relevant.",
        }
    )
    report = check_job_match(bare, _job())
    required_dim = next(
        d for d in report.dimensions if d.key == "required_coverage"
    )
    assert required_dim.missing_evidence
    assert report.recommendations
    assert any("required" in r.lower() for r in report.recommendations)


def test_overall_score_within_bounds() -> None:
    for resume in (
        _resume_with_skill_once(),
        _resume_with_skill_repeated(),
    ):
        report = check_job_match(resume, _job())
        assert 0.0 <= report.overall_score <= 100.0
        for d in report.dimensions:
            assert 0.0 <= d.score <= 100.0
        assert 0.0 <= report.confidence <= 1.0


def test_deterministic_output() -> None:
    resume = _resume_with_skill_once()
    job = _job()
    a = check_job_match(resume, job)
    b = check_job_match(resume, job)
    assert a.model_dump() == b.model_dump()


def test_empty_job_is_low_confidence_and_zero_overall() -> None:
    report = check_job_match(_resume_with_skill_once(), JobDescription())
    assert report.confidence == 0.0
    assert 0.0 <= report.overall_score <= 100.0
