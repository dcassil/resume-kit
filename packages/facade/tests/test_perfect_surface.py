from __future__ import annotations

import asyncio
import json
from pathlib import Path

from resume_kit_cli.app import app
from resume_kit_facade.capabilities import build_perfect_capability
from resume_kit_facade.models import BuildPerfectRequest, CapabilityOptions
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    save_config,
    set_active,
    set_version,
    working_dir,
)
from resume_kit_schemas import (
    AdditionalInfo,
    CandidateEvidence,
    EvidenceKind,
    Experience,
    JobDescription,
    PersonalInfo,
    ResumeDocument,
)
from typer.testing import CliRunner


def _resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Jane",
            email="jane@example.com",
        ),
        summary="Results-driven proven Python FastAPI engineer",
        workExperience=[
            Experience(
                title="Staff Engineer",
                company="Acme",
                years="2022 - Present",
                description=[
                    "Reduced Python API latency 35% with FastAPI and Postgres.",
                    "Tools: email, spreadsheets, calendar.",
                    "Led platform architecture roadmap with product stakeholders.",
                ],
            ),
            Experience(
                title="Intern",
                company="OldCo",
                years="2015 - 2016",
                description=["Maintained internal spreadsheet reports."],
            ),
        ],
        additional=AdditionalInfo(
            technicalSkills=["Python", "FastAPI", "Teamwork", "Email"]
        ),
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


def _setup_project(root: Path) -> None:
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


def _data_fields(payload: dict[str, object]) -> tuple[object, object]:
    data = payload["data"]
    assert isinstance(data, dict)
    return data["final_path"], data["violations"]


def test_build_perfect_facade_and_cli_fit_parity(tmp_path: Path) -> None:
    facade_root = tmp_path / "facade"
    cli_root = tmp_path / "cli"
    _setup_project(facade_root)
    _setup_project(cli_root)

    facade_response = asyncio.run(
        build_perfect_capability(
            BuildPerfectRequest(root=facade_root, auto_fit=True),
            CapabilityOptions(),
        )
    )
    cli_response = CliRunner().invoke(
        app,
        ["fit", "--root", str(cli_root), "--auto-fit"],
    )

    assert cli_response.exit_code == 0, cli_response.stdout
    cli_payload = json.loads(cli_response.stdout)

    assert facade_response.ok
    assert _data_fields(facade_response.model_dump(mode="json")) == _data_fields(
        cli_payload
    )
