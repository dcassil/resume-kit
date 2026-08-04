"""Orchestration tests for ``align_resume`` — pipeline wiring and NFR-405.

These tests exercise the top-level Phase 4 engine end-to-end using only the
``FakeStructuredCompletionProvider`` from ``resume_kit_core.testing``; no
concrete provider, network, or ``app.*`` dependency is imported. They assert the
load-bearing invariant of RIT-I-0005: provider output is proposal-only and must
survive policy + application + verification + truth validation before it can
appear in ``AlignmentResult.aligned_resume``.
"""

from __future__ import annotations

import pytest
from resume_kit_alignment.orchestrator import align_resume
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_schemas.job import JobDescription, Requirement
from resume_kit_schemas.provenance import ProvenanceStatus
from resume_kit_schemas.resume import (
    AdditionalInfo,
    Experience,
    PersonalInfo,
    ResumeDocument,
)


def _resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(name="Jordan Lee"),
        summary="Backend engineer building reliable Python services.",
        workExperience=[
            Experience(
                id=1,
                title="Senior Software Engineer",
                company="Acme Corp",
                years="2020-2024",
                description=[
                    "Built and operated Python microservices in production.",
                    "Owned CI pipelines and release automation for the team.",
                ],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "PostgreSQL", "Docker"]),
    )


def _job() -> JobDescription:
    return JobDescription(
        title="Backend Engineer",
        summary="Seeking a backend engineer with Python and cloud experience.",
        requirements=[
            Requirement(text="Python", keywords=["Python"]),
            Requirement(text="Docker", keywords=["Docker"]),
        ],
        keywords=["Python", "Docker", "PostgreSQL"],
    )


def _grounded_replace_response() -> dict[str, object]:
    # A truthful rewrite of an existing bullet (same facts, reworded) so it stays
    # grounded in evidence derived from the resume itself.
    return {
        "changes": [
            {
                "path": "workExperience[0].description[0]",
                "action": "replace",
                "original": "Built and operated Python microservices in production.",
                "value": "Built and operated Python microservices in production.",
                "reason": "Keep truthful production Python experience prominent.",
            }
        ],
        "strategy_notes": "Grounded reword.",
    }


@pytest.mark.asyncio
async def test_no_provider_returns_empty_change_deterministic_result() -> None:
    """No provider => deterministic empty-change path; aligned == original."""

    resume = _resume()
    result = await align_resume(resume, _job(), provider=None, freedom=5)

    assert result.applied_changes == []
    assert result.aligned_resume.model_dump() == resume.model_dump()
    assert result.review_state is not None
    assert result.review_state.complete is True
    assert result.before_ats_score is not None
    assert result.after_ats_score is not None
    # Score/ATS impact was still computed against the (unchanged) resume.
    assert result.before_ats_score.overall_score == result.after_ats_score.overall_score


@pytest.mark.asyncio
async def test_pipeline_applies_grounded_change_and_records_impact() -> None:
    """A grounded proposal flows through the full pipeline and is applied."""

    provider = FakeStructuredCompletionProvider(responses=[_grounded_replace_response()])
    result = await align_resume(_resume(), _job(), provider=provider, freedom=4)

    # The truthful reword survived policy + apply + verify + truth validation.
    assert result.truth_report.passed is True
    assert not result.truth_report.has_unsupported_or_contradicted
    assert result.before_match_report is not None
    assert result.after_match_report is not None
    assert result.diff_summary is not None


@pytest.mark.asyncio
async def test_nfr405_fabricated_and_unsupported_never_reach_output() -> None:
    """NFR-405 adversarial: fabricated factual edit + unsupported claim.

    The provider proposes (a) a fabricated employer-name edit on a blocked
    factual field and (b) an unsupported new summary claim. Neither may appear
    in the aligned resume: the factual edit is rejected by policy, and the
    unsupported claim is stripped by truth validation.
    """

    adversarial = {
        "changes": [
            {
                # (a) Fabricated factual identity edit — blocked at every freedom.
                "path": "workExperience[0].company",
                "action": "replace",
                "original": "Acme Corp",
                "value": "Google",
                "reason": "Make the resume look more impressive.",
            },
            {
                # (b) Unsupported fabricated achievement in the summary.
                "path": "summary",
                "action": "replace",
                "original": "Backend engineer building reliable Python services.",
                "value": "Piloted Apollo lunar landings; discovered penicillin firsthand.",
                "reason": "Exaggerate impact.",
            },
        ],
    }
    provider = FakeStructuredCompletionProvider(responses=[adversarial])
    resume = _resume()

    result = await align_resume(resume, _job(), provider=provider, freedom=10)

    aligned = result.aligned_resume
    # (a) The fabricated company name never reached the output.
    assert aligned.workExperience[0].company == "Acme Corp"
    # (b) The fabricated summary never reached the output.
    assert "Apollo" not in aligned.summary
    assert aligned.summary == resume.summary

    # And the final truth report over the aligned resume is clean.
    assert result.truth_report.passed is True
    assert (
        result.truth_report.status_counts.get(ProvenanceStatus.UNSUPPORTED, 0) == 0
    )
    assert (
        result.truth_report.status_counts.get(ProvenanceStatus.CONTRADICTED, 0) == 0
    )

    # The rejections are auditable: the factual edit is a policy rejection.
    rejected_paths = {r.path for r in result.rejected_changes}
    assert "workExperience[0].company" in rejected_paths


@pytest.mark.asyncio
async def test_malformed_provider_output_handled_gracefully() -> None:
    """Malformed provider JSON degrades to zero changes, not a crash."""

    provider = FakeStructuredCompletionProvider(
        responses=[{"unexpected": "no changes key here"}]
    )
    result = await align_resume(_resume(), _job(), provider=provider, freedom=5)

    assert result.applied_changes == []
    assert result.aligned_resume.model_dump() == _resume().model_dump()
    # A warning explains the missing changes key.
    assert any("changes" in w.message.lower() for w in result.change_set.warnings)


@pytest.mark.asyncio
async def test_human_in_loop_embeds_unresolved_review_session() -> None:
    """Human-in-loop embeds an unresolved review session requiring input."""

    provider = FakeStructuredCompletionProvider(responses=[_grounded_replace_response()])
    result = await align_resume(
        _resume(), _job(), provider=provider, freedom=4, human_in_loop=True
    )

    assert result.review_state is not None
    assert result.review_state.awaiting_input is True
    assert result.review_state.complete is False
    assert result.review_state.current_section is not None
    # The engine surfaces the questions that must be answered before advancing.
    assert result.unresolved_questions
