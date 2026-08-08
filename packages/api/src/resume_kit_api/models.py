"""HTTP transport request bodies for the Resume Kit REST API.

Each model is a thin pydantic wrapper carrying ``resume_kit_schemas`` domain
value types plus the shared execution flags (:attr:`no_llm`, :attr:`strict`,
:attr:`human_in_loop`).  Bodies are validated by FastAPI and then translated
into the frozen ``resume_kit_facade`` request dataclasses by the routes; no
business logic lives here.  The API never accepts or constructs a concrete LLM
provider, so provider-requiring capabilities run only when the caller also sets
``no_llm`` (the deterministic path) — otherwise the facade returns the stable
provider-not-configured envelope.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from resume_kit_export.models import ExportFormat, ExportOptions
from resume_kit_feedback import Candidate, FeatureContext
from resume_kit_schemas import (
    CandidateEvidence,
    ChangeProposal,
    ClaimProvenance,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    JobDescription,
    PreferencePair,
    ResumeDocument,
    ReviewAction,
    ScoreDelta,
    TerminologyAlignment,
    UserPreferenceProfile,
)


class _Options(BaseModel):
    """Execution flags shared by every endpoint body.

    ``provider`` is intentionally absent: the HTTP transport does not build or
    accept providers.  LLM paths are reachable only through the deterministic
    ``no_llm`` route; otherwise the facade emits provider-not-configured.
    """

    no_llm: bool = Field(default=False, description="Force the deterministic path.")
    strict: bool = Field(default=False, description="Escalate warnings to errors.")
    human_in_loop: bool = Field(default=False, description="Request human-in-the-loop behaviour.")


class ExtractResumeBody(_Options):
    """Body for ``POST /extract`` — raw resume text plus a filename."""

    content: str = Field(description="Raw resume text to extract from.")
    filename: str = Field(default="resume.txt", description="Source filename.")


class ExtractResumeTextBody(_Options):
    """Body for ``POST /extract-text`` — raw file text plus a filename.

    Deterministic, no-LLM primitive (RIT-T-0090): returns the extracted
    ``TextExtractionResult``. Over HTTP ``content`` is a UTF-8 string (encoded
    to bytes by the route), so this endpoint serves the plain-text / Markdown
    decode path; the filename extension drives deterministic dispatch.
    """

    content: str = Field(description="Raw file text to extract from.")
    filename: str = Field(default="resume.txt", description="Source filename.")


class ExtractJobDescriptionBody(_Options):
    """Body for ``POST /extract-job``."""

    raw_text: str = Field(description="Raw job-description text.")


class CheckResumeAtsBody(_Options):
    """Body for ``POST /check-ats``."""

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class CheckAtsStructureBody(_Options):
    """Body for ``POST /check-structure`` — resume only, no job."""

    resume: ResumeDocument


class CheckResumeJobMatchBody(_Options):
    """Body for ``POST /match``."""

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class SelectBestResumeBody(_Options):
    """Body for ``POST /select``."""

    resumes: list[ResumeDocument]
    job: JobDescription
    labels: list[str] | None = None


class CompareResumeVersionsBody(_Options):
    """Body for ``POST /compare``."""

    base: ResumeDocument
    candidate: ResumeDocument
    job: JobDescription
    base_label: str = "base"
    candidate_label: str = "candidate"


class IdentifyResumeGapsBody(_Options):
    """Body for ``POST /identify-gaps``."""

    job: JobDescription
    tailored: ResumeDocument
    master: ResumeDocument
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class SuggestTerminologyBody(_Options):
    """Body for ``POST /suggest-terminology``."""

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class AlignTerminologyBody(_Options):
    """Body for ``POST /align-terminology`` — apply ONE accepted suggestion."""

    suggestion: TerminologyAlignment = Field(
        description="The accepted terminology-mirroring suggestion to apply."
    )
    location: str = Field(
        description="Resume path from ``suggestion.locations`` to apply the swap at."
    )
    resume: ResumeDocument
    job: JobDescription
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    freedom: int | None = Field(
        default=None,
        description="Explicit policy-freedom level; default is the minimal level.",
    )
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class AlignResumeBody(_Options):
    """Body for ``POST /align``."""

    resume: ResumeDocument
    job: JobDescription
    evidence: list[CandidateEvidence] | None = None


class EvidenceEnvelope(BaseModel):
    """Evidence records carried in a first-party response envelope."""

    data: list[CandidateEvidence] = Field(default_factory=list)


class ValidateResumeTruthBody(_Options):
    """Body for ``POST /validate-truth``."""

    resume: ResumeDocument
    evidence: list[CandidateEvidence] | EvidenceEnvelope = Field(default_factory=list)
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware validation.",
    )


class ValidateFaithfulnessBody(_Options):
    """Body for ``POST /validate-faithfulness`` — deterministic HARD GATE.

    Compares ``resume`` against the ORIGINAL source. Supply exactly one source
    input: ``source_text`` (pre-extracted) OR ``source_content`` (raw file text,
    UTF-8 encoded to bytes by the route) plus ``source_filename`` whose extension
    drives docx/pdf/md/txt dispatch.
    """

    resume: ResumeDocument
    source_text: str | None = Field(
        default=None, description="Pre-extracted source text to diff against."
    )
    source_content: str | None = Field(
        default=None, description="Raw source file text (encoded to bytes)."
    )
    source_filename: str = Field(
        default="source.txt", description="Source filename (extension drives decode)."
    )


class BuildCandidateEvidenceBody(_Options):
    """Body for ``POST /build-evidence``."""

    resume: ResumeDocument
    approved_claims: list[CandidateEvidence] | list[str] | None = None


class AddEvidenceBody(_Options):
    """Body for ``POST /add-evidence``."""

    content: str = Field(description="Confirmed evidence content.")
    kind: EvidenceKind = Field(default=EvidenceKind.USER_STATEMENT)
    tags: list[str] = Field(default_factory=list)
    confirmed: bool = Field(
        default=False, description="Must be true to persist confirmed evidence."
    )
    root: str = Field(default=".", description="Project root containing resume-kit/.")
    evidence_file: str = Field(default="working/user-confirmed-evidence.json")
    update_active: bool = Field(default=False)


class RecordEditFeedbackBody(_Options):
    """Body for ``POST /record-edit-feedback``."""

    feedback: EditFeedback
    preference_pair: PreferencePair | None = None
    base_path: str | None = None


class RankEditCandidatesBody(_Options):
    """Body for ``POST /rank-edit-candidates``."""

    candidates: list[Candidate]
    context: FeatureContext
    profile: UserPreferenceProfile = Field(default_factory=UserPreferenceProfile)
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware validation.",
    )


class RefreshPreferencesBody(_Options):
    """Body for ``POST /refresh-preferences``."""

    now: str = Field(description="Caller-supplied ISO timestamp.")
    records: list[EditFeedback] | None = None
    base_path: str | None = None


class OpenEditSessionBody(_Options):
    """Body for ``POST /review-edits/open``."""

    mode: str = Field(description="interactive, review_at_end, or auto.")
    changes: list[ChangeProposal]
    root: str = Field(default=".", description="Project root containing resume-kit/.")
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    claim_provenance: list[ClaimProvenance] = Field(default_factory=list)
    expected_score_deltas: list[ScoreDelta] = Field(default_factory=list)


class SessionRootBody(_Options):
    """Body for session operations that only need a project root."""

    root: str = Field(default=".", description="Project root containing resume-kit/.")


class DecideChangeBody(_Options):
    """Body for ``POST /review-edits/decide``."""

    path: str
    action: ReviewAction
    reason_code: EditFeedbackReasonCode | None = None
    note: str | None = None
    root: str = Field(default=".", description="Project root containing resume-kit/.")
    edited_content: str | None = None


class CommitSessionBody(_Options):
    """Body for ``POST /review-edits/commit``."""

    root: str = Field(default=".", description="Project root containing resume-kit/.")
    freedom: int = Field(default=10, ge=0, le=10)
    alias_timestamp: str | None = Field(
        default=None,
        description="Optional ISO timestamp for accepted-edit alias provenance.",
    )


class InitProjectBody(_Options):
    """Body for ``POST /init`` — scaffold the resume-kit/ working directory.

    Filesystem-local (RIT-T-0091): idempotently creates the tree + config.json
    under ``root`` (default: the server's current directory) and returns the
    resulting ``ProjectConfig``.
    """

    root: str = Field(default=".", description="Project root containing resume-kit/.")


class SetActiveBody(_Options):
    """Body for ``POST /set-active`` — record active pointers + source paths.

    At least one of ``resume`` / ``job`` must be set; a ``*_source`` without its
    matching document is rejected by the capability.
    """

    resume: str | None = Field(
        default=None, description="Active resume JSON path (relative to resume-kit/)."
    )
    resume_source: str | None = Field(
        default=None, description="Original source file the active resume came from."
    )
    job: str | None = Field(
        default=None, description="Active job JSON path (relative to resume-kit/)."
    )
    job_source: str | None = Field(
        default=None, description="Original source file the active job came from."
    )
    root: str = Field(default=".", description="Project root containing resume-kit/.")


class BuildBaseBody(_Options):
    """Body for ``POST /build-base`` — run the original->base write path.

    Filesystem-local (RIT-T-0115): runs the structural check + auto-safe fixes
    under ``root`` behind the claim-preservation gate, writes the ``base``
    version, and records the pointer. ``mode`` currently supports only ``auto``.
    """

    root: str = Field(default=".", description="Project root containing resume-kit/.")
    mode: str = Field(default="auto", description="Fix mode (only 'auto' is supported).")


class BuildStandardBody(_Options):
    """Body for ``POST /build-standard`` — run the base->standard write path.

    Deprecated alias for ``POST /build-refine``. Kept with the same input shape
    for callers still using the legacy route.
    """

    root: str = Field(default=".", description="Project root containing resume-kit/.")
    answers: dict[str, str] | None = Field(
        default=None,
        description="Optional map of finding keys to user-supplied rewrites.",
    )


class BuildRefineBody(BuildStandardBody):
    """Body for ``POST /build-refine`` — run the base->refine wording pass."""


class AnalyzeShapeBody(_Options):
    """Body for ``POST /analyze-shape`` — resume shape report, no writes.

    Pure and deterministic (RIT-T-0138): loads the shape policy for ``root`` and
    returns a read-only shape report for the supplied resume.
    """

    resume: ResumeDocument
    root: str = Field(default=".", description="Project root containing resume-kit/.")


class BuildStructureBody(_Options):
    """Body for ``POST /build-structure`` — run the base->structure shape path.

    Filesystem-local (RIT-T-0138): applies report-driven, non-destructive shape
    transforms under ``root`` behind content-ledger and cross-section claim
    gates, writes the ``structure`` version on success, and records lineage.
    """

    root: str = Field(default=".", description="Project root containing resume-kit/.")
    answers: dict[str, str] | None = Field(
        default=None,
        description="Optional map of source section names to canonical targets.",
    )


class AnalyzeBestPracticesBody(_Options):
    """Body for ``POST /analyze-best-practices`` — resume only, no job.

    Pure and deterministic (RIT-T-0117): returns the generic, job-independent
    ``BestPracticesReport`` for the resume.
    """

    resume: ResumeDocument


class AtsViewBody(_Options):
    """Body for ``POST /ats-view`` — resume only, read-only ATS view.

    Pure and deterministic (RIT-T-0109): returns the read-only
    ``AtsViewReport`` (sections, entities+YoE, zoned keywords). ``reference_date``
    is an optional ISO ``YYYY-MM-DD`` used only for years-of-experience.
    """

    resume: ResumeDocument
    reference_date: str | None = Field(
        default=None,
        description="Optional ISO reference date (YYYY-MM-DD) for years-of-experience.",
    )


class ExportResumeBody(_Options):
    """Body for ``POST /export`` — render a resume to ``pdf`` or ``docx``.

    ``format`` selects the output; ``options`` carries the deterministic export
    tuning (fonts, margins, page size).  ``artifact_id`` may override the
    deterministic hash-derived id.
    """

    resume: ResumeDocument
    format: ExportFormat
    options: ExportOptions | None = None
    artifact_id: str | None = None
