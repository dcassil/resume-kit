"""Integration: FakeStructuredCompletionProvider → domain model pipeline.

Proves the StructuredCompletionProvider Protocol boundary is usable to produce
resume_kit_schemas domain models without any network, LLM, or concrete SDK.
All assertions are deterministic.
"""

from __future__ import annotations

from typing import Any

import pytest
from resume_kit_core import StructuredCompletionRequest
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_schemas import (
    AnalysisReport,
    ResumeDocument,
)

# ---------------------------------------------------------------------------
# Helper: thin parsing layer that any real service layer would provide
# ---------------------------------------------------------------------------


def parse_analysis_report(raw: dict[str, Any]) -> AnalysisReport:
    """Parse a raw provider dict into an AnalysisReport domain model."""
    return AnalysisReport.model_validate(raw)


def parse_resume_document(raw: dict[str, Any]) -> ResumeDocument:
    """Parse a raw provider dict into a ResumeDocument domain model."""
    return ResumeDocument.model_validate(raw)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def canned_analysis_payload() -> dict[str, Any]:
    return {
        "ats_score": {
            "overall_score": 85.0,
            "sub_scores": {
                "keyword_match": 88.0,
                "skills_coverage": 82.0,
                "section_completeness": 85.0,
            },
            "missing_keywords": ["Terraform"],
        },
        "keyword_gap": {
            "missing_keywords": ["Terraform"],
            "current_match_percentage": 82.0,
        },
        "warnings": [],
    }


@pytest.fixture()
def canned_resume_payload() -> dict[str, Any]:
    return {
        "personalInfo": {
            "name": "Alice Example",
            "email": "alice@example.com",
            "phone": "555-0100",
        },
        "summary": "Experienced software engineer.",
        "workExperience": [],
        "education": [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFakeProviderProducesAnalysisReport:
    """Fake provider → parse → AnalysisReport end-to-end flow."""

    @pytest.mark.asyncio
    async def test_complete_json_returns_canned_dict(
        self, canned_analysis_payload: dict[str, Any]
    ) -> None:
        provider = FakeStructuredCompletionProvider(responses=[canned_analysis_payload])
        request = StructuredCompletionRequest(prompt="Analyse this resume against the JD.")

        raw = await provider.complete_json(request)

        assert raw == canned_analysis_payload
        assert len(provider.calls) == 1
        assert provider.calls[0].prompt == "Analyse this resume against the JD."

    @pytest.mark.asyncio
    async def test_parse_raw_into_analysis_report(
        self, canned_analysis_payload: dict[str, Any]
    ) -> None:
        provider = FakeStructuredCompletionProvider(responses=[canned_analysis_payload])
        request = StructuredCompletionRequest(prompt="Analyse this resume.")

        raw = await provider.complete_json(request)
        report = parse_analysis_report(raw)

        assert isinstance(report, AnalysisReport)
        assert report.ats_score is not None
        assert report.ats_score.overall_score == pytest.approx(85.0)
        assert report.ats_score.sub_scores is not None
        assert report.ats_score.sub_scores.keyword_match == pytest.approx(88.0)

    @pytest.mark.asyncio
    async def test_keyword_gaps_parsed_correctly(
        self, canned_analysis_payload: dict[str, Any]
    ) -> None:
        provider = FakeStructuredCompletionProvider(responses=[canned_analysis_payload])
        raw = await provider.complete_json(
            StructuredCompletionRequest(prompt="Gap analysis.")
        )
        report = parse_analysis_report(raw)

        assert report.keyword_gap is not None
        assert "Terraform" in report.keyword_gap.missing_keywords


class TestFakeProviderProducesResumeDocument:
    """Fake provider → parse → ResumeDocument end-to-end flow."""

    @pytest.mark.asyncio
    async def test_parse_raw_into_resume_document(
        self, canned_resume_payload: dict[str, Any]
    ) -> None:
        provider = FakeStructuredCompletionProvider(responses=[canned_resume_payload])
        raw = await provider.complete_json(
            StructuredCompletionRequest(prompt="Parse this resume text into structured JSON.")
        )
        doc = parse_resume_document(raw)

        assert isinstance(doc, ResumeDocument)
        assert doc.personalInfo.name == "Alice Example"
        assert doc.personalInfo.email == "alice@example.com"


class TestFakeProviderQueueBehavior:
    """Verify the fake drains in order and respects default_response."""

    @pytest.mark.asyncio
    async def test_multiple_responses_drain_in_order(self) -> None:
        payloads = [
            {"ats_score": {"overall_score": 60.0}, "warnings": []},
            {"ats_score": {"overall_score": 90.0}, "warnings": []},
        ]
        provider = FakeStructuredCompletionProvider(responses=payloads)
        req = StructuredCompletionRequest(prompt="x")

        first = parse_analysis_report(await provider.complete_json(req))
        second = parse_analysis_report(await provider.complete_json(req))

        assert first.ats_score is not None
        assert first.ats_score.overall_score == pytest.approx(60.0)
        assert second.ats_score is not None
        assert second.ats_score.overall_score == pytest.approx(90.0)

    @pytest.mark.asyncio
    async def test_default_response_used_when_queue_empty(self) -> None:
        default = {"ats_score": {"overall_score": 50.0}, "warnings": []}
        provider = FakeStructuredCompletionProvider(
            responses=[], default_response=default
        )
        req = StructuredCompletionRequest(prompt="y")

        result = parse_analysis_report(await provider.complete_json(req))
        assert result.ats_score is not None
        assert result.ats_score.overall_score == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_exhausted_queue_raises(self) -> None:
        from resume_kit_core.errors import ResumeKitError

        provider = FakeStructuredCompletionProvider(responses=[])
        with pytest.raises(ResumeKitError):
            await provider.complete_json(StructuredCompletionRequest(prompt="z"))


class TestFakeProviderSatisfiesProtocol:
    """FakeStructuredCompletionProvider satisfies StructuredCompletionProvider Protocol."""

    def test_isinstance_check(self) -> None:
        from resume_kit_core import StructuredCompletionProvider

        provider = FakeStructuredCompletionProvider()
        assert isinstance(provider, StructuredCompletionProvider)
