"""Integration proof for the composable resume-intelligence flows.

The test drives the real CLI transport for the built surfaces and keeps sockets
blocked while the flow runs. It models the agent-owned parse/learn steps by
writing the schema JSON and confirmed alias file those skills own, then uses the
CLI for the code-owned gates and mutations.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from resume_kit_cli.app import app
from resume_kit_export import check_page_budget
from resume_kit_facade.project_config import (
    load_config,
    load_evidence_file,
    save_config,
    working_dir,
)
from resume_kit_policy import load_shape_policy
from resume_kit_schemas import (
    AdditionalInfo,
    ChangeProposal,
    Experience,
    JobDescription,
    PersonalInfo,
    Requirement,
    ResumeDocument,
)
from resume_kit_schemas.resume import SectionMeta, SectionType
from typer.testing import CliRunner

_RUNNER = CliRunner()
_JSON_OBJECT = TypeAdapter(dict[str, object])

_SOURCE_TEXT = (
    "Alex Kim\n"
    "Platform Engineer\n"
    "alex@example.com\n"
    "Backend engineer with responsive UI and monitoring experience.\n"
    "Platform Engineer, Northstar Labs, 2021 - Present\n"
    "- Built responsive UI systems and FastAPI services.\n"
    "- Owned zorbulator monitoring for platform incidents.\n"
    "- Maintained Docker workflows with Python.\n"
    "Python, FastAPI, Docker\n"
    "cloudSkills: Kubernetes, responsive UI, monitoring\n"
    "BS Computer Science, State University, 2018\n"
)

_BUDGETS = {
    "max_skills": 4,
    "max_experience_entries": 1,
    "max_bullets_per_role": 2,
    "max_summary_words": 7,
    "max_bullet_words": 9,
    "max_pages": 2,
}


@dataclass(frozen=True)
class JobCase:
    slug: str
    source_term: str
    job_term: str
    bullet_index: int
    keywords: list[str]


def _run_cli(args: list[str], *, expected_exit: int = 0) -> dict[str, object]:
    result = _RUNNER.invoke(app, [*args, "--output", "json"])
    assert result.exit_code == expected_exit, result.stdout
    return _JSON_OBJECT.validate_json(result.stdout)


def _run_export(resume: Path, out: Path) -> None:
    result = _RUNNER.invoke(
        app,
        [
            "export",
            "--format",
            "pdf",
            "--resume",
            str(resume),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.is_file()
    assert out.stat().st_size > 0


def _data(payload: dict[str, object]) -> dict[str, object]:
    value = payload["data"]
    assert isinstance(value, dict)
    return value


def _dict_field(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload[key]
    assert isinstance(value, dict)
    return value


def _str_field(payload: dict[str, object], key: str) -> str:
    value = payload[key]
    assert isinstance(value, str)
    return value


def _list_field(payload: dict[str, object], key: str) -> list[object]:
    value = payload[key]
    assert isinstance(value, list)
    return value


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _source_resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Alex Kim",
            title="Platform Engineer",
            email="alex@example.com",
        ),
        summary="Backend engineer with responsive UI and monitoring experience.",
        workExperience=[
            Experience(
                title="Platform Engineer",
                company="Northstar Labs",
                years="2021 - Present",
                description=[
                    "Built responsive UI systems and FastAPI services.",
                    "Owned zorbulator monitoring for platform incidents.",
                    "Maintained Docker workflows with Python.",
                ],
            )
        ],
        education=[
            {
                "degree": "BS Computer Science",
                "institution": "State University",
                "years": "2018",
            }
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "FastAPI", "Docker"]),
        sectionMeta=[
            *[
                SectionMeta.model_validate(item)
                for item in [
                    {
                        "id": "personalInfo",
                        "key": "personalInfo",
                        "displayName": "Personal Info",
                        "sectionType": "personalInfo",
                        "order": 0,
                    },
                    {
                        "id": "summary",
                        "key": "summary",
                        "displayName": "Summary",
                        "sectionType": "text",
                        "order": 1,
                    },
                    {
                        "id": "workExperience",
                        "key": "workExperience",
                        "displayName": "Experience",
                        "sectionType": "itemList",
                        "order": 2,
                    },
                    {
                        "id": "education",
                        "key": "education",
                        "displayName": "Education",
                        "sectionType": "itemList",
                        "order": 3,
                    },
                    {
                        "id": "additional",
                        "key": "additional",
                        "displayName": "Skills",
                        "sectionType": "stringList",
                        "order": 4,
                    },
                    {
                        "id": "cloudSkills",
                        "key": "cloudSkills",
                        "displayName": "Cloud Skills",
                        "sectionType": "stringList",
                        "isDefault": False,
                        "order": 5,
                    },
                ]
            ]
        ],
        customSections={
            "cloudSkills": {
                "sectionType": SectionType.STRING_LIST,
                "strings": ["Kubernetes", "responsive UI", "monitoring"],
            }
        },
    )


def _job(case: JobCase) -> JobDescription:
    return JobDescription(
        title=f"{case.job_term.title()} Platform Engineer",
        company=f"{case.slug.title()} Corp",
        raw_text=" ".join(case.keywords),
        requirements=[
            Requirement(text=f"Requires {keyword}.", keywords=[keyword])
            for keyword in case.keywords
        ],
        keywords=case.keywords,
    )


def _read_resume(path: Path) -> ResumeDocument:
    return ResumeDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _snapshot(paths: list[Path]) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in paths}


def _assert_snapshot_unchanged(snapshot: dict[str, bytes], paths: list[Path]) -> None:
    for path in paths:
        assert path.read_bytes() == snapshot[path.name], path


def _append_confirmed_alias(
    alias_file: Path,
    *,
    canonical: str,
    alias: str,
    why: str,
) -> None:
    if alias_file.exists():
        payload = json.loads(alias_file.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
    else:
        payload = {"version": 1, "aliases": {}, "justifications": {}}

    aliases = payload.setdefault("aliases", {})
    assert isinstance(aliases, dict)
    existing_group = aliases.setdefault(canonical, [])
    assert isinstance(existing_group, list)
    if all(str(item).casefold() != alias.casefold() for item in existing_group):
        existing_group.append(alias)

    justifications = payload.setdefault("justifications", {})
    assert isinstance(justifications, dict)
    justifications[canonical] = why
    payload["version"] = 1
    _write_json(alias_file, payload)


def _configure_budgets(root: Path) -> None:
    config = load_config(root)
    config.shape_policy = {"informational_budgets": _BUDGETS}
    save_config(root, config)


def _select_resume_for_fit(root: Path, resume_rel: str) -> None:
    config = load_config(root)
    config.refine_resume = resume_rel
    save_config(root, config)


def _working_dir_relative(path_text: str) -> str:
    path = Path(path_text)
    if len(path.parts) > 1 and path.parts[0] == "resume-kit":
        return str(Path(*path.parts[1:]))
    return path_text


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access attempted during composable flow")

    monkeypatch.setattr(socket, "getaddrinfo", _no_network)
    monkeypatch.setattr(socket.socket, "connect", _no_network)


def test_composable_flows_reuse_prepared_resume_across_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_network(monkeypatch)

    # Flow 1: init -> extract-text -> faithfulness gate -> activate -> baseline.
    _run_cli(["init", "--root", str(tmp_path)])
    _configure_budgets(tmp_path)

    source = tmp_path / "alex-resume.txt"
    source.write_text(_SOURCE_TEXT, encoding="utf-8")
    extracted = _run_cli(["extract-text", str(source)])
    assert "cloudSkills" in _str_field(_data(extracted), "text")

    rk = working_dir(tmp_path)
    original_path = rk / "resumes" / "alex-original.json"
    original_path.write_text(_source_resume().model_dump_json(indent=2), encoding="utf-8")

    faithfulness = _run_cli(
        ["validate-faithfulness", "--source", str(source), "--json", str(original_path)]
    )
    assert _data(faithfulness)["passed"] is True
    _run_cli(
        [
            "set-active",
            "--root",
            str(tmp_path),
            "--resume",
            "resumes/alex-original.json",
            "--source",
            str(source),
        ]
    )

    base = _run_cli(["build-base", "--root", str(tmp_path)])
    shape_answers = _write_json(tmp_path / "shape-answers.json", {"Cloud Skills": "skills"})
    structure = _run_cli(
        ["build-structure", "--root", str(tmp_path), "--answers", str(shape_answers)]
    )
    assert _str_field(_data(base), "base_path") == "resumes/alex-base.json"
    assert _str_field(_data(structure), "structure_path") == "resumes/alex-structure.json"
    _run_cli(
        [
            "analyze-best-practices",
            "--resume",
            str(rk / "resumes" / "alex-structure.json"),
        ]
    )
    refine = _run_cli(["build-refine", "--root", str(tmp_path)])
    refine_rel = _str_field(_data(refine), "refine_path")
    assert refine_rel == "resumes/alex-refine.json"

    seed = _run_cli(["seed-full-resume-evidence", "--root", str(tmp_path)])
    evidence_rel = _str_field(_data(seed), "evidence_file")
    evidence_path = rk / evidence_rel
    evidence = load_evidence_file(evidence_path)
    evidence_contents = {item.content for item in evidence}
    assert "Kubernetes" in evidence_contents
    assert "responsive UI" in evidence_contents
    assert "monitoring" in evidence_contents

    prepared_refine_path = rk / refine_rel
    prepared_refine = _read_resume(prepared_refine_path)
    assert prepared_refine.customSections == {}
    assert {"Kubernetes", "responsive UI", "monitoring"}.issubset(
        set(prepared_refine.additional.technicalSkills)
    )

    flow1_paths = [
        original_path,
        rk / "resumes" / "alex-base.json",
        rk / "resumes" / "alex-structure.json",
        prepared_refine_path,
        evidence_path,
    ]
    flow1_snapshot = _snapshot(flow1_paths)

    alias_path = rk / "learning" / "synonyms.json"
    cases = [
        JobCase(
            slug="responsive",
            source_term="responsive UI",
            job_term="responsive design",
            bullet_index=0,
            keywords=["responsive design", "FastAPI", "Kubernetes"],
        ),
        JobCase(
            slug="quibble",
            source_term="zorbulator",
            job_term="quibblewidget",
            bullet_index=1,
            keywords=["quibblewidget", "Python", "Docker"],
        ),
    ]

    exported: list[Path] = []
    for case in cases:
        job_source = tmp_path / f"{case.slug}-job.txt"
        job_source.write_text(" ".join(case.keywords), encoding="utf-8")
        _run_cli(["extract-text", str(job_source)])

        job_rel = f"jobs/{case.slug}-job.json"
        job_path = rk / job_rel
        job_path.write_text(_job(case).model_dump_json(indent=2), encoding="utf-8")
        _run_cli(
            [
                "set-active",
                "--root",
                str(tmp_path),
                "--job",
                job_rel,
                "--job-source",
                str(job_source),
            ]
        )

        _run_cli(
            [
                "suggest-terminology-candidates",
                "--resume",
                str(prepared_refine_path),
                "--job",
                str(job_path),
                *(
                    ["--alias-file", str(alias_path)]
                    if alias_path.exists()
                    else []
                ),
            ]
        )
        _append_confirmed_alias(
            alias_path,
            canonical=case.job_term,
            alias=case.source_term,
            why=f"{case.source_term} is the resume wording for {case.job_term}.",
        )
        if case.slug == "quibble":
            _append_confirmed_alias(
                alias_path,
                canonical="responsive design",
                alias="responsive UI",
                why="duplicate append proves case-insensitive dedupe.",
            )
        _run_cli(
            [
                "set-active",
                "--root",
                str(tmp_path),
                "--alias-file",
                "learning/synonyms.json",
            ]
        )

        match_before = _run_cli(
            [
                "match",
                "--resume",
                str(prepared_refine_path),
                "--job",
                str(job_path),
                "--alias-file",
                str(alias_path),
            ]
        )
        gaps_before = _run_cli(
            [
                "identify-gaps",
                "--tailored",
                str(prepared_refine_path),
                "--master",
                str(prepared_refine_path),
                "--job",
                str(job_path),
                "--alias-file",
                str(alias_path),
            ]
        )
        assert _data(match_before)["overall_score"] is not None
        missing_before = _list_field(_data(gaps_before), "missing_keywords")
        if case.slug == "responsive":
            assert case.job_term not in missing_before
        else:
            assert case.job_term in missing_before

        current_refine = _read_resume(prepared_refine_path)
        original_bullet = current_refine.workExperience[0].description[case.bullet_index]
        assert case.source_term in original_bullet
        replacement = original_bullet.replace(case.source_term, case.job_term)
        change = ChangeProposal(
            path=f"workExperience[0].description[{case.bullet_index}]",
            action="replace",
            original=original_bullet,
            value=replacement,
            reason=(
                "Mirror the employer's exact terminology while preserving the "
                "same proved claim."
            ),
        )
        changes_path = tmp_path / f"{case.slug}-changes.json"
        _write_json(changes_path, [change.model_dump(mode="json")])

        stale_working = rk / "working" / f"{prepared_refine_path.stem}.tailored.json"
        if stale_working.exists():
            stale_working.unlink()
        _run_cli(
            [
                "review-edits",
                "open",
                "--root",
                str(tmp_path),
                "--mode",
                "interactive",
                "--changes",
                str(changes_path),
                "--evidence",
                str(evidence_path),
            ]
        )
        _run_cli(
            [
                "review-edits",
                "decide",
                "--root",
                str(tmp_path),
                "--path",
                change.path,
                "--action",
                "approve",
            ]
        )
        committed = _run_cli(
            [
                "review-edits",
                "commit",
                "--root",
                str(tmp_path),
                "--alias-timestamp",
                "2026-08-11T00:00:00+00:00",
            ]
        )
        assert len(_list_field(_data(committed), "applied")) == 1
        state = _dict_field(_data(committed), "state")
        working_rel = _working_dir_relative(_str_field(state, "working_path"))
        working_path = rk / working_rel
        assert working_path.is_file()

        validate = _run_cli(
            [
                "validate-truth",
                "--resume",
                str(working_path),
                "--evidence",
                str(evidence_path),
                "--alias-file",
                str(alias_path),
            ]
        )
        claims = _list_field(_data(validate), "claims")
        assert all(
            isinstance(claim, dict)
            and claim.get("status") != "contradicted"
            for claim in claims
        )

        match_after = _run_cli(
            [
                "match",
                "--resume",
                str(working_path),
                "--job",
                str(job_path),
                "--alias-file",
                str(alias_path),
            ]
        )
        gaps_after = _run_cli(
            [
                "identify-gaps",
                "--tailored",
                str(working_path),
                "--master",
                str(prepared_refine_path),
                "--job",
                str(job_path),
                "--alias-file",
                str(alias_path),
            ]
        )
        assert _data(match_after)["overall_score"] is not None
        assert case.job_term not in _list_field(_data(gaps_after), "missing_keywords")

        _select_resume_for_fit(tmp_path, working_rel)
        stale_fit_working = rk / "working" / f"{Path(working_rel).stem}.tailored.json"
        if stale_fit_working.exists():
            stale_fit_working.unlink()
        fit = _run_cli(["fit", "--root", str(tmp_path), "--auto-fit"])
        fit_data = _data(fit)
        final_rel = _str_field(fit_data, "final_path")
        assert final_rel.startswith("working/alex-")
        assert final_rel.endswith("-final.tailored.json")
        final_path = rk / final_rel
        assert final_path.is_file()

        final_resume = _read_resume(final_path)
        page = check_page_budget(final_resume, load_shape_policy(tmp_path))
        assert page.blocked is False
        assert page.pages <= 2

        out = tmp_path / f"{case.slug}.pdf"
        _run_export(final_path, out)
        exported.append(out)

        _select_resume_for_fit(tmp_path, refine_rel)
        _assert_snapshot_unchanged(flow1_snapshot, flow1_paths)

    alias_payload = json.loads(alias_path.read_text(encoding="utf-8"))
    assert alias_payload["aliases"]["responsive design"] == ["responsive UI"]
    assert alias_payload["aliases"]["quibblewidget"] == ["zorbulator"]
    assert len(exported) == 2
