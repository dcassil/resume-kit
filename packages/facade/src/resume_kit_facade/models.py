"""Transport-agnostic request and options models for the capability facade.

These models carry only ``resume_kit_schemas`` value types plus a shared
:class:`CapabilityOptions` bundle.  They deliberately do NOT construct or import
any concrete LLM provider: a caller passes an already-built
:class:`~resume_kit_core.StructuredCompletionProvider` (or ``None``) via the
``provider`` option.  Transports translate their own inputs (CLI args, MCP tool
params, HTTP bodies) into these models before calling a capability.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field
from resume_kit_core import StructuredCompletionProvider
from resume_kit_core.storage import ArtifactStore
from resume_kit_export import ExportFormat, ExportOptions
from resume_kit_feedback.features import Candidate, FeatureContext
from resume_kit_feedback.ranker import RankedCandidate
from resume_kit_schemas import (
    ATSScore,
    CandidateEvidence,
    ClaimProvenance,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    JobDescription,
    JobMatchReport,
    PreferencePair,
    ProvenanceStatus,
    ResumeDocument,
    ReviewAction,
    ReviewSession,
    ScoreDelta,
    TerminologyAlignment,
    UserPreferenceProfile,
)
from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.results import PolicyRejection
from resume_kit_schemas.shape import ContentLedger, ShapeReport


@dataclass(frozen=True)
class CapabilityOptions:
    """Cross-capability execution options shared by every facade callable.

    Attributes:
        no_llm: Force the deterministic, provider-free path for capabilities
            that have one.  When True the ``provider`` is never invoked.
        strict: Escalate advisory warnings to failures in the response
            substrate (see ``build_success(strict=...)``).
        human_in_loop: Request human-in-the-loop behaviour for capabilities
            that support it (currently ``align-resume``).
        provider: An already-constructed structured-completion provider, or
            ``None``.  LLM-requiring capabilities return the stable
            provider-not-configured error when this is ``None`` and
            ``no_llm`` is False.
        artifact_store: Optional :class:`~resume_kit_core.storage.ArtifactStore`
            injection point for capabilities that persist rendered bytes (e.g.
            ``export-resume``).  When ``None`` such capabilities fall back to a
            deterministic in-memory store.  No concrete backend is required.
    """

    no_llm: bool = False
    strict: bool = False
    human_in_loop: bool = False
    provider: StructuredCompletionProvider | None = None
    artifact_store: ArtifactStore | None = None


@dataclass(frozen=True)
class ExtractResumeRequest:
    """Inputs for the extract-resume capability."""

    content: bytes
    filename: str


@dataclass(frozen=True)
class ExtractResumeTextRequest:
    """Inputs for the extract-resume-text capability (RIT-T-0090).

    Deterministic, no-LLM, no-network primitive: returns the raw extracted
    text of a resume/job file (docx/pdf/md/txt) as a ``TextExtractionResult``.
    Mirrors :class:`ExtractResumeRequest` (raw bytes + filename) — the filename
    extension drives deterministic dispatch in the document-parser engine.
    """

    content: bytes
    filename: str


@dataclass(frozen=True)
class InitProjectRequest:
    """Inputs for the init-project capability (RIT-T-0091).

    Deterministic, filesystem-local: idempotently scaffolds the ``resume-kit/``
    working-directory tree (``config.json`` + ``resumes/``, ``jobs/``,
    ``working/``, ``learning/``) under ``root`` and returns the resulting
    :class:`~resume_kit_facade.project_config.ProjectConfig`.  ``root`` defaults
    to the current directory.
    """

    root: str | Path = "."


@dataclass(frozen=True)
class SetActiveRequest:
    """Inputs for the set-active capability (RIT-T-0091).

    Records the ``active_resume`` / ``active_job`` pointer(s) plus the
    originating source file path(s) through the code-owned config schema. At
    least one of ``resume`` / ``job`` must be set; a ``*_source`` without its
    matching document is rejected by the capability. ``root`` defaults to the
    current directory.
    """

    resume: str | None = None
    resume_source: str | None = None
    job: str | None = None
    job_source: str | None = None
    root: str | Path = "."


@dataclass(frozen=True)
class BuildBaseRequest:
    """Inputs for the build-base capability (RIT-I-0016, RIT-T-0115).

    Deterministic, filesystem-local: runs the ``original -> base`` write path on
    the active original resume under ``root`` (structural check → auto-safe fixes
    → claim-preservation gate → persist ``<name>-base.json`` → record the ``base``
    pointer). ``mode`` currently supports only ``"auto"`` (auto-safe fixes;
    ``needs_judgment`` findings are deferred for the ``standard`` walkthrough).
    """

    root: str | Path = "."
    mode: str = "auto"


@dataclass(frozen=True)
class BuildStandardRequest:
    """Inputs for the build-standard capability (RIT-I-0016, RIT-T-0118).

    Deterministic, filesystem-local: runs the ``base -> standard`` best-practices
    write path under ``root`` (analyze best practices → apply auto-suggestible
    edits + any user-supplied ``answers`` rewrites keyed by
    ``resume_kit_scoring.finding_key`` → claim-preservation gate → persist
    ``<name>-standard.json`` → record the ``standard`` pointer). Findings needing
    user input that were not answered are returned as ``deferred``.
    """

    root: str | Path = "."
    answers: dict[str, str] | None = None


@dataclass(frozen=True)
class BuildPerfectRequest:
    """Inputs for the fit/build-perfect capability.

    Deterministic, filesystem-local: runs the job-aware budget fit against the
    resolved active resume and job under ``root``. ``decisions`` maps proposal
    paths to review actions for the explicit decision path; ``auto_fit`` uses
    ranked candidates to commit an automated fit through the same edit-session
    gate.
    """

    root: str | Path = "."
    job: str | None = None
    decisions: dict[str, str] | None = None
    auto_fit: bool = False


@dataclass(frozen=True)
class AnalyzeShapeRequest:
    """Inputs for the analyze-shape capability (RIT-I-0019, RIT-T-0138).

    Pure and deterministic: loads the shape policy for ``root`` and returns a
    read-only :class:`~resume_kit_schemas.shape.ShapeReport` for ``resume``. The
    analyzer never mutates the resume, writes files, or applies mappings.
    """

    resume: ResumeDocument
    root: str | Path = "."


@dataclass(frozen=True)
class BuildStructureRequest:
    """Inputs for the build-structure capability (RIT-I-0019, RIT-T-0138).

    Deterministic, filesystem-local: runs the ``base -> structure`` canonical
    shape build under ``root``. Optional ``answers`` map source-section display
    names to canonical section names. Ambiguous or unsupported mappings remain
    deferred by the engine.
    """

    root: str | Path = "."
    answers: dict[str, str] | None = None


@dataclass(frozen=True)
class AnalyzeBestPracticesRequest:
    """Inputs for the analyze-best-practices capability (RIT-I-0016, RIT-T-0117).

    Pure and deterministic: projects a ScoreDoc for ``resume`` at a fixed
    placement reference date (dates are irrelevant to generic best-practices
    analysis) and returns the generic, job-independent
    :class:`~resume_kit_schemas.BestPracticesReport`. Never requires a provider
    and ignores ``no_llm``; introduces no per-item LLM calls (NFR-001).
    """

    resume: ResumeDocument


@dataclass(frozen=True)
class AtsViewRequest:
    """Inputs for the ats-view capability (RIT-I-0016, RIT-T-0109).

    Pure and deterministic: projects a ScoreDoc for ``resume`` and returns the
    read-only :class:`~resume_kit_schemas.AtsViewReport` (what the ATS is likely
    to parse — sections, entities+YoE, zoned keywords). Never requires a provider
    and ignores ``no_llm``; introduces no per-item LLM calls (NFR-001).

    ``reference_date`` is a caller-supplied ISO ``YYYY-MM-DD`` used only for the
    years-of-experience computation on open-ended roles. When ``None`` the
    capability uses a fixed default so the report is byte-identical across
    surfaces that do not supply one.
    """

    resume: ResumeDocument
    reference_date: str | None = None


class BaseBuildResult(BaseModel):
    """Serializable outcome of the ``original -> base`` build (RIT-T-0115).

    Frozen facade response mirroring the engine's ``BuildBaseResult`` dataclass
    so CLI/MCP/API can return the write-path outcome as JSON.
    """

    model_config = {"frozen": True}

    base_path: str = Field(description="Written base version path, relative to resume-kit/.")
    applied: list[str] = Field(default_factory=list, description="Auto-safe fixes applied.")
    deferred: list[str] = Field(
        default_factory=list, description="Findings deferred to the standard walkthrough."
    )


class RefineBuildResult(BaseModel):
    """Serializable outcome of the ``base -> refine`` build (RIT-T-0118).

    Frozen facade response mirroring the engine's ``BuildRefineResult``
    dataclass so future surfaces can return the write-path outcome as JSON.
    """

    model_config = {"frozen": True}

    refine_path: str = Field(description="Written refine version path, relative to resume-kit/.")
    applied: list[str] = Field(default_factory=list, description="Best-practices edits applied.")
    deferred: list[str] = Field(
        default_factory=list, description="Findings needing user input that were not answered."
    )


class StandardBuildResult(BaseModel):
    """Serializable outcome of the ``base -> standard`` build (RIT-T-0118).

    Frozen facade response mirroring the engine's ``BuildStandardResult``
    dataclass so CLI/MCP/API can return the write-path outcome as JSON.
    """

    model_config = {"frozen": True}

    standard_path: str = Field(
        description="Written standard version path, relative to resume-kit/."
    )
    applied: list[str] = Field(default_factory=list, description="Best-practices edits applied.")
    deferred: list[str] = Field(
        default_factory=list, description="Findings needing user input that were not answered."
    )


class StructureBuildResult(BaseModel):
    """Serializable outcome of the ``base -> structure`` shape build.

    Frozen facade response mirroring the engine's ``BuildStructureResult`` so
    CLI/MCP/API can return the write-path outcome as JSON.
    """

    model_config = {"frozen": True}

    structure_path: str | None = Field(
        default=None,
        description="Written structure version path, relative to resume-kit/; null when gated.",
    )
    report: ShapeReport
    ledger: ContentLedger
    ledger_ok: bool
    claims_ok: bool
    applied: list[str] = Field(default_factory=list, description="Shape findings applied.")
    deferred: list[str] = Field(default_factory=list, description="Shape findings deferred.")


@dataclass(frozen=True)
class ValidateFaithfulnessRequest:
    """Inputs for the validate-faithfulness capability (RIT-T-0092).

    Deterministic HARD GATE: compares ``resume`` (the agent-produced
    :class:`~resume_kit_schemas.ResumeDocument`) against the ORIGINAL source
    document and returns a :class:`~resume_kit_schemas.FaithfulnessReport`. Never
    requires a provider and ignores ``no_llm`` — the check is pure/deterministic.

    Exactly one source input must be given: either pre-extracted ``source_text``
    OR the raw bytes of a source file (``source_content`` + ``source_filename``),
    which the capability decodes via the deterministic ``extract_resume_text``
    engine (docx/pdf/md/txt) before diffing.
    """

    resume: ResumeDocument
    source_text: str | None = None
    source_content: bytes | None = None
    source_filename: str | None = None


@dataclass(frozen=True)
class ExtractJobDescriptionRequest:
    """Inputs for the extract-job-description capability."""

    raw_text: str


@dataclass(frozen=True)
class CheckResumeAtsRequest:
    """Inputs for the check-resume-ats capability.

    ``alias_file`` is an optional path to a project alias JSON (RIT-T-0068
    format). When set, scoring becomes aware of those project synonyms for this
    call; ``None`` (the default) is seed-only, identical to pre-0009 behaviour.
    """

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class CheckAtsStructureRequest:
    """Inputs for the check-structure capability (RIT-T-0077).

    Resume-only: runs the deterministic structural ATS check on *resume* alone
    (section presence + structural recommendations). No job description and no
    alias file are involved — the check carries no keyword/skills-coverage
    signal, so project synonyms are irrelevant to it.
    """

    resume: ResumeDocument


@dataclass(frozen=True)
class CheckResumeJobMatchRequest:
    """Inputs for the check-resume-job-match capability.

    ``alias_file`` optionally points at a project alias JSON (RIT-T-0068
    format) to make matching aware of project synonyms for this call; ``None``
    (default) is seed-only, identical to pre-0009 behaviour.
    """

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class SelectBestResumeRequest:
    """Inputs for the select-resume capability."""

    resumes: Sequence[ResumeDocument]
    job: JobDescription
    labels: Sequence[str] | None = None


@dataclass(frozen=True)
class CompareResumeVersionsRequest:
    """Inputs for the compare-versions capability."""

    base: ResumeDocument
    candidate: ResumeDocument
    job: JobDescription
    base_label: str = "base"
    candidate_label: str = "candidate"


@dataclass(frozen=True)
class IdentifyResumeGapsRequest:
    """Inputs for the check-gaps capability.

    ``alias_file`` optionally points at a project alias JSON (RIT-T-0068
    format) to make gap analysis aware of project synonyms for this call;
    ``None`` (default) is seed-only, identical to pre-0009 behaviour.
    """

    job: JobDescription
    tailored: ResumeDocument
    master: ResumeDocument
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class AlignResumeRequest:
    """Inputs for the align-resume capability."""

    resume: ResumeDocument
    job: JobDescription
    evidence: Sequence[CandidateEvidence] | None = None


@dataclass(frozen=True)
class ValidateResumeTruthRequest:
    """Inputs for the validate-facts capability."""

    resume: ResumeDocument
    evidence: list[CandidateEvidence] = field(default_factory=list)
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class BuildCandidateEvidenceRequest:
    """Inputs for the extract-evidence capability."""

    resume: ResumeDocument
    approved_claims: list[CandidateEvidence] | list[str] | None = None


@dataclass(frozen=True)
class RecordEditFeedbackRequest:
    """Inputs for the record-edit-feedback capability.

    ``base_path`` points at the ``resume-kit/`` working directory whose
    ``learning/`` logs should receive the records. When omitted, the feedback
    engine's default ``resume-kit/`` path is used.
    """

    feedback: EditFeedback
    preference_pair: PreferencePair | None = None
    base_path: str | Path | None = None


@dataclass(frozen=True)
class RankEditCandidatesRequest:
    """Inputs for the rank-edit-candidates capability."""

    candidates: list[Candidate]
    context: FeatureContext
    profile: UserPreferenceProfile = field(default_factory=UserPreferenceProfile)
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class RefreshPreferencesRequest:
    """Inputs for the refresh-preferences capability.

    When ``records`` is ``None``, persisted records are loaded from
    ``base_path`` before deriving the profile. ``now`` is caller-supplied data
    for deterministic time-decay.
    """

    now: str
    records: list[EditFeedback] | None = None
    base_path: str | Path | None = None


EditSessionMode = str


@dataclass(frozen=True)
class OpenEditSessionRequest:
    """Inputs for opening the single active edit session."""

    mode: EditSessionMode
    changes: list[ChangeProposal]
    root: str | Path = "."
    evidence: list[CandidateEvidence] = field(default_factory=list)
    claim_provenance: list[ClaimProvenance] = field(default_factory=list)
    expected_score_deltas: list[ScoreDelta] = field(default_factory=list)


@dataclass(frozen=True)
class SessionPromptRequest:
    """Inputs for loading and prompting the active edit session."""

    root: str | Path = "."


@dataclass(frozen=True)
class DecideChangeRequest:
    """Inputs for recording one terminal or reopen decision."""

    path: str
    action: ReviewAction
    reason_code: EditFeedbackReasonCode | None = None
    note: str | None = None
    root: str | Path = "."
    edited_content: str | None = None


@dataclass(frozen=True)
class CommitSessionRequest:
    """Inputs for committing gated, reviewed changes to the working resume."""

    root: str | Path = "."
    freedom: int = 10
    alias_timestamp: str | None = None


@dataclass(frozen=True)
class SessionStatusRequest:
    """Inputs for reading edit-session progress."""

    root: str | Path = "."


@dataclass(frozen=True)
class ReconcileSessionRequest:
    """Inputs for accepting an intentional out-of-band working-file edit."""

    root: str | Path = "."


class EditSessionState(BaseModel):
    """Persisted edit-session envelope wrapping ``ReviewSession``."""

    session_id: str
    mode: str
    active_resume: str
    active_job: str
    working_path: str
    review_session: ReviewSession
    original_hash: str
    committed_hash: str | None = None


class EditSessionStatus(BaseModel):
    """Serializable progress report for the active edit session."""

    session_id: str
    mode: str
    active_resume: str
    active_job: str
    working_path: str
    progress: dict[str, int]
    decided: list[str] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    deferred: list[str] = Field(default_factory=list)
    truth_summary: dict[ProvenanceStatus, int] = Field(default_factory=dict)
    committed_hash: str | None = None


class AliasGrowthEntry(BaseModel):
    """Project alias learned from an accepted terminology edit."""

    canonical: str
    alias: str
    original_term: str
    accepted_term: str
    source: str = "accepted_edit"
    timestamp: str
    alias_file: str


class CommitSessionResult(BaseModel):
    """Result of a gated edit-session commit."""

    state: EditSessionState
    applied: list[ChangeProposal] = Field(default_factory=list)
    rejected: list[PolicyRejection] = Field(default_factory=list)
    grown_aliases: list[AliasGrowthEntry] = Field(default_factory=list)
    before_match_report: JobMatchReport | None = None
    after_match_report: JobMatchReport | None = None
    before_ats_score: ATSScore | None = None
    after_ats_score: ATSScore | None = None


class ReconcileSessionResult(BaseModel):
    """Result of re-hashing a manually edited working resume."""

    state: EditSessionState
    previous_hash: str | None = None
    reconciled_hash: str | None = None


@dataclass(frozen=True)
class AddEvidenceRequest:
    """Inputs for adding one deterministic user-confirmed evidence record."""

    content: str
    kind: EvidenceKind
    tags: list[str] = field(default_factory=list)
    root: str | Path = "."
    evidence_file: str = "working/user-confirmed-evidence.json"
    update_active: bool = False


class AddEvidenceResult(BaseModel):
    """Serializable result for a persisted user-confirmed evidence record."""

    model_config = {"frozen": True}

    evidence: CandidateEvidence = Field(description="The confirmed evidence record.")
    evidence_file: str = Field(
        description="Evidence file path relative to the resume-kit working dir."
    )
    active_evidence: str | None = Field(
        default=None, description="Updated active evidence pointer, if requested."
    )


class RecordEditFeedbackResult(BaseModel):
    """Serializable result after persisting feedback records."""

    model_config = {"frozen": True}

    feedback: EditFeedback = Field(description="The persisted feedback record.")
    preference_pair: PreferencePair | None = Field(
        default=None, description="Optional persisted preference-pair record."
    )


class RankEditCandidatesResult(BaseModel):
    """Serializable ranked candidate list."""

    model_config = {"frozen": True}

    ranked: list[RankedCandidate] = Field(description="Truth-passing ranked candidates.")


@dataclass(frozen=True)
class ExportResumeRequest:
    """Inputs for the export-resume capability.

    The exported artifact id is deterministic: a caller may supply an explicit
    ``artifact_id``; otherwise :meth:`resolved_artifact_id` derives a stable
    SHA-256-based id over the format plus rendered content — no UUIDs,
    timestamps, or random values.
    """

    resume: ResumeDocument
    format: ExportFormat
    options: ExportOptions | None = None
    artifact_id: str | None = None

    def resolved_artifact_id(self, data: bytes) -> str:
        """Return the caller-supplied id or a deterministic hash-derived one."""
        if self.artifact_id is not None:
            return self.artifact_id
        digest = hashlib.sha256(self.format.value.encode("utf-8") + data)
        return f"resume-{self.format.value}-{digest.hexdigest()}"


@dataclass(frozen=True)
class SuggestTerminologyRequest:
    """Inputs for the suggest-terminology capability (RIT-I-0010).

    Analysis-only: lists the terminology-mirroring suggestions for *resume*
    against *job* (each an alias hit the employer words differently). No
    mutation happens; a caller reviews the list and then applies a chosen
    suggestion via the align-terminology capability (human-in-loop).

    ``alias_file`` optionally points at a project alias JSON (RIT-T-0068
    format) so grown project synonyms feed the suggestions for this call;
    ``None`` (default) is seed-only, identical to pre-0009 behaviour.
    """

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class AlignTerminologyRequest:
    """Inputs for the align-terminology capability (RIT-I-0010).

    Applies exactly ONE accepted terminology suggestion (never a bulk apply):
    it swaps the resume's current wording for the employer's exact wording at a
    single chosen ``location``, routed through the Phase-4 policy + truth gates,
    and reports the before/after score delta.

    Attributes:
        suggestion: The accepted alias-backed suggestion to apply.
        location: One resume path drawn from ``suggestion.locations`` — the
            field whose surface term is rewritten.
        resume: The resume to edit (never mutated; a new document is returned).
        job: The target job description, used for the score delta.
        evidence: Ground-truth candidate evidence for truth re-validation.
        freedom: Optional explicit policy-freedom level; when ``None`` the
            minimal sufficient level for ``location`` is used.
        alias_file: Optional project alias JSON path (see
            :class:`SuggestTerminologyRequest`).
    """

    suggestion: TerminologyAlignment
    location: str
    resume: ResumeDocument
    job: JobDescription
    evidence: Sequence[CandidateEvidence] = field(default_factory=tuple)
    freedom: int | None = None
    alias_file: str | Path | None = None


class TerminologyAlignmentDelta(BaseModel):
    """Deterministic before/after keyword-match + skills-coverage scores.

    Serializable mirror of the alignment engine's ``ScoreDelta`` dataclass so
    the applied-terminology outcome can be returned as JSON by every surface.
    ``*_delta`` fields are ``after - before`` (positive means improvement).
    """

    model_config = {"frozen": True}

    keyword_match_before: float = Field(description="Keyword-match score before.")
    keyword_match_after: float = Field(description="Keyword-match score after.")
    keyword_match_delta: float = Field(description="after - before keyword match.")
    skills_coverage_before: float = Field(description="Skills-coverage score before.")
    skills_coverage_after: float = Field(description="Skills-coverage score after.")
    skills_coverage_delta: float = Field(description="after - before skills coverage.")


class AlignTerminologyResult(BaseModel):
    """Serializable outcome of applying one accepted terminology suggestion.

    Frozen facade response mirroring the alignment engine's ``AcceptResult``
    dataclass (which is not a schema model) so CLI/MCP/API can return the
    applied result — the updated resume, the change, policy applied/rejected
    records, the freedom used, the before/after score delta, whether truth
    still passed and whether the swap actually fired — as JSON.
    """

    model_config = {"frozen": True}

    resume: ResumeDocument = Field(description="Updated resume (untouched on reject).")
    change: ChangeProposal = Field(description="The single surface-swap change.")
    applied: list[ChangeProposal] = Field(
        default_factory=list, description="Changes the policy gate applied."
    )
    rejected: list[PolicyRejection] = Field(
        default_factory=list, description="Policy rejections, if any."
    )
    freedom: int = Field(description="Policy-freedom level the swap was gated at.")
    delta: TerminologyAlignmentDelta = Field(description="Before/after score delta.")
    truth_passed: bool = Field(description="Whether truth validation still passed.")
    swap_applied: bool = Field(description="Whether the surface swap actually fired.")
    location: str = Field(description="Resume path the swap targeted.")
    field_before: str = Field(default="", description="Field text before the swap.")
    field_after: str = Field(default="", description="Field text after the swap.")
