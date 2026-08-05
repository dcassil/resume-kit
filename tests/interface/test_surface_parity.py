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
    AlignResumeRequest,
    AlignTerminologyRequest,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckAtsStructureRequest,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    ExportResumeRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    ExtractResumeTextRequest,
    IdentifyResumeGapsRequest,
    SuggestTerminologyRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_mcp.tools import HANDLERS
from resume_kit_schemas import (
    AdditionalInfo,
    CandidateEvidence,
    EvidenceKind,
    Experience,
    JobDescription,
    PersonalInfo,
    Requirement,
    RequirementKind,
    ResumeDocument,
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
            "Backend engineer delivering Python APIs, Docker services, and "
            "PostgreSQL analytics."
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
        term_resume=_write_json(
            tmp_path / "term_resume.json", _json_model(fixtures.term_resume)
        ),
        term_job=_write_json(
            tmp_path / "term_job.json", _json_model(fixtures.term_job)
        ),
        term_suggestion=_write_json(
            tmp_path / "term_suggestion.json", _json_model(fixtures.term_suggestion)
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
        request=lambda ctx: CheckResumeJobMatchRequest(
            resume=ctx.data.resume, job=ctx.data.job
        ),
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
        request=lambda ctx: CheckResumeAtsRequest(
            resume=ctx.data.resume, job=ctx.data.job
        ),
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
        name="check-ats-structure",
        capability="check-ats-structure",
        request=lambda ctx: CheckAtsStructureRequest(resume=ctx.data.resume),
        cli_args=lambda ctx: [
            "check-ats-structure",
            "--resume",
            str(ctx.paths.resume),
        ],
        mcp_name="resume_check_ats_structure",
        mcp_args=lambda ctx: {"resume": _resume(ctx)},
        api_path="/check-ats-structure",
        api_body=lambda ctx: {"resume": _resume(ctx)},
    ),
    SurfaceCase(
        name="identify-resume-gaps",
        capability="identify-resume-gaps",
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
        name="validate-resume-truth",
        capability="validate-resume-truth",
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
        name="build-candidate-evidence",
        capability="build-candidate-evidence",
        request=lambda ctx: BuildCandidateEvidenceRequest(resume=ctx.data.resume),
        cli_args=lambda ctx: ["build-evidence", "--resume", str(ctx.paths.resume)],
        mcp_name="candidate_evidence_build",
        mcp_args=lambda ctx: {"resume": _resume(ctx)},
        api_path="/build-evidence",
        api_body=lambda ctx: {"resume": _resume(ctx)},
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
def test_core_fields_are_equivalent_across_surfaces(
    tmp_path: Path, case: SurfaceCase
) -> None:
    ctx = _context(tmp_path)

    direct = _direct_json(case.capability, case.request(ctx), no_llm=case.no_llm)
    cli = _cli_json(case.cli_args(ctx))
    mcp = _mcp_json(case.mcp_name, case.mcp_args(ctx))
    api = _api_json(case.api_path, case.api_body(ctx))

    assert cli == direct
    assert mcp == direct
    assert api == direct


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
        _await_response(
            REGISTRY["export-resume"](request, CapabilityOptions(artifact_store=store))
        )
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
