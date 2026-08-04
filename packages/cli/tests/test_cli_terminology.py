"""CLI tests for the terminology-alignment commands (RIT-I-0010).

``suggest-terminology`` lists alias-hit mirror suggestions; ``align-terminology``
applies exactly one accepted suggestion at one location and reports the
before/after delta. Both are thin adapters over the facade; the k8s/Kubernetes
seed alias drives a deterministic suggestion.
"""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_cli.app import app
from resume_kit_schemas import JobDescription, ResumeDocument, TerminologyAlignment
from resume_kit_schemas.job import Requirement
from resume_kit_schemas.resume import (
    AdditionalInfo,
    Experience,
    PersonalInfo,
)
from typer.testing import CliRunner

runner = CliRunner()


def _resume_doc() -> ResumeDocument:
    return ResumeDocument(
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


def _job_doc() -> JobDescription:
    return JobDescription(
        title="Platform Engineer",
        summary="Kubernetes platform role.",
        requirements=[Requirement(text="k8s", keywords=["k8s"])],
        keywords=["k8s"],
    )


def _write(path: Path, model: object) -> str:
    path.write_text(model.model_dump_json(), encoding="utf-8")  # type: ignore[attr-defined]
    return str(path)


def test_suggest_terminology_lists_alias_hit(tmp_path: Path) -> None:
    resume = _write(tmp_path / "r.json", _resume_doc())
    job = _write(tmp_path / "j.json", _job_doc())
    result = runner.invoke(
        app, ["suggest-terminology", "--resume", resume, "--job", job]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["errors"] == []
    assert isinstance(payload["data"], list)
    assert any(s["jd_keyword"] == "k8s" for s in payload["data"])


def test_align_terminology_applies_one_suggestion(tmp_path: Path) -> None:
    resume_doc = _resume_doc()
    job_doc = _job_doc()
    resume = _write(tmp_path / "r.json", resume_doc)
    job = _write(tmp_path / "j.json", job_doc)
    suggestion = TerminologyAlignment(
        jd_keyword="k8s",
        current_wording="kubernetes",
        locations=["workExperience[0].description[0]"],
        canonical="kubernet",
    )
    sug_path = _write(tmp_path / "s.json", suggestion)

    result = runner.invoke(
        app,
        [
            "align-terminology",
            "--suggestion",
            sug_path,
            "--location",
            "workExperience[0].description[0]",
            "--resume",
            resume,
            "--job",
            job,
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["errors"] == []
    data = payload["data"]
    assert data["swap_applied"] is True
    assert data["freedom"] == 4
    assert (
        data["resume"]["workExperience"][0]["description"][0]
        == "Ran workloads on k8s across three regions."
    )
