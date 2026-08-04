"""The ``resume-tool`` Typer application.

A thin transport adapter over :mod:`resume_kit_facade`.  Each command reads its
inputs, builds a :class:`~resume_kit_facade.models.CapabilityOptions`, invokes
exactly one facade capability (awaited via :func:`asyncio.run`), renders the
returned :class:`~resume_kit_core.response.InterfaceResponse` through
:mod:`resume_kit_cli.formatters`, and exits with the deterministic code from
:func:`resume_kit_core.interface.exit_code_for`.

No business logic lives here: parsing is delegated to :mod:`resume_kit_cli.io`,
formatting to :mod:`resume_kit_cli.formatters`, and all real work to the facade.
No concrete LLM provider is constructed; ``provider`` is ``None`` unless a test
injects one through :data:`PROVIDER`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import typer
from resume_kit_core import StructuredCompletionProvider
from resume_kit_core.interface import exit_code_for
from resume_kit_core.response import InterfaceResponse
from resume_kit_facade import capabilities as caps
from resume_kit_facade.models import (
    AlignResumeRequest,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CompareResumeVersionsRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    IdentifyResumeGapsRequest,
    SelectBestResumeRequest,
    ValidateResumeTruthRequest,
)

from resume_kit_cli import io
from resume_kit_cli.formatters import OutputFormat, render

app = typer.Typer(
    help="Resume Kit command-line transport over the capability facade.",
    no_args_is_help=True,
)

# Optional injected provider seam.  In production this stays ``None`` (there is
# no concrete provider in Phase 5); tests may set it to a fake to exercise the
# LLM path deterministically.
PROVIDER: StructuredCompletionProvider | None = None


# ---------------------------------------------------------------------------
# Shared option annotations
# ---------------------------------------------------------------------------

_Output = typer.Option(OutputFormat.JSON, "--output", help="Output format.")
_NoLlm = typer.Option(False, "--no-llm", help="Force the deterministic path.")
_Strict = typer.Option(False, "--strict", help="Escalate warnings to failures.")
_HumanInLoop = typer.Option(
    False,
    "--human-in-loop/--non-interactive",
    help="Request human-in-the-loop behaviour where supported.",
)
_Config = typer.Option(None, "--config", help="Optional config JSON path (not persisted).")


def _options(no_llm: bool, strict: bool, human_in_loop: bool) -> CapabilityOptions:
    """Build the shared capability options bundle for a command invocation."""
    return CapabilityOptions(
        no_llm=no_llm,
        strict=strict,
        human_in_loop=human_in_loop,
        provider=PROVIDER,
    )


def _run(
    coro: Coroutine[Any, Any, InterfaceResponse[object]],
    output: OutputFormat,
) -> None:
    """Await ``coro``, render the response, and exit with its mapped code."""
    response = asyncio.run(coro)
    typer.echo(render(response, output))
    raise typer.Exit(code=exit_code_for(response))


# ---------------------------------------------------------------------------
# LLM-capable commands
# ---------------------------------------------------------------------------


@app.command()
def extract(
    resume: str = typer.Argument(..., help="Resume file path, or '-' for stdin."),
    output: OutputFormat = _Output,
    no_llm: bool = _NoLlm,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Extract a structured resume from a resume file (bytes)."""
    filename = resume if resume != "-" else "resume.txt"
    request = ExtractResumeRequest(content=io.read_bytes(resume), filename=filename)
    options = _options(no_llm, strict, False)
    _run(caps.extract_resume(request, options), output)


@app.command(name="extract-job")
def extract_job(
    job: str = typer.Argument(..., help="Job text file path, or '-' for stdin."),
    output: OutputFormat = _Output,
    no_llm: bool = _NoLlm,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Extract a structured job description from raw job text."""
    request = ExtractJobDescriptionRequest(raw_text=io.read_text(job))
    options = _options(no_llm, strict, False)
    _run(caps.extract_job_description(request, options), output)


@app.command()
def align(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    output: OutputFormat = _Output,
    no_llm: bool = _NoLlm,
    strict: bool = _Strict,
    human_in_loop: bool = _HumanInLoop,
    evidence: str | None = typer.Option(None, "--evidence", help="Evidence JSON path."),
    config: str | None = _Config,
) -> None:
    """Run controlled alignment of a resume toward a job description."""
    request = AlignResumeRequest(
        resume=io.load_resume(resume),
        job=io.load_job(job),
        evidence=io.load_evidence(evidence) if evidence else None,
    )
    options = _options(no_llm, strict, human_in_loop)
    _run(caps.align_resume(request, options), output)


# ---------------------------------------------------------------------------
# Deterministic commands
# ---------------------------------------------------------------------------


@app.command(name="check-ats")
def check_ats(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Compute the deterministic ATS score for a resume against a job."""
    request = CheckResumeAtsRequest(resume=io.load_resume(resume), job=io.load_job(job))
    options = _options(False, strict, False)
    _run(caps.check_resume_ats(request, options), output)


@app.command()
def match(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Compute the deterministic resume/job match report."""
    request = CheckResumeJobMatchRequest(
        resume=io.load_resume(resume), job=io.load_job(job)
    )
    options = _options(False, strict, False)
    _run(caps.check_resume_job_match(request, options), output)


@app.command()
def select(
    resumes: str = typer.Option(..., "--resumes", help="JSON array of resumes path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Select the best-matching resume from a set for a job."""
    request = SelectBestResumeRequest(
        resumes=io.load_resumes(resumes), job=io.load_job(job)
    )
    options = _options(False, strict, False)
    _run(caps.select_best_resume(request, options), output)


@app.command()
def compare(
    base: str = typer.Option(..., "--base", help="Base resume JSON path."),
    candidate: str = typer.Option(..., "--candidate", help="Candidate resume JSON path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Compare two resume versions against a job description."""
    request = CompareResumeVersionsRequest(
        base=io.load_resume(base),
        candidate=io.load_resume(candidate),
        job=io.load_job(job),
    )
    options = _options(False, strict, False)
    _run(caps.compare_resume_versions(request, options), output)


@app.command(name="identify-gaps")
def identify_gaps(
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    tailored: str = typer.Option(..., "--tailored", help="Tailored resume JSON path."),
    master: str = typer.Option(..., "--master", help="Master resume JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Analyse keyword gaps between a tailored resume, master, and job."""
    request = IdentifyResumeGapsRequest(
        job=io.load_job(job),
        tailored=io.load_resume(tailored),
        master=io.load_resume(master),
    )
    options = _options(False, strict, False)
    _run(caps.identify_resume_gaps(request, options), output)


@app.command(name="validate-truth")
def validate_truth(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    evidence: str | None = typer.Option(None, "--evidence", help="Evidence JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Validate a resume against candidate evidence for truthfulness."""
    request = ValidateResumeTruthRequest(
        resume=io.load_resume(resume),
        evidence=io.load_evidence(evidence) if evidence else [],
    )
    options = _options(False, strict, False)
    _run(caps.validate_resume_truth_capability(request, options), output)


@app.command(name="build-evidence")
def build_evidence(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Build candidate evidence records from a resume."""
    request = BuildCandidateEvidenceRequest(resume=io.load_resume(resume))
    options = _options(False, strict, False)
    _run(caps.build_candidate_evidence_capability(request, options), output)


def main() -> None:
    """Console-script entry point delegating to the Typer app."""
    app()
