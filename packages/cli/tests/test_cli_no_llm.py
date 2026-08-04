"""No-LLM deterministic-path tests: no provider, no network, exit 0."""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_cli.app import app
from resume_kit_schemas import JobDescription, ResumeDocument
from typer.testing import CliRunner

runner = CliRunner()


def _resume(path: Path) -> str:
    path.write_text(ResumeDocument().model_dump_json(), encoding="utf-8")
    return str(path)


def _job(path: Path) -> str:
    job = JobDescription(raw_text="Backend role. Requirements: Python, SQL, AWS.")
    path.write_text(job.model_dump_json(), encoding="utf-8")
    return str(path)


def test_extract_no_llm(tmp_path: Path) -> None:
    src = tmp_path / "resume.txt"
    src.write_text("Ada Lovelace\nEngineer\nSkills: Python\n", encoding="utf-8")
    result = runner.invoke(app, ["extract", str(src), "--no-llm"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["errors"] == []


def test_extract_job_no_llm(tmp_path: Path) -> None:
    src = tmp_path / "job.txt"
    src.write_text("Data Engineer. Requirements: Spark.", encoding="utf-8")
    result = runner.invoke(app, ["extract-job", str(src), "--no-llm"])
    assert result.exit_code == 0, result.stdout


def test_extract_from_stdin(tmp_path: Path) -> None:
    result = runner.invoke(app, ["extract", "-", "--no-llm"], input="Grace Hopper\nEng\n")
    assert result.exit_code == 0, result.stdout


def test_ats_and_match_and_select(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    job = _job(tmp_path / "j.json")
    resumes = tmp_path / "rs.json"
    resumes.write_text(
        json.dumps([ResumeDocument().model_dump(mode="json")]), encoding="utf-8"
    )
    for args in (
        ["check-ats", "--resume", resume, "--job", job],
        ["match", "--resume", resume, "--job", job],
        ["select", "--resumes", str(resumes), "--job", job],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.stdout)


def test_compare_gaps_truth_evidence(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    job = _job(tmp_path / "j.json")
    for args in (
        ["compare", "--base", resume, "--candidate", resume, "--job", job],
        ["identify-gaps", "--job", job, "--tailored", resume, "--master", resume],
        ["validate-truth", "--resume", resume],
        ["build-evidence", "--resume", resume],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.stdout)
