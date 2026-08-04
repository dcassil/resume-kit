"""Deterministic tests for the job-hunter bridge (no network, no LLM).

These cover: provider-free analysis/validate/build paths succeed; align without
a provider returns the stable provider-not-configured error; input objects are
never mutated; and artifact/question/provenance envelope fields survive the
round-trip.
"""

from __future__ import annotations

import pytest
from resume_kit_core import InterfaceResponse
from resume_kit_core.errors import ErrorCode
from resume_kit_facade.models import CapabilityOptions
from resume_kit_job_hunter_bridge import (
    align_resume_for_job,
    align_resume_for_job_sync,
    analyze_resume_for_job,
    build_evidence,
    validate_truth,
)
from resume_kit_schemas import (
    CandidateEvidence,
    EvidenceKind,
    JobDescription,
    Requirement,
    RequirementKind,
    ResumeDocument,
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
        keywords=["python", "docker"],
    )


def _resume() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jane Dev",
                "email": "jane@example.com",
                "phone": "555-1000",
            },
            "summary": "Backend engineer with Python and Docker experience.",
        }
    )


def _evidence() -> list[CandidateEvidence]:
    return [
        CandidateEvidence(
            id="e1",
            kind=EvidenceKind.SKILL,
            content="Python",
            tags=["python"],
        )
    ]


@pytest.mark.asyncio
async def test_analyze_runs_all_three_paths_without_provider() -> None:
    analysis = await analyze_resume_for_job(_resume(), _job())
    assert analysis.ats.ok
    assert analysis.job_match.ok
    assert analysis.gaps.ok
    # Canonical schema data, not bridge-local DTOs.
    assert analysis.ats.data is not None
    assert type(analysis.ats.data).__module__.startswith("resume_kit_schemas")
    assert type(analysis.job_match.data).__module__.startswith("resume_kit_schemas")
    assert type(analysis.gaps.data).__module__.startswith("resume_kit_schemas")


@pytest.mark.asyncio
async def test_validate_truth_without_provider_succeeds() -> None:
    resp = await validate_truth(_resume(), _evidence())
    assert resp.ok
    assert resp.data is not None
    assert type(resp.data).__module__.startswith("resume_kit_schemas")


@pytest.mark.asyncio
async def test_build_evidence_without_provider_succeeds() -> None:
    resp = await build_evidence(_resume())
    assert resp.ok
    assert isinstance(resp.data, list)


@pytest.mark.asyncio
async def test_align_without_provider_returns_provider_not_configured() -> None:
    resp = await align_resume_for_job(_resume(), _job())
    assert not resp.ok
    assert resp.data is None
    codes = [e.code for e in resp.errors]
    assert ErrorCode.PROVIDER_NOT_CONFIGURED in codes


def test_align_sync_without_provider_returns_provider_not_configured() -> None:
    resp = align_resume_for_job_sync(_resume(), _job())
    assert not resp.ok
    assert ErrorCode.PROVIDER_NOT_CONFIGURED in [e.code for e in resp.errors]


@pytest.mark.asyncio
async def test_align_no_llm_succeeds_without_provider() -> None:
    resp = await align_resume_for_job(
        _resume(), _job(), options=CapabilityOptions(no_llm=True)
    )
    assert resp.ok
    assert resp.data is not None


@pytest.mark.asyncio
async def test_inputs_are_not_mutated() -> None:
    resume = _resume()
    job = _job()
    evidence = _evidence()
    resume_before = resume.model_dump()
    job_before = job.model_dump()
    evidence_before = [e.model_dump() for e in evidence]

    await analyze_resume_for_job(resume, job)
    await validate_truth(resume, evidence)
    await build_evidence(resume)
    await align_resume_for_job(
        resume, job, evidence=evidence, options=CapabilityOptions(no_llm=True)
    )

    assert resume.model_dump() == resume_before
    assert job.model_dump() == job_before
    assert [e.model_dump() for e in evidence] == evidence_before


@pytest.mark.asyncio
async def test_envelope_fields_are_preserved() -> None:
    resp: InterfaceResponse[object] = await validate_truth(_resume(), _evidence())
    # The canonical envelope fields exist and are the facade-produced values.
    assert resp.warnings == list(resp.warnings)
    assert resp.questions == list(resp.questions)
    assert resp.artifacts == list(resp.artifacts)
    assert resp.provenance == list(resp.provenance)
    # A successful deterministic path requires no human input.
    assert resp.requires_human_input is False
