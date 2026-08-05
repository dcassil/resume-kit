"""Unit tests for Phase 4 result schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas.analysis import ATSScore, JobMatchReport, ScoreDelta
from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.common import Warning
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.provenance import ClaimProvenance, ProvenanceStatus
from resume_kit_schemas.results import (
    AlignmentResult,
    PolicyDecision,
    PolicyReasonCode,
    PolicyRejection,
    ReviewAction,
    ReviewDecision,
    ReviewSession,
    SkillTarget,
    SkillTargetPlan,
    SkillTargetRejection,
    SkillTargetSource,
    TruthReport,
)
from resume_kit_schemas.resume import ResumeDocument


def test_policy_decision_defaults_and_bounds() -> None:
    decision = PolicyDecision()
    assert decision.freedom_level == 0
    assert decision.allowed is True
    assert decision.reason_code is PolicyReasonCode.ALLOWED
    assert decision.action == "replace"

    with pytest.raises(ValidationError):
        PolicyDecision(freedom_level=11)


def test_policy_reason_and_review_action_enum_values() -> None:
    assert PolicyReasonCode.BLOCKED_FIELD.value == "blocked_field"
    assert PolicyReasonCode.TRUTH_VALIDATION_FAILED.value == "truth_validation_failed"
    assert {action.value for action in ReviewAction} == {
        "approve",
        "reject",
        "edit",
        "retry",
        "reduce_freedom",
        "increase_freedom",
        "skip",
    }


def test_policy_rejection_composes_change_proposal() -> None:
    change = ChangeProposal(
        path="personalInfo.name",
        action="replace",
        original="A",
        value="B",
        reason="targeted rewrite",
    )
    rejection = PolicyRejection(
        path=change.path,
        action=change.action,
        reason_code=PolicyReasonCode.BLOCKED_FIELD,
        explanation="Names are factual identity fields.",
        change=change,
    )
    assert rejection.change == change
    assert rejection.reason_code is PolicyReasonCode.BLOCKED_FIELD


def test_skill_target_plan_defaults_and_composition() -> None:
    evidence = CandidateEvidence(
        id="ev1",
        kind=EvidenceKind.SKILL,
        content="Candidate uses Python daily.",
        tags=["python"],
    )
    plan = SkillTargetPlan(
        proposed_skills=["Python", "Kubernetes"],
        accepted_targets=[
            SkillTarget(
                normalized_skill="python",
                display_skill="Python",
                source=SkillTargetSource.EVIDENCE_BACKED,
                evidence_ids=["ev1"],
                evidence_kinds=[EvidenceKind.SKILL],
            )
        ],
        rejected_targets=[
            SkillTargetRejection(
                normalized_skill="kubernetes",
                display_skill="Kubernetes",
                reason_code=PolicyReasonCode.UNSUPPORTED_SKILL,
                reason="No supporting evidence.",
            )
        ],
        supporting_evidence=[evidence],
    )
    assert plan.verified_skills == ["Python"]
    assert plan.unverified_skills == ["Kubernetes"]
    assert plan.supporting_evidence == [evidence]
    assert SkillTargetPlan().accepted_targets == []


def test_truth_report_detects_unsupported_or_contradicted_claims() -> None:
    report = TruthReport(
        claims=[
            ClaimProvenance(
                claim="Built a parser",
                status=ProvenanceStatus.SUPPORTED,
                evidence_ids=["ev1"],
            ),
            ClaimProvenance(
                claim="Led a 20-person team",
                status=ProvenanceStatus.UNSUPPORTED,
            ),
            ClaimProvenance(
                claim="Worked at Example Co",
                status=ProvenanceStatus.CONTRADICTED,
            ),
        ]
    )
    assert report.status_counts[ProvenanceStatus.SUPPORTED] == 1
    assert report.status_counts[ProvenanceStatus.UNSUPPORTED] == 1
    assert report.status_counts[ProvenanceStatus.CONTRADICTED] == 1
    assert report.needs_evidence_count == 1
    assert report.contradiction_count == 1
    assert report.has_unsupported_or_contradicted is True
    assert report.passed is False


def test_truth_report_passes_without_failure_statuses() -> None:
    report = TruthReport(
        claims=[
            ClaimProvenance(
                claim="Python",
                status=ProvenanceStatus.VERIFIED,
                field_path="additional.technicalSkills[0]",
            )
        ]
    )
    assert report.has_unsupported_or_contradicted is False
    assert report.passed is True


def test_truth_report_model_dump_roundtrip_recomputes_summary() -> None:
    report = TruthReport(
        claims=[
            ClaimProvenance(claim="X", status=ProvenanceStatus.UNSUPPORTED),
        ]
    )
    again = TruthReport.model_validate(report.model_dump())
    assert again == report
    assert again.has_unsupported_or_contradicted is True


def test_review_session_defaults_and_decisions() -> None:
    decision = ReviewDecision(
        section="summary",
        action=ReviewAction.EDIT,
        edited_content="Edited summary.",
        freedom_target=3,
    )
    session = ReviewSession(
        sections=["summary"],
        current_section="summary",
        decisions=[decision],
        awaiting_input=True,
    )
    assert session.complete is False
    assert session.awaiting_input is True
    assert session.decisions[0].action is ReviewAction.EDIT

    with pytest.raises(ValidationError):
        ReviewDecision(action=ReviewAction.INCREASE_FREEDOM, freedom_target=12)


def test_alignment_result_defaults_are_incremental() -> None:
    result = AlignmentResult()
    assert isinstance(result.original_resume, ResumeDocument)
    assert isinstance(result.aligned_resume, ResumeDocument)
    assert result.applied_changes == []
    assert result.change_set.changes == []
    assert result.rejected_changes == []
    assert result.warnings == []
    assert result.unresolved_questions == []
    assert result.truth_report.passed is True
    assert result.review_state is None


def test_alignment_result_model_dump_roundtrip() -> None:
    change = ChangeProposal(
        path="summary",
        action="replace",
        original="Old",
        value="New",
        reason="Improve match.",
    )
    result = AlignmentResult(
        original_resume=ResumeDocument(summary="Old"),
        aligned_resume=ResumeDocument(summary="New"),
        applied_changes=[change],
        rejected_changes=[
            PolicyRejection(
                path="personalInfo.name",
                action="replace",
                reason_code=PolicyReasonCode.BLOCKED_FIELD,
                explanation="Identity field.",
            )
        ],
        warnings=[Warning(message="One change rejected.")],
        unresolved_questions=["Confirm leadership scope."],
        candidate_evidence=[
            CandidateEvidence(
                id="ev1",
                kind=EvidenceKind.WORK_HISTORY,
                content="Built search services.",
            )
        ],
        before_ats_score=ATSScore(overall_score=60.0),
        after_ats_score=ATSScore(overall_score=70.0),
        before_match_report=JobMatchReport(overall_score=61.0),
        after_match_report=JobMatchReport(overall_score=72.0),
        score_deltas=[ScoreDelta(metric="match.overall", before=61.0, after=72.0, delta=11.0)],
        truth_report=TruthReport(
            claims=[ClaimProvenance(claim="Built search", status=ProvenanceStatus.SUPPORTED)]
        ),
        review_state=ReviewSession(complete=True),
    )
    again = AlignmentResult.model_validate(result.model_dump())
    assert again == result
    assert again.applied_changes[0].path == "summary"
