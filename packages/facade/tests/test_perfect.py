from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import resume_kit_facade.perfect as perfect_module
from resume_kit_facade.perfect import build_perfect
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    save_config,
    set_active,
    set_version,
    working_dir,
)
from resume_kit_schemas import (
    CandidateEvidence,
    EvidenceKind,
    JobDescription,
    ResumeDocument,
)
from resume_kit_schemas.shape import ContentFate


def _resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo={"name": "Jane", "email": "jane@example.com"},
        summary="Results-driven proven Python FastAPI engineer",
        workExperience=[
            {
                "title": "Staff Engineer",
                "company": "Acme",
                "years": "2022 - Present",
                "description": [
                    "Reduced Python API latency 35% with FastAPI and Postgres.",
                    "Tools: email, spreadsheets, calendar.",
                    "Led platform architecture roadmap with product stakeholders.",
                ],
            },
            {
                "title": "Intern",
                "company": "OldCo",
                "years": "2015 - 2016",
                "description": ["Maintained internal spreadsheet reports."],
            },
        ],
        additional={
            "technicalSkills": ["Python", "FastAPI", "Teamwork", "Email"]
        },
    )


def _job() -> JobDescription:
    return JobDescription(
        title="Python API Engineer",
        keywords=["Python", "FastAPI", "Postgres"],
        raw_text="Python FastAPI Postgres APIs",
    )


