"""Stable typed callables the job-hunter tool imports to reach resume-kit.

This is a PURE LIBRARY bridge (REQ-506). It offers a small, stable Python
surface that job-hunter calls to analyze a resume for a job, align a resume for
a job, validate resume truth, and build candidate evidence. Every callable
delegates to :data:`resume_kit_facade.REGISTRY` and returns a canonical
:class:`~resume_kit_core.InterfaceResponse` carrying ``resume_kit_schemas``
data (never a bridge-local DTO).

The bridge is deliberately inert with respect to job-hunter: it never reads or
writes job-hunter application state, storage, queues, HTTP clients, CLIs, MCP,
FastAPI, or Typer. It imports only ``resume_kit_facade``, ``resume_kit_core``,
``resume_kit_schemas``, and the standard library.

No-mutation guarantee
---------------------
The bridge never mutates its inputs. Facade request models are frozen
dataclasses and the engines behind them treat their ``resume_kit_schemas``
arguments as read-only value objects, producing new result objects rather than
editing the inputs in place. The bridge itself performs no attribute
assignment, ``list``/``dict`` mutation, or ``model_copy`` write-back on any
argument it receives.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Sequence

from resume_kit_core import InterfaceResponse
from resume_kit_facade.capabilities import REGISTRY
from resume_kit_facade.models import (
    AlignResumeRequest,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    IdentifyResumeGapsRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_schemas import (
    CandidateEvidence,
    JobDescription,
    ResumeDocument,
)

__all__ = [
    "ResumeJobAnalysis",
    "analyze_resume_for_job",
    "align_resume_for_job",
    "validate_truth",
    "build_evidence",
    "analyze_resume_for_job_sync",
    "align_resume_for_job_sync",
    "validate_truth_sync",
    "build_evidence_sync",
]


class ResumeJobAnalysis:
    """The three canonical analysis responses for a resume/job pair.

    Each attribute is a canonical :class:`InterfaceResponse` produced by the
    corresponding facade capability, carrying ``resume_kit_schemas`` data:

    * :attr:`ats` — ``check-resume-ats`` (``ATSScore``).
    * :attr:`job_match` — ``check-resume-job-match`` (``JobMatchReport``).
    * :attr:`gaps` — ``identify-resume-gaps`` (``KeywordGapAnalysis``).
    """

    __slots__ = ("ats", "job_match", "gaps")

    def __init__(
        self,
        ats: InterfaceResponse[object],
        job_match: InterfaceResponse[object],
        gaps: InterfaceResponse[object],
    ) -> None:
        self.ats = ats
        self.job_match = job_match
        self.gaps = gaps


async def _dispatch(
    capability: str,
    request: object,
    options: CapabilityOptions,
) -> InterfaceResponse[object]:
    """Delegate to a single facade capability by its registry name."""
    return await REGISTRY[capability](request, options)


async def analyze_resume_for_job(
    resume: ResumeDocument,
    job: JobDescription,
    *,
    master: ResumeDocument | None = None,
    options: CapabilityOptions | None = None,
) -> ResumeJobAnalysis:
    """Analyze ``resume`` against ``job`` for a job-hunter application.

    Runs the three deterministic analysis capabilities and returns their
    canonical responses. ``master`` supplies the baseline for gap analysis and
    defaults to ``resume`` when not provided. All three paths are provider-free.
    """
    opts = options or CapabilityOptions()
    baseline = master if master is not None else resume
    ats = await _dispatch(
        "check-resume-ats",
        CheckResumeAtsRequest(resume=resume, job=job),
        opts,
    )
    job_match = await _dispatch(
        "check-resume-job-match",
        CheckResumeJobMatchRequest(resume=resume, job=job),
        opts,
    )
    gaps = await _dispatch(
        "identify-resume-gaps",
        IdentifyResumeGapsRequest(job=job, tailored=resume, master=baseline),
        opts,
    )
    return ResumeJobAnalysis(ats=ats, job_match=job_match, gaps=gaps)


async def align_resume_for_job(
    resume: ResumeDocument,
    job: JobDescription,
    *,
    evidence: Sequence[CandidateEvidence] | None = None,
    options: CapabilityOptions | None = None,
) -> InterfaceResponse[object]:
    """Align ``resume`` to ``job`` via the ``align-resume`` capability.

    This is the one LLM-requiring bridge callable. Without a provider (and
    without ``no_llm``) it returns the stable provider-not-configured error
    exactly as the facade produces it; nothing is called and nothing crashes.
    """
    opts = options or CapabilityOptions()
    return await _dispatch(
        "align-resume",
        AlignResumeRequest(resume=resume, job=job, evidence=evidence),
        opts,
    )


async def validate_truth(
    resume: ResumeDocument,
    evidence: list[CandidateEvidence] | None = None,
    *,
    options: CapabilityOptions | None = None,
) -> InterfaceResponse[object]:
    """Validate ``resume`` against ``evidence`` via ``validate-resume-truth``.

    Deterministic and provider-free; returns a canonical ``TruthReport``
    response.
    """
    opts = options or CapabilityOptions()
    return await _dispatch(
        "validate-resume-truth",
        ValidateResumeTruthRequest(resume=resume, evidence=list(evidence or [])),
        opts,
    )


async def build_evidence(
    resume: ResumeDocument,
    *,
    approved_claims: list[CandidateEvidence] | list[str] | None = None,
    options: CapabilityOptions | None = None,
) -> InterfaceResponse[object]:
    """Build candidate evidence from ``resume`` via ``build-candidate-evidence``.

    Deterministic and provider-free; returns a canonical response whose data is
    a ``list[CandidateEvidence]``.
    """
    opts = options or CapabilityOptions()
    return await _dispatch(
        "build-candidate-evidence",
        BuildCandidateEvidenceRequest(resume=resume, approved_claims=approved_claims),
        opts,
    )


# ---------------------------------------------------------------------------
# Synchronous convenience wrappers
# ---------------------------------------------------------------------------


def _run[R](coro: Coroutine[object, object, R]) -> R:
    """Run a bridge coroutine to completion on a fresh event loop."""
    return asyncio.run(coro)


def analyze_resume_for_job_sync(
    resume: ResumeDocument,
    job: JobDescription,
    *,
    master: ResumeDocument | None = None,
    options: CapabilityOptions | None = None,
) -> ResumeJobAnalysis:
    """Synchronous wrapper around :func:`analyze_resume_for_job`."""
    return _run(
        analyze_resume_for_job(resume, job, master=master, options=options)
    )


def align_resume_for_job_sync(
    resume: ResumeDocument,
    job: JobDescription,
    *,
    evidence: Sequence[CandidateEvidence] | None = None,
    options: CapabilityOptions | None = None,
) -> InterfaceResponse[object]:
    """Synchronous wrapper around :func:`align_resume_for_job`."""
    return _run(
        align_resume_for_job(resume, job, evidence=evidence, options=options)
    )


def validate_truth_sync(
    resume: ResumeDocument,
    evidence: list[CandidateEvidence] | None = None,
    *,
    options: CapabilityOptions | None = None,
) -> InterfaceResponse[object]:
    """Synchronous wrapper around :func:`validate_truth`."""
    return _run(validate_truth(resume, evidence, options=options))


def build_evidence_sync(
    resume: ResumeDocument,
    *,
    approved_claims: list[CandidateEvidence] | list[str] | None = None,
    options: CapabilityOptions | None = None,
) -> InterfaceResponse[object]:
    """Synchronous wrapper around :func:`build_evidence`."""
    return _run(
        build_evidence(resume, approved_claims=approved_claims, options=options)
    )
