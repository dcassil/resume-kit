"""E2E coverage for the structure -> refine wording pass."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from resume_kit_facade.baseline import build_base, build_refine, build_structure
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    resolve_active_resume,
    set_active,
    set_version,
    working_dir,
)
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.canonical import Resume
from resume_kit_scoring import (
    analyze_best_practices,
    claims_preserved,
    content_preserved,
    finding_key,
    project_builddoc_from_canonical,
    project_scoredoc,
)

_REF = date(2000, 1, 1)


def _refine_fixture() -> dict:
    return {
        "personalInfo": {
            "name": "Riley Refine",
            "email": "riley@example.com",
            "phone": "555-0199",
            "location": "Chicago, IL",
            "title": "Platform Engineer",
        },
        "summary": (
            "Platform engineer focused on reliable internal tools, payment workflows, "
            "release operations, incident learning, customer support enablement, data "
            "quality, onboarding systems, documentation practices, stakeholder "
            "collaboration, service ownership, operational telemetry, change "
            "management, engineering standards, accessibility review, maintainable "
            "delivery, cross functional planning, careful rollout design, and durable "
            "handoffs for distributed product teams that need clear execution and "
            "measurable business outcomes without overstating unsupported scope."
        ),
        "workExperience": [
            {
                "id": 1,
                "title": "Platform Engineer",
                "company": "Acme Systems",
                "years": "2021-2024",
                "description": [
                    "Improved onboarding dashboards for support managers.",
                    "Reduced incident review delays for operations partners.",
                    "Maintained deployment checklist for release managers.",
                    "Helped with release planning across 4 product teams.",
                ],
            },
            {
                "id": 2,
                "title": "Software Engineer",
                "company": "Beta Apps",
                "years": "2018-2021",
                "description": [
                    "Coordinated accessibility fixes across product surfaces.",
                    "Documented customer escalation workflows for account teams.",
                    "Was responsible for maintaining partner intake reviews.",
                ],
            },
        ],
        "education": [
            {
                "id": 1,
                "institution": "State University",
                "degree": "BS Computer Science",
                "years": "2018",
            }
        ],
        "additional": {
            "technicalSkills": ["Python", "SQL", "Microsoft Word"],
            "certificationsTraining": [],
            "awards": [],
            "languages": [],
        },
    }


def _setup(root: Path, resume: dict) -> None:
    init_project(root)
    target = working_dir(root) / "resumes" / "riley-original.json"
    target.write_text(json.dumps(resume), encoding="utf-8")
    set_active(root, resume="resumes/riley-original.json")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _builddoc_from_structure(path: Path) -> ResumeDocument:
    return project_builddoc_from_canonical(Resume.model_validate(_load_json(path)))


def _codes(resume: ResumeDocument) -> list[str]:
    scoredoc = project_scoredoc(resume, reference_date=_REF)
    return [f.rule_code for f in analyze_best_practices(resume, scoredoc).findings]


def _quant_answer(entity_id: str | None, bullet_index: int | None) -> str:
    assert entity_id is not None
    assert bullet_index is not None
    answers = {
        ("1", 0): "Improved onboarding dashboards for 12 support managers.",
        ("1", 1): "Reduced incident review delays by 35% for operations partners.",
        ("1", 2): "Maintained deployment checklist for 6 release managers.",
        ("2", 0): "Coordinated accessibility fixes across 9 product surfaces.",
        ("2", 1): "Documented customer escalation workflows for 14 account teams.",
        ("2", 2): "Maintained partner intake reviews for 7 integration partners.",
    }
    return answers[(entity_id, bullet_index)]


def _bullet(resume: ResumeDocument, entity_id: str | None, bullet_index: int | None) -> str:
    assert entity_id is not None
    assert bullet_index is not None
    experience = next(exp for exp in resume.workExperience if str(exp.id) == entity_id)
    return experience.description[bullet_index]


def test_structure_to_refine_lineage_and_whole_resume_wording_e2e(
    tmp_path: Path,
) -> None:
    _setup(tmp_path, _refine_fixture())

    base_result = build_base(tmp_path, mode="auto")
    assert base_result.base_path == "resumes/riley-base.json"

    structure_result = build_structure(tmp_path)
    assert structure_result.structure_path == "resumes/riley-structure.json"
    assert structure_result.structure_path is not None
    assert structure_result.ledger_ok
    assert structure_result.claims_ok

    structure_path = working_dir(tmp_path) / structure_result.structure_path
    structure_source = _builddoc_from_structure(structure_path)
    source_report = analyze_best_practices(
        structure_source,
        project_scoredoc(structure_source, reference_date=_REF),
    )
    source_codes = [finding.rule_code for finding in source_report.findings]
    assert "MISSING_QUANTIFICATION_MORE" not in source_codes
    assert "SUMMARY_TOO_LONG" not in source_codes
    assert "FOUNDATIONAL_SKILL" not in source_codes
    assert "VAGUE_IMPACT" in source_codes
    assert len(structure_source.summary.split()) > 60

    quantification_findings = [
        finding
        for finding in source_report.findings
        if finding.rule_code == "MISSING_QUANTIFICATION"
    ]
    assert len(quantification_findings) > 3
    answers = {
        finding_key(finding): _quant_answer(
            finding.location.entity_id,
            finding.location.bullet_index,
        )
        for finding in quantification_findings
    }

    refine_result = build_refine(tmp_path, answers=answers)

    assert refine_result.refine_path == "resumes/riley-refine.json"
    assert "VAGUE_IMPACT" in refine_result.applied
    assert "SUMMARY_TOO_LONG" not in refine_result.applied + refine_result.deferred
    assert "FOUNDATIONAL_SKILL" not in refine_result.applied + refine_result.deferred
    refine_path = working_dir(tmp_path) / refine_result.refine_path
    assert refine_path.exists()
    refine = ResumeDocument.model_validate(_load_json(refine_path))

    config = load_config(tmp_path)
    assert config.refine_resume == "resumes/riley-refine.json"
    assert config.refine_derived_from == "resumes/riley-structure.json"
    assert resolve_active_resume(config) == "resumes/riley-refine.json"

    for finding in quantification_findings:
        expected = answers[finding_key(finding)]
        assert (
            _bullet(refine, finding.location.entity_id, finding.location.bullet_index)
            == expected
        )

    refine_bullets = [
        bullet
        for exp in refine.workExperience
        for bullet in exp.description
    ]
    assert "Helped with release planning across 4 product teams." not in refine_bullets
    assert "Supported release planning across 4 product teams." in refine_bullets

    assert "Microsoft Word" in refine.additional.technicalSkills
    assert refine.summary == structure_source.summary
    assert len(refine.summary.split()) == len(structure_source.summary.split())
    assert "SUMMARY_TOO_LONG" not in _codes(refine)
    assert "FOUNDATIONAL_SKILL" not in _codes(refine)
    assert claims_preserved(structure_source, refine)
    assert content_preserved(structure_source, refine)


def test_legacy_standard_pointer_resolves_then_refine_preserves_it(
    tmp_path: Path,
) -> None:
    _setup(tmp_path, _refine_fixture())
    base_result = build_base(tmp_path, mode="auto")

    legacy_standard = "resumes/riley-standard.json"
    (working_dir(tmp_path) / legacy_standard).write_text(
        (working_dir(tmp_path) / base_result.base_path).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    config = set_version(
        tmp_path,
        standard=legacy_standard,
        standard_derived_from=base_result.base_path,
    )
    assert config.refine_resume is None
    assert resolve_active_resume(config) == legacy_standard

    result = build_refine(tmp_path)

    assert result.refine_path == "resumes/riley-refine.json"
    assert (working_dir(tmp_path) / result.refine_path).exists()
    config = load_config(tmp_path)
    assert config.refine_resume == "resumes/riley-refine.json"
    assert config.refine_derived_from == base_result.base_path
    assert config.standard_resume == legacy_standard
    assert config.standard_derived_from == base_result.base_path
    assert resolve_active_resume(config) == "resumes/riley-refine.json"
