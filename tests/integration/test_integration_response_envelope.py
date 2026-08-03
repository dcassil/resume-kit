"""Integration: InterfaceResponse[<schema model>] composes correctly.

Proves that resume_kit_core's generic envelope can carry resume_kit_schemas
domain models as its ``data`` payload, and that the combined object round-trips
through Pydantic JSON serialisation without loss.
"""

from __future__ import annotations

import json

import pytest
from resume_kit_core import InterfaceResponse, ProvenanceRef
from resume_kit_core.errors import CoreWarning, WarningCode
from resume_kit_core.storage import ArtifactRef
from resume_kit_schemas import (
    AnalysisReport,
    ATSScore,
    ATSSubScores,
    KeywordGapAnalysis,
    PersonalInfo,
    ResumeDocument,
    Severity,
    Warning,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_resume() -> ResumeDocument:
    """A minimal but fully constructed ResumeDocument."""
    return ResumeDocument(
        personalInfo=PersonalInfo(name="Jane Smith", email="jane@example.com"),
        summary="Senior engineer with 10 years of experience.",
    )


@pytest.fixture()
def sample_analysis_report() -> AnalysisReport:
    """A plausible AnalysisReport with nested scoring objects."""
    return AnalysisReport(
        ats_score=ATSScore(
            overall_score=72.5,
            sub_scores=ATSSubScores(
                keyword_match=70.0,
                skills_coverage=75.0,
                section_completeness=72.5,
            ),
        ),
        keyword_gap=KeywordGapAnalysis(
            missing_keywords=["Kubernetes", "Terraform"],
            current_match_percentage=65.0,
        ),
        warnings=[
            Warning(
                code="LOW_KEYWORD_DENSITY",
                message="Keyword density is below recommended threshold.",
                severity=Severity.WARNING,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnvelopeWithResumeDocument:
    """InterfaceResponse parameterised with ResumeDocument."""

    def test_success_constructor(self, minimal_resume: ResumeDocument) -> None:
        resp = InterfaceResponse[ResumeDocument].success(minimal_resume)

        assert resp.ok is True
        assert resp.data is not None
        assert resp.data.personalInfo.name == "Jane Smith"
        assert resp.errors == []
        assert resp.warnings == []

    def test_json_round_trip(self, minimal_resume: ResumeDocument) -> None:
        resp = InterfaceResponse[ResumeDocument].success(minimal_resume)
        serialised = resp.model_dump_json()

        # Must be valid JSON
        parsed = json.loads(serialised)
        assert parsed["data"]["personalInfo"]["name"] == "Jane Smith"

        # Round-trip back through Pydantic
        restored = InterfaceResponse[ResumeDocument].model_validate_json(serialised)
        assert restored.data is not None
        assert restored.data.personalInfo.name == "Jane Smith"


class TestEnvelopeWithAnalysisReport:
    """InterfaceResponse parameterised with AnalysisReport."""

    def test_carries_analysis_report(self, sample_analysis_report: AnalysisReport) -> None:
        resp = InterfaceResponse[AnalysisReport].success(sample_analysis_report)

        assert resp.ok is True
        assert resp.data is not None
        assert resp.data.ats_score is not None
        assert resp.data.ats_score.overall_score == pytest.approx(72.5)

    def test_envelope_with_warnings_and_provenance(
        self, sample_analysis_report: AnalysisReport
    ) -> None:
        warning = CoreWarning(
            code=WarningCode.HUMAN_REVIEW_SUGGESTED,
            message="Low confidence score — human review recommended.",
        )
        prov = ProvenanceRef(
            source_id="job-123",
            source_type="job_description",
            field_path="requirements",
        )
        artifact = ArtifactRef(
            artifact_id="report-001",
            artifact_type="analysis_report",
            content_type="application/json",
        )

        resp = InterfaceResponse[AnalysisReport].success(
            sample_analysis_report,
            warnings=[warning],
            provenance=[prov],
            artifacts=[artifact],
        )

        assert resp.ok is True
        assert len(resp.warnings) == 1
        assert resp.warnings[0].code == WarningCode.HUMAN_REVIEW_SUGGESTED
        assert len(resp.provenance) == 1
        assert resp.provenance[0].source_id == "job-123"
        assert len(resp.artifacts) == 1
        assert resp.artifacts[0].artifact_id == "report-001"

    def test_json_round_trip_with_analysis_report(
        self, sample_analysis_report: AnalysisReport
    ) -> None:
        resp = InterfaceResponse[AnalysisReport].success(sample_analysis_report)
        serialised = resp.model_dump_json()
        parsed = json.loads(serialised)

        assert parsed["data"]["ats_score"]["overall_score"] == pytest.approx(72.5)
        assert "Kubernetes" in parsed["data"]["keyword_gap"]["missing_keywords"]

        restored = InterfaceResponse[AnalysisReport].model_validate_json(serialised)
        assert restored.data is not None
        assert restored.data.keyword_gap is not None
        assert "Kubernetes" in restored.data.keyword_gap.missing_keywords

    def test_failure_envelope_no_data(self) -> None:
        from resume_kit_core.errors import CoreError, ErrorCode

        resp = InterfaceResponse[AnalysisReport].failure(
            errors=[
                CoreError(
                    code=ErrorCode.PROVIDER_INVALID_RESPONSE,
                    message="LLM returned malformed JSON.",
                )
            ]
        )

        assert resp.ok is False
        assert resp.data is None
        assert len(resp.errors) == 1
        assert resp.errors[0].code == ErrorCode.PROVIDER_INVALID_RESPONSE
