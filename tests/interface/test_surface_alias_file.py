"""RIT-T-0069: every surface honors an explicit project ``alias_file``.

A project alias JSON (RIT-T-0068 format) that maps a job keyword to a term the
resume actually uses must change deterministic scoring identically across the
facade, CLI, MCP, and API surfaces — and the ``alias_file`` env indirection
must never leak between calls (seed-only calls stay unchanged).

The fixture uses fabricated terms absent from the packaged seed lexicon: the
resume writes ``zflow`` while the job requires ``Zephyrflow``. Only a project
alias mapping ``Zephyrflow -> [zflow]`` lets that keyword register as matched.
With no alias file every surface scores it as a miss (identical to pre-0009
behaviour). Fabricated terms are used deliberately so the seed lexicon can never
mask the effect of the project alias file.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
from collections.abc import Awaitable, Mapping
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from resume_kit_api.app import create_app
from resume_kit_core import InterfaceResponse
from resume_kit_facade.capabilities import REGISTRY
from resume_kit_facade.models import (
    CapabilityOptions,
    CheckResumeAtsRequest,
    SuggestTerminologyRequest,
)
from resume_kit_mcp.tools import HANDLERS
from resume_kit_schemas import (
    AdditionalInfo,
    Experience,
    JobDescription,
    PersonalInfo,
    Requirement,
    RequirementKind,
    ResumeDocument,
)
from resume_kit_terms.aliases import PROJECT_ALIAS_ENV_VAR
from typer import Typer
from typer.testing import CliRunner

JsonDict = dict[str, object]

_CLIENT = TestClient(create_app())
_RUNNER = CliRunner()
_CLI_APP = cast(Typer, importlib.import_module("resume_kit_cli.app").app)


def _resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Sam Rivera",
            title="Platform Engineer",
            email="sam@example.com",
            phone="555-0111",
            location="Denver, CO",
        ),
        summary="Platform engineer operating zflow pipelines and Python services.",
        workExperience=[
            Experience(
                id=1,
                title="Platform Engineer",
                company="Globex",
                years="2020-2025",
                description=["Operated zflow pipelines running Python workloads."],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "zflow"]),
    )


def _job() -> JobDescription:
    return JobDescription(
        title="Platform Engineer",
        company="Initech",
        raw_text="Operate Zephyrflow pipelines. Requirements: Python, Zephyrflow.",
        summary="Operate data pipeline platforms.",
        requirements=[
            Requirement(
                text="Operate Zephyrflow pipelines.",
                kind=RequirementKind.REQUIRED,
                keywords=["Zephyrflow"],
            ),
            Requirement(
                text="Write Python services.",
                kind=RequirementKind.REQUIRED,
                keywords=["Python"],
            ),
        ],
        keywords=["Python", "Zephyrflow"],
    )


def _alias_json(tmp_path: Path) -> Path:
    path = tmp_path / "synonyms.json"
    path.write_text(
        json.dumps({"version": 1, "aliases": {"Zephyrflow": ["zflow"]}}),
        encoding="utf-8",
    )
    return path


def _write_json(path: Path, model: ResumeDocument | JobDescription) -> Path:
    path.write_text(
        json.dumps(model.model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    return path


async def _await_response(
    awaitable: Awaitable[InterfaceResponse[object]],
) -> InterfaceResponse[object]:
    return await awaitable


async def _await_json(awaitable: Awaitable[JsonDict]) -> JsonDict:
    return await awaitable


def _ats_percentage(payload: Mapping[str, object]) -> float:
    data = cast(dict[str, object], payload["data"])
    return cast(float, data["overall_score"])


# --- surface callers, each returning the ATS response payload as JSON --------


def _direct_ats(resume: ResumeDocument, job: JobDescription, alias: str | None) -> JsonDict:
    response = asyncio.run(
        _await_response(
            REGISTRY["check-resume-ats"](
                CheckResumeAtsRequest(resume=resume, job=job, alias_file=alias),
                CapabilityOptions(),
            )
        )
    )
    return cast(JsonDict, response.model_dump(mode="json"))


def _cli_ats(resume_path: Path, job_path: Path, alias: str | None) -> JsonDict:
    args = ["check-ats", "--resume", str(resume_path), "--job", str(job_path)]
    if alias is not None:
        args += ["--alias-file", alias]
    result = _RUNNER.invoke(_CLI_APP, [*args, "--output", "json"])
    assert result.exit_code == 0, result.stdout
    return cast(JsonDict, json.loads(result.stdout))


def _mcp_ats(resume: ResumeDocument, job: JobDescription, alias: str | None) -> JsonDict:
    args: JsonDict = {
        "resume": resume.model_dump(mode="json"),
        "job": job.model_dump(mode="json"),
    }
    if alias is not None:
        args["alias_file"] = alias
    return asyncio.run(_await_json(HANDLERS["resume_check_ats"](args)))


def _api_ats(resume: ResumeDocument, job: JobDescription, alias: str | None) -> JsonDict:
    body: JsonDict = {
        "resume": resume.model_dump(mode="json"),
        "job": job.model_dump(mode="json"),
    }
    if alias is not None:
        body["alias_file"] = alias
    response = _CLIENT.post("/check-ats", json=body)
    assert response.status_code == 200, response.text
    return cast(JsonDict, response.json())


# ---------------------------------------------------------------------------


def test_alias_file_raises_score_on_every_surface(tmp_path: Path) -> None:
    resume, job = _resume(), _job()
    alias = str(_alias_json(tmp_path))
    resume_path = _write_json(tmp_path / "resume.json", resume)
    job_path = _write_json(tmp_path / "job.json", job)

    baseline = _ats_percentage(_direct_ats(resume, job, None))
    with_alias = _ats_percentage(_direct_ats(resume, job, alias))
    # The alias lets ``zflow`` satisfy the ``Zephyrflow`` requirement, so scoring
    # must strictly improve — proving the fixture actually exercises the alias.
    assert with_alias > baseline

    assert _ats_percentage(_cli_ats(resume_path, job_path, alias)) == with_alias
    assert _ats_percentage(_mcp_ats(resume, job, alias)) == with_alias
    assert _ats_percentage(_api_ats(resume, job, alias)) == with_alias

    # No alias -> every surface matches the seed-only baseline.
    assert _ats_percentage(_cli_ats(resume_path, job_path, None)) == baseline
    assert _ats_percentage(_mcp_ats(resume, job, None)) == baseline
    assert _ats_percentage(_api_ats(resume, job, None)) == baseline


def test_suggest_terminology_honors_alias_file_on_every_surface(
    tmp_path: Path,
) -> None:
    """A project alias makes ``zflow`` an alias hit for the JD's ``Zephyrflow``,
    so ``suggest-terminology`` emits a mirror suggestion only WITH the alias
    file — identically across facade, CLI, MCP, and API."""
    resume, job = _resume(), _job()
    alias = str(_alias_json(tmp_path))
    resume_path = _write_json(tmp_path / "resume.json", resume)
    job_path = _write_json(tmp_path / "job.json", job)

    def _keywords(payload: Mapping[str, object]) -> set[str]:
        data = cast(list[dict[str, object]], payload["data"])
        return {cast(str, item["jd_keyword"]) for item in data}

    def _direct(a: str | None) -> JsonDict:
        response = asyncio.run(
            _await_response(
                REGISTRY["suggest-terminology"](
                    SuggestTerminologyRequest(resume=resume, job=job, alias_file=a),
                    CapabilityOptions(),
                )
            )
        )
        return cast(JsonDict, response.model_dump(mode="json"))

    def _cli(a: str | None) -> JsonDict:
        args = [
            "suggest-terminology",
            "--resume",
            str(resume_path),
            "--job",
            str(job_path),
        ]
        if a is not None:
            args += ["--alias-file", a]
        result = _RUNNER.invoke(_CLI_APP, [*args, "--output", "json"])
        assert result.exit_code == 0, result.stdout
        return cast(JsonDict, json.loads(result.stdout))

    def _mcp(a: str | None) -> JsonDict:
        args: JsonDict = {
            "resume": resume.model_dump(mode="json"),
            "job": job.model_dump(mode="json"),
        }
        if a is not None:
            args["alias_file"] = a
        return asyncio.run(_await_json(HANDLERS["resume_suggest_terminology"](args)))

    def _api(a: str | None) -> JsonDict:
        body: JsonDict = {
            "resume": resume.model_dump(mode="json"),
            "job": job.model_dump(mode="json"),
        }
        if a is not None:
            body["alias_file"] = a
        response = _CLIENT.post("/suggest-terminology", json=body)
        assert response.status_code == 200, response.text
        return cast(JsonDict, response.json())

    # With the alias file the fabricated ``Zephyrflow`` keyword surfaces as a
    # mirror suggestion on every surface ...
    assert "Zephyrflow" in _keywords(_direct(alias))
    for payload in (_cli(alias), _mcp(alias), _api(alias)):
        assert "Zephyrflow" in _keywords(payload)

    # ... and without it no surface emits that suggestion (seed-only parity).
    assert "Zephyrflow" not in _keywords(_direct(None))
    for payload in (_cli(None), _mcp(None), _api(None)):
        assert "Zephyrflow" not in _keywords(payload)


def test_alias_file_env_does_not_leak_between_calls(tmp_path: Path) -> None:
    resume, job = _resume(), _job()
    alias = str(_alias_json(tmp_path))

    assert PROJECT_ALIAS_ENV_VAR not in os.environ
    with_alias = _ats_percentage(_direct_ats(resume, job, alias))
    # After a scoped alias call the env must be restored (was unset).
    assert PROJECT_ALIAS_ENV_VAR not in os.environ
    # The very next seed-only call is unaffected by the prior alias call.
    seed_only = _ats_percentage(_direct_ats(resume, job, None))
    assert seed_only < with_alias
    assert PROJECT_ALIAS_ENV_VAR not in os.environ


def test_alias_file_restores_prior_env_value(tmp_path: Path) -> None:
    resume, job = _resume(), _job()
    alias = str(_alias_json(tmp_path))
    sentinel = str(tmp_path / "preexisting.json")
    os.environ[PROJECT_ALIAS_ENV_VAR] = sentinel
    try:
        _direct_ats(resume, job, alias)
        # A scoped call restores the caller's pre-existing value, not unset.
        assert os.environ[PROJECT_ALIAS_ENV_VAR] == sentinel
    finally:
        os.environ.pop(PROJECT_ALIAS_ENV_VAR, None)
