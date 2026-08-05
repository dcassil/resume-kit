"""Phase 4 result schemas for resume-kit.

New resume-kit result-schema module (no upstream port; no attribution row
needed). These models compose the existing canonical resume, change, evidence,
provenance, and analysis schemas into transport-agnostic result envelopes.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from .analysis import ATSScore, JobMatchReport, ScoreDelta
from .change import ChangeAction, ChangeProposal, ChangeSet, Diff, ResumeDiffSummary
from .common import Warning
from .evidence import CandidateEvidence, EvidenceKind
from .job import JobDescription
from .provenance import ClaimProvenance, ProvenanceStatus
from .resume import ResumeDocument


class PolicyReasonCode(StrEnum):
    """Stable reason codes for freedom-policy decisions and rejections."""

    ALLOWED = "allowed"
    BLOCKED_PATH = "blocked_path"
    BLOCKED_FIELD = "blocked_field"
    FREEDOM_TOO_LOW = "freedom_too_low"
    UNSUPPORTED_SKILL = "unsupported_skill"
    DUPLICATE_SKILL = "duplicate_skill"
    ORIGINAL_MISMATCH = "original_mismatch"
    UNSUPPORTED_ACTION = "unsupported_action"
    MALFORMED_PATH = "malformed_path"
    TRUTH_VALIDATION_FAILED = "truth_validation_failed"
    REVIEW_REJECTED = "review_rejected"


class PolicyDecision(BaseModel):
    """Freedom-aware allow/block result for one proposed change target."""

    freedom_level: int = Field(default=0, ge=0, le=10)
    allowed: bool = True
    reason_code: PolicyReasonCode = PolicyReasonCode.ALLOWED
    explanation: str = ""
    path: str = ""
    action: ChangeAction = "replace"
    change: ChangeProposal | None = None


class PolicyRejection(BaseModel):
    """Minimal rejection record for a blocked or unapplied proposal."""

    path: str = ""
    action: ChangeAction = "replace"
    reason_code: PolicyReasonCode = PolicyReasonCode.BLOCKED_PATH
    explanation: str = ""
    change: ChangeProposal | None = None


class SkillTargetSource(StrEnum):
    """Why a skill target is considered grounded enough to add."""

    EXISTING = "existing"
    JD_ADDED = "jd_added"
    SUPPORTED_BY_RESUME = "supported_by_resume"
    EVIDENCE_BACKED = "evidence_backed"


class SkillTarget(BaseModel):
    """An accepted skill-addition target after deterministic gate checks."""

    normalized_skill: str = ""
    display_skill: str = ""
    source: SkillTargetSource = SkillTargetSource.EXISTING
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_kinds: list[EvidenceKind] = Field(default_factory=list)


class SkillTargetRejection(BaseModel):
    """A proposed skill target rejected by the deterministic gate."""

    normalized_skill: str = ""
    display_skill: str = ""
    reason_code: PolicyReasonCode = PolicyReasonCode.UNSUPPORTED_SKILL
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class SkillTargetPlan(BaseModel):
    """Verified and rejected skill-addition targets from a planner/gate."""

    proposed_skills: list[str] = Field(default_factory=list)
    accepted_targets: list[SkillTarget] = Field(default_factory=list)
    rejected_targets: list[SkillTargetRejection] = Field(default_factory=list)
    supporting_evidence: list[CandidateEvidence] = Field(default_factory=list)
    accepted_changes: list[ChangeProposal] = Field(default_factory=list)
    rejected_changes: list[PolicyRejection] = Field(default_factory=list)
    job: JobDescription | None = None

    @property
    def verified_skills(self) -> list[str]:
        """Accepted display skills, preserving deterministic target order."""

        return [target.display_skill for target in self.accepted_targets]

    @property
    def unverified_skills(self) -> list[str]:
        """Rejected display skills, preserving deterministic target order."""

        return [target.display_skill for target in self.rejected_targets]


class TruthReport(BaseModel):
    """Per-claim provenance plus a deterministic truth-validation summary."""

    claims: list[ClaimProvenance] = Field(default_factory=list)
    status_counts: dict[ProvenanceStatus, int] = Field(default_factory=dict)
    needs_evidence_count: int = 0
    contradiction_count: int = 0
    has_unsupported_or_contradicted: bool = False
    passed: bool = True

    @model_validator(mode="after")
    def _summarize_claim_statuses(self) -> TruthReport:
        counts = {status: 0 for status in ProvenanceStatus}
        for claim in self.claims:
            counts[claim.status] += 1

        has_failure = (
            counts[ProvenanceStatus.UNSUPPORTED] > 0 or counts[ProvenanceStatus.CONTRADICTED] > 0
        )
        self.status_counts = counts
        self.needs_evidence_count = counts[ProvenanceStatus.UNSUPPORTED]
        self.contradiction_count = counts[ProvenanceStatus.CONTRADICTED]
        self.has_unsupported_or_contradicted = has_failure
        self.passed = not has_failure
        return self


class FaithfulnessCode(StrEnum):
    """Stable finding codes for the deterministic faithfulness gate.

    Each code names one class of drift between an original source document and
    the agent-produced :class:`ResumeDocument` JSON. ``severity`` on the finding
    (error vs warning) — not the code — decides whether the gate hard-fails; the
    code identifies *what* drifted.
    """

    BULLET_COUNT_MISMATCH = "BULLET_COUNT_MISMATCH"
    SECTION_COUNT_MISMATCH = "SECTION_COUNT_MISMATCH"
    DROPPED_SPANS = "DROPPED_SPANS"
    DROPPED_TOKENS = "DROPPED_TOKENS"
    ALTERED_FIELD = "ALTERED_FIELD"
    ADDED_TOKENS = "ADDED_TOKENS"
    NON_ASCII = "NON_ASCII"


class FaithfulnessFinding(BaseModel):
    """One drift finding from the deterministic faithfulness comparison.

    ``severity`` is ``"error"`` for HARD-FAIL findings (which set the report's
    ``passed`` to ``False``) and ``"warning"`` for advisory ones that never fail
    the gate. ``items`` carries the offending content (dropped spans, altered
    field values, added tokens, non-ASCII glyphs) so a caller can act on it.
    """

    model_config = {"frozen": True}

    code: FaithfulnessCode = Field(description="Which class of drift was found.")
    severity: str = Field(description="'error' (hard-fail) or 'warning' (advisory).")
    message: str = Field(description="Human-readable explanation of the finding.")
    items: list[str] = Field(default_factory=list, description="The offending items, if any.")


class FaithfulnessReport(BaseModel):
    """Deterministic source-vs-JSON faithfulness report (RIT-T-0092).

    Produced by comparing an original source document (extracted text) against
    the agent-produced :class:`ResumeDocument`. ``passed`` is ``False`` iff any
    finding carries ``severity == "error"`` (a HARD-FAIL). The report is data,
    never an exception; a transport maps ``passed=False`` to a non-zero exit.
    """

    passed: bool = Field(default=True, description="False iff any error-severity finding exists.")
    findings: list[FaithfulnessFinding] = Field(
        default_factory=list, description="All drift findings, error and warning."
    )

    @model_validator(mode="after")
    def _derive_passed(self) -> FaithfulnessReport:
        self.passed = not any(f.severity == "error" for f in self.findings)
        return self


class ReviewAction(StrEnum):
    """Human review actions supported by the section review controller."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    RETRY = "retry"
    REDUCE_FREEDOM = "reduce_freedom"
    INCREASE_FREEDOM = "increase_freedom"
    SKIP = "skip"


