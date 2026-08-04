"""Provider-not-configured tests for LLM-requiring commands."""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_cli.app import app
from resume_kit_schemas import JobDescription, ResumeDocument
from typer.testing import CliRunner

# ExitCode.PROVIDER_NOT_CONFIGURED from resume_kit_core.interface.
_PROVIDER_NOT_CONFIGURED_EXIT = 3

runner = CliRunner()


def _resume(path: Path) -> str:
    path.write_text(ResumeDocument().model_dump_json(), encoding="utf-8")
    return str(path)


def _job(path: Path) -> str:
    path.write_text(JobDescription(raw_text="Role").model_dump_json(), encoding="utf-8")
    return str(path)


def _assert_provider_error(stdout: str) -> None:
    payload = json.loads(stdout)
    assert payload["data"] is None
    codes = [error["code"] for error in payload["errors"]]
    assert any("provider_not_configured" in str(code).lower() for code in codes), codes


def test_extract_without_provider(tmp_path: Path) -> None:
    src = tmp_path / "resume.txt"
    src.write_text("Someone\n", encoding="utf-8")
    result = runner.invoke(app, ["extract", str(src)])
    assert result.exit_code == _PROVIDER_NOT_CONFIGURED_EXIT, result.stdout
    _assert_provider_error(result.stdout)


def test_extract_job_without_provider(tmp_path: Path) -> None:
    src = tmp_path / "job.txt"
    src.write_text("Some job description text", encoding="utf-8")
    result = runner.invoke(app, ["extract-job", str(src)])
    assert result.exit_code == _PROVIDER_NOT_CONFIGURED_EXIT, result.stdout
    _assert_provider_error(result.stdout)


def test_align_without_provider(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    job = _job(tmp_path / "j.json")
    result = runner.invoke(app, ["align", "--resume", resume, "--job", job])
    assert result.exit_code == _PROVIDER_NOT_CONFIGURED_EXIT, result.stdout
    _assert_provider_error(result.stdout)


def test_align_no_traceback_in_output(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    job = _job(tmp_path / "j.json")
    result = runner.invoke(app, ["align", "--resume", resume, "--job", job])
    assert "Traceback" not in result.stdout
    assert result.exception is None or isinstance(result.exception, SystemExit)
