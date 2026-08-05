"""The Phase 5 capability facade: one uniform callable per capability.

Each callable maps exactly one engine public API into an
:class:`~resume_kit_core.InterfaceResponse` via the core substrate
(``build_success`` / ``build_provider_not_configured`` / ``from_resume_kit_error``
/ ``from_exception``).  This is the ONLY place a transport ever needs to reach
engine functions; transports enumerate and dispatch through :data:`REGISTRY`.

Rules enforced here:

* ``no_llm=True`` uses the deterministic engine path for every capability that
  has one (and an explicit no-change path for ``align-resume``).
* An LLM-requiring capability with ``provider=None`` (and ``no_llm`` False)
  returns the stable provider-not-configured failure — the engine is never
  called and nothing crashes.
* Engine ``ResumeKitError`` maps through ``from_resume_kit_error``; any other
  exception maps through ``from_exception``.

Every capability is exposed as an ``async`` callable with the uniform signature
``(request, options) -> InterfaceResponse[object]`` so a single registry can
type-check without casts or ignores; deterministic capabilities simply do not
await anything internally.

No transport dependency (Typer, MCP SDK, FastAPI, uvicorn, httpx) and no
concrete provider are imported here.  Everything depends inward on core,
schemas, and the engine packages only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from pathlib import Path

from resume_kit_alignment import accept_terminology_alignment
from resume_kit_alignment import align_resume as _align_resume
from resume_kit_ats import check_ats_structure as _check_ats_structure
from resume_kit_ats import check_faithfulness as _check_faithfulness
from resume_kit_ats import compute_ats_score
from resume_kit_core import InterfaceResponse, Question, ResumeKitError
from resume_kit_core.interface import (
    build_provider_not_configured as _build_provider_not_configured,
)
from resume_kit_core.interface import (
    build_success,
)
from resume_kit_core.interface import (
    from_exception as _from_exception,
)
from resume_kit_core.interface import (
    from_resume_kit_error as _from_resume_kit_error,
)
from resume_kit_core.storage import ArtifactRef, ArtifactStore
from resume_kit_document_parser import (
    TextExtractionResult,
    extract_resume_text,
    extract_resume_text_only,
    parse_resume_structured,
)
from resume_kit_evidence import build_candidate_evidence, validate_resume_truth
from resume_kit_export import render
from resume_kit_export.models import mime_type
from resume_kit_feedback import (
    HeuristicRanker,
    append_edit_feedback,
    append_preference_pair,
    derive_preferences,
    read_edit_feedback,
)
from resume_kit_job_parser import (
    parse_job_description,
    parse_job_description_text_only,
)
from resume_kit_matching import (
    analyze_keyword_gaps,
    analyze_terminology_alignment,
    check_job_match,
    compare_versions,
    select_best,
)
from resume_kit_schemas import (
    AlignmentResult,
    ATSScore,
    AtsStructureReport,
    CandidateEvidence,
    EvidenceKind,
    FaithfulnessReport,
    JobDescription,
    JobMatchReport,
    KeywordGapAnalysis,
    ResumeComparisonResult,
    ResumeDocument,
    ResumeSelectionResult,
    TerminologyAlignment,
    TruthReport,
)

from resume_kit_facade import edit_session as _edit_session
from resume_kit_facade.alias_scope import use_alias_file
from resume_kit_facade.models import (
    AddEvidenceRequest,
    AddEvidenceResult,
    AlignResumeRequest,
    AlignTerminologyRequest,
    AlignTerminologyResult,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckAtsStructureRequest,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CommitSessionRequest,
    CompareResumeVersionsRequest,
    DecideChangeRequest,
    ExportResumeRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    ExtractResumeTextRequest,
    IdentifyResumeGapsRequest,
    InitProjectRequest,
    OpenEditSessionRequest,
    RankEditCandidatesRequest,
    RankEditCandidatesResult,
    ReconcileSessionRequest,
    RecordEditFeedbackRequest,
    RecordEditFeedbackResult,
    RefreshPreferencesRequest,
    SelectBestResumeRequest,
    SessionPromptRequest,
    SessionStatusRequest,
    SetActiveRequest,
    SuggestTerminologyRequest,
    TerminologyAlignmentDelta,
    ValidateFaithfulnessRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    load_evidence_file,
    save_config,
    save_evidence_file,
    set_active,
    working_dir,
)

# A capability takes a request object plus options and yields an
# InterfaceResponse.  Registry values narrow their request via ``isinstance``.
Capability = Callable[[object, CapabilityOptions], Awaitable[InterfaceResponse[object]]]


def _widen(response: InterfaceResponse[None]) -> InterfaceResponse[object]:
    """Widen a data-less failure/pause response to ``InterfaceResponse[object]``.

    ``InterfaceResponse`` is invariant in its type parameter, but the substrate
    failure builders return ``InterfaceResponse[None]`` (always ``data=None``).
    Re-wrap the envelope into the widened type so capabilities can return a
    single ``InterfaceResponse[object]`` type across success and failure.
    """
    return InterfaceResponse[object](
        data=None,
        warnings=response.warnings,
        errors=response.errors,
        requires_human_input=response.requires_human_input,
        questions=response.questions,
        artifacts=response.artifacts,
        provenance=response.provenance,
    )


def from_resume_kit_error(exc: ResumeKitError) -> InterfaceResponse[object]:
    """Widened ``from_resume_kit_error`` for capability return positions."""
    return _widen(_from_resume_kit_error(exc))


def from_exception(exc: BaseException) -> InterfaceResponse[object]:
    """Widened ``from_exception`` for capability return positions."""
    return _widen(_from_exception(exc))


def build_provider_not_configured(
    *, details: dict[str, object] | None = None
) -> InterfaceResponse[object]:
    """Widened ``build_provider_not_configured`` for capability returns."""
    return _widen(_build_provider_not_configured(details=details))


class _UnexpectedRequestError(ResumeKitError):
    """Raised when a capability receives a request of the wrong type."""


def _bad_request(request: object, expected: str) -> ResumeKitError:
    from resume_kit_core.errors import CoreError, ErrorCode

    return _UnexpectedRequestError(
        CoreError(
            code=ErrorCode.INVALID_INPUT,
            message=f"Expected {expected} request.",
            details={"received_type": type(request).__name__},
        )
    )


# ---------------------------------------------------------------------------
# LLM-capable capabilities
# ---------------------------------------------------------------------------


async def extract_resume(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Extract a structured resume from raw bytes (LLM or deterministic)."""
    if not isinstance(request, ExtractResumeRequest):
        return from_resume_kit_error(_bad_request(request, "ExtractResumeRequest"))
    document: ResumeDocument | None
    if options.no_llm:
        try:
            result = extract_resume_text_only(request.content, request.filename)
        except ResumeKitError as exc:
            return from_resume_kit_error(exc)
        except Exception as exc:  # noqa: BLE001 - map any engine failure
            return from_exception(exc)
        document = result.document
        return build_success(
            document,
            warnings=result.warnings,
            provenance=result.provenance,
            strict=options.strict,
        )

    if options.provider is None:
        return build_provider_not_configured(details={"capability": "extract-resume"})
    try:
        result = await parse_resume_structured(request.content, request.filename, options.provider)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    document = result.document
    return build_success(
        document,
        warnings=result.warnings,
        provenance=result.provenance,
        strict=options.strict,
    )


