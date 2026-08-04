"""Happy-path tests for every facade capability (deterministic + provider).

Covers each capability's deterministic (``no_llm``) path, the provider path via
``FakeStructuredCompletionProvider`` for LLM-requiring capabilities, the async
awaiting of ``align-resume``, the registry contents, and the architectural
invariant that ``resume_kit_facade`` imports no transport package.
"""

from __future__ import annotations

import importlib
import sys

import pytest
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_facade import capabilities as caps
from resume_kit_facade.models import (
    AlignResumeRequest,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CompareResumeVersionsRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    IdentifyResumeGapsRequest,
    SelectBestResumeRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_schemas import (
    AlignmentResult,
    ATSScore,
    CandidateEvidence,
    JobDescription,
    JobMatchReport,
    KeywordGapAnalysis,
    Requirement,
    RequirementKind,
    ResumeComparisonResult,
    ResumeDocument,
    ResumeSelectionResult,
    TruthReport,
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
        ],
    )


def _resume() -> ResumeDocument:
    return ResumeDocument(summary="Python engineer with Docker experience.")


_DETERMINISTIC = CapabilityOptions(no_llm=True)


# --- Registry -------------------------------------------------------------


def test_registry_contains_all_ten_capabilities() -> None:
    assert set(caps.REGISTRY) == {
        "extract-resume",
        "extract-job-description",
        "check-resume-ats",
        "check-resume-job-match",
        "select-best-resume",
        "compare-resume-versions",
        "identify-resume-gaps",
        "align-resume",
        "validate-resume-truth",
        "build-candidate-evidence",
    }


@pytest.mark.asyncio
async def test_registry_dispatch_is_uniform_and_awaitable() -> None:
    response = await caps.REGISTRY["check-resume-job-match"](
        CheckResumeJobMatchRequest(resume=_resume(), job=_job()), _DETERMINISTIC
    )
    assert response.ok
    assert isinstance(response.data, JobMatchReport)


# --- Extract resume -------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_resume_deterministic() -> None:
    response = await caps.extract_resume(
        ExtractResumeRequest(content=b"Jane Doe\nPython Engineer", filename="cv.txt"),
        _DETERMINISTIC,
    )
    assert response.ok


@pytest.mark.asyncio
async def test_extract_resume_provider() -> None:
    provider = FakeStructuredCompletionProvider(
        [{"summary": "Senior Python engineer."}]
    )
    response = await caps.extract_resume(
        ExtractResumeRequest(content=b"Jane Doe\nPython Engineer", filename="cv.txt"),
        CapabilityOptions(provider=provider),
    )
    assert response.ok
    assert isinstance(response.data, ResumeDocument)


# --- Extract job description ----------------------------------------------


@pytest.mark.asyncio
async def test_extract_job_description_deterministic() -> None:
    response = await caps.extract_job_description(
        ExtractJobDescriptionRequest(raw_text="Backend Engineer at Acme"),
        _DETERMINISTIC,
    )
    assert response.ok
    assert isinstance(response.data, JobDescription)


@pytest.mark.asyncio
async def test_extract_job_description_provider() -> None:
    provider = FakeStructuredCompletionProvider([{"title": "Backend Engineer"}])
    response = await caps.extract_job_description(
        ExtractJobDescriptionRequest(raw_text="Backend Engineer at Acme"),
        CapabilityOptions(provider=provider),
    )
    assert response.ok
    assert isinstance(response.data, JobDescription)


# --- Deterministic capabilities -------------------------------------------


@pytest.mark.asyncio
async def test_check_resume_ats() -> None:
    response = await caps.check_resume_ats(
        CheckResumeAtsRequest(resume=_resume(), job=_job()), _DETERMINISTIC
    )
    assert response.ok
    assert isinstance(response.data, ATSScore)


@pytest.mark.asyncio
async def test_check_resume_job_match() -> None:
    response = await caps.check_resume_job_match(
        CheckResumeJobMatchRequest(resume=_resume(), job=_job()), _DETERMINISTIC
    )
    assert response.ok
    assert isinstance(response.data, JobMatchReport)


@pytest.mark.asyncio
async def test_select_best_resume() -> None:
    response = await caps.select_best_resume(
        SelectBestResumeRequest(resumes=[_resume(), _resume()], job=_job()),
        _DETERMINISTIC,
    )
    assert response.ok
    assert isinstance(response.data, ResumeSelectionResult)


@pytest.mark.asyncio
async def test_compare_resume_versions() -> None:
    response = await caps.compare_resume_versions(
        CompareResumeVersionsRequest(
            base=_resume(), candidate=_resume(), job=_job()
        ),
        _DETERMINISTIC,
    )
    assert response.ok
    assert isinstance(response.data, ResumeComparisonResult)


@pytest.mark.asyncio
async def test_identify_resume_gaps() -> None:
    response = await caps.identify_resume_gaps(
        IdentifyResumeGapsRequest(
            job=_job(), tailored=_resume(), master=_resume()
        ),
        _DETERMINISTIC,
    )
    assert response.ok
    assert isinstance(response.data, KeywordGapAnalysis)


@pytest.mark.asyncio
async def test_validate_resume_truth() -> None:
    response = await caps.validate_resume_truth_capability(
        ValidateResumeTruthRequest(resume=_resume(), evidence=[]), _DETERMINISTIC
    )
    assert response.ok
    assert isinstance(response.data, TruthReport)


@pytest.mark.asyncio
async def test_build_candidate_evidence() -> None:
    response = await caps.build_candidate_evidence_capability(
        BuildCandidateEvidenceRequest(resume=_resume()), _DETERMINISTIC
    )
    assert response.ok
    assert isinstance(response.data, list)
    for item in response.data:
        assert isinstance(item, CandidateEvidence)


# --- Align resume ---------------------------------------------------------


@pytest.mark.asyncio
async def test_align_resume_deterministic_no_change() -> None:
    resume = _resume()
    response = await caps.align_resume(
        AlignResumeRequest(resume=resume, job=_job()), _DETERMINISTIC
    )
    assert response.ok
    assert isinstance(response.data, AlignmentResult)
    assert response.data.aligned_resume == resume


@pytest.mark.asyncio
async def test_align_resume_awaits_provider_path() -> None:
    provider = FakeStructuredCompletionProvider(default_response={})
    response = await caps.align_resume(
        AlignResumeRequest(resume=_resume(), job=_job()),
        CapabilityOptions(provider=provider),
    )
    # Provider path was awaited and produced a shaped response (success or
    # mapped failure); it must not raise or hang.
    assert response is not None


# --- Architectural invariant ----------------------------------------------


def test_facade_imports_no_transport_package() -> None:
    importlib.import_module("resume_kit_facade.capabilities")
    importlib.import_module("resume_kit_facade.models")
    forbidden = {"typer", "mcp", "fastapi", "uvicorn", "httpx"}
    loaded = set(sys.modules)
    assert forbidden.isdisjoint(loaded), forbidden & loaded
