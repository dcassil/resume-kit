"""REQ-508 cross-surface parity tests for the Phase 5 interfaces."""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import NamedTuple, cast

import pytest
from fastapi.testclient import TestClient
from resume_kit_api.app import create_app
from resume_kit_cli.io import InMemoryArtifactStore
from resume_kit_core import InterfaceResponse, StructuredCompletionProvider
from resume_kit_core.interface import ExitCode
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_export.models import ExportFormat, mime_type
from resume_kit_facade.capabilities import REGISTRY
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
    DecideChangeRequest,
    ExportResumeRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    ExtractResumeTextRequest,
    IdentifyResumeGapsRequest,
    OpenEditSessionRequest,
    RankEditCandidatesRequest,
    ReconcileSessionRequest,
    RecordEditFeedbackRequest,
    RefreshPreferencesRequest,
    SessionPromptRequest,
    SessionStatusRequest,
    SuggestTerminologyRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_facade.project_config import init_project, set_active, working_dir
from resume_kit_feedback import Candidate, FeatureContext
from resume_kit_mcp.tools import HANDLERS
from resume_kit_schemas import (
    AdditionalInfo,
    CandidateEvidence,
    ChangeProposal,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    Experience,
    JobDescription,
    PersonalInfo,
    Requirement,
    RequirementKind,
    ResumeDocument,
    ReviewAction,
    TerminologyAlignment,
)
from typer import Typer
from typer.testing import CliRunner

JsonDict = dict[str, object]
RequestFactory = Callable[["FixtureContext"], object]
ArgsFactory = Callable[["FixtureContext"], list[str]]
PayloadFactory = Callable[["FixtureContext"], JsonDict]

_COMPARE_FIELDS = (
    "data",
    "errors",
    "warnings",
    "questions",
    "requires_human_input",
    "provenance",
)

_CLIENT = TestClient(create_app())
_RUNNER = CliRunner()
_CLI_APP_MODULE = importlib.import_module("resume_kit_cli.app")
_CLI_APP = cast(Typer, _CLI_APP_MODULE.app)


@dataclass(frozen=True)
class Fixtures:
    resume: ResumeDocument
    master: ResumeDocument
    job: JobDescription
    evidence: list[CandidateEvidence]
    resume_text: str
    job_text: str
    term_resume: ResumeDocument
    term_job: JobDescription
    term_suggestion: TerminologyAlignment
    term_location: str
    feedback: EditFeedback
    preference_records: list[EditFeedback]
    rank_candidates: list[Candidate]
    rank_context: FeatureContext


@dataclass(frozen=True)
class FixturePaths:
    resume: Path
    master: Path
    job: Path
    evidence: Path
    resume_text: Path
    job_text: Path
    term_resume: Path
    term_job: Path
    term_suggestion: Path
    feedback: Path
    preference_records: Path
    rank_candidates: Path
    rank_context: Path
    approved_claims: Path


@dataclass(frozen=True)
class FixtureContext:
    data: Fixtures
    paths: FixturePaths


class SurfaceCase(NamedTuple):
    name: str
    capability: str
    request: RequestFactory
    cli_args: ArgsFactory
    mcp_name: str
    mcp_args: PayloadFactory
    api_path: str
    api_body: PayloadFactory
    no_llm: bool = False


