"""End-to-end integration for the tailored -> perfect fit pass."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from resume_kit_evidence import validate_resume_truth
from resume_kit_export import check_page_budget
from resume_kit_facade.perfect import BuildPerfectResult, build_perfect
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    save_config,
    set_active,
    set_version,
    working_dir,
)
from resume_kit_policy import load_shape_policy
from resume_kit_schemas import (
    AdditionalInfo,
    CandidateEvidence,
    EvidenceKind,
    Experience,
    JobDescription,
    PersonalInfo,
    ProvenanceStatus,
    ResumeDocument,
)
from resume_kit_schemas.shape import ContentFate, ContentLedgerEntry
from resume_kit_scoring import content_ledger_ok_perfect

_BUDGETS = {
    "max_skills": 3,
    "max_experience_entries": 2,
    "max_bullets_per_role": 2,
    "max_summary_words": 5,
    "max_bullet_words": 9,
    "max_pages": 2,
}

_LINEAGE_RELS = (
    "resumes/riley-original.json",
    "resumes/riley-base.json",
    "resumes/riley-structure.json",
    "resumes/riley-standard.json",
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _over_budget_tailored_resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Riley Chen",
            email="riley@example.com",
        ),
        summary=(
            "Results-driven proven seasoned Python FastAPI Postgres platform "
            "engineer"
        ),
        workExperience=[
            Experience(
                title="Staff Platform Engineer",
                company="Acme Health",
                years="2021 - Present",
                description=[
                    (
                        "Successfully reduced Python API latency 35% with "
                        "FastAPI and Postgres."
                    ),
                    "Led FastAPI reliability roadmap with platform stakeholders.",
                    "Tools: email, spreadsheets, calendar.",
                    "Responsible for maintaining internal spreadsheets.",
                ],
            ),
            Experience(
                title="Backend Engineer",
                company="Legacy Data",
                years="2018 - 2021",
                description=[
                    "Maintained Java batch reports for legacy finance workflows.",
                ],
            ),
            Experience(
                title="IT Intern",
                company="OldCo",
                years="2015 - 2016",
                description=[
                    "Updated office inventory spreadsheets.",
                ],
            ),
        ],
        additional=AdditionalInfo(
            technicalSkills=[
                "Python",
                "FastAPI",
                "Postgres",
                "Email",
                "Teamwork",
                "Agile",
                "Python",
            ]
        ),
    )


def _job() -> JobDescription:
    return JobDescription(
        title="Python API Engineer",
        company="Contoso",
        raw_text="Python FastAPI Postgres API reliability latency platform",
        keywords=["Python", "FastAPI", "Postgres", "API", "reliability"],
    )


def _evidence() -> list[CandidateEvidence]:
    return [
        CandidateEvidence(
            id="summary",
            kind=EvidenceKind.USER_STATEMENT,
            content="Python FastAPI Postgres platform engineer",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="latency",
            kind=EvidenceKind.WORK_HISTORY,
            content="Reduced Python API latency 35% with FastAPI and Postgres.",
            tags=["Acme Health"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="roadmap",
            kind=EvidenceKind.WORK_HISTORY,
            content="Led FastAPI reliability roadmap with platform stakeholders.",
            tags=["Acme Health"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="tools",
            kind=EvidenceKind.WORK_HISTORY,
            content="Tools: email, spreadsheets, calendar.",
            tags=["Acme Health"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="spreadsheets",
            kind=EvidenceKind.WORK_HISTORY,
            content="Responsible for maintaining internal spreadsheets.",
            tags=["Acme Health"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="legacy",
            kind=EvidenceKind.WORK_HISTORY,
            content="Maintained Java batch reports for legacy finance workflows.",
            tags=["Legacy Data"],
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="oldco",
            kind=EvidenceKind.WORK_HISTORY,
            content="Updated office inventory spreadsheets.",
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
            id="postgres",
            kind=EvidenceKind.SKILL,
            content="Postgres",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="email",
            kind=EvidenceKind.SKILL,
            content="Email",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="teamwork",
            kind=EvidenceKind.SKILL,
            content="Teamwork",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="agile",
            kind=EvidenceKind.SKILL,
            content="Agile",
            user_confirmed=True,
        ),
    ]


def _setup_project(root: Path) -> dict[str, bytes]:
    init_project(root)
    base = working_dir(root)
    resume_payload = _over_budget_tailored_resume().model_dump(mode="json")
    for rel in _LINEAGE_RELS:
        _write_json(base / rel, resume_payload)
    _write_json(base / "jobs" / "python-api.json", _job().model_dump(mode="json"))
    _write_json(
        base / "evidence.json",
        [item.model_dump(mode="json") for item in _evidence()],
    )

    set_active(root, resume="resumes/riley-original.json", job="jobs/python-api.json")
    set_version(
        root,
        base="resumes/riley-base.json",
        base_derived_from="resumes/riley-original.json",
    )
    set_version(
        root,
        structure="resumes/riley-structure.json",
        structure_derived_from="resumes/riley-base.json",
    )
    set_version(
        root,
        standard="resumes/riley-standard.json",
        standard_derived_from="resumes/riley-structure.json",
    )
    config = load_config(root)
    config.active_evidence = "evidence.json"
    config.shape_policy = {"informational_budgets": _BUDGETS}
    save_config(root, config)
    return _lineage_snapshot(root)


def _lineage_snapshot(root: Path) -> dict[str, bytes]:
    base = working_dir(root)
    return {rel: (base / rel).read_bytes() for rel in _LINEAGE_RELS}


def _assert_lineage_unchanged(root: Path, snapshot: dict[str, bytes]) -> None:
    base = working_dir(root)
    for rel, expected in snapshot.items():
        assert (base / rel).read_bytes() == expected


def _read_resume(root: Path, rel: str) -> ResumeDocument:
    return ResumeDocument.model_validate_json(
        (working_dir(root) / rel).read_text(encoding="utf-8")
    )


def _word_count(value: str | None) -> int:
    if value is None:
        return 0
    return len([word for word in value.split() if word])


def _ledger_entries(
    result: BuildPerfectResult, fate: ContentFate
) -> list[ContentLedgerEntry]:
    return [entry for entry in result.ledger.entries if entry.fate is fate]


def _token_at_path(resume: ResumeDocument, path: str) -> str:
    if path.startswith("additional.technicalSkills["):
        index = int(path.removeprefix("additional.technicalSkills[").removesuffix("]"))
        return resume.additional.technicalSkills[index]
    prefix = "workExperience["
    rest = path.removeprefix(prefix)
    work_index_text, bullet_part = rest.split("].description[", maxsplit=1)
    bullet_index = int(bullet_part.removesuffix("]"))
    return resume.workExperience[int(work_index_text)].description[bullet_index]


def _assert_removed_items_are_ledged(
    original: ResumeDocument,
    result: BuildPerfectResult,
) -> None:
    compression_paths = {
        compression.path
        for compression in result.compressions
        if compression.claim_preserving
    }
    dropped = _ledger_entries(result, ContentFate.DROPPED_BY_RANKED_BUDGET)
    dropped_by_path = {entry.source_path: entry for entry in dropped}
    removed_paths = [
        path
        for path in result.applied
        if path.startswith("additional.technicalSkills[")
        or path.startswith("workExperience[")
        if path not in compression_paths
    ]

    assert removed_paths
    for path in removed_paths:
        entry = dropped_by_path[path]
        assert entry.token == _token_at_path(original, path)
        assert entry.reason


def _assert_compressions_are_ledged(result: BuildPerfectResult) -> None:
    compressed = _ledger_entries(result, ContentFate.COMPRESSED)
    compressed_by_path = {entry.source_path: entry for entry in compressed}
    applied_compressions = [
        compression
        for compression in result.compressions
        if compression.claim_preserving and compression.path in result.applied
    ]

    assert {compression.path for compression in applied_compressions} == {
        "summary",
        "workExperience[0].description[0]",
    }
    for compression in applied_compressions:
        entry = compressed_by_path[compression.path]
        assert entry.token == compression.original
        assert entry.target_path == compression.path
        assert entry.reason == compression.reason


def _page_count_proxy(resume: ResumeDocument) -> int:
    size = (
        _word_count(resume.summary)
        + len(resume.additional.technicalSkills)
        + len(resume.workExperience)
        + sum(len(experience.description) for experience in resume.workExperience)
    )
    return 1 + size // 12


def _patch_page_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    page_count = {"value": 0}

    def fake_render(
        resume: ResumeDocument,
        _fmt: object,
        _options: object | None = None,
    ) -> bytes:
        page_count["value"] = _page_count_proxy(resume)
        return b""

    monkeypatch.setattr("resume_kit_export.page_gate.render", fake_render)
    monkeypatch.setattr(
        "resume_kit_export.page_gate.count_pdf_pages",
        lambda _pdf_bytes: page_count["value"],
    )


def test_tailored_to_perfect_auto_fit_is_accounted_and_exportable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _setup_project(tmp_path)
    original = _over_budget_tailored_resume()
    policy = load_shape_policy(tmp_path)
    _patch_page_gate(monkeypatch)

    original_page_budget = check_page_budget(original, policy)
    assert original_page_budget.pages == 3
    assert original_page_budget.blocked is True
    assert check_page_budget(original, policy, override=True).blocked is False

    result = build_perfect(tmp_path, auto_fit=True)

    assert result.committed is True
    assert result.final_path is not None
    assert result.final_path == "resumes/riley-python-api-final.json"
    assert result.ledger_ok is True
    assert content_ledger_ok_perfect(result.ledger) is True
    assert result.deferred
    assert "workExperience[2]" in result.deferred

    final = _read_resume(tmp_path, result.final_path)
    budgets = policy.informational_budgets
    assert len(final.additional.technicalSkills) <= budgets.max_skills
    assert len(final.workExperience[0].description) <= budgets.max_bullets_per_role
    assert _word_count(final.summary) <= budgets.max_summary_words
    assert (
        _word_count(final.workExperience[0].description[0])
        <= budgets.max_bullet_words
    )

    _assert_removed_items_are_ledged(original, result)
    _assert_compressions_are_ledged(result)

    truth_report = validate_resume_truth(final, _evidence())
    contradicted_paths = [
        claim.field_path
        for claim in truth_report.claims
        if claim.status is ProvenanceStatus.CONTRADICTED
    ]
    assert contradicted_paths == []

    fitted_page_budget = check_page_budget(final, policy)
    assert fitted_page_budget.pages == 2
    assert fitted_page_budget.blocked is False

    _assert_lineage_unchanged(tmp_path, snapshot)