async def extract_job_description(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Extract a structured job description from raw text (LLM or deterministic)."""
    if not isinstance(request, ExtractJobDescriptionRequest):
        return from_resume_kit_error(_bad_request(request, "ExtractJobDescriptionRequest"))
    job: JobDescription
    if options.no_llm:
        try:
            job = parse_job_description_text_only(request.raw_text)
        except ResumeKitError as exc:
            return from_resume_kit_error(exc)
        except Exception as exc:  # noqa: BLE001 - map any engine failure
            return from_exception(exc)
        return build_success(job, strict=options.strict)

    if options.provider is None:
        return build_provider_not_configured(
            details={"capability": "extract-job-description"},
        )
    try:
        job = await parse_job_description(request.raw_text, options.provider)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(job, strict=options.strict)


async def extract_resume_text_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Extract raw text from a resume/job file — deterministic, no LLM, no network.

    First-class EXTRACTION primitive (RIT-T-0090): delegates to the
    document-parser :func:`extract_resume_text` engine function and returns its
    :class:`TextExtractionResult` (text + warnings + method). Never contacts a
    provider and never requires one; ``no_llm`` is irrelevant here because the
    operation is deterministic by construction.
    """
    if not isinstance(request, ExtractResumeTextRequest):
        return from_resume_kit_error(_bad_request(request, "ExtractResumeTextRequest"))
    try:
        result: TextExtractionResult = extract_resume_text(request.content, request.filename)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(result, warnings=result.warnings, strict=options.strict)


async def align_resume(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Run controlled alignment (LLM), or a deterministic no-change path."""
    if not isinstance(request, AlignResumeRequest):
        return from_resume_kit_error(_bad_request(request, "AlignResumeRequest"))
    result: AlignmentResult
    if options.no_llm:
        result = AlignmentResult(
            original_resume=request.resume,
            aligned_resume=request.resume,
            job=request.job,
        )
        return build_success(result, strict=options.strict)

    if options.provider is None:
        return build_provider_not_configured(details={"capability": "align-resume"})
    try:
        result = await _align_resume(
            request.resume,
            request.job,
            request.evidence,
            human_in_loop=options.human_in_loop,
            provider=options.provider,
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return _align_success(result, strict=options.strict)


def _align_success(result: AlignmentResult, *, strict: bool) -> InterfaceResponse[object]:
    """Shape the alignment result into the canonical envelope.

    When the human-in-loop review left unresolved questions, surface them as
    ``requires_human_input`` + ``questions`` on the envelope (REQ-408) rather than
    burying them in ``data`` — so every transport (CLI/MCP/API) reports the pause
    identically. The ``AlignmentResult`` is still carried as ``data``.
    """
    response: InterfaceResponse[object] = build_success(result, strict=strict)
    if response.errors or not result.unresolved_questions:
        return response
    questions = [
        Question(
            question_id=f"align-resume:{index}",
            text=text,
            metadata={"source": "alignment.review_state"},
        )
        for index, text in enumerate(result.unresolved_questions)
    ]
    return response.model_copy(update={"requires_human_input": True, "questions": questions})


# ---------------------------------------------------------------------------
# Deterministic capabilities (no provider ever required)
# ---------------------------------------------------------------------------


async def check_resume_ats(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Compute the deterministic ATS score for a resume against a job."""
    if not isinstance(request, CheckResumeAtsRequest):
        return from_resume_kit_error(_bad_request(request, "CheckResumeAtsRequest"))
    try:
        with use_alias_file(request.alias_file):
            gap = analyze_keyword_gaps(request.job, request.resume, request.resume)
            score: ATSScore = compute_ats_score(
                request.resume,
                request.job,
                gap.current_match_percentage,
                gap.non_injectable_keywords,
                gap.injectable_keywords,
            )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(score, strict=options.strict)


async def check_ats_structure(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Run the RESUME-ONLY structural ATS check (no job, no composite score).

    Deterministic and job-independent: returns an
    :class:`~resume_kit_schemas.AtsStructureReport` carrying only section
    completeness and structural recommendations. This does NOT compute the
    job-requiring composite ``check-resume-ats`` — it surfaces the resume-only
    structural signal on its own.
    """
    if not isinstance(request, CheckAtsStructureRequest):
        return from_resume_kit_error(_bad_request(request, "CheckAtsStructureRequest"))
    try:
        report: AtsStructureReport = _check_ats_structure(request.resume)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(report, strict=options.strict)


async def check_resume_job_match(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Compute the deterministic resume/job match report."""
    if not isinstance(request, CheckResumeJobMatchRequest):
        return from_resume_kit_error(_bad_request(request, "CheckResumeJobMatchRequest"))
    try:
        with use_alias_file(request.alias_file):
            report: JobMatchReport = check_job_match(request.resume, request.job)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(report, strict=options.strict)


async def select_best_resume(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Select the best-matching resume from a set for a job."""
    if not isinstance(request, SelectBestResumeRequest):
        return from_resume_kit_error(_bad_request(request, "SelectBestResumeRequest"))
    try:
        result: ResumeSelectionResult = select_best(request.resumes, request.job, request.labels)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


async def compare_resume_versions(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Compare two resume versions against a job description."""
    if not isinstance(request, CompareResumeVersionsRequest):
        return from_resume_kit_error(_bad_request(request, "CompareResumeVersionsRequest"))
    try:
        result: ResumeComparisonResult = compare_versions(
            request.base,
            request.candidate,
            request.job,
            request.base_label,
            request.candidate_label,
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


async def identify_resume_gaps(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Analyse keyword gaps between a tailored resume, master, and job."""
    if not isinstance(request, IdentifyResumeGapsRequest):
        return from_resume_kit_error(_bad_request(request, "IdentifyResumeGapsRequest"))
    try:
        with use_alias_file(request.alias_file):
            gap: KeywordGapAnalysis = analyze_keyword_gaps(
                request.job, request.tailored, request.master
            )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(gap, strict=options.strict)


async def validate_resume_truth_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Validate a resume against candidate evidence for truthfulness."""
    if not isinstance(request, ValidateResumeTruthRequest):
        return from_resume_kit_error(_bad_request(request, "ValidateResumeTruthRequest"))
    try:
        with use_alias_file(request.alias_file):
            report: TruthReport = validate_resume_truth(
                request.resume,
                request.evidence,
                alias_file=str(request.alias_file) if request.alias_file else None,
            )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(report, strict=options.strict)


async def validate_faithfulness_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Deterministic faithfulness HARD GATE: source vs. ResumeDocument (RIT-T-0092).

    Pure and deterministic: never requires a provider and ignores ``no_llm``.
    Resolves the source text (either supplied directly, or decoded from source
    file bytes via the deterministic ``extract_resume_text`` engine) and returns
    a :class:`~resume_kit_schemas.FaithfulnessReport`. The report's ``passed`` is
    ``False`` iff a hard-fail finding exists; transports map that to a non-zero
    exit. Setting ``strict`` escalates the report's advisory warnings too, but
    the ``passed`` contract itself is driven only by error-severity findings.
    """
    if not isinstance(request, ValidateFaithfulnessRequest):
        return from_resume_kit_error(_bad_request(request, "ValidateFaithfulnessRequest"))
    try:
        source_text = _resolve_source_text(request)
        report: FaithfulnessReport = _check_faithfulness(source_text, request.resume)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(report, strict=options.strict)


def _resolve_source_text(request: ValidateFaithfulnessRequest) -> str:
    """Return the source text: given directly, or decoded from file bytes.

    Exactly one source input is expected. ``source_text`` wins when present;
    otherwise the raw ``source_content`` bytes are decoded through the
    deterministic ``extract_resume_text`` engine using ``source_filename`` (its
    extension drives docx/pdf/md/txt dispatch). A missing source is rejected.
    """
    if request.source_text is not None:
        return request.source_text
    if request.source_content is not None:
        filename = request.source_filename or "source.txt"
        result: TextExtractionResult = extract_resume_text(request.source_content, filename)
        return result.text
    from resume_kit_core.errors import CoreError, ErrorCode

    raise ResumeKitError(
        CoreError(
            code=ErrorCode.INVALID_INPUT,
            message="Provide either source_text or source_content for the source.",
        )
    )


async def build_candidate_evidence_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Build candidate evidence records from a resume."""
    if not isinstance(request, BuildCandidateEvidenceRequest):
        return from_resume_kit_error(_bad_request(request, "BuildCandidateEvidenceRequest"))
    try:
        evidence: list[CandidateEvidence] = build_candidate_evidence(
            request.resume, approved_claims=request.approved_claims
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(evidence, strict=options.strict)


async def record_edit_feedback_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Append edit feedback and an optional preference-pair record."""
    if not isinstance(request, RecordEditFeedbackRequest):
        return from_resume_kit_error(_bad_request(request, "RecordEditFeedbackRequest"))
    try:
        base_path = _optional_path(request.base_path)
        append_edit_feedback(request.feedback, base_path=base_path)
        if request.preference_pair is not None:
            append_preference_pair(request.preference_pair, base_path=base_path)
        result = RecordEditFeedbackResult(
            feedback=request.feedback,
            preference_pair=request.preference_pair,
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


async def rank_edit_candidates_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Rank edit candidates through the deterministic feedback ranker."""
    if not isinstance(request, RankEditCandidatesRequest):
        return from_resume_kit_error(_bad_request(request, "RankEditCandidatesRequest"))
    try:
        alias_file = (
            str(request.alias_file)
            if request.alias_file is not None
            else request.context.alias_file
        )
        context = request.context.model_copy(update={"alias_file": alias_file})
        with use_alias_file(alias_file):
            ranked = HeuristicRanker().rank(
                request.candidates,
                context,
                profile=request.profile,
            )
        result = RankEditCandidatesResult(ranked=ranked)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


async def refresh_preferences_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Derive and persist the user preference profile."""
    if not isinstance(request, RefreshPreferencesRequest):
        return from_resume_kit_error(_bad_request(request, "RefreshPreferencesRequest"))
    try:
        base_path = _optional_path(request.base_path)
        records = (
            read_edit_feedback(base_path=base_path) if request.records is None else request.records
        )
        profile = derive_preferences(records, now=request.now, base_path=base_path)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence failure
        return from_exception(exc)
    return build_success(profile, strict=options.strict)


async def add_evidence_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Persist one deterministic user-confirmed evidence record."""
    if not isinstance(request, AddEvidenceRequest):
        return from_resume_kit_error(_bad_request(request, "AddEvidenceRequest"))
    try:
        evidence_file = _normalize_evidence_file(request.evidence_file)
        path = working_dir(request.root) / evidence_file
        record = _confirmed_evidence(
            content=request.content,
            kind=request.kind,
            tags=request.tags,
        )
        evidence = load_evidence_file(path)
        evidence_by_id = {item.id: item for item in evidence}
        evidence_by_id[record.id] = record
        merged = sorted(evidence_by_id.values(), key=lambda item: item.id)
        save_evidence_file(path, merged)

        config = load_config(request.root)
        config.evidence_file = evidence_file
        if request.update_active:
            config.active_evidence = evidence_file
        save_config(request.root, config)

        result = AddEvidenceResult(
            evidence=record,
            evidence_file=evidence_file,
            active_evidence=config.active_evidence,
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any filesystem failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


async def open_edit_session_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Open and persist the single active edit session."""
    if not isinstance(request, OpenEditSessionRequest):
        return from_resume_kit_error(_bad_request(request, "OpenEditSessionRequest"))
    try:
        state, feedback = _edit_session.open_session(
            root=request.root,
            mode=request.mode,
            changes=request.changes,
            evidence=request.evidence,
            claim_provenance=request.claim_provenance,
            expected_score_deltas=request.expected_score_deltas,
        )
        for record in feedback:
            response = await record_edit_feedback_capability(
                RecordEditFeedbackRequest(
                    feedback=record,
                    base_path=working_dir(request.root),
                ),
                options,
            )
            if response.errors:
                return response
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence failure
        return from_exception(exc)
    return build_success(state, strict=options.strict)


async def session_prompt_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Load the active session and delegate prompt rendering to ReviewController."""
    if not isinstance(request, SessionPromptRequest):
        return from_resume_kit_error(_bad_request(request, "SessionPromptRequest"))
    try:
        response = _edit_session.prompt_session(request.root)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence failure
        return from_exception(exc)
    if isinstance(response, InterfaceResponse):
        return response
    return build_success(response, strict=options.strict)


async def decide_change_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Record one review decision and append the corresponding feedback log."""
    if not isinstance(request, DecideChangeRequest):
        return from_resume_kit_error(_bad_request(request, "DecideChangeRequest"))
    try:
        state, feedback = _edit_session.decide_change(
            root=request.root,
            path=request.path,
            action=request.action,
            reason_code=request.reason_code,
            note=request.note,
            edited_content=request.edited_content,
        )
        response = await record_edit_feedback_capability(
            RecordEditFeedbackRequest(
                feedback=feedback,
                base_path=working_dir(request.root),
            ),
            options,
        )
        if response.errors:
            return response
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence failure
        return from_exception(exc)
    return build_success(state, strict=options.strict)


async def commit_session_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Commit approved changes through the hard write gate."""
    if not isinstance(request, CommitSessionRequest):
        return from_resume_kit_error(_bad_request(request, "CommitSessionRequest"))
    try:
        result = _edit_session.commit_session(
            root=request.root,
            freedom=request.freedom,
            alias_timestamp=request.alias_timestamp,
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence/apply failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


async def session_status_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Return progress for the active edit session."""
    if not isinstance(request, SessionStatusRequest):
        return from_resume_kit_error(_bad_request(request, "SessionStatusRequest"))
    try:
        result = _edit_session.session_status(request.root)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


async def reconcile_session_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Re-hash the working resume after an intentional manual edit."""
    if not isinstance(request, ReconcileSessionRequest):
        return from_resume_kit_error(_bad_request(request, "ReconcileSessionRequest"))
    try:
        result = _edit_session.reconcile_session(request.root)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any persistence failure
        return from_exception(exc)
    return build_success(result, strict=options.strict)


def _optional_path(value: str | Path | None) -> Path | None:
    """Return ``value`` as a Path when supplied."""
    if value is None:
        return None
    return Path(value)


def _normalize_evidence_file(value: str) -> str:
    """Return a relative evidence path safe to join under ``resume-kit/``."""
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("evidence_file must be relative to resume-kit/.")
    return path.as_posix()


def _confirmed_evidence(
    *,
    content: str,
    kind: EvidenceKind,
    tags: list[str],
) -> CandidateEvidence:
    """Construct a deterministic user-confirmed evidence record."""
    normalized = " ".join(content.split())
    digest = hashlib.sha256(f"{kind.value}\n{normalized}".encode()).hexdigest()[:16]
    return CandidateEvidence(
        id=f"ev-confirmed-{digest}",
        kind=kind,
        content=content,
        source="user_confirmed",
        tags=sorted(dict.fromkeys(tags)),
        user_confirmed=True,
    )


class _InMemoryArtifactStore:
    """Deterministic in-memory :class:`ArtifactStore` used as the export default.

    Kept out of ``resume_kit_core.testing`` on purpose: production code must not
    import test fakes.  Stores bytes in a plain dict keyed by artifact id.
    """

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def put(
        self,
        artifact_id: str,
        artifact_type: str,
        data: object,
        *,
        content_type: str = "application/json",
        metadata: dict[str, object] | None = None,
    ) -> ArtifactRef:
        self._store[artifact_id] = data
        return ArtifactRef(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_type=content_type,
            metadata=metadata or {},
        )

    async def get(self, artifact_id: str) -> object:
        if artifact_id not in self._store:
            from resume_kit_core.errors import CoreError, ErrorCode

            raise ResumeKitError(
                CoreError(
                    code=ErrorCode.ARTIFACT_NOT_FOUND,
                    message=f"Artifact '{artifact_id}' not found.",
                )
            )
        return self._store[artifact_id]

    async def exists(self, artifact_id: str) -> bool:
        return artifact_id in self._store


async def export_resume(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Render a resume to bytes and persist them through an ArtifactStore.

    Deterministic: never requires ``provider`` and ignores ``no_llm``.  Raw
    bytes are kept out of ``data`` — the returned ``ArtifactRef`` (also carried
    in ``artifacts``) is the retrieval handle.
    """
    if not isinstance(request, ExportResumeRequest):
        return from_resume_kit_error(_bad_request(request, "ExportResumeRequest"))
    try:
        data = render(request.resume, request.format, request.options)
        artifact_id = request.resolved_artifact_id(data)
        content_type = mime_type(request.format)
        store: ArtifactStore = (
            options.artifact_store
            if options.artifact_store is not None
            else _InMemoryArtifactStore()
        )
        ref = await store.put(
            artifact_id,
            "resume",
            data,
            content_type=content_type,
            metadata={"format": request.format.value},
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(ref, artifacts=[ref], strict=options.strict)


async def suggest_terminology(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """List terminology-mirroring suggestions for a resume against a job.

    Deterministic, analysis-only (RIT-I-0010): returns the
    ``list[TerminologyAlignment]`` of alias hits the employer words differently.
    It never mutates the resume — a caller reviews the list and applies a chosen
    suggestion via :func:`align_terminology` (human-in-loop). Honors
    ``alias_file`` so grown project synonyms feed the suggestions.
    """
    if not isinstance(request, SuggestTerminologyRequest):
        return from_resume_kit_error(_bad_request(request, "SuggestTerminologyRequest"))
    try:
        with use_alias_file(request.alias_file):
            suggestions: list[TerminologyAlignment] = analyze_terminology_alignment(
                request.job, request.resume
            )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    return build_success(suggestions, strict=options.strict)


async def align_terminology(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Apply ONE accepted terminology suggestion and report the score delta.

    Deterministic (RIT-I-0010): swaps the resume's current wording for the
    employer's exact wording at a single chosen ``location``, routed through the
    Phase-4 policy + truth gates, and returns the updated resume plus the
    before/after delta. Human-in-loop by construction — exactly one accepted
    suggestion at one location is applied; there is no bulk apply. Honors
    ``alias_file`` so scoring reflects grown project synonyms.
    """
    if not isinstance(request, AlignTerminologyRequest):
        return from_resume_kit_error(_bad_request(request, "AlignTerminologyRequest"))
    try:
        with use_alias_file(request.alias_file):
            accepted = accept_terminology_alignment(
                request.suggestion,
                request.location,
                request.resume,
                request.job,
                list(request.evidence),
                freedom=request.freedom,
            )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any engine failure
        return from_exception(exc)
    result = AlignTerminologyResult(
        resume=accepted.resume,
        change=accepted.change,
        applied=accepted.applied,
        rejected=accepted.rejected,
        freedom=accepted.freedom,
        delta=TerminologyAlignmentDelta(
            keyword_match_before=accepted.delta.keyword_match_before,
            keyword_match_after=accepted.delta.keyword_match_after,
            keyword_match_delta=accepted.delta.keyword_match_delta,
            skills_coverage_before=accepted.delta.skills_coverage_before,
            skills_coverage_after=accepted.delta.skills_coverage_after,
            skills_coverage_delta=accepted.delta.skills_coverage_delta,
        ),
        truth_passed=accepted.truth_passed,
        swap_applied=accepted.swap_applied,
        location=accepted.location,
        field_before=accepted.field_before,
        field_after=accepted.field_after,
    )
    return build_success(result, strict=options.strict)


# ---------------------------------------------------------------------------
# Working-directory state capabilities (RIT-T-0091, filesystem-local)
# ---------------------------------------------------------------------------


async def init_project_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Idempotently scaffold the ``resume-kit/`` working-directory tree.

    Deterministic and filesystem-local (RIT-T-0091): never requires a provider
    and ignores ``no_llm``. Creates the folder tree + ``config.json`` and
    returns the resulting :class:`ProjectConfig` as data. Re-running preserves
    existing pointers and any unknown (preference) keys — no content is deleted.
    """
    if not isinstance(request, InitProjectRequest):
        return from_resume_kit_error(_bad_request(request, "InitProjectRequest"))
    try:
        config = init_project(request.root)
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any filesystem failure
        return from_exception(exc)
    return build_success(config, strict=options.strict)


async def set_active_capability(
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Record active resume/job pointers plus source paths through the schema.

    Deterministic and filesystem-local (RIT-T-0091): loads the existing config
    (preserving unknown keys and any pointer not being changed), updates the
    supplied pointer(s) and their source path(s), saves atomically, and returns
    the updated :class:`ProjectConfig`.
    """
    if not isinstance(request, SetActiveRequest):
        return from_resume_kit_error(_bad_request(request, "SetActiveRequest"))
    try:
        config = set_active(
            request.root,
            resume=request.resume,
            resume_source=request.resume_source,
            job=request.job,
            job_source=request.job_source,
        )
    except ResumeKitError as exc:
        return from_resume_kit_error(exc)
    except Exception as exc:  # noqa: BLE001 - map any filesystem/validation failure
        return from_exception(exc)
    return build_success(config, strict=options.strict)


# ---------------------------------------------------------------------------
# Capability registry
# ---------------------------------------------------------------------------

REGISTRY: dict[str, Capability] = {
    "extract-resume": extract_resume,
    "extract-resume-text": extract_resume_text_capability,
    "extract-job-description": extract_job_description,
    "check-resume-ats": check_resume_ats,
    "check-ats-structure": check_ats_structure,
    "check-resume-job-match": check_resume_job_match,
    "select-best-resume": select_best_resume,
    "compare-resume-versions": compare_resume_versions,
    "identify-resume-gaps": identify_resume_gaps,
    "align-resume": align_resume,
    "validate-resume-truth": validate_resume_truth_capability,
    "validate-faithfulness": validate_faithfulness_capability,
    "build-candidate-evidence": build_candidate_evidence_capability,
    "record-edit-feedback": record_edit_feedback_capability,
    "rank-edit-candidates": rank_edit_candidates_capability,
    "refresh-preferences": refresh_preferences_capability,
    "add-evidence": add_evidence_capability,
    "open-edit-session": open_edit_session_capability,
    "session-prompt": session_prompt_capability,
    "decide-change": decide_change_capability,
    "commit-session": commit_session_capability,
    "session-status": session_status_capability,
    "reconcile-session": reconcile_session_capability,
    "export-resume": export_resume,
    "suggest-terminology": suggest_terminology,
    "align-terminology": align_terminology,
    "init-project": init_project_capability,
    "set-active": set_active_capability,
}
