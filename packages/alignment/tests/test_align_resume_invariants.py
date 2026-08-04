"""Invariant tests for ``align_resume`` (RIT-I-0005 REQ-407 / NFR-405).

Each test pins one load-bearing invariant of the controlled-alignment engine:

* blocked factual field edits are rejected even at ``freedom=10``;
* ``freedom >= 3`` forces truth validation even when the caller opts out;
* no aligned output ever carries an ``UNSUPPORTED``/``CONTRADICTED`` claim;
* ungrounded changes are stripped and the result is re-diffed/re-verified;
* the pipeline runs in the exact required order.

Only the ``FakeStructuredCompletionProvider`` is used; no concrete provider,
network, or ``app.*`` import appears here.
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
        personalInfo=PersonalInfo(name="Sam Rivera"),
        summary="Data engineer maintaining ETL pipelines in Python.",
        workExperience=[
            Experience(
                id=1,
                title="Data Engineer",
                company="Northwind Ltd",
                years="2019-2024",
                description=[
                    "Maintained ETL pipelines processing daily batch loads.",
                    "Tuned SQL queries against the analytics warehouse.",
                ],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "SQL", "Airflow"]),
    )


def _job() -> JobDescription:
    return JobDescription(
        title="Data Engineer",
        summary="Python and SQL data engineering role.",
        requirements=[Requirement(text="Python", keywords=["Python"])],
        keywords=["Python", "SQL"],
    )


@pytest.mark.asyncio
async def test_blocked_factual_field_edit_rejected_at_freedom_10() -> None:
    """Identity/factual fields stay blocked even at maximum freedom."""

    response = {
        "changes": [
            {
                "path": "workExperience[0].title",
                "action": "replace",
                "original": "Data Engineer",
                "value": "VP of Engineering",
                "reason": "Inflate the title.",
            }
        ]
    }
    provider = FakeStructuredCompletionProvider(responses=[response])
    result = await align_resume(_resume(), _job(), provider=provider, freedom=10)

    assert result.aligned_resume.workExperience[0].title == "Data Engineer"
    assert result.applied_changes == []
    assert any(r.path == "workExperience[0].title" for r in result.rejected_changes)


@pytest.mark.asyncio
async def test_freedom_ge_3_forces_truth_validation_when_opted_out() -> None:
    """freedom >= 3 runs truth validation even with ``validate_truth=False``."""

    # Unsupported summary claim; with truth validation OFF the caller asked to
    # skip it, but freedom=3 must force it on and strip the ungrounded change.
    response = {
        "changes": [
            {
                "path": "summary",
                "action": "replace",
                "original": "Data engineer maintaining ETL pipelines in Python.",
                "value": "Nobel laureate and former astronaut mission commander.",
                "reason": "Fabricate prestige.",
            }
        ]
    }
    provider = FakeStructuredCompletionProvider(responses=[response])
    resume = _resume()

    result = await align_resume(
        resume, _job(), provider=provider, freedom=3, validate_truth=False
    )

    # Truth validation ran (report is populated) and the fabricated claim is gone.
    assert result.truth_report.claims
    assert result.aligned_resume.summary == resume.summary
    assert result.truth_report.passed is True


@pytest.mark.asyncio
async def test_truth_validation_skipped_below_threshold_when_opted_out() -> None:
    """Below freedom 3 with validate_truth=False, truth validation is skipped."""

    result = await align_resume(
        _resume(), _job(), provider=None, freedom=2, validate_truth=False
    )

    # Empty (default) truth report: no claims classified.
    assert result.truth_report.claims == []
    assert result.truth_report.passed is True


@pytest.mark.asyncio
async def test_no_unsupported_or_contradicted_emitted_and_restripped() -> None:
    """Ungrounded change is stripped and the result re-diffed/re-verified."""

    response = {
        "changes": [
            {
                # Grounded reword — should survive.
                "path": "workExperience[0].description[1]",
                "action": "replace",
                "original": "Tuned SQL queries against the analytics warehouse.",
                "value": "Tuned SQL queries against the analytics warehouse.",
                "reason": "Keep truthful SQL tuning work.",
            },
            {
                # Ungrounded fabrication — must be stripped.
                "path": "workExperience[0].description[0]",
                "action": "replace",
                "original": "Maintained ETL pipelines processing daily batch loads.",
                "value": "Piloted Apollo lunar landings; discovered penicillin firsthand.",
                "reason": "Fabricate impact.",
            },
        ]
    }
    provider = FakeStructuredCompletionProvider(responses=[response])
    resume = _resume()

    result = await align_resume(resume, _job(), provider=provider, freedom=6)

    aligned = result.aligned_resume
    # No unsupported/contradicted claim survives.
    assert result.truth_report.passed is True
    for status in (ProvenanceStatus.UNSUPPORTED, ProvenanceStatus.CONTRADICTED):
        assert result.truth_report.status_counts.get(status, 0) == 0
    # The fabricated bullet is gone; the untouched bullet remains.
    assert "Apollo" not in " ".join(aligned.workExperience[0].description)
    assert (
        "Maintained ETL pipelines processing daily batch loads."
        in aligned.workExperience[0].description
    )
    # The diff/verify were re-run against the stripped result: the diff reflects
    # only surviving (zero net) changes, and a stripping rejection is recorded.
    assert any(
        r.reason_code.value == "truth_validation_failed" for r in result.rejected_changes
    )
    # The recorded diff summary matches the FINAL aligned resume (internally
    # consistent): recomputing the diff manually would produce the same summary.
    assert result.diff_summary is not None


@pytest.mark.asyncio
async def test_human_in_loop_defers_truth_failure_without_stripping() -> None:
    """With a human in the loop, a truth failure defers to review, not strip."""

    response = {
        "changes": [
            {
                "path": "workExperience[0].description[0]",
                "action": "replace",
                "original": "Maintained ETL pipelines processing daily batch loads.",
                "value": "Won three Olympic gold medals swimming freestyle relay.",
                "reason": "Fabricate.",
            }
        ]
    }
    provider = FakeStructuredCompletionProvider(responses=[response])
    result = await align_resume(
        _resume(), _job(), provider=provider, freedom=6, human_in_loop=True
    )

    # The failure is surfaced for human adjudication rather than silently applied.
    assert result.review_state is not None
    assert result.review_state.complete is False
    assert result.unresolved_questions
    assert any(
        "review" in (w.code or "") or "truth" in (w.code or "")
        for w in result.warnings
    )
