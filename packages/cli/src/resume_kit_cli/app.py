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
import base64
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import typer
from resume_kit_core import StructuredCompletionProvider
from resume_kit_core.interface import ExitCode, exit_code_for
from resume_kit_core.response import InterfaceResponse
from resume_kit_export.models import ExportFormat
from resume_kit_facade import capabilities as caps
from resume_kit_facade.models import (
    AddEvidenceRequest,
    AlignResumeRequest,
    AlignTerminologyRequest,
    AnalyzeBestPracticesRequest,
    BuildBaseRequest,
    BuildCandidateEvidenceRequest,
    BuildStandardRequest,
    CapabilityOptions,
    CheckAtsStructureRequest,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CommitSessionRequest,
    CompareResumeVersionsRequest,
    DecideChangeRequest,
    ExportResumeRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    ExtractResumeTextRequest,
    IdentifyResumeGapsRequest,
    InitProjectRequest,
    OpenEditSessionRequest,
    RankEditCandidatesRequest,
    ReconcileSessionRequest,
    RecordEditFeedbackRequest,
    RefreshPreferencesRequest,
    SelectBestResumeRequest,
    SessionPromptRequest,
    SessionStatusRequest,
    SetActiveRequest,
    SuggestTerminologyRequest,
    ValidateFaithfulnessRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_feedback import Candidate, FeatureContext
from resume_kit_schemas import (
    CandidateEvidence,
    ChangeProposal,
    ClaimProvenance,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    FaithfulnessReport,
    PreferencePair,
    ReviewAction,
    ScoreDelta,
    UserPreferenceProfile,
)

from resume_kit_cli import io
from resume_kit_cli.formatters import OutputFormat, render

app = typer.Typer(
    help="Resume Kit command-line transport over the capability facade.",
    no_args_is_help=True,
)
review_edits_app = typer.Typer(
    help="Open, review, decide, commit, and reconcile edit sessions.",
    no_args_is_help=True,
)
app.add_typer(review_edits_app, name="review-edits")

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
_AliasFile = typer.Option(
    None,
    "--alias-file",
    help="Optional project alias JSON path for synonym-aware scoring.",
)
_Format = typer.Option(..., "--format", help="Export format: pdf or docx.")
_Out = typer.Option(None, "--out", help="Write raw bytes to this path.")
_ResumeOrStdin = typer.Option("-", "--resume", help="Resume JSON path, or '-' for stdin.")
_BasePath = typer.Option(
    None,
    "--base-path",
    help="Optional resume-kit/ working directory for learning logs.",
)
_Root = typer.Option(".", "--root", help="Project root containing resume-kit/.")
_EvidenceKind = typer.Option(
    EvidenceKind.USER_STATEMENT,
    "--kind",
    help="Evidence kind.",
)
_EvidenceTag = typer.Option(
    None,
    "--tag",
    help="Evidence tag; may be supplied multiple times.",
)
_Confirmed = typer.Option(
    False,
    "--confirmed",
    help="Required to persist user-confirmed evidence.",
)
_EvidenceFile = typer.Option(
    "working/user-confirmed-evidence.json",
    "--evidence-file",
    help="Evidence file path relative to resume-kit/.",
)
_UpdateActive = typer.Option(
    False,
    "--update-active",
    help="Update config.active_evidence to this evidence file.",
)
_ReviewAction = typer.Option(..., "--action", help="Review action.")
_FeedbackReasonCode = typer.Option(
    None,
    "--reason-code",
    help="Optional structured feedback reason.",
)


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


def _run_gate(
    coro: Coroutine[Any, Any, InterfaceResponse[object]],
    output: OutputFormat,
) -> None:
    """Await a gate ``coro``, render it, and exit non-zero when the gate fails.

    A faithfulness report is carried as ``data`` on an otherwise-ok envelope, so
    ``exit_code_for`` alone would return 0 even when the report failed. This
    HARD GATE maps ``report.passed is False`` to a non-zero exit (``INVALID_INPUT``)
    while still printing the full report, so callers can both read the findings
    and branch on the exit code.
    """
    response = asyncio.run(coro)
    typer.echo(render(response, output))
    code = exit_code_for(response)
    data = response.data
    if isinstance(data, FaithfulnessReport) and not data.passed:
        code = code or int(ExitCode.INVALID_INPUT)
    raise typer.Exit(code=code)


def _load_approved_claims(
    source: str | None,
) -> list[CandidateEvidence] | list[str] | None:
    """Load approved claims from JSON strings or evidence records."""
    if source is None:
        return None
    value = io.load_json_value(source)
    if not isinstance(value, list):
        raise typer.BadParameter("--approved-claims must contain a JSON array.")
    if all(isinstance(item, str) for item in value):
        return [item for item in value if isinstance(item, str)]
    return [CandidateEvidence.model_validate(item) for item in value]


def _load_candidates(source: str) -> list[Candidate]:
    """Load a JSON array of feedback ``Candidate`` records."""
    value = io.load_json_value(source)
    if not isinstance(value, list):
        raise typer.BadParameter("--candidates must contain a JSON array.")
    return [Candidate.model_validate(item) for item in value]


def _load_feedback_records(source: str) -> list[EditFeedback]:
    """Load a JSON array of ``EditFeedback`` records."""
    value = io.load_json_value(source)
    if not isinstance(value, list):
        raise typer.BadParameter("--records must contain a JSON array.")
    return [EditFeedback.model_validate(item) for item in value]


def _load_changes(source: str) -> list[ChangeProposal]:
    """Load a JSON array of ``ChangeProposal`` records."""
    value = io.load_json_value(source)
    if not isinstance(value, list):
        raise typer.BadParameter("--changes must contain a JSON array.")
    return [ChangeProposal.model_validate(item) for item in value]


def _load_claim_provenance(source: str | None) -> list[ClaimProvenance]:
    """Load optional claim-provenance records."""
    if source is None:
        return []
    value = io.load_json_value(source)
    if not isinstance(value, list):
        raise typer.BadParameter("--claim-provenance must contain a JSON array.")
    return [ClaimProvenance.model_validate(item) for item in value]


def _load_score_deltas(source: str | None) -> list[ScoreDelta]:
    """Load optional expected score deltas."""
    if source is None:
        return []
    value = io.load_json_value(source)
    if not isinstance(value, list):
        raise typer.BadParameter("--expected-score-deltas must contain a JSON array.")
    return [ScoreDelta.model_validate(item) for item in value]


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


@app.command(name="extract-text")
def extract_text(
    file: str = typer.Argument(..., help="Resume/job file path, or '-' for stdin."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Extract raw text from a resume/job file (docx/pdf/md/txt) — no LLM, no network.

    Deterministic EXTRACTION primitive: returns the raw ``TextExtractionResult``
    (text + warnings + method). Accepts ``-`` for stdin bytes like ``extract``;
    for stdin the filename defaults to ``resume.txt`` so plain-text decode is
    used (pass a real path to extract PDF/DOCX).
    """
    filename = file if file != "-" else "resume.txt"
    request = ExtractResumeTextRequest(content=io.read_bytes(file), filename=filename)
    options = _options(False, strict, False)
    _run(caps.extract_resume_text_capability(request, options), output)


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
    alias_file: str | None = _AliasFile,
) -> None:
    """Compute the deterministic ATS score for a resume against a job."""
    request = CheckResumeAtsRequest(
        resume=io.load_resume(resume), job=io.load_job(job), alias_file=alias_file
    )
    options = _options(False, strict, False)
    _run(caps.check_resume_ats(request, options), output)


# Renamed to "check-structure" from "check-ats-structure" in v1.0.0 (RIT-A-0005).
@app.command(name="check-structure")
def check_ats_structure(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Run the resume-only structural ATS check (no job)."""
    request = CheckAtsStructureRequest(resume=io.load_resume(resume))
    options = _options(False, strict, False)
    _run(caps.check_ats_structure(request, options), output)


@app.command()
def match(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
    alias_file: str | None = _AliasFile,
) -> None:
    """Compute the deterministic resume/job match report."""
    request = CheckResumeJobMatchRequest(
        resume=io.load_resume(resume), job=io.load_job(job), alias_file=alias_file
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
    request = SelectBestResumeRequest(resumes=io.load_resumes(resumes), job=io.load_job(job))
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
    alias_file: str | None = _AliasFile,
) -> None:
    """Analyse keyword gaps between a tailored resume, master, and job."""
    request = IdentifyResumeGapsRequest(
        job=io.load_job(job),
        tailored=io.load_resume(tailored),
        master=io.load_resume(master),
        alias_file=alias_file,
    )
    options = _options(False, strict, False)
    _run(caps.identify_resume_gaps(request, options), output)


@app.command(name="suggest-terminology")
def suggest_terminology(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
    alias_file: str | None = _AliasFile,
) -> None:
    """List terminology-mirroring suggestions for a resume against a job."""
    request = SuggestTerminologyRequest(
        resume=io.load_resume(resume), job=io.load_job(job), alias_file=alias_file
    )
    options = _options(False, strict, False)
    _run(caps.suggest_terminology(request, options), output)


@app.command(name="align-terminology")
def align_terminology(
    suggestion: str = typer.Option(
        ..., "--suggestion", help="TerminologyAlignment suggestion JSON path."
    ),
    location: str = typer.Option(
        ..., "--location", help="Resume path from suggestion.locations to apply."
    ),
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    job: str = typer.Option(..., "--job", help="Job description JSON path."),
    evidence: str | None = typer.Option(None, "--evidence", help="Evidence JSON path."),
    freedom: int | None = typer.Option(
        None, "--freedom", help="Explicit policy-freedom level (default: minimal)."
    ),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
    alias_file: str | None = _AliasFile,
) -> None:
    """Apply one accepted terminology suggestion and report the score delta."""
    request = AlignTerminologyRequest(
        suggestion=io.load_suggestion(suggestion),
        location=location,
        resume=io.load_resume(resume),
        job=io.load_job(job),
        evidence=io.load_evidence(evidence) if evidence else (),
        freedom=freedom,
        alias_file=alias_file,
    )
    options = _options(False, strict, False)
    _run(caps.align_terminology(request, options), output)


@app.command(name="validate-truth")
def validate_truth(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    evidence: str | None = typer.Option(None, "--evidence", help="Evidence JSON path."),
    alias_file: str | None = _AliasFile,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Validate a resume against candidate evidence for truthfulness."""
    request = ValidateResumeTruthRequest(
        resume=io.load_resume(resume),
        evidence=io.load_evidence(evidence) if evidence else [],
        alias_file=alias_file,
    )
    options = _options(False, strict, False)
    _run(caps.validate_resume_truth_capability(request, options), output)


@app.command(name="validate-faithfulness")
def validate_faithfulness(
    source: str = typer.Option(
        ..., "--source", help="Source file path (docx/pdf/md/txt), or '-' for stdin."
    ),
    json_path: str = typer.Option(
        ..., "--json", help="ResumeDocument JSON path to check against the source."
    ),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Deterministic faithfulness HARD GATE — exits non-zero on drift.

    Compares the agent-produced ``ResumeDocument`` JSON against the ORIGINAL
    source document (no LLM, no network). Reports dropped/added/altered content
    and count mismatches; exits non-zero when the report's ``passed`` is False.
    ``-`` reads the source text from stdin; a real path decodes docx/pdf/md/txt.
    """
    if source == "-":
        request = ValidateFaithfulnessRequest(
            resume=io.load_resume(json_path),
            source_text=io.read_text(source),
        )
    else:
        request = ValidateFaithfulnessRequest(
            resume=io.load_resume(json_path),
            source_content=io.read_bytes(source),
            source_filename=source,
        )
    options = _options(False, strict, False)
    _run_gate(caps.validate_faithfulness_capability(request, options), output)


@app.command(name="build-evidence")
def build_evidence(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    approved_claims: str | None = typer.Option(
        None,
        "--approved-claims",
        help="JSON path containing approved claim strings or CandidateEvidence records.",
    ),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Build candidate evidence records from a resume."""
    request = BuildCandidateEvidenceRequest(
        resume=io.load_resume(resume),
        approved_claims=_load_approved_claims(approved_claims),
    )
    options = _options(False, strict, False)
    _run(caps.build_candidate_evidence_capability(request, options), output)


@app.command(name="record-edit-feedback")
def record_edit_feedback(
    feedback: str = typer.Option(..., "--feedback", help="EditFeedback JSON path."),
    preference_pair: str | None = typer.Option(
        None,
        "--preference-pair",
        help="Optional PreferencePair JSON path.",
    ),
    base_path: str | None = _BasePath,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Append edit feedback and an optional preference-pair record."""
    request = RecordEditFeedbackRequest(
        feedback=io.load_model(feedback, EditFeedback),
        preference_pair=(
            io.load_model(preference_pair, PreferencePair) if preference_pair is not None else None
        ),
        base_path=base_path,
    )
    options = _options(False, strict, False)
    _run(caps.record_edit_feedback_capability(request, options), output)


@app.command(name="rank-edit-candidates")
def rank_edit_candidates(
    candidates: str = typer.Option(..., "--candidates", help="Candidate array JSON path."),
    context: str = typer.Option(..., "--context", help="FeatureContext JSON path."),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Optional UserPreferenceProfile JSON path.",
    ),
    alias_file: str | None = _AliasFile,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Rank edit candidates with the deterministic heuristic ranker."""
    request = RankEditCandidatesRequest(
        candidates=_load_candidates(candidates),
        context=io.load_model(context, FeatureContext),
        profile=(
            io.load_model(profile, UserPreferenceProfile)
            if profile is not None
            else UserPreferenceProfile()
        ),
        alias_file=alias_file,
    )
    options = _options(False, strict, False)
    _run(caps.rank_edit_candidates_capability(request, options), output)


@app.command(name="refresh-preferences")
def refresh_preferences(
    now: str = typer.Option(..., "--now", help="Caller-supplied ISO timestamp."),
    records: str | None = typer.Option(
        None,
        "--records",
        help="Optional EditFeedback array JSON path; otherwise persisted log is read.",
    ),
    base_path: str | None = _BasePath,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Derive and persist the user preference profile."""
    request = RefreshPreferencesRequest(
        now=now,
        records=_load_feedback_records(records) if records is not None else None,
        base_path=base_path,
    )
    options = _options(False, strict, False)
    _run(caps.refresh_preferences_capability(request, options), output)


@app.command(name="add-evidence")
def add_evidence(
    content: str = typer.Option(..., "--content", help="Confirmed evidence content."),
    kind: EvidenceKind = _EvidenceKind,
    tag: list[str] | None = _EvidenceTag,
    confirmed: bool = _Confirmed,
    root: str = _Root,
    evidence_file: str = _EvidenceFile,
    update_active: bool = _UpdateActive,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Persist one user-confirmed evidence record under resume-kit/."""
    if not confirmed:
        raise typer.BadParameter("Pass --confirmed to persist confirmed evidence.")
    request = AddEvidenceRequest(
        content=content,
        kind=kind,
        tags=tag or [],
        root=root,
        evidence_file=evidence_file,
        update_active=update_active,
    )
    options = _options(False, strict, False)
    _run(caps.add_evidence_capability(request, options), output)


@app.command()
def export(
    format: ExportFormat = _Format,
    out: str | None = _Out,
    resume: str = _ResumeOrStdin,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
    config: str | None = _Config,
) -> None:
    """Render a resume to PDF/DOCX bytes via the export-resume capability."""
    request = ExportResumeRequest(resume=io.load_resume(resume), format=format)
    store = io.InMemoryArtifactStore()
    options = CapabilityOptions(strict=strict, artifact_store=store)
    response = asyncio.run(caps.export_resume(request, options))
    code = exit_code_for(response)
    if response.errors or not response.artifacts:
        typer.echo(render(response, output))
        raise typer.Exit(code=code)
    data = asyncio.run(store.get(response.artifacts[0].artifact_id))
    if not isinstance(data, bytes):  # defensive: store must hold rendered bytes
        typer.echo(render(response, output))
        raise typer.Exit(code=code)
    if out is not None:
        Path(out).write_bytes(data)
        typer.echo(f"Wrote {len(data)} bytes to {out}")
    else:
        typer.echo(base64.b64encode(data).decode("ascii"))
    raise typer.Exit(code=code)


# ---------------------------------------------------------------------------
# Working-directory state commands (RIT-T-0091)
# ---------------------------------------------------------------------------


@app.command()
def init(
    root: str = _Root,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Idempotently scaffold the resume-kit/ working directory + config.json."""
    request = InitProjectRequest(root=root)
    options = _options(False, strict, False)
    _run(caps.init_project_capability(request, options), output)


@app.command(name="set-active")
def set_active(
    resume: str | None = typer.Option(
        None, "--resume", help="Active resume JSON path (relative to resume-kit/)."
    ),
    resume_source: str | None = typer.Option(
        None, "--source", help="Original source file the active resume came from."
    ),
    job: str | None = typer.Option(
        None, "--job", help="Active job JSON path (relative to resume-kit/)."
    ),
    job_source: str | None = typer.Option(
        None, "--job-source", help="Original source file the active job came from."
    ),
    root: str = _Root,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Record active resume/job pointers plus source paths through the schema."""
    request = SetActiveRequest(
        resume=resume,
        resume_source=resume_source,
        job=job,
        job_source=job_source,
        root=root,
    )
    options = _options(False, strict, False)
    _run(caps.set_active_capability(request, options), output)


# ---------------------------------------------------------------------------
# Baselining commands (RIT-I-0016)
# ---------------------------------------------------------------------------


@app.command(name="build-base")
def build_base(
    root: str = _Root,
    mode: str = typer.Option("auto", "--mode", help="Fix mode (only 'auto' is supported)."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Run the original->base write path behind the claim-preservation gate."""
    request = BuildBaseRequest(root=root, mode=mode)
    options = _options(False, strict, False)
    _run(caps.build_base_capability(request, options), output)


@app.command(name="build-standard")
def build_standard(
    root: str = _Root,
    answers: str | None = typer.Option(
        None,
        "--answers",
        help="Optional JSON path mapping finding keys to user-supplied rewrites.",
    ),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Run the base->standard best-practices write path behind the gate."""
    request = BuildStandardRequest(root=root, answers=io.load_answers(answers))
    options = _options(False, strict, False)
    _run(caps.build_standard_capability(request, options), output)


@app.command(name="analyze-best-practices")
def analyze_best_practices(
    resume: str = typer.Option(..., "--resume", help="Resume JSON path."),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Run the generic (job-independent) best-practices score on a resume."""
    request = AnalyzeBestPracticesRequest(resume=io.load_resume(resume))
    options = _options(False, strict, False)
    _run(caps.analyze_best_practices_capability(request, options), output)


@review_edits_app.command(name="open")
def review_edits_open(
    mode: str = typer.Option(..., "--mode", help="interactive, review_at_end, or auto."),
    changes: str = typer.Option(..., "--changes", help="ChangeProposal array JSON path."),
    root: str = _Root,
    evidence: str | None = typer.Option(None, "--evidence", help="Evidence array JSON path."),
    claim_provenance: str | None = typer.Option(
        None,
        "--claim-provenance",
        help="ClaimProvenance array JSON path.",
    ),
    expected_score_deltas: str | None = typer.Option(
        None,
        "--expected-score-deltas",
        help="ScoreDelta array JSON path.",
    ),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Open the single active edit session."""
    request = OpenEditSessionRequest(
        mode=mode,
        changes=_load_changes(changes),
        root=root,
        evidence=io.load_evidence(evidence) if evidence is not None else [],
        claim_provenance=_load_claim_provenance(claim_provenance),
        expected_score_deltas=_load_score_deltas(expected_score_deltas),
    )
    options = _options(False, strict, False)
    _run(caps.open_edit_session_capability(request, options), output)


@review_edits_app.command(name="prompt")
def review_edits_prompt(
    root: str = _Root,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Return the next review prompt for the active session."""
    request = SessionPromptRequest(root=root)
    options = _options(False, strict, False)
    _run(caps.session_prompt_capability(request, options), output)


@review_edits_app.command(name="decide")
def review_edits_decide(
    path: str = typer.Option(..., "--path", help="ChangeProposal path to decide."),
    action: ReviewAction = _ReviewAction,
    reason_code: EditFeedbackReasonCode | None = _FeedbackReasonCode,
    note: str | None = typer.Option(None, "--note", help="Optional free-text note."),
    edited_content: str | None = typer.Option(
        None,
        "--edited-content",
        help="Final text for an edit action.",
    ),
    root: str = _Root,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Record a decision for one proposed change."""
    request = DecideChangeRequest(
        path=path,
        action=action,
        reason_code=reason_code,
        note=note,
        root=root,
        edited_content=edited_content,
    )
    options = _options(False, strict, False)
    _run(caps.decide_change_capability(request, options), output)


@review_edits_app.command(name="commit")
def review_edits_commit(
    root: str = _Root,
    freedom: int = typer.Option(10, "--freedom", min=0, max=10),
    alias_timestamp: str | None = typer.Option(
        None,
        "--alias-timestamp",
        help="Optional ISO timestamp for accepted-edit alias provenance.",
    ),
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Commit approved changes through the hard write gate."""
    request = CommitSessionRequest(
        root=root,
        freedom=freedom,
        alias_timestamp=alias_timestamp,
    )
    options = _options(False, strict, False)
    _run(caps.commit_session_capability(request, options), output)


@review_edits_app.command(name="status")
def review_edits_status(
    root: str = _Root,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Return progress for the active edit session."""
    request = SessionStatusRequest(root=root)
    options = _options(False, strict, False)
    _run(caps.session_status_capability(request, options), output)


@review_edits_app.command(name="reconcile")
def review_edits_reconcile(
    root: str = _Root,
    output: OutputFormat = _Output,
    strict: bool = _Strict,
) -> None:
    """Re-hash intentional manual edits to the working resume."""
    request = ReconcileSessionRequest(root=root)
    options = _options(False, strict, False)
    _run(caps.reconcile_session_capability(request, options), output)


def main() -> None:
    """Console-script entry point delegating to the Typer app."""
    app()
