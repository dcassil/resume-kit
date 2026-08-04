"""Top-level Phase 4 controlled-alignment engine.

New resume-kit orchestration (no line-for-line upstream port). It wires the
already-written alignment primitives into a single ``align_resume`` engine that
enforces the load-bearing invariant of RIT-I-0005 (REQ-407 / NFR-405): the LLM
never directly writes the final document. Provider output is *proposal-only* and
must survive, in order:

1. provider proposal generation (``generation.generate_change_proposals``),
2. the freedom-aware path policy gate + deterministic application
   (``apply.apply_diffs``),
3. structural verification (``verify.verify_diff_result``),
4. structured diffing (``diff.calculate_resume_diff``),
5. evidence truth validation (``resume_kit_evidence.validate_resume_truth``),
6. before/after score + ATS impact (``resume_kit_matching`` + ``resume_kit_ats``),
7. optional human-in-the-loop review state (``review.ReviewController``),

before any content appears in the returned resume. If truth validation flags an
``UNSUPPORTED`` or ``CONTRADICTED`` claim, the offending applied changes are
stripped and the diff/verification/truth passes are RE-RUN against the stripped
result so the returned :class:`AlignmentResult` is internally consistent; when a
human is in the loop the failure is surfaced as unresolved review instead.

This module imports only inward workspace packages (core, schemas, policy,
evidence, matching, ats) and its own siblings. It never imports a concrete
provider, the network, or ``app.*``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from resume_kit_ats import compute_ats_score
from resume_kit_core.providers import StructuredCompletionProvider
from resume_kit_core.response import InterfaceResponse
from resume_kit_evidence.builder import build_candidate_evidence
from resume_kit_evidence.truth import validate_resume_truth
from resume_kit_matching import analyze_keyword_gaps, calculate_keyword_match, check_job_match
from resume_kit_policy.path_policy import FREEDOM_MAX, FREEDOM_MIN
from resume_kit_schemas.analysis import ATSScore, JobMatchReport, ScoreDelta
from resume_kit_schemas.change import ChangeProposal, ChangeSet, Diff, ResumeDiffSummary
from resume_kit_schemas.common import Warning
from resume_kit_schemas.evidence import CandidateEvidence
from resume_kit_schemas.job import JobDescription
from resume_kit_schemas.provenance import ClaimProvenance, ProvenanceStatus
from resume_kit_schemas.results import (
    AlignmentResult,
    PolicyReasonCode,
    PolicyRejection,
    ReviewSession,
    SkillTargetPlan,
    TruthReport,
)
from resume_kit_schemas.resume import ResumeDocument

from resume_kit_alignment.apply import apply_diffs
from resume_kit_alignment.diff import calculate_resume_diff
from resume_kit_alignment.generation import generate_change_proposals
from resume_kit_alignment.review import ReviewController
from resume_kit_alignment.verify import verify_diff_result

__all__ = ["align_resume"]

# Freedom at/above which truth validation is ALWAYS run regardless of the caller
# request flag (REQ-407: higher editorial freedom demands stronger grounding).
_TRUTH_MANDATORY_FREEDOM = 3

_FAILING_STATUSES = frozenset(
    {ProvenanceStatus.UNSUPPORTED, ProvenanceStatus.CONTRADICTED}
)


def _to_document(resume: ResumeDocument | dict[str, Any]) -> ResumeDocument:
    if isinstance(resume, ResumeDocument):
        return resume
    return ResumeDocument.model_validate(resume)


def _clamp_freedom(freedom: int) -> int:
    return max(FREEDOM_MIN, min(FREEDOM_MAX, freedom))


def _warning(message: str, *, code: str, field_path: str | None = None) -> Warning:
    return Warning(message=message, code=code, field_path=field_path)


def _ats_for(resume: ResumeDocument, job: JobDescription) -> ATSScore:
    gap = analyze_keyword_gaps(job, resume, resume)
    match_pct = calculate_keyword_match(resume, job)
    return compute_ats_score(
        resume,
        job,
        keyword_match_percentage=match_pct,
        missing_keywords=gap.non_injectable_keywords,
        injectable_keywords=gap.injectable_keywords,
    )


def _score_deltas(
    before_ats: ATSScore,
    after_ats: ATSScore,
    before_match: JobMatchReport,
    after_match: JobMatchReport,
) -> list[ScoreDelta]:
    def _delta(metric: str, before: float, after: float) -> ScoreDelta:
        return ScoreDelta(metric=metric, before=before, after=after, delta=after - before)

    return [
        _delta("ats.overall", before_ats.overall_score, after_ats.overall_score),
        _delta("match.overall", before_match.overall_score, after_match.overall_score),
    ]


def _failing_paths(truth_report: TruthReport) -> set[str]:
    """Field paths of every claim classified unsupported/contradicted."""

    return {
        claim.field_path
        for claim in truth_report.claims
        if claim.status in _FAILING_STATUSES and claim.field_path
    }


def _change_touches_failing(change: ChangeProposal, failing_paths: set[str]) -> bool:
    """True if an applied change's path overlaps a failing claim path.

    Truth claims are keyed by concrete field paths (e.g.
    ``additional.technicalSkills[3]``) while changes may target a container
    (e.g. ``additional.technicalSkills`` for an ``add_skill`` / ``reorder``).
    A change is stripped when its path is a prefix of, equal to, or a suffix
    extension of a failing claim path, so both directions are covered.
    """

    change_path = change.path
    for failing in failing_paths:
        if change_path == failing:
            return True
        if failing.startswith(change_path) and failing[len(change_path):len(change_path) + 1] in (
            ".",
            "[",
        ):
            return True
        if change_path.startswith(failing) and change_path[len(failing):len(failing) + 1] in (
            ".",
            "[",
        ):
            return True
    return False


class _Applied:
    """Result of one application/verification/diff pass over the resume."""

    __slots__ = (
        "result_doc",
        "applied",
        "rejected",
        "verify_warnings",
        "diff_summary",
        "diffs",
    )

    def __init__(
        self,
        result_doc: ResumeDocument,
        applied: list[ChangeProposal],
        rejected: list[PolicyRejection],
        verify_warnings: list[Warning],
        diff_summary: ResumeDiffSummary,
        diffs: list[Diff],
    ) -> None:
        self.result_doc = result_doc
        self.applied = applied
        self.rejected = rejected
        self.verify_warnings = verify_warnings
        self.diff_summary = diff_summary
        self.diffs = diffs


def _apply_verify_diff(
    original: ResumeDocument,
    changes: Sequence[ChangeProposal],
    *,
    freedom: int,
    allowed_skill_targets: SkillTargetPlan | None,
) -> _Applied:
    """Run apply_diffs -> verify_diff_result -> calculate_resume_diff once."""

    original_dict = original.model_dump()
    result_dict, applied, rejected = apply_diffs(
        original,
        list(changes),
        freedom=freedom,
        allowed_skill_targets=allowed_skill_targets,
    )
    verify_warnings = verify_diff_result(original_dict, result_dict, applied)
    diff_summary, diffs = calculate_resume_diff(original_dict, result_dict)
    result_doc = ResumeDocument.model_validate(result_dict)
    return _Applied(result_doc, applied, rejected, verify_warnings, diff_summary, diffs)


async def align_resume(
    resume: ResumeDocument | dict[str, Any],
    job: JobDescription,
    evidence: Sequence[CandidateEvidence] | None = None,
    *,
    freedom: int = FREEDOM_MAX,
    human_in_loop: bool = False,
    provider: StructuredCompletionProvider | None = None,
    validate_truth: bool = True,
    skill_targets: SkillTargetPlan | None = None,
    language: str = "en",
    prompt_id: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> AlignmentResult:
    """Run the controlled-alignment pipeline and return an ``AlignmentResult``.

    Args:
        resume: The original resume (``ResumeDocument`` or upstream-shape dict).
        job: The structured job description to align against.
        evidence: Ground-truth candidate evidence. When ``None`` it is derived
            deterministically from ``resume`` via ``build_candidate_evidence``.
        freedom: Editorial freedom (0-10) handed to the policy gate. Blocked
            factual identity fields stay blocked at every level, including 10.
        human_in_loop: When true, the returned result embeds an unresolved
            :class:`ReviewSession` (and questions) rather than auto-applying;
            Phase 5 owns the interactive loop.
        provider: Injected structured-completion provider. When ``None`` the
            engine takes the deterministic empty-change path (aligned == original)
            and never calls an LLM.
        validate_truth: Request truth validation. Ignored (forced on) when
            ``freedom >= 3``.
        skill_targets: Pre-verified skill targets that gate ``add_skill`` changes.
        language / prompt_id / model / temperature: Passed through to generation.

    Returns:
        A fully populated :class:`AlignmentResult`. No claim classified
        ``UNSUPPORTED`` or ``CONTRADICTED`` survives in ``aligned_resume``.
    """

    original = _to_document(resume)
    clamped_freedom = _clamp_freedom(freedom)
    evidence_list = (
        list(evidence)
        if evidence is not None
        else build_candidate_evidence(original)
    )
    run_truth = validate_truth or clamped_freedom >= _TRUTH_MANDATORY_FREEDOM

    warnings: list[Warning] = []

    # ---- Stage 1: provider proposal generation (proposal-only). -----------
    if provider is None:
        change_set = ChangeSet()
    else:
        change_set = await generate_change_proposals(
            provider,
            original_resume="",
            job_description=job.summary or job.title,
            job_keywords=job,
            language=language,
            prompt_id=prompt_id,
            original_resume_data=original,
            skill_targets=skill_targets,
            model=model,
            temperature=temperature,
        )
    warnings.extend(change_set.warnings)

    # ---- Stage 2-4: policy gate + apply -> verify -> diff. ----------------
    passed = _apply_verify_diff(
        original,
        change_set.changes,
        freedom=clamped_freedom,
        allowed_skill_targets=skill_targets,
    )

    # ---- Stage 5: truth validation (mandatory when freedom >= 3). ---------
    truth_report = TruthReport()
    truth_review_required = False
    if run_truth:
        truth_report = validate_resume_truth(passed.result_doc, evidence_list)
        if truth_report.has_unsupported_or_contradicted:
            passed, truth_report, truth_review_required = _resolve_truth_failure(
                original,
                passed,
                truth_report,
                evidence_list,
                freedom=clamped_freedom,
                human_in_loop=human_in_loop,
                skill_targets=skill_targets,
                warnings=warnings,
            )

    # ---- Stage 6: before/after score + ATS impact. ------------------------
    before_ats = _ats_for(original, job)
    after_ats = _ats_for(passed.result_doc, job)
    before_match = check_job_match(original, job)
    after_match = check_job_match(passed.result_doc, job)
    deltas = _score_deltas(before_ats, after_ats, before_match, after_match)

    warnings.extend(passed.verify_warnings)

    # ---- Stage 7: optional human-in-the-loop review state. ----------------
    review_state = _build_review_state(
        passed.applied,
        evidence_list,
        truth_report.claims,
        deltas,
        human_in_loop=human_in_loop,
        truth_review_required=truth_review_required,
    )
    unresolved = _unresolved_questions(review_state, human_in_loop, truth_review_required)

    return AlignmentResult(
        original_resume=original,
        aligned_resume=passed.result_doc,
        job=job,
        applied_changes=passed.applied,
        change_set=change_set,
        rejected_changes=passed.rejected,
        diffs=passed.diffs,
        diff_summary=passed.diff_summary,
        warnings=warnings,
        unresolved_questions=unresolved,
        candidate_evidence=evidence_list,
        before_ats_score=before_ats,
        after_ats_score=after_ats,
        before_match_report=before_match,
        after_match_report=after_match,
        score_deltas=deltas,
        truth_report=truth_report,
        review_state=review_state,
    )


def _resolve_truth_failure(
    original: ResumeDocument,
    passed: _Applied,
    truth_report: TruthReport,
    evidence_list: list[CandidateEvidence],
    *,
    freedom: int,
    human_in_loop: bool,
    skill_targets: SkillTargetPlan | None,
    warnings: list[Warning],
) -> tuple[_Applied, TruthReport, bool]:
    """Strip ungrounded changes and re-run, or defer to human review.

    When a human is in the loop the failure is left for review (the applied
    changes are not silently stripped so the human can adjudicate). Otherwise
    every applied change overlapping an unsupported/contradicted claim path is
    removed and the FULL apply->verify->diff->truth pipeline is re-run against
    the stripped changeset so the returned result is internally consistent and
    provably free of ungrounded output.
    """

    failing_paths = _failing_paths(truth_report)

    if human_in_loop:
        warnings.append(
            _warning(
                "Truth validation flagged ungrounded claims; deferred to human review.",
                code="truth_review_required",
            )
        )
        return passed, truth_report, True

    kept_changes = [
        change
        for change in passed.applied
        if not _change_touches_failing(change, failing_paths)
    ]
    stripped_count = len(passed.applied) - len(kept_changes)

    reapplied = _apply_verify_diff(
        original,
        kept_changes,
        freedom=freedom,
        allowed_skill_targets=skill_targets,
    )
    # Carry forward the ORIGINAL rejections plus a rejection per stripped change.
    stripped_rejections = [
        PolicyRejection(
            path=change.path,
            action=change.action,
            reason_code=PolicyReasonCode.TRUTH_VALIDATION_FAILED,
            explanation="Change stripped: it introduced an ungrounded (unsupported "
            "or contradicted) claim.",
            change=change,
        )
        for change in passed.applied
        if _change_touches_failing(change, failing_paths)
    ]
    reapplied.rejected = [*passed.rejected, *reapplied.rejected, *stripped_rejections]

    if stripped_count:
        warnings.append(
            _warning(
                f"Stripped {stripped_count} ungrounded change(s) that failed truth "
                "validation; re-verified the resulting resume.",
                code="ungrounded_changes_stripped",
            )
        )

    # Re-validate the stripped result. If it still fails (e.g. a structural
    # invariant unrelated to any single change), force human review so no
    # ungrounded output can ever be emitted silently.
    revalidated = validate_resume_truth(reapplied.result_doc, evidence_list)
    if revalidated.has_unsupported_or_contradicted:
        warnings.append(
            _warning(
                "Truth validation still failing after stripping; forcing human review.",
                code="truth_review_required",
            )
        )
        return reapplied, revalidated, True

    return reapplied, revalidated, False


def _build_review_state(
    applied: list[ChangeProposal],
    evidence_list: list[CandidateEvidence],
    claim_provenance: list[ClaimProvenance],
    deltas: list[ScoreDelta],
    *,
    human_in_loop: bool,
    truth_review_required: bool,
) -> ReviewSession:
    session = ReviewController.initialize(
        applied,
        evidence=evidence_list,
        claim_provenance=claim_provenance,
        expected_score_deltas=deltas,
    )
    if human_in_loop or truth_review_required:
        # Leave the session awaiting human input; Phase 5 drives the loop.
        return session
    # No human: auto-resolve every section so the embedded state is terminal.
    return ReviewController.resolve_without_human(session)


def _unresolved_questions(
    review_state: ReviewSession,
    human_in_loop: bool,
    truth_review_required: bool,
) -> list[str]:
    if not (human_in_loop or truth_review_required):
        return []
    if review_state.complete or review_state.current_section is None:
        return []
    prompt: InterfaceResponse[None] = ReviewController.prompt(review_state)
    return [question.text for question in prompt.questions]