def _fixtures() -> Fixtures:
    resume = ResumeDocument(
        personalInfo=PersonalInfo(
            name="Jordan Lee",
            title="Senior Backend Engineer",
            email="jordan@example.com",
            phone="555-0100",
            location="Austin, TX",
        ),
        summary=(
            "Backend engineer delivering Python APIs, Docker services, and PostgreSQL analytics."
        ),
        workExperience=[
            Experience(
                id=1,
                title="Senior Software Engineer",
                company="Acme Labs",
                years="2021-2025",
                description=[
                    "Built Python APIs with FastAPI and PostgreSQL.",
                    "Containerized services with Docker and automated CI pipelines.",
                ],
            )
        ],
        additional=AdditionalInfo(
            technicalSkills=["Python", "FastAPI", "PostgreSQL", "Docker", "CI"]
        ),
    )
    master = resume.model_copy(
        update={
            "summary": (
                "Backend engineer delivering Python APIs, Docker services, "
                "PostgreSQL analytics, AWS systems, and Kubernetes platforms."
            ),
            "additional": AdditionalInfo(
                technicalSkills=[
                    "Python",
                    "FastAPI",
                    "PostgreSQL",
                    "Docker",
                    "CI",
                    "AWS",
                    "Kubernetes",
                ]
            ),
        }
    )
    job_text = "\n".join(
        [
            "Senior Backend Engineer",
            "Build Python and FastAPI services backed by PostgreSQL.",
            "Requirements: Python, FastAPI, Docker, Kubernetes, PostgreSQL.",
            "Preferred: AWS.",
        ]
    )
    job = JobDescription(
        title="Senior Backend Engineer",
        company="Contoso",
        raw_text=job_text,
        summary="Build backend services for data-heavy product workflows.",
        requirements=[
            Requirement(
                text="Build Python and FastAPI services.",
                kind=RequirementKind.REQUIRED,
                keywords=["Python", "FastAPI"],
            ),
            Requirement(
                text="Operate Docker and Kubernetes workloads.",
                kind=RequirementKind.REQUIRED,
                keywords=["Docker", "Kubernetes"],
            ),
            Requirement(
                text="Use PostgreSQL for product analytics.",
                kind=RequirementKind.REQUIRED,
                keywords=["PostgreSQL"],
            ),
        ],
        qualifications=[
            Requirement(
                text="AWS experience preferred.",
                kind=RequirementKind.PREFERRED,
                keywords=["AWS"],
            )
        ],
        keywords=["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL", "AWS"],
    )
    evidence = [
        CandidateEvidence(
            id="ev-python-api",
            kind=EvidenceKind.WORK_HISTORY,
            content="Built Python APIs with FastAPI and PostgreSQL.",
            source="master_resume",
            tags=["Python", "FastAPI", "PostgreSQL"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="ev-docker",
            kind=EvidenceKind.SKILL,
            content="Docker",
            source="master_resume",
            tags=["Docker"],
            user_confirmed=True,
        ),
    ]
    resume_text = "\n".join(
        [
            "Jordan Lee",
            "Senior Backend Engineer",
            "Built Python APIs with FastAPI and PostgreSQL.",
            "Containerized services with Docker and automated CI pipelines.",
        ]
    )
    # Terminology-alignment fixtures: the k8s/Kubernetes seed alias makes the
    # resume's "Kubernetes" an alias hit for the job's exact "k8s" wording.
    term_resume = ResumeDocument(
        personalInfo=PersonalInfo(name="Sam Rivera"),
        summary="Platform engineer.",
        workExperience=[
            Experience(
                id=1,
                title="Platform Engineer",
                company="Northwind Ltd",
                years="2019-2024",
                description=["Ran workloads on Kubernetes across three regions."],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "Kubernetes"]),
    )
    term_job = JobDescription(
        title="Platform Engineer",
        summary="Kubernetes platform role.",
        requirements=[
            Requirement(
                text="k8s",
                kind=RequirementKind.REQUIRED,
                keywords=["k8s"],
            )
        ],
        keywords=["k8s"],
    )
    term_suggestion = TerminologyAlignment(
        jd_keyword="k8s",
        current_wording="kubernetes",
        locations=["workExperience[0].description[0]"],
        canonical="kubernet",
    )
    feedback = EditFeedback(
        edit_id="edit-1",
        resume_id="resume-1",
        job_id="job-1",
        section="summary",
        edit_type="keyword_substitution",
        original_text="Built APIs.",
        proposed_text="Built Python APIs.",
        final_text=None,
        predicted_ats_gain=2.0,
        confidence=0.8,
        outcome="rejected",
        reason_code=EditFeedbackReasonCode.NOT_MY_VOICE,
        timestamp="2026-08-05T00:00:00+00:00",
    )
    preference_records = [
        feedback.model_copy(
            update={
                "edit_id": f"accepted-{index}",
                "outcome": "accepted",
                "final_text": "Built scalable Python APIs.",
            }
        )
        for index in range(3)
    ]
    rank_candidates = [Candidate(candidate_id="safe", section="skill", proposed_text="Docker")]
    rank_context = FeatureContext(resume=resume, job=job, evidence=evidence)
    return Fixtures(
        resume=resume,
        master=master,
        job=job,
        evidence=evidence,
        resume_text=resume_text,
        job_text=job_text,
        term_resume=term_resume,
        term_job=term_job,
        term_suggestion=term_suggestion,
        term_location="workExperience[0].description[0]",
        feedback=feedback,
        preference_records=preference_records,
        rank_candidates=rank_candidates,
        rank_context=rank_context,
    )


def _json_model(
    model: ResumeDocument | JobDescription | CandidateEvidence | TerminologyAlignment,
) -> JsonDict:
    return cast(JsonDict, model.model_dump(mode="json"))


def _json_models(models: list[CandidateEvidence]) -> list[JsonDict]:
    return [_json_model(model) for model in models]


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _context(tmp_path: Path) -> FixtureContext:
    fixtures = _fixtures()
    paths = FixturePaths(
        resume=_write_json(tmp_path / "resume.json", _json_model(fixtures.resume)),
        master=_write_json(tmp_path / "master.json", _json_model(fixtures.master)),
        job=_write_json(tmp_path / "job.json", _json_model(fixtures.job)),
        evidence=_write_json(tmp_path / "evidence.json", _json_models(fixtures.evidence)),
        resume_text=tmp_path / "resume.txt",
        job_text=tmp_path / "job.txt",
        term_resume=_write_json(tmp_path / "term_resume.json", _json_model(fixtures.term_resume)),
        term_job=_write_json(tmp_path / "term_job.json", _json_model(fixtures.term_job)),
        term_suggestion=_write_json(
            tmp_path / "term_suggestion.json", _json_model(fixtures.term_suggestion)
        ),
        feedback=_write_json(tmp_path / "feedback.json", fixtures.feedback.model_dump(mode="json")),
        preference_records=_write_json(
            tmp_path / "preference_records.json",
            [item.model_dump(mode="json") for item in fixtures.preference_records],
        ),
        rank_candidates=_write_json(
            tmp_path / "rank_candidates.json",
            [item.model_dump(mode="json") for item in fixtures.rank_candidates],
        ),
        rank_context=_write_json(
            tmp_path / "rank_context.json",
            fixtures.rank_context.model_dump(mode="json"),
        ),
        approved_claims=_write_json(
            tmp_path / "approved_claims.json",
            ["Confirmed Docker work"],
        ),
    )
    paths.resume_text.write_text(fixtures.resume_text, encoding="utf-8")
    paths.job_text.write_text(fixtures.job_text, encoding="utf-8")
    return FixtureContext(data=fixtures, paths=paths)


def _canonical(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _canonical(nested)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def _normalize(payload: Mapping[str, object]) -> JsonDict:
    return {field: _canonical(payload[field]) for field in _COMPARE_FIELDS}


def _loads_json(text: str) -> JsonDict:
    return cast(JsonDict, json.loads(text))


async def _await_response(
    awaitable: Awaitable[InterfaceResponse[object]],
) -> InterfaceResponse[object]:
    return await awaitable


async def _await_json(awaitable: Awaitable[JsonDict]) -> JsonDict:
    return await awaitable


def _direct_json(
    capability: str,
    request: object,
    *,
    no_llm: bool = False,
    human_in_loop: bool = False,
    provider: StructuredCompletionProvider | None = None,
) -> JsonDict:
    response: InterfaceResponse[object] = asyncio.run(
        _await_response(
            REGISTRY[capability](
                request,
                CapabilityOptions(
                    no_llm=no_llm,
                    human_in_loop=human_in_loop,
                    provider=provider,
                ),
            )
        )
    )
    return _normalize(cast(JsonDict, response.model_dump(mode="json")))


def _cli_json(args: list[str], expected_exit: int | None = 0) -> JsonDict:
    result = _RUNNER.invoke(_CLI_APP, [*args, "--output", "json"])
    if expected_exit is not None:
        assert result.exit_code == expected_exit, result.stdout
    return _normalize(_loads_json(result.stdout))


def _mcp_json(name: str, arguments: JsonDict) -> JsonDict:
    payload: JsonDict = asyncio.run(_await_json(HANDLERS[name](arguments)))
    return _normalize(payload)


def _api_json(path: str, body: JsonDict, expected_status: int = 200) -> JsonDict:
    response = _CLIENT.post(path, json=body)
    assert response.status_code == expected_status, response.text
    return _normalize(cast(JsonDict, response.json()))


def _resume(ctx: FixtureContext) -> JsonDict:
    return _json_model(ctx.data.resume)


def _master(ctx: FixtureContext) -> JsonDict:
    return _json_model(ctx.data.master)


def _job(ctx: FixtureContext) -> JsonDict:
    return _json_model(ctx.data.job)


def _evidence(ctx: FixtureContext) -> list[JsonDict]:
    return _json_models(ctx.data.evidence)


_SURFACE_CASES = (
    SurfaceCase(
        name="check-resume-job-match",
        capability="check-resume-job-match",
        request=lambda ctx: CheckResumeJobMatchRequest(resume=ctx.data.resume, job=ctx.data.job),
        cli_args=lambda ctx: [
            "match",
            "--resume",
            str(ctx.paths.resume),
            "--job",
            str(ctx.paths.job),
        ],
        mcp_name="resume_check_job_match",
        mcp_args=lambda ctx: {"resume": _resume(ctx), "job": _job(ctx)},
        api_path="/match",
        api_body=lambda ctx: {"resume": _resume(ctx), "job": _job(ctx)},
    ),
    SurfaceCase(
        name="check-resume-ats",
        capability="check-resume-ats",
        request=lambda ctx: CheckResumeAtsRequest(resume=ctx.data.resume, job=ctx.data.job),
        cli_args=lambda ctx: [
            "check-ats",
            "--resume",
            str(ctx.paths.resume),
            "--job",
            str(ctx.paths.job),
        ],
        mcp_name="resume_check_ats",
        mcp_args=lambda ctx: {"resume": _resume(ctx), "job": _job(ctx)},
        api_path="/check-ats",
        api_body=lambda ctx: {"resume": _resume(ctx), "job": _job(ctx)},
    ),
    SurfaceCase(
        name="check-structure",
        capability="check-structure",
        request=lambda ctx: CheckAtsStructureRequest(resume=ctx.data.resume),
        cli_args=lambda ctx: [
            "check-structure",
            "--resume",
            str(ctx.paths.resume),
        ],
        mcp_name="resume_check_ats_structure",
        mcp_args=lambda ctx: {"resume": _resume(ctx)},
        api_path="/check-structure",
        api_body=lambda ctx: {"resume": _resume(ctx)},
    ),
    SurfaceCase(
        name="analyze-best-practices",
        capability="analyze-best-practices",
        request=lambda ctx: AnalyzeBestPracticesRequest(resume=ctx.data.resume),
        cli_args=lambda ctx: [
            "analyze-best-practices",
            "--resume",
            str(ctx.paths.resume),
        ],
        mcp_name="resume_analyze_best_practices",
        mcp_args=lambda ctx: {"resume": _resume(ctx)},
        api_path="/analyze-best-practices",
        api_body=lambda ctx: {"resume": _resume(ctx)},
    ),
    SurfaceCase(
        name="check-gaps",
        capability="check-gaps",
        request=lambda ctx: IdentifyResumeGapsRequest(
            job=ctx.data.job,
            tailored=ctx.data.resume,
            master=ctx.data.master,
        ),
        cli_args=lambda ctx: [
            "identify-gaps",
            "--job",
            str(ctx.paths.job),
            "--tailored",
            str(ctx.paths.resume),
            "--master",
            str(ctx.paths.master),
        ],
        mcp_name="resume_identify_gaps",
        mcp_args=lambda ctx: {
            "job": _job(ctx),
            "tailored": _resume(ctx),
            "master": _master(ctx),
        },
        api_path="/identify-gaps",
        api_body=lambda ctx: {
            "job": _job(ctx),
            "tailored": _resume(ctx),
            "master": _master(ctx),
        },
    ),
    SurfaceCase(
        name="suggest-terminology",
        capability="suggest-terminology",
        request=lambda ctx: SuggestTerminologyRequest(
            resume=ctx.data.term_resume, job=ctx.data.term_job
        ),
        cli_args=lambda ctx: [
            "suggest-terminology",
            "--resume",
            str(ctx.paths.term_resume),
            "--job",
            str(ctx.paths.term_job),
        ],
        mcp_name="resume_suggest_terminology",
        mcp_args=lambda ctx: {
            "resume": _json_model(ctx.data.term_resume),
            "job": _json_model(ctx.data.term_job),
        },
        api_path="/suggest-terminology",
        api_body=lambda ctx: {
            "resume": _json_model(ctx.data.term_resume),
            "job": _json_model(ctx.data.term_job),
        },
    ),
    SurfaceCase(
        name="align-terminology",
        capability="align-terminology",
        request=lambda ctx: AlignTerminologyRequest(
            suggestion=ctx.data.term_suggestion,
            location=ctx.data.term_location,
            resume=ctx.data.term_resume,
            job=ctx.data.term_job,
        ),
        cli_args=lambda ctx: [
            "align-terminology",
            "--suggestion",
            str(ctx.paths.term_suggestion),
            "--location",
            ctx.data.term_location,
            "--resume",
            str(ctx.paths.term_resume),
            "--job",
            str(ctx.paths.term_job),
        ],
        mcp_name="resume_align_terminology",
        mcp_args=lambda ctx: {
            "suggestion": _json_model(ctx.data.term_suggestion),
            "location": ctx.data.term_location,
            "resume": _json_model(ctx.data.term_resume),
            "job": _json_model(ctx.data.term_job),
        },
        api_path="/align-terminology",
        api_body=lambda ctx: {
            "suggestion": _json_model(ctx.data.term_suggestion),
            "location": ctx.data.term_location,
            "resume": _json_model(ctx.data.term_resume),
            "job": _json_model(ctx.data.term_job),
        },
    ),
    SurfaceCase(
        name="validate-facts",
        capability="validate-facts",
        request=lambda ctx: ValidateResumeTruthRequest(
            resume=ctx.data.resume, evidence=ctx.data.evidence
        ),
        cli_args=lambda ctx: [
            "validate-truth",
            "--resume",
            str(ctx.paths.resume),
            "--evidence",
            str(ctx.paths.evidence),
        ],
        mcp_name="resume_validate_truth",
        mcp_args=lambda ctx: {"resume": _resume(ctx), "evidence": _evidence(ctx)},
        api_path="/validate-truth",
        api_body=lambda ctx: {"resume": _resume(ctx), "evidence": _evidence(ctx)},
    ),
    SurfaceCase(
        name="extract-evidence",
        capability="extract-evidence",
        request=lambda ctx: BuildCandidateEvidenceRequest(resume=ctx.data.resume),
        cli_args=lambda ctx: ["build-evidence", "--resume", str(ctx.paths.resume)],
        mcp_name="candidate_evidence_build",
        mcp_args=lambda ctx: {"resume": _resume(ctx)},
        api_path="/build-evidence",
        api_body=lambda ctx: {"resume": _resume(ctx)},
    ),
    SurfaceCase(
        name="extract-evidence-approved-claims",
        capability="extract-evidence",
        request=lambda ctx: BuildCandidateEvidenceRequest(
            resume=ctx.data.resume, approved_claims=["Confirmed Docker work"]
        ),
        cli_args=lambda ctx: [
            "build-evidence",
            "--resume",
            str(ctx.paths.resume),
            "--approved-claims",
            str(ctx.paths.approved_claims),
        ],
        mcp_name="candidate_evidence_build",
        mcp_args=lambda ctx: {
            "resume": _resume(ctx),
            "approved_claims": ["Confirmed Docker work"],
        },
        api_path="/build-evidence",
        api_body=lambda ctx: {
            "resume": _resume(ctx),
            "approved_claims": ["Confirmed Docker work"],
        },
    ),
    SurfaceCase(
        name="record-edit-feedback",
        capability="record-edit-feedback",
        request=lambda ctx: RecordEditFeedbackRequest(
            feedback=ctx.data.feedback,
            base_path=ctx.paths.resume.parent / "resume-kit",
        ),
        cli_args=lambda ctx: [
            "record-edit-feedback",
            "--feedback",
            str(ctx.paths.feedback),
            "--base-path",
            str(ctx.paths.resume.parent / "resume-kit"),
        ],
        mcp_name="edit_feedback_record",
        mcp_args=lambda ctx: {
            "feedback": ctx.data.feedback.model_dump(mode="json"),
            "base_path": str(ctx.paths.resume.parent / "resume-kit"),
        },
        api_path="/record-edit-feedback",
        api_body=lambda ctx: {
            "feedback": ctx.data.feedback.model_dump(mode="json"),
            "base_path": str(ctx.paths.resume.parent / "resume-kit"),
        },
    ),
    SurfaceCase(
        name="rank-edit-candidates",
        capability="rank-edit-candidates",
        request=lambda ctx: RankEditCandidatesRequest(
            candidates=ctx.data.rank_candidates,
            context=ctx.data.rank_context,
        ),
        cli_args=lambda ctx: [
            "rank-edit-candidates",
            "--candidates",
            str(ctx.paths.rank_candidates),
            "--context",
            str(ctx.paths.rank_context),
        ],
        mcp_name="edit_candidates_rank",
        mcp_args=lambda ctx: {
            "candidates": [item.model_dump(mode="json") for item in ctx.data.rank_candidates],
            "context": ctx.data.rank_context.model_dump(mode="json"),
        },
        api_path="/rank-edit-candidates",
        api_body=lambda ctx: {
            "candidates": [item.model_dump(mode="json") for item in ctx.data.rank_candidates],
            "context": ctx.data.rank_context.model_dump(mode="json"),
        },
    ),
    SurfaceCase(
        name="refresh-preferences",
        capability="refresh-preferences",
        request=lambda ctx: RefreshPreferencesRequest(
            now="2026-08-05T00:00:00+00:00",
            records=ctx.data.preference_records,
            base_path=ctx.paths.resume.parent / "resume-kit",
        ),
        cli_args=lambda ctx: [
            "refresh-preferences",
            "--now",
            "2026-08-05T00:00:00+00:00",
            "--records",
            str(ctx.paths.preference_records),
            "--base-path",
            str(ctx.paths.resume.parent / "resume-kit"),
        ],
        mcp_name="preferences_refresh",
        mcp_args=lambda ctx: {
            "now": "2026-08-05T00:00:00+00:00",
            "records": [item.model_dump(mode="json") for item in ctx.data.preference_records],
            "base_path": str(ctx.paths.resume.parent / "resume-kit"),
        },
        api_path="/refresh-preferences",
        api_body=lambda ctx: {
            "now": "2026-08-05T00:00:00+00:00",
            "records": [item.model_dump(mode="json") for item in ctx.data.preference_records],
            "base_path": str(ctx.paths.resume.parent / "resume-kit"),
        },
    ),
    SurfaceCase(
        name="add-evidence",
        capability="add-evidence",
        request=lambda ctx: AddEvidenceRequest(
            content="Confirmed Docker work",
            kind=EvidenceKind.USER_STATEMENT,
            tags=["Docker"],
            root=ctx.paths.resume.parent,
            update_active=True,
        ),
        cli_args=lambda ctx: [
            "add-evidence",
            "--confirmed",
            "--content",
            "Confirmed Docker work",
            "--kind",
            "user_statement",
            "--tag",
            "Docker",
            "--root",
            str(ctx.paths.resume.parent),
            "--update-active",
        ],
        mcp_name="candidate_evidence_add",
        mcp_args=lambda ctx: {
            "confirmed": True,
            "content": "Confirmed Docker work",
            "kind": "user_statement",
            "tags": ["Docker"],
            "root": str(ctx.paths.resume.parent),
            "update_active": True,
        },
        api_path="/add-evidence",
        api_body=lambda ctx: {
            "confirmed": True,
            "content": "Confirmed Docker work",
            "kind": "user_statement",
            "tags": ["Docker"],
            "root": str(ctx.paths.resume.parent),
            "update_active": True,
        },
    ),
    SurfaceCase(
        name="extract-job-description-no-llm",
        capability="extract-job-description",
        request=lambda ctx: ExtractJobDescriptionRequest(raw_text=ctx.data.job_text),
        cli_args=lambda ctx: ["extract-job", str(ctx.paths.job_text), "--no-llm"],
        mcp_name="job_description_extract",
        mcp_args=lambda ctx: {"raw_text": ctx.data.job_text, "no_llm": True},
        api_path="/extract-job",
        api_body=lambda ctx: {"raw_text": ctx.data.job_text, "no_llm": True},
        no_llm=True,
    ),
    SurfaceCase(
        name="extract-resume-text",
        capability="extract-resume-text",
        request=lambda ctx: ExtractResumeTextRequest(
            content=ctx.paths.resume_text.read_bytes(),
            filename=str(ctx.paths.resume_text),
        ),
        cli_args=lambda ctx: ["extract-text", str(ctx.paths.resume_text)],
        mcp_name="resume_extract_text",
        mcp_args=lambda ctx: {
            "content": ctx.paths.resume_text.read_bytes(),
            "filename": str(ctx.paths.resume_text),
        },
        api_path="/extract-text",
        api_body=lambda ctx: {
            "content": ctx.data.resume_text,
            "filename": str(ctx.paths.resume_text),
        },
    ),
    SurfaceCase(
        name="extract-resume-no-llm",
        capability="extract-resume",
        request=lambda ctx: ExtractResumeRequest(
            content=ctx.paths.resume_text.read_bytes(),
            filename=str(ctx.paths.resume_text),
        ),
        cli_args=lambda ctx: ["extract", str(ctx.paths.resume_text), "--no-llm"],
        mcp_name="resume_extract",
        mcp_args=lambda ctx: {
            "content": ctx.paths.resume_text.read_bytes(),
            "filename": str(ctx.paths.resume_text),
            "no_llm": True,
        },
        api_path="/extract",
        api_body=lambda ctx: {
            "content": ctx.data.resume_text,
            "filename": str(ctx.paths.resume_text),
            "no_llm": True,
        },
        no_llm=True,
    ),
)


@pytest.mark.parametrize("case", _SURFACE_CASES, ids=[case.name for case in _SURFACE_CASES])
def test_core_fields_are_equivalent_across_surfaces(tmp_path: Path, case: SurfaceCase) -> None:
    ctx = _context(tmp_path)

    direct = _direct_json(case.capability, case.request(ctx), no_llm=case.no_llm)
    cli = _cli_json(case.cli_args(ctx))
    mcp = _mcp_json(case.mcp_name, case.mcp_args(ctx))
    api = _api_json(case.api_path, case.api_body(ctx))

    assert cli == direct
    assert mcp == direct
    assert api == direct


def test_build_evidence_output_feeds_validate_truth_without_reshaping(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)

    cli_build = _RUNNER.invoke(
        _CLI_APP,
        ["build-evidence", "--resume", str(ctx.paths.resume), "--output", "json"],
    )
    assert cli_build.exit_code == 0, cli_build.stdout
    envelope_path = tmp_path / "built-evidence-envelope.json"
    envelope_path.write_text(cli_build.stdout, encoding="utf-8")
    cli_validate = _RUNNER.invoke(
        _CLI_APP,
        [
            "validate-truth",
            "--resume",
            str(ctx.paths.resume),
            "--evidence",
            str(envelope_path),
            "--output",
            "json",
        ],
    )
    assert cli_validate.exit_code == 0, cli_validate.stdout

    mcp_build = asyncio.run(
        _await_json(HANDLERS["candidate_evidence_build"]({"resume": _resume(ctx)}))
    )
    mcp_validate = asyncio.run(
        _await_json(
            HANDLERS["resume_validate_truth"]({"resume": _resume(ctx), "evidence": mcp_build})
        )
    )
    assert mcp_validate["errors"] == []

    api_build = _CLIENT.post("/build-evidence", json={"resume": _resume(ctx)})
    assert api_build.status_code == 200, api_build.text
    api_validate = _CLIENT.post(
        "/validate-truth",
        json={"resume": _resume(ctx), "evidence": api_build.json()},
    )
    assert api_validate.status_code == 200, api_validate.text


def test_provider_not_configured_error_is_equivalent_across_transports(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path)

    cli = _cli_json(
        [
            "align",
            "--resume",
            str(ctx.paths.resume),
            "--job",
            str(ctx.paths.job),
        ],
        expected_exit=int(ExitCode.PROVIDER_NOT_CONFIGURED),
    )
    mcp = _mcp_json("resume_align", {"resume": _resume(ctx), "job": _job(ctx)})
    api = _api_json(
        "/align",
        {"resume": _resume(ctx), "job": _job(ctx)},
        expected_status=501,
    )

    assert cli == mcp == api
    errors = cast(list[JsonDict], cli["errors"])
    assert errors == [
        {
            "code": "provider_not_configured",
            "message": "No LLM provider is configured for this operation.",
            "details": {"capability": "align-resume"},
        }
    ]


def _align_provider(ctx: FixtureContext) -> FakeStructuredCompletionProvider:
    return FakeStructuredCompletionProvider(
        [
            {
                "changes": [
                    {
                        "path": "summary",
                        "action": "replace",
                        "original": ctx.data.resume.summary,
                        "value": ctx.data.resume.summary,
                        "reason": "No-op review gate parity check.",
                    }
                ]
            }
        ]
    )


def test_align_human_in_loop_surfaces_questions_across_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _context(tmp_path)
    direct = _direct_json(
        "align-resume",
        AlignResumeRequest(resume=ctx.data.resume, job=ctx.data.job),
        human_in_loop=True,
        provider=_align_provider(ctx),
    )

    monkeypatch.setattr(_CLI_APP_MODULE, "PROVIDER", _align_provider(ctx))
    cli = _cli_json(
        [
            "align",
            "--resume",
            str(ctx.paths.resume),
            "--job",
            str(ctx.paths.job),
            "--human-in-loop",
        ],
        expected_exit=None,
    )

    mcp = _mcp_json(
        "resume_align",
        {
            "resume": _resume(ctx),
            "job": _job(ctx),
            "human_in_loop": True,
            "provider": _align_provider(ctx),
        },
    )

    original = REGISTRY["align-resume"]

    async def api_align_with_provider(
        request: object, options: CapabilityOptions
    ) -> InterfaceResponse[object]:
        return await original(request, replace(options, provider=_align_provider(ctx)))

    monkeypatch.setitem(REGISTRY, "align-resume", api_align_with_provider)
    api = _api_json(
        "/align",
        {"resume": _resume(ctx), "job": _job(ctx), "human_in_loop": True},
        expected_status=200,
    )

    surfaces = {"direct": direct, "cli": cli, "mcp": mcp, "api": api}
    assert all(payload["requires_human_input"] is True for payload in surfaces.values())
    assert all(payload["questions"] for payload in surfaces.values())


def _session_change() -> ChangeProposal:
    return ChangeProposal(
        path="summary",
        action="replace",
        original="Backend engineer delivering Python APIs.",
        value="Backend engineer delivering Python and FastAPI APIs.",
        reason="Surface a truthful framework already present in the resume.",
    )


def _session_root(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    init_project(root)
    base = working_dir(root)
    resume = ResumeDocument(
        summary="Backend engineer delivering Python APIs.",
        additional=AdditionalInfo(technicalSkills=["Python", "FastAPI"]),
    )
    job = JobDescription(title="Backend Engineer", keywords=["FastAPI"])
    (base / "resumes" / "jordan-original.json").write_text(
        resume.model_dump_json(),
        encoding="utf-8",
    )
    (base / "jobs" / "job.json").write_text(job.model_dump_json(), encoding="utf-8")
    set_active(root, resume="resumes/jordan-original.json", job="jobs/job.json")
    _write_json(
        root / "changes.json",
        [_session_change().model_dump(mode="json")],
    )
    return root


def _scrub_session_payload(payload: JsonDict) -> JsonDict:
    scrubbed = json.loads(json.dumps(payload))

    def scrub(value: object) -> None:
        if isinstance(value, dict):
            if "session_id" in value:
                value["session_id"] = "<session>"
            for nested in value.values():
                scrub(nested)
        elif isinstance(value, list):
            for nested in value:
                scrub(nested)

    scrub(scrubbed)
    return cast(JsonDict, scrubbed)


def _direct_session_lifecycle(root: Path) -> list[JsonDict]:
    change = _session_change()
    responses = [
        _direct_json(
            "open-edit-session",
            OpenEditSessionRequest(root=root, mode="interactive", changes=[change]),
        ),
        _direct_json("session-prompt", SessionPromptRequest(root=root)),
        _direct_json(
            "decide-change",
            DecideChangeRequest(root=root, path="summary", action=ReviewAction.APPROVE),
        ),
        _direct_json("commit-session", CommitSessionRequest(root=root)),
    ]
    working = working_dir(root) / "working" / "jordan.tailored.json"
    payload = json.loads(working.read_text(encoding="utf-8"))
    payload["summary"] = "Intentional manual reconciliation."
    working.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    responses.extend(
        [
            _direct_json("reconcile-session", ReconcileSessionRequest(root=root)),
            _direct_json("session-status", SessionStatusRequest(root=root)),
        ]
    )
    return [_scrub_session_payload(response) for response in responses]


def _cli_session_lifecycle(root: Path) -> list[JsonDict]:
    responses = [
        _cli_json(
            [
                "review-edits",
                "open",
                "--mode",
                "interactive",
                "--changes",
                str(root / "changes.json"),
                "--root",
                str(root),
            ]
        ),
        _cli_json(
            ["review-edits", "prompt", "--root", str(root)],
            expected_exit=int(ExitCode.HUMAN_INPUT_REQUIRED),
        ),
        _cli_json(
            [
                "review-edits",
                "decide",
                "--path",
                "summary",
                "--action",
                "approve",
                "--root",
                str(root),
            ]
        ),
        _cli_json(["review-edits", "commit", "--root", str(root)]),
    ]
    working = working_dir(root) / "working" / "jordan.tailored.json"
    payload = json.loads(working.read_text(encoding="utf-8"))
    payload["summary"] = "Intentional manual reconciliation."
    working.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    responses.extend(
        [
            _cli_json(["review-edits", "reconcile", "--root", str(root)]),
            _cli_json(["review-edits", "status", "--root", str(root)]),
        ]
    )
    return [_scrub_session_payload(response) for response in responses]


def _mcp_session_lifecycle(root: Path) -> list[JsonDict]:
    change = _session_change().model_dump(mode="json")
    responses = [
        _mcp_json(
            "edit_session_open",
            {"root": str(root), "mode": "interactive", "changes": [change]},
        ),
        _mcp_json("edit_session_prompt", {"root": str(root)}),
        _mcp_json(
            "edit_session_decide",
            {"root": str(root), "path": "summary", "action": "approve"},
        ),
        _mcp_json("edit_session_commit", {"root": str(root)}),
    ]
    working = working_dir(root) / "working" / "jordan.tailored.json"
    payload = json.loads(working.read_text(encoding="utf-8"))
    payload["summary"] = "Intentional manual reconciliation."
    working.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    responses.extend(
        [
            _mcp_json("edit_session_reconcile", {"root": str(root)}),
            _mcp_json("edit_session_status", {"root": str(root)}),
        ]
    )
    return [_scrub_session_payload(response) for response in responses]


def _api_session_lifecycle(root: Path) -> list[JsonDict]:
    change = _session_change().model_dump(mode="json")
    responses = [
        _api_json(
            "/review-edits/open",
            {"root": str(root), "mode": "interactive", "changes": [change]},
        ),
        _api_json("/review-edits/prompt", {"root": str(root)}),
        _api_json(
            "/review-edits/decide",
            {"root": str(root), "path": "summary", "action": "approve"},
        ),
        _api_json("/review-edits/commit", {"root": str(root)}),
    ]
    working = working_dir(root) / "working" / "jordan.tailored.json"
    payload = json.loads(working.read_text(encoding="utf-8"))
    payload["summary"] = "Intentional manual reconciliation."
    working.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    responses.extend(
        [
            _api_json("/review-edits/reconcile", {"root": str(root)}),
            _api_json("/review-edits/status", {"root": str(root)}),
        ]
    )
    return [_scrub_session_payload(response) for response in responses]


def test_review_edits_lifecycle_parity_across_surfaces(tmp_path: Path) -> None:
    roots = {
        "direct": _session_root(tmp_path, "direct"),
        "cli": _session_root(tmp_path, "cli"),
        "mcp": _session_root(tmp_path, "mcp"),
        "api": _session_root(tmp_path, "api"),
    }

    direct = _direct_session_lifecycle(roots["direct"])
    cli = _cli_session_lifecycle(roots["cli"])
    mcp = _mcp_session_lifecycle(roots["mcp"])
    api = _api_session_lifecycle(roots["api"])

    assert cli == direct
    assert mcp == direct
    assert api == direct


# ---------------------------------------------------------------------------
# Baselining lifecycle parity (RIT-I-0016): build-base then build-standard
# ---------------------------------------------------------------------------


def _baseline_root(tmp_path: Path, name: str) -> Path:
    """Scaffold a project with an active original resume needing grooming."""
    root = tmp_path / name
    init_project(root)
    base = working_dir(root)
    resume = ResumeDocument(
        personalInfo=PersonalInfo(
            name="Jordan Lee",
            title="Senior Backend Engineer",
            email="jordan@example.com",
            phone="555-0100",
            location="Austin, TX",
        ),
        summary=(
            "Responsible for building Python APIs, Docker services, and PostgreSQL analytics."
        ),
        workExperience=[
            Experience(
                id=1,
                title="Senior Software Engineer",
                company="Acme Labs",
                years="2021-2025",
                description=[
                    "Responsible for Python APIs with FastAPI and PostgreSQL.",
                    "Containerized services with Docker and automated CI pipelines.",
                ],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "FastAPI", "PostgreSQL", "Docker"]),
    )
    (base / "resumes" / "jordan-original.json").write_text(
        resume.model_dump_json(), encoding="utf-8"
    )
    set_active(root, resume="resumes/jordan-original.json")
    return root


def _direct_baseline_lifecycle(root: Path) -> list[JsonDict]:
    return [
        _direct_json("build-base", BuildBaseRequest(root=root)),
        _direct_json("build-standard", BuildStandardRequest(root=root)),
    ]


def _cli_baseline_lifecycle(root: Path) -> list[JsonDict]:
    return [
        _cli_json(["build-base", "--root", str(root)]),
        _cli_json(["build-standard", "--root", str(root)]),
    ]


def _mcp_baseline_lifecycle(root: Path) -> list[JsonDict]:
    return [
        _mcp_json("resume_build_base", {"root": str(root)}),
        _mcp_json("resume_build_standard", {"root": str(root)}),
    ]


def _api_baseline_lifecycle(root: Path) -> list[JsonDict]:
    return [
        _api_json("/build-base", {"root": str(root)}),
        _api_json("/build-standard", {"root": str(root)}),
    ]


def test_baseline_lifecycle_parity_across_surfaces(tmp_path: Path) -> None:
    roots = {
        "direct": _baseline_root(tmp_path, "direct"),
        "cli": _baseline_root(tmp_path, "cli"),
        "mcp": _baseline_root(tmp_path, "mcp"),
        "api": _baseline_root(tmp_path, "api"),
    }

    direct = _direct_baseline_lifecycle(roots["direct"])
    cli = _cli_baseline_lifecycle(roots["cli"])
    mcp = _mcp_baseline_lifecycle(roots["mcp"])
    api = _api_baseline_lifecycle(roots["api"])

    assert cli == direct
    assert mcp == direct
    assert api == direct


# ---------------------------------------------------------------------------
# Export parity (REQ-604): facade ≡ CLI ≡ MCP ≡ API on artifact metadata
# ---------------------------------------------------------------------------

# Magic-byte signature each format's bytes must start with.
_FORMAT_SIGNATURES: dict[ExportFormat, bytes] = {
    ExportFormat.pdf: b"%PDF-",
    ExportFormat.docx: b"PK",
}


class ArtifactResult(NamedTuple):
    """The semantic export result, normalized across transports."""

    content_type: str
    signature: bytes


def _artifact_result(content_type: str, data: bytes, fmt: ExportFormat) -> ArtifactResult:
    signature = _FORMAT_SIGNATURES[fmt]
    return ArtifactResult(content_type=content_type, signature=data[: len(signature)])


def _export_direct(fmt: ExportFormat, resume: ResumeDocument) -> ArtifactResult:
    """Direct facade: inject an in-memory store, read bytes back via the ref."""
    store = InMemoryArtifactStore()
    request = ExportResumeRequest(resume=resume, format=fmt)
    response = asyncio.run(
        _await_response(REGISTRY["export-resume"](request, CapabilityOptions(artifact_store=store)))
    )
    ref = response.artifacts[0]
    data = asyncio.run(store.get(ref.artifact_id))
    assert isinstance(data, bytes)
    return _artifact_result(ref.content_type, data, fmt)


def _export_cli(fmt: ExportFormat, resume_path: Path, out_path: Path) -> ArtifactResult:
    """CLI ``export``: writes raw bytes to ``--out``; content_type is derived."""
    result = _RUNNER.invoke(
        _CLI_APP,
        [
            "export",
            "--format",
            fmt.value,
            "--resume",
            str(resume_path),
            "--out",
            str(out_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    data = out_path.read_bytes()
    return _artifact_result(mime_type(fmt), data, fmt)


def _export_mcp(fmt: ExportFormat, resume: JsonDict) -> ArtifactResult:
    """MCP ``resume_export``: returns base64 bytes + the ArtifactRef in JSON."""
    payload = asyncio.run(
        _await_json(HANDLERS["resume_export"]({"resume": resume, "format": fmt.value}))
    )
    ref = cast(JsonDict, payload["data"])
    content_type = cast(str, ref["content_type"])
    data = base64.b64decode(cast(str, payload["artifact_bytes_base64"]))
    return _artifact_result(content_type, data, fmt)


def _export_api(fmt: ExportFormat, resume: JsonDict) -> ArtifactResult:
    """API ``POST /export``: returns raw bytes as the body + Content-Type header."""
    response = _CLIENT.post("/export", json={"resume": resume, "format": fmt.value})
    assert response.status_code == 200, response.text
    content_type = response.headers["content-type"]
    return _artifact_result(content_type, response.content, fmt)


@pytest.mark.parametrize("fmt", list(ExportFormat), ids=lambda f: f.value)
def test_export_artifact_metadata_equivalent_across_surfaces(
    tmp_path: Path, fmt: ExportFormat
) -> None:
    """Every surface agrees on export content_type + byte signature (REQ-604)."""
    ctx = _context(tmp_path)
    resume_json = _resume(ctx)

    direct = _export_direct(fmt, ctx.data.resume)
    cli = _export_cli(fmt, ctx.paths.resume, tmp_path / f"out.{fmt.value}")
    mcp = _export_mcp(fmt, resume_json)
    api = _export_api(fmt, resume_json)

    # Each surface must expose the format's canonical MIME type ...
    assert direct.content_type == mime_type(fmt)
    for surface in (cli, mcp, api):
        assert surface.content_type == direct.content_type

    # ... and produce bytes carrying the format's magic signature.
    expected_signature = _FORMAT_SIGNATURES[fmt]
    for surface in (direct, cli, mcp, api):
        assert surface.signature == expected_signature