def _evidence() -> list[CandidateEvidence]:
    return [
        CandidateEvidence(
            id="summary",
            kind=EvidenceKind.USER_STATEMENT,
            content="Python FastAPI engineer",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="latency",
            kind=EvidenceKind.WORK_HISTORY,
            content="Reduced Python API latency 35% with FastAPI and Postgres.",
            tags=["Acme"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="tools",
            kind=EvidenceKind.WORK_HISTORY,
            content="Tools: email, spreadsheets, calendar.",
            tags=["Acme"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="roadmap",
            kind=EvidenceKind.WORK_HISTORY,
            content="Led platform architecture roadmap with product stakeholders.",
            tags=["Acme"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="oldco",
            kind=EvidenceKind.WORK_HISTORY,
            content="Maintained internal spreadsheet reports.",
            tags=["OldCo"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="python",
            kind=EvidenceKind.SKILL,
            content="Python",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="fastapi",
            kind=EvidenceKind.SKILL,
            content="FastAPI",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="teamwork",
            kind=EvidenceKind.SKILL,
            content="Teamwork",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="email",
            kind=EvidenceKind.SKILL,
            content="Email",
            user_confirmed=True,
        ),
    ]


def _setup_project(root: Path) -> dict[str, bytes]:
    init_project(root)
    base = working_dir(root)
    resume_payload = _resume().model_dump(mode="json")
    for suffix in ("original", "base", "structure", "standard"):
        (base / "resumes" / f"jane-{suffix}.json").write_text(
            json.dumps(resume_payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    (base / "jobs" / "python-api.json").write_text(
        _job().model_dump_json(),
        encoding="utf-8",
    )
    (base / "evidence.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in _evidence()]),
        encoding="utf-8",
    )
    set_active(root, resume="resumes/jane-original.json", job="jobs/python-api.json")
    set_version(
        root,
        base="resumes/jane-base.json",
        base_derived_from="resumes/jane-original.json",
    )
    set_version(
        root,
        structure="resumes/jane-structure.json",
        structure_derived_from="resumes/jane-base.json",
    )
    set_version(
        root,
        standard="resumes/jane-standard.json",
        standard_derived_from="resumes/jane-structure.json",
    )
    config = load_config(root)
    config.active_evidence = "evidence.json"
    config.shape_policy = {
        "informational_budgets": {
            "max_skills": 2,
            "max_experience_entries": 1,
            "max_bullets_per_role": 2,
            "max_summary_words": 3,
        }
    }
    save_config(root, config)
    return _lineage_snapshot(root)


def _lineage_snapshot(root: Path) -> dict[str, bytes]:
    base = working_dir(root)
    return {
        rel: (base / rel).read_bytes()
        for rel in (
            "resumes/jane-original.json",
            "resumes/jane-base.json",
            "resumes/jane-structure.json",
            "resumes/jane-standard.json",
        )
    }


def _assert_lineage_unchanged(root: Path, snapshot: dict[str, bytes]) -> None:
    base = working_dir(root)
    for rel, expected in snapshot.items():
        assert (base / rel).read_bytes() == expected


def test_build_perfect_auto_fit_commits_final_and_ledger(
    tmp_path: Path,
) -> None:
    snapshot = _setup_project(tmp_path)

    result = build_perfect(tmp_path, auto_fit=True)

    assert result.committed
    assert result.final_path == "resumes/jane-python-api-final.json"
    assert result.ledger_ok
    assert result.applied
    assert {
        ContentFate.DROPPED_BY_RANKED_BUDGET,
        ContentFate.COMPRESSED,
    } <= {entry.fate for entry in result.ledger.entries}
    final = ResumeDocument.model_validate_json(
        (working_dir(tmp_path) / result.final_path).read_text(encoding="utf-8")
    )
    working = ResumeDocument.model_validate_json(
        (
            working_dir(tmp_path) / "working" / "jane-standard.tailored.json"
        ).read_text(encoding="utf-8")
    )
    assert final == working
    assert len(final.additional.technicalSkills) <= 2
    assert len(final.workExperience[0].description) <= 2
    assert final.summary == "Python FastAPI engineer"
    config = load_config(tmp_path)
    assert config.final_resume == result.final_path
    assert config.final_derived_from == "resumes/jane-standard.json"
    assert config.final_job_id == "python-api"
    _assert_lineage_unchanged(tmp_path, snapshot)


def test_build_perfect_without_decisions_defers_without_writes(
    tmp_path: Path,
) -> None:
    snapshot = _setup_project(tmp_path)

    result = build_perfect(tmp_path)

    assert not result.committed
    assert result.final_path is None
    assert result.violations
    assert result.candidates
    assert not (working_dir(tmp_path) / "resumes" / "jane-python-api-final.json").exists()
    assert not (working_dir(tmp_path) / "working" / "jane-standard.tailored.json").exists()
    assert load_config(tmp_path).final_resume is None
    _assert_lineage_unchanged(tmp_path, snapshot)


def test_build_perfect_reuses_edit_session_commit(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _setup_project(tmp_path)
    calls = {"open": 0, "commit": 0}
    real_open = perfect_module.open_session
    real_commit = perfect_module.commit_session

    def spy_open(*args: Any, **kwargs: Any) -> Any:
        calls["open"] += 1
        return real_open(*args, **kwargs)

    def spy_commit(*args: Any, **kwargs: Any) -> Any:
        calls["commit"] += 1
        return real_commit(*args, **kwargs)

    monkeypatch.setattr(perfect_module, "open_session", spy_open)
    monkeypatch.setattr(perfect_module, "commit_session", spy_commit)

    result = build_perfect(tmp_path, auto_fit=True)

    assert result.committed
    assert calls == {"open": 1, "commit": 1}
    session_file = working_dir(tmp_path) / "working" / "edit-session.json"
    working_file = working_dir(tmp_path) / "working" / "jane-standard.tailored.json"
    assert session_file.exists()
    assert working_file.exists()


def test_build_perfect_master_lineage_unchanged_after_interactive_and_auto(
    tmp_path: Path,
) -> None:
    snapshot = _setup_project(tmp_path)

    interactive = build_perfect(tmp_path)
    assert not interactive.committed
    _assert_lineage_unchanged(tmp_path, snapshot)

    auto = build_perfect(tmp_path, auto_fit=True)
    assert auto.committed
    _assert_lineage_unchanged(tmp_path, snapshot)


def test_build_perfect_defers_whole_role_removal(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)

    result = build_perfect(tmp_path, auto_fit=True)

    assert any(path.startswith("workExperience[") for path in result.deferred)
    assert "workExperience[1]" in result.deferred
