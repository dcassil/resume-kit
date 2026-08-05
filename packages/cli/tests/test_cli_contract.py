"""Contract tests: command registration, output formats, and success codes."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from resume_kit_cli.app import app
from resume_kit_feedback import Candidate, FeatureContext
from resume_kit_schemas import (
    CandidateEvidence,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    JobDescription,
    ResumeDocument,
)
from typer.testing import CliRunner

runner = CliRunner()


def _write(path: Path, model: ResumeDocument | JobDescription) -> str:
    path.write_text(model.model_dump_json(), encoding="utf-8")
    return str(path)


def _resume(path: Path) -> str:
    return _write(path, ResumeDocument())


def _job(path: Path) -> str:
    return _write(path, JobDescription(raw_text="Python engineer. Requirements: Python."))


def _resumes(path: Path) -> str:
    path.write_text(json.dumps([ResumeDocument().model_dump(mode="json")]), encoding="utf-8")
    return str(path)


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    expected = [
        "extract",
        "extract-text",
        "extract-job",
        "check-ats",
        "check-ats-structure",
        "match",
        "select",
        "compare",
        "identify-gaps",
        "suggest-terminology",
        "align-terminology",
        "align",
        "validate-truth",
        "validate-faithfulness",
        "build-evidence",
        "add-evidence",
        "record-edit-feedback",
        "rank-edit-candidates",
        "refresh-preferences",
        "review-edits",
        "export",
        "init",
        "set-active",
    ]
    for name in expected:
        assert name in result.stdout


def test_review_edits_help_lists_lifecycle_commands() -> None:
    result = runner.invoke(app, ["review-edits", "--help"])
    assert result.exit_code == 0
    for name in ["open", "prompt", "decide", "commit", "status", "reconcile"]:
        assert name in result.stdout


def test_export_pdf_writes_file(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    out = tmp_path / "resume.pdf"
    result = runner.invoke(
        app, ["export", "--resume", resume, "--format", "pdf", "--out", str(out)]
    )
    assert result.exit_code == 0, result.stdout
    assert out.read_bytes().startswith(b"%PDF-")


def test_export_docx_writes_file(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    out = tmp_path / "resume.docx"
    result = runner.invoke(
        app, ["export", "--resume", resume, "--format", "docx", "--out", str(out)]
    )
    assert result.exit_code == 0, result.stdout
    assert out.read_bytes().startswith(b"PK")


def test_export_base64_stdout_matches_file(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    out = tmp_path / "resume.pdf"
    file_res = runner.invoke(
        app, ["export", "--resume", resume, "--format", "pdf", "--out", str(out)]
    )
    assert file_res.exit_code == 0, file_res.stdout
    stdout_res = runner.invoke(app, ["export", "--resume", resume, "--format", "pdf"])
    assert stdout_res.exit_code == 0, stdout_res.stdout
    decoded = base64.b64decode(stdout_res.stdout.strip())
    assert decoded == out.read_bytes()
    assert decoded.startswith(b"%PDF-")


def test_extract_all_output_formats(tmp_path: Path) -> None:
    src = tmp_path / "resume.txt"
    src.write_text("Jane Doe\nSoftware Engineer\n", encoding="utf-8")
    for fmt in ("json", "text", "md"):
        result = runner.invoke(app, ["extract", str(src), "--no-llm", "--output", fmt])
        assert result.exit_code == 0, result.stdout
        assert result.stdout.strip()


def test_extract_job_all_formats(tmp_path: Path) -> None:
    src = tmp_path / "job.txt"
    src.write_text("Senior Python Engineer. Requirements: Python, SQL.", encoding="utf-8")
    for fmt in ("json", "text", "md"):
        result = runner.invoke(app, ["extract-job", str(src), "--no-llm", "--output", fmt])
        assert result.exit_code == 0, result.stdout


def test_deterministic_commands_succeed(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    job = _job(tmp_path / "j.json")
    resumes = _resumes(tmp_path / "rs.json")
    cases = [
        ["check-ats", "--resume", resume, "--job", job],
        ["match", "--resume", resume, "--job", job],
        ["select", "--resumes", resumes, "--job", job],
        ["compare", "--base", resume, "--candidate", resume, "--job", job],
        ["identify-gaps", "--job", job, "--tailored", resume, "--master", resume],
        ["suggest-terminology", "--resume", resume, "--job", job],
        ["validate-truth", "--resume", resume],
        ["build-evidence", "--resume", resume],
    ]
    for args in cases:
        for fmt in ("json", "text", "md"):
            result = runner.invoke(app, [*args, "--output", fmt])
            assert result.exit_code == 0, (args, fmt, result.stdout)


def _feedback() -> EditFeedback:
    return EditFeedback(
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


def test_feedback_and_evidence_commands_succeed(tmp_path: Path) -> None:
    feedback_path = tmp_path / "feedback.json"
    feedback_path.write_text(_feedback().model_dump_json(), encoding="utf-8")
    base = tmp_path / "resume-kit"

    record = runner.invoke(
        app,
        [
            "record-edit-feedback",
            "--feedback",
            str(feedback_path),
            "--base-path",
            str(base),
        ],
    )
    assert record.exit_code == 0, record.stdout
    assert (base / "learning" / "edit-feedback.jsonl").is_file()

    refresh = runner.invoke(
        app,
        [
            "refresh-preferences",
            "--now",
            "2026-08-05T00:00:00+00:00",
            "--base-path",
            str(base),
        ],
    )
    assert refresh.exit_code == 0, refresh.stdout

    candidate_path = tmp_path / "candidates.json"
    candidate_path.write_text(
        json.dumps(
            [
                Candidate(
                    candidate_id="c1",
                    section="skill",
                    proposed_text="Docker",
                ).model_dump(mode="json")
            ]
        ),
        encoding="utf-8",
    )
    context_path = tmp_path / "context.json"
    context = FeatureContext(
        resume=ResumeDocument(summary="Python engineer."),
        job=JobDescription(raw_text="Docker"),
        evidence=[
            CandidateEvidence(
                id="ev-docker",
                kind=EvidenceKind.SKILL,
                content="Docker",
                user_confirmed=True,
            )
        ],
    )
    context_path.write_text(context.model_dump_json(), encoding="utf-8")
    rank = runner.invoke(
        app,
        [
            "rank-edit-candidates",
            "--candidates",
            str(candidate_path),
            "--context",
            str(context_path),
        ],
    )
    assert rank.exit_code == 0, rank.stdout

    add = runner.invoke(
        app,
        [
            "add-evidence",
            "--confirmed",
            "--root",
            str(tmp_path),
            "--content",
            "Confirmed Docker work",
            "--kind",
            "user_statement",
            "--tag",
            "Docker",
            "--update-active",
        ],
    )
    assert add.exit_code == 0, add.stdout
    evidence_file = tmp_path / "resume-kit" / "working" / "user-confirmed-evidence.json"
    assert evidence_file.is_file()


def test_build_evidence_approved_claims_and_validate_round_trip(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    approved = tmp_path / "approved.json"
    approved.write_text(json.dumps(["Confirmed Docker work"]), encoding="utf-8")
    built = runner.invoke(
        app,
        [
            "build-evidence",
            "--resume",
            resume,
            "--approved-claims",
            str(approved),
        ],
    )
    assert built.exit_code == 0, built.stdout
    envelope = tmp_path / "built-envelope.json"
    envelope.write_text(built.stdout, encoding="utf-8")
    validate = runner.invoke(
        app,
        ["validate-truth", "--resume", resume, "--evidence", str(envelope)],
    )
    assert validate.exit_code == 0, validate.stdout


def test_json_output_is_parseable(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    job = _job(tmp_path / "j.json")
    result = runner.invoke(app, ["check-ats", "--resume", resume, "--job", job])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["errors"] == []
    assert payload["data"] is not None


def test_align_no_llm_succeeds(tmp_path: Path) -> None:
    resume = _resume(tmp_path / "r.json")
    job = _job(tmp_path / "j.json")
    result = runner.invoke(app, ["align", "--resume", resume, "--job", job, "--no-llm"])
    assert result.exit_code == 0, result.stdout


def test_init_then_set_active_records_source(tmp_path: Path) -> None:
    init_res = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert init_res.exit_code == 0, init_res.stdout
    assert (tmp_path / "resume-kit" / "config.json").is_file()

    set_res = runner.invoke(
        app,
        [
            "set-active",
            "--root",
            str(tmp_path),
            "--resume",
            "resumes/x-original.json",
            "--source",
            "/path/x.docx",
        ],
    )
    assert set_res.exit_code == 0, set_res.stdout
    on_disk = json.loads((tmp_path / "resume-kit" / "config.json").read_text(encoding="utf-8"))
    assert on_disk["active_resume"] == "resumes/x-original.json"
    assert on_disk["active_resume_source"] == "/path/x.docx"


def test_init_is_idempotent_via_cli(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--root", str(tmp_path)])
    config = tmp_path / "resume-kit" / "config.json"
    config.write_text(json.dumps({"active_job": "jobs/j.json"}), encoding="utf-8")
    second = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert second.exit_code == 0, second.stdout
    on_disk = json.loads(config.read_text(encoding="utf-8"))
    assert on_disk["active_job"] == "jobs/j.json"
