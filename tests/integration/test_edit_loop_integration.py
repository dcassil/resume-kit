"""End-to-end integration for the RIT-I-0015 edit loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from resume_kit_cli.app import app
from resume_kit_core.interface import ExitCode
from resume_kit_facade.project_config import init_project, load_config, save_config, working_dir
from resume_kit_schemas import (
    AdditionalInfo,
    ChangeProposal,
    ClaimProvenance,
    EditFeedback,
    Experience,
    JobDescription,
    PersonalInfo,
    ProvenanceStatus,
    ResumeDocument,
)
from typer.testing import CliRunner

_RUNNER = CliRunner()
_NOW = "2026-08-05T00:00:00+00:00"
_TERMINOLOGY_REASON = (
    "Mirror the employer's exact terminology: the resume already demonstrates "
    "this via an equivalent term, so the surface wording is aligned to the job "
    "description without altering the underlying claim."
)


def _run_cli(args: list[str], *, expected_exit: int = 0) -> dict[str, Any]:
    result = _RUNNER.invoke(app, [*args, "--output", "json"])
    assert result.exit_code == expected_exit, result.stdout
    return cast(dict[str, Any], json.loads(result.stdout))


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(name="Jordan Lee", email="jordan@example.com"),
        summary="Built things for production systems.",
        workExperience=[
            Experience(
                title="Senior Backend Engineer",
                company="Acme Labs",
                years="2021 - Present",
                description=[
                    "Improved fixes for React apps.",
                    "Added improvements for mobile React.",
                    "Improved quality for mobile React.",
                ],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "FastAPI", "Docker"]),
    )


def _job() -> JobDescription:
    return JobDescription(
        title="Senior Backend Engineer",
        company="Contoso",
        raw_text="FastAPI React Chrome SSR compatibility OpenTelemetry",
        keywords=["FastAPI", "React", "Chrome", "SSR", "compatibility", "OpenTelemetry"],
    )


def _setup_project(root: Path) -> tuple[Path, Path, Path]:
    init_project(root)
    base = working_dir(root)
    resume_path = base / "resumes" / "jordan-original.json"
    job_path = base / "jobs" / "job.json"
    alias_path = base / "learning" / "aliases.json"
    _write_json(resume_path, _resume().model_dump(mode="json"))
    _write_json(job_path, _job().model_dump(mode="json"))
    config = load_config(root)
    config.active_resume = "resumes/jordan-original.json"
    config.active_job = "jobs/job.json"
    config.alias_file = "learning/aliases.json"
    save_config(root, config)
    return resume_path, job_path, alias_path


def _loop_changes() -> list[ChangeProposal]:
    return [
        ChangeProposal(
            path="summary",
            action="replace",
            original="Built things for production systems.",
            value="Built FastAPI services for production systems.",
            reason="Surface a truthful framework already present in the resume.",
        ),
        ChangeProposal(
            path="workExperience[0].description[0]",
            action="replace",
            original="Improved fixes for React apps.",
            value="Improved fixes for React apps.",
            reason="Offer a vague draft for human refinement.",
        ),
        ChangeProposal(
            path="workExperience[0].description[1]",
            action="replace",
            original="Added improvements for mobile React.",
            value="Added improvements for mobile React.",
            reason="Offer a vague draft for human refinement.",
        ),
        ChangeProposal(
            path="workExperience[0].description[2]",
            action="replace",
            original="Improved quality for mobile React.",
            value="Improved quality for mobile React.",
            reason="Offer a vague draft for human refinement.",
        ),
        ChangeProposal(
            path="additional.technicalSkills[2]",
            action="replace",
            original="Docker",
            value="Synergy",
            reason="A bad suggestion the user rejects.",
        ),
    ]


def _alias_change() -> ChangeProposal:
    return ChangeProposal(
        path="summary",
        action="replace",
        original="Built zorbulator systems.",
        value="Built quibblewidget systems.",
        reason=_TERMINOLOGY_REASON,
    )


def _open_session(
    root: Path,
    changes_path: Path,
    *,
    mode: str,
    claim_provenance_path: Path | None = None,
) -> dict[str, Any]:
    args = [
        "review-edits",
        "open",
        "--mode",
        mode,
        "--changes",
        str(changes_path),
        "--root",
        str(root),
    ]
    if claim_provenance_path is not None:
        args.extend(["--claim-provenance", str(claim_provenance_path)])
    return _run_cli(args)


def _feedback_records(root: Path) -> list[EditFeedback]:
    path = working_dir(root) / "learning" / "edit-feedback.jsonl"
    return [
        EditFeedback.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _claim_by_path(report: dict[str, Any], field_path: str) -> dict[str, Any]:
    for claim in report["data"]["claims"]:
        if claim["field_path"] == field_path:
            return cast(dict[str, Any], claim)
    raise AssertionError(f"Missing claim for {field_path}")


def test_unlogged_and_truth_failing_changes_fail_with_machine_readable_errors(
    tmp_path: Path,
) -> None:
    unlogged_root = tmp_path / "unlogged"
    _setup_project(unlogged_root)
    unlogged_changes = _write_json(
        unlogged_root / "changes.json",
        [_loop_changes()[0].model_dump(mode="json")],
    )
    _open_session(unlogged_root, unlogged_changes, mode="interactive")

    unlogged = _run_cli(
        ["review-edits", "commit", "--root", str(unlogged_root)],
        expected_exit=int(ExitCode.INVALID_INPUT),
    )

    assert unlogged["errors"][0]["code"] == "validation_failed"
    assert unlogged["errors"][0]["details"]["gate_code"] == "unlogged_decision"
    assert unlogged["errors"][0]["details"]["paths"] == ["summary"]
    assert not (working_dir(unlogged_root) / "working" / "jordan.tailored.json").exists()

    truth_root = tmp_path / "truth-failing"
    _setup_project(truth_root)
    truth_change = ChangeProposal(
        path="summary",
        action="replace",
        original="Built things for production systems.",
        value="Built blockchain consensus engines.",
        reason="Fabricated claim used to prove the hard truth gate.",
    )
    truth_changes = _write_json(
        truth_root / "changes.json",
        [truth_change.model_dump(mode="json")],
    )
    provenance = _write_json(
        truth_root / "claim-provenance.json",
        [
            ClaimProvenance(
                claim="Built blockchain consensus engines.",
                field_path="summary",
                status=ProvenanceStatus.CONTRADICTED,
            ).model_dump(mode="json")
        ],
    )
    _open_session(
        truth_root,
        truth_changes,
        mode="interactive",
        claim_provenance_path=provenance,
    )
    _run_cli(
        [
            "review-edits",
            "decide",
            "--path",
            "summary",
            "--action",
            "approve",
            "--root",
            str(truth_root),
        ]
    )

    contradicted = _run_cli(
        ["review-edits", "commit", "--root", str(truth_root)],
        expected_exit=int(ExitCode.INVALID_INPUT),
    )

    assert contradicted["errors"][0]["code"] == "validation_failed"
    assert contradicted["errors"][0]["details"]["gate_code"] == "truth_contradicted"
    assert contradicted["errors"][0]["details"]["paths"] == ["summary"]


def test_reviewed_modes_apply_only_logged_changes_and_feed_learning_loop(
    tmp_path: Path,
) -> None:
    tailored_paths: list[Path] = []

    for mode in ("interactive", "review_at_end"):
        root = tmp_path / mode
        _setup_project(root)
        changes = _write_json(
            root / "changes.json",
            [change.model_dump(mode="json") for change in _loop_changes()],
        )
        _open_session(root, changes, mode=mode)

        _run_cli(
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
        )
        edits = [
            ("workExperience[0].description[0]", "Added Chrome coverage for React apps."),
            ("workExperience[0].description[1]", "Added SSR handling for mobile React."),
            (
                "workExperience[0].description[2]",
                "Improved compatibility checks for mobile React.",
            ),
        ]
        for path, edited_content in edits:
            _run_cli(
                [
                    "review-edits",
                    "decide",
                    "--path",
                    path,
                    "--action",
                    "edit",
                    "--edited-content",
                    edited_content,
                    "--reason-code",
                    "too_vague",
                    "--note",
                    "Prefer concrete browser/platform details.",
                    "--root",
                    str(root),
                ]
            )
        _run_cli(
            [
                "review-edits",
                "decide",
                "--path",
                "additional.technicalSkills[2]",
                "--action",
                "reject",
                "--reason-code",
                "not_my_voice",
                "--root",
                str(root),
            ]
        )

        committed = _run_cli(
            [
                "review-edits",
                "commit",
                "--root",
                str(root),
                "--alias-timestamp",
                _NOW,
            ]
        )
        assert committed["errors"] == []
        assert len(committed["data"]["applied"]) == 4
        tailored = working_dir(root) / "working" / "jordan.tailored.json"
        tailored_paths.append(tailored)
        written = json.loads(tailored.read_text(encoding="utf-8"))
        assert written["summary"] == "Built FastAPI services for production systems."
        assert written["workExperience"][0]["description"] == [
            "Added Chrome coverage for React apps.",
            "Added SSR handling for mobile React.",
            "Improved compatibility checks for mobile React.",
        ]
        assert written["additional"]["technicalSkills"] == ["Python", "FastAPI", "Docker"]

        feedback = _feedback_records(root)
        assert [record.outcome for record in feedback] == [
            "accepted",
            "accepted_modified",
            "accepted_modified",
            "accepted_modified",
            "rejected",
        ]
        assert feedback[1].removed_terms == ["improved", "fixes"]
        assert "chrome" in feedback[1].added_terms
        assert feedback[-1].final_text is None

        preferences = _run_cli(
            [
                "refresh-preferences",
                "--now",
                _NOW,
                "--base-path",
                str(working_dir(root)),
            ]
        )
        profile = preferences["data"]
        assert any(
            pattern.startswith("prefers specific over vague")
            for pattern in profile["disliked_patterns"]
        )
        assert any("fixes" in pattern for pattern in profile["disliked_patterns"])
        assert any(
            phrase.startswith("specific replacements") and "chrome" in phrase
            for phrase in profile["accepted_phrases"]
        )

    export_out = tmp_path / "tailored.pdf"
    export_result = _RUNNER.invoke(
        app,
        [
            "export",
            "--format",
            "pdf",
            "--resume",
            str(tailored_paths[0]),
            "--out",
            str(export_out),
        ],
    )
    assert export_result.exit_code == 0, export_result.stdout
    assert export_out.read_bytes().startswith(b"%PDF-")


def test_auto_mode_applies_only_verified_non_judgment_changes(tmp_path: Path) -> None:
    root = tmp_path / "auto"
    _setup_project(root)
    changes = [
        _loop_changes()[0],
        ChangeProposal(
            path="additional.technicalSkills",
            action="append",
            original=None,
            value="OpenTelemetry",
            reason="Judgment addition must stay deferred in auto mode.",
        ),
    ]
    changes_path = _write_json(
        root / "changes.json",
        [change.model_dump(mode="json") for change in changes],
    )
    provenance = _write_json(
        root / "claim-provenance.json",
        [
            ClaimProvenance(
                claim="Built FastAPI services for production systems.",
                field_path="summary",
                status=ProvenanceStatus.VERIFIED,
            ).model_dump(mode="json")
        ],
    )
    _open_session(root, changes_path, mode="auto", claim_provenance_path=provenance)
    status = _run_cli(["review-edits", "status", "--root", str(root)])
    assert status["data"]["decided"] == ["summary"]
    assert status["data"]["deferred"] == ["additional.technicalSkills"]

    _run_cli(["review-edits", "commit", "--root", str(root)])
    tailored = json.loads(
        (working_dir(root) / "working" / "jordan.tailored.json").read_text(encoding="utf-8")
    )
    assert tailored["summary"] == "Built FastAPI services for production systems."
    assert "OpenTelemetry" not in tailored["additional"]["technicalSkills"]


def test_confirmed_evidence_and_refutations_survive_truth_validation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "evidence"
    init_project(root)
    base_resume = ResumeDocument(summary="Built Python services.")
    base_resume_path = _write_json(
        root / "base-resume.json",
        base_resume.model_dump(mode="json"),
    )
    envelope = _RUNNER.invoke(
        app,
        ["build-evidence", "--resume", str(base_resume_path), "--output", "json"],
    )
    assert envelope.exit_code == 0, envelope.stdout
    envelope_path = root / "built-evidence-envelope.json"
    envelope_path.write_text(envelope.stdout, encoding="utf-8")

    seam = _run_cli(
        [
            "validate-truth",
            "--resume",
            str(base_resume_path),
            "--evidence",
            str(envelope_path),
        ]
    )
    assert seam["errors"] == []
    assert seam["data"]["claims"][0]["status"] == "supported"

    evidence_path = working_dir(root) / "evidence.json"
    evidence_path.write_text(envelope.stdout, encoding="utf-8")
    _run_cli(
        [
            "add-evidence",
            "--confirmed",
            "--content",
            "OpenTelemetry tracing for Python services.",
            "--kind",
            "user_statement",
            "--tag",
            "OpenTelemetry",
            "--root",
            str(root),
            "--evidence-file",
            "evidence.json",
            "--update-active",
        ]
    )
    truth_resume = ResumeDocument(summary="Built OpenTelemetry tracing for Python services.")
    truth_resume_path = _write_json(
        root / "truth-resume.json",
        truth_resume.model_dump(mode="json"),
    )
    confirmed = _run_cli(
        [
            "validate-truth",
            "--resume",
            str(truth_resume_path),
            "--evidence",
            str(evidence_path),
        ]
    )
    claim = _claim_by_path(confirmed, "summary")
    assert claim["status"] == "user-confirmed"
    assert claim["reason_code"] == "strong_evidence_overlap"
    assert claim["status"] != "contradicted"

    refuted_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    refuted_evidence.append(
        {
            "id": "ev-refute-blockchain",
            "kind": "user_statement",
            "content": "Candidate did not build blockchain consensus engines.",
            "tags": ["refuted:Built blockchain consensus engines."],
            "user_confirmed": True,
        }
    )
    refuted_path = _write_json(root / "refuted-evidence.json", refuted_evidence)
    refuted_resume = ResumeDocument(summary="Built blockchain consensus engines.")
    refuted_resume_path = _write_json(
        root / "refuted-resume.json",
        refuted_resume.model_dump(mode="json"),
    )
    refuted = _run_cli(
        [
            "validate-truth",
            "--resume",
            str(refuted_resume_path),
            "--evidence",
            str(refuted_path),
        ]
    )
    refuted_claim = _claim_by_path(refuted, "summary")
    assert refuted_claim["status"] == "contradicted"
    assert refuted_claim["reason_code"] == "refuted_by_evidence"


def test_accepted_terminology_edit_grows_project_alias_and_match_rerun_sees_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "alias-growth"
    resume_path, job_path, alias_path = _setup_project(root)
    source_resume = ResumeDocument(summary="Built zorbulator systems.")
    alias_job = JobDescription(
        title="Systems Engineer",
        raw_text="quibblewidget",
        keywords=["quibblewidget"],
    )
    _write_json(resume_path, source_resume.model_dump(mode="json"))
    _write_json(job_path, alias_job.model_dump(mode="json"))
    change_path = _write_json(
        root / "alias-change.json",
        [_alias_change().model_dump(mode="json")],
    )

    baseline = _run_cli(
        [
            "match",
            "--resume",
            str(resume_path),
            "--job",
            str(job_path),
            "--alias-file",
            str(alias_path),
        ]
    )
    assert baseline["data"]["keyword_gap"]["current_match_percentage"] == 0.0

    _open_session(root, change_path, mode="interactive")
    _run_cli(
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
    )
    committed = _run_cli(
        [
            "review-edits",
            "commit",
            "--root",
            str(root),
            "--alias-timestamp",
            _NOW,
        ]
    )
    assert committed["data"]["grown_aliases"][0]["canonical"] == "quibblewidget"
    assert committed["data"]["grown_aliases"][0]["alias"] == "zorbulator"

    rerun = _run_cli(
        [
            "match",
            "--resume",
            str(resume_path),
            "--job",
            str(job_path),
            "--alias-file",
            str(alias_path),
        ]
    )
    assert rerun["data"]["keyword_gap"]["current_match_percentage"] == 100.0