class ReviewDecision(BaseModel):
    """A single human review action for one resume section."""

    section: str = ""
    action: ReviewAction = ReviewAction.APPROVE
    edited_content: str | None = None
    freedom_target: int | None = Field(default=None, ge=0, le=10)
    explanation: str = ""
    changes: list[ChangeProposal] = Field(default_factory=list)


class ReviewSession(BaseModel):
    """Interface-agnostic human-in-the-loop state across resume sections."""

    sections: list[str] = Field(default_factory=list)
    current_section: str | None = None
    decisions: list[ReviewDecision] = Field(default_factory=list)
    awaiting_input: bool = False
    complete: bool = False
    pending_changes: list[ChangeProposal] = Field(default_factory=list)
    claim_provenance: list[ClaimProvenance] = Field(default_factory=list)
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    expected_score_deltas: list[ScoreDelta] = Field(default_factory=list)


class AlignmentResult(BaseModel):
    """Top-level controlled-alignment result envelope."""

    original_resume: ResumeDocument = Field(default_factory=ResumeDocument)
    aligned_resume: ResumeDocument = Field(default_factory=ResumeDocument)
    job: JobDescription | None = None
    applied_changes: list[ChangeProposal] = Field(default_factory=list)
    change_set: ChangeSet = Field(default_factory=ChangeSet)
    rejected_changes: list[PolicyRejection] = Field(default_factory=list)
    diffs: list[Diff] = Field(default_factory=list)
    diff_summary: ResumeDiffSummary | None = None
    warnings: list[Warning] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    candidate_evidence: list[CandidateEvidence] = Field(default_factory=list)
    before_ats_score: ATSScore | None = None
    after_ats_score: ATSScore | None = None
    before_match_report: JobMatchReport | None = None
    after_match_report: JobMatchReport | None = None
    score_deltas: list[ScoreDelta] = Field(default_factory=list)
    truth_report: TruthReport = Field(default_factory=TruthReport)
    review_state: ReviewSession | None = None
