"""CLI tests for the check-structure command (RIT-T-0077)."""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_cli.app import app
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.resume import (
    AdditionalInfo,
    Experience,
    PersonalInfo,
)
from typer.testing import CliRunner

runner = CliRunner()


def _complete_resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Sam Rivera",
            email="sam@example.com",
            phone="555-0100",
        ),
        summary="Platform engineer.",
        workExperience=[
            Experience(
                id=1,
                title="Platform Engineer",
                company="Northwind Ltd",
                years="2019-2024",
                description=["Ran production workloads across three regions."],
            )
        ],
        education=[],
        additional=AdditionalInfo(technicalSkills=["Python", "Kubernetes"]),
    )


def _sparse_resume() -> ResumeDocument:
    return ResumeDocument(personalInfo=PersonalInfo(name="Sam Rivera"))


def _write(path: Path, model: ResumeDocument) -> str:
    path.write_text(model.model_dump_json(), encoding="utf-8")
    return str(path)


def test_check_ats_structure_reports_section_completeness(tmp_path: Path) -> None:
    resume = _write(tmp_path / "r.json", _complete_resume())
    result = runner.invoke(app, ["check-structure", "--resume", resume])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["errors"] == []
    data = payload["data"]
    assert data["section_completeness"] == 75.0
    assert isinstance(data["recommendations"], list)
    # Resume-only report: no keyword/coverage/composite fields.
    assert "keyword_match" not in data
    assert "skills_coverage" not in data
    assert "overall_score" not in data


def test_check_ats_structure_flags_missing_sections(tmp_path: Path) -> None:
    resume = _write(tmp_path / "r.json", _sparse_resume())
    result = runner.invoke(app, ["check-structure", "--resume", resume])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)["data"]
    assert data["section_completeness"] == 0.0
    assert any("email" in tip for tip in data["recommendations"])
