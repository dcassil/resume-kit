"""Unit tests for the explainable job-match / selection / comparison models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import (
    ATSScore,
    JobMatchReport,
    KeywordGapAnalysis,
    MatchDimensionScore,
    ResumeComparisonResult,
    ResumeSelectionResult,
    ResumeVariantScore,
    ScoreDelta,
)


def test_match_dimension_score_defaults_and_evidence() -> None:
    dim = MatchDimensionScore(
        key="skills",
        name="Skills",
        score=80.0,
        weight=0.5,
        evidence=["Python listed in summary and 3 bullets"],
    )
    assert dim.missing_evidence == []
    assert dim.rationale == ""
    assert dim.evidence[0].startswith("Python")


@pytest.mark.parametrize("score", [-1.0, 101.0])
def test_match_dimension_score_bounds(score: float) -> None:
    with pytest.raises(ValidationError):
        MatchDimensionScore(key="k", name="n", score=score)


def test_match_dimension_weight_bounds() -> None:
    with pytest.raises(ValidationError):
        MatchDimensionScore(key="k", name="n", weight=1.5)


def test_job_match_report_defaults() -> None:
    report = JobMatchReport()
    assert report.overall_score == 0.0
    assert report.confidence == 1.0
    assert report.dimensions == []
    assert report.ats_score is None
    assert report.keyword_gap is None


def test_job_match_report_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        JobMatchReport(confidence=1.5)
    with pytest.raises(ValidationError):
        JobMatchReport(overall_score=200.0)


def test_job_match_report_composes_existing_ats_and_keyword_gap() -> None:
    """JobMatchReport composes existing ATSScore + KeywordGapAnalysis (no dupes)."""
    report = JobMatchReport(
        overall_score=72.5,
        dimensions=[
            MatchDimensionScore(
                key="skills",
                name="Skills",
                score=90.0,
                weight=0.6,
                evidence=["Kubernetes in experience section"],
                missing_evidence=["Terraform"],
                rationale="Strong core skill coverage.",
            )
        ],
        ats_score=ATSScore(overall_score=75.0),
        keyword_gap=KeywordGapAnalysis(current_match_percentage=70.0),
        recommendations=["Add Terraform experience"],
    )
    assert isinstance(report.ats_score, ATSScore)
    assert isinstance(report.keyword_gap, KeywordGapAnalysis)
    again = JobMatchReport.model_validate_json(report.model_dump_json())
    assert again == report


def test_resume_variant_score_overall_property() -> None:
    variant = ResumeVariantScore(
        variant_id="v1",
        label="Backend-focused",
        report=JobMatchReport(overall_score=88.0),
    )
    assert variant.overall_score == 88.0


def test_resume_selection_result_defaults_and_roundtrip() -> None:
    result = ResumeSelectionResult(
        ranked=[
            ResumeVariantScore(variant_id="v1", report=JobMatchReport(overall_score=90.0)),
            ResumeVariantScore(variant_id="v2", report=JobMatchReport(overall_score=60.0)),
        ],
        selected_variant_id="v1",
        explanation="v1 has stronger skills coverage.",
    )
    again = ResumeSelectionResult.model_validate_json(result.model_dump_json())
    assert again == result
    assert ResumeSelectionResult().ranked == []
    assert ResumeSelectionResult().selected_variant_id is None


def test_score_delta_construction() -> None:
    delta = ScoreDelta(metric="ats.overall", before=70.0, after=82.0, delta=12.0)
    assert delta.delta == 12.0


def test_resume_comparison_result_roundtrip() -> None:
    comparison = ResumeComparisonResult(
        variant_labels=["baseline", "tailored"],
        deltas=[
            ScoreDelta(metric="ats.overall", before=70.0, after=82.0, delta=12.0),
            ScoreDelta(metric="match.overall", before=65.0, after=78.0, delta=13.0),
        ],
        summary="Tailored variant improves ATS and match scores.",
    )
    again = ResumeComparisonResult.model_validate_json(comparison.model_dump_json())
    assert again == comparison
    assert ResumeComparisonResult().deltas == []
