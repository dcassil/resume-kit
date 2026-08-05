"""Happy-path tests for every facade capability (deterministic + provider).

Covers each capability's deterministic (``no_llm``) path, the provider path via
``FakeStructuredCompletionProvider`` for LLM-requiring capabilities, the async
awaiting of ``align-resume``, the registry contents, and the architectural
invariant that ``resume_kit_facade`` imports no transport package.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from resume_kit_core.storage import ArtifactRef
from resume_kit_core.testing import FakeArtifactStore, FakeStructuredCompletionProvider
from resume_kit_export import ExportFormat
from resume_kit_facade import capabilities as caps
from resume_kit_facade.models import (
    AddEvidenceRequest,
    AlignResumeRequest,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CompareResumeVersionsRequest,
    ExportResumeRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    IdentifyResumeGapsRequest,
    RankEditCandidatesRequest,
    RecordEditFeedbackRequest,
    RefreshPreferencesRequest,
    SelectBestResumeRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_feedback import Candidate, FeatureContext
from resume_kit_schemas import (
    AlignmentResult,
    ATSScore,
    CandidateEvidence,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    JobDescription,
    JobMatchReport,
    KeywordGapAnalysis,
    Requirement,
    RequirementKind,
    ResumeComparisonResult,
    ResumeDocument,
    ResumeSelectionResult,
    TruthReport,
    UserPreferenceProfile,
)
from resume_kit_schemas.provenance import ProvenanceReasonCode


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


def test_registry_contains_all_capabilities() -> None:
    assert set(caps.REGISTRY) == {
        "extract-resume",
        "extract-resume-text",
        "extract-job-description",
        "check-resume-ats",
        "check-ats-structure",
        "check-resume-job-match",
        "select-best-resume",
        "compare-resume-versions",
        "identify-resume-gaps",
        "align-resume",
        "validate-resume-truth",
        "validate-faithfulness",
        "build-candidate-evidence",
        "record-edit-feedback",
        "rank-edit-candidates",
        "refresh-preferences",
        "add-evidence",
        "open-edit-session",
        "session-prompt",
        "decide-change",
        "commit-session",
        "session-status",
        "reconcile-session",
        "export-resume",
        "suggest-terminology",
        "align-terminology",
        "init-project",
        "set-active",
        "build-base",
        "build-standard",
        "analyze-best-practices",
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
    provider = FakeStructuredCompletionProvider([{"summary": "Senior Python engineer."}])
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
        CompareResumeVersionsRequest(base=_resume(), candidate=_resume(), job=_job()),
        _DETERMINISTIC,
    )
    assert response.ok
    assert isinstance(response.data, ResumeComparisonResult)


@pytest.mark.asyncio
async def test_identify_resume_gaps() -> None:
    response = await caps.identify_resume_gaps(
        IdentifyResumeGapsRequest(job=_job(), tailored=_resume(), master=_resume()),
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
    assert response.data.needs_evidence_count >= 1
    assert response.data.claims[0].reason_code is ProvenanceReasonCode.MISSING_EVIDENCE


@pytest.mark.asyncio
async def test_build_candidate_evidence() -> None:
    response = await caps.build_candidate_evidence_capability(
        BuildCandidateEvidenceRequest(resume=_resume()), _DETERMINISTIC
    )
    assert response.ok
    assert isinstance(response.data, list)
    for item in response.data:
        assert isinstance(item, CandidateEvidence)


def _feedback_record() -> EditFeedback:
    return EditFeedback(
        edit_id="edit-1",
        resume_id="resume-1",
        job_id="job-1",
        section="summary",
        edit_type="keyword_substitution",
        original_text="Built APIs.",
        proposed_text="Built scalable Python APIs.",
        final_text=None,
        predicted_ats_gain=3.0,
        confidence=0.7,
        outcome="rejected",
        reason_code=EditFeedbackReasonCode.NOT_MY_VOICE,
        timestamp="2026-08-05T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_record_edit_feedback_persists(tmp_path: Path) -> None:
    response = await caps.record_edit_feedback_capability(
        RecordEditFeedbackRequest(
            feedback=_feedback_record(),
            base_path=tmp_path / "resume-kit",
        ),
        _DETERMINISTIC,
    )
    assert response.ok
    log = tmp_path / "resume-kit" / "learning" / "edit-feedback.jsonl"
    assert log.is_file()
    assert "not_my_voice" in log.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_refresh_preferences_derives_from_persisted_log(tmp_path: Path) -> None:
    base = tmp_path / "resume-kit"
    for index in range(3):
        await caps.record_edit_feedback_capability(
            RecordEditFeedbackRequest(
                feedback=_feedback_record().model_copy(
                    update={
                        "edit_id": f"edit-{index}",
                        "outcome": "accepted",
                        "final_text": "Built scalable Python APIs.",
                        # Diff-aware derivation (RIT-T-0102) mines added_terms,
                        # not raw final_text tokens; give the accepted records
                        # repeated diff signal above the support threshold.
                        "added_terms": ["Python"],
                        "removed_terms": ["stuff"],
                    }
                ),
                base_path=base,
            ),
            _DETERMINISTIC,
        )
    response = await caps.refresh_preferences_capability(
        RefreshPreferencesRequest(now="2026-08-05T00:00:00+00:00", base_path=base),
        _DETERMINISTIC,
    )
    assert response.ok
    assert isinstance(response.data, UserPreferenceProfile)
    assert "python" in response.data.accepted_phrases
    assert (base / "learning" / "preferences.json").is_file()


@pytest.mark.asyncio
async def test_rank_edit_candidates_preserves_truth_hard_block() -> None:
    request = RankEditCandidatesRequest(
        candidates=[
            Candidate(
                candidate_id="safe",
                section="skill",
                proposed_text="Docker",
            ),
            Candidate(
                candidate_id="blocked",
                section="skill",
                proposed_text="Kubernetes",
            ),
        ],
        context=FeatureContext(
            resume=_resume(),
            job=_job(),
            evidence=[
                CandidateEvidence(
                    id="ev-docker",
                    kind=EvidenceKind.SKILL,
                    content="Docker",
                    tags=["Docker"],
                    user_confirmed=True,
                )
            ],
        ),
    )
    response = await caps.rank_edit_candidates_capability(request, _DETERMINISTIC)
    assert response.ok
    assert response.data is not None
    dumped = response.data.model_dump(mode="json")
    ranked = dumped["ranked"]
    assert [item["candidate"]["candidate_id"] for item in ranked] == ["safe"]


@pytest.mark.asyncio
async def test_add_evidence_persists_stable_confirmed_record(tmp_path: Path) -> None:
    request = AddEvidenceRequest(
        content="Led Docker platform migration",
        kind=EvidenceKind.USER_STATEMENT,
        tags=["Docker"],
        root=tmp_path,
        update_active=True,
    )
    first = await caps.add_evidence_capability(request, _DETERMINISTIC)
    second = await caps.add_evidence_capability(request, _DETERMINISTIC)
    assert first.ok and second.ok
    assert first.data == second.data
    evidence_file = tmp_path / "resume-kit" / "working" / "user-confirmed-evidence.json"
    evidence = evidence_file.read_text(encoding="utf-8")
    assert evidence.count("ev-confirmed-") == 1


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
    """Importing the facade in a clean interpreter pulls in no transport package.

    Runs in a subprocess so the check is not polluted by other test modules that
    legitimately import the transports (the Phase 5 CLI/MCP/API test suites).
    """
    script = (
        "import sys\n"
        "import resume_kit_facade.capabilities\n"
        "import resume_kit_facade.models\n"
        "forbidden = {'typer', 'mcp', 'fastapi', 'uvicorn', 'httpx'}\n"
        "hit = sorted(forbidden & set(sys.modules))\n"
        "assert not hit, hit\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# --- Export resume --------------------------------------------------------


@pytest.mark.asyncio
async def test_export_resume_pdf_persists_to_injected_store() -> None:
    store = FakeArtifactStore()
    options = CapabilityOptions(artifact_store=store)
    request = ExportResumeRequest(resume=_resume(), format=ExportFormat.pdf)
    response = await caps.export_resume(request, options)
    assert response.ok
    assert len(response.artifacts) == 1
    ref = response.artifacts[0]
    assert isinstance(ref, ArtifactRef)
    assert ref.content_type == "application/pdf"
    assert ref.metadata == {"format": "pdf"}
    data = await store.get(ref.artifact_id)
    assert isinstance(data, bytes)
    assert data.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_export_resume_docx_persists_to_injected_store() -> None:
    store = FakeArtifactStore()
    options = CapabilityOptions(artifact_store=store)
    request = ExportResumeRequest(resume=_resume(), format=ExportFormat.docx)
    response = await caps.export_resume(request, options)
    assert response.ok
    assert len(response.artifacts) == 1
    ref = response.artifacts[0]
    assert ref.content_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert ref.metadata == {"format": "docx"}
    data = await store.get(ref.artifact_id)
    assert isinstance(data, bytes)
    assert data.startswith(b"PK")


@pytest.mark.asyncio
async def test_export_resume_is_deterministic() -> None:
    request = ExportResumeRequest(resume=_resume(), format=ExportFormat.pdf)
    store_a = FakeArtifactStore()
    store_b = FakeArtifactStore()
    first = await caps.export_resume(request, CapabilityOptions(artifact_store=store_a))
    second = await caps.export_resume(request, CapabilityOptions(artifact_store=store_b))
    id_a = first.artifacts[0].artifact_id
    id_b = second.artifacts[0].artifact_id
    assert id_a == id_b
    assert await store_a.get(id_a) == await store_b.get(id_b)


@pytest.mark.asyncio
async def test_export_resume_rejects_wrong_request_type() -> None:
    response = await caps.export_resume(_resume(), CapabilityOptions())
    assert not response.ok
    assert len(response.errors) == 1


@pytest.mark.asyncio
async def test_export_resume_needs_no_provider_and_ignores_no_llm() -> None:
    options = CapabilityOptions(no_llm=True, provider=None)
    request = ExportResumeRequest(resume=_resume(), format=ExportFormat.pdf)
    response = await caps.export_resume(request, options)
    assert response.ok
    assert len(response.artifacts) == 1


@pytest.mark.asyncio
async def test_export_resume_uses_default_store_when_none_injected() -> None:
    request = ExportResumeRequest(resume=_resume(), format=ExportFormat.pdf)
    response = await caps.export_resume(request, CapabilityOptions())
    assert response.ok
    assert len(response.artifacts) == 1
