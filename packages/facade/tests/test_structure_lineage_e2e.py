"""E2E lineage coverage for original -> base -> structure -> standard."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from resume_kit_facade.baseline import build_base, build_standard, build_structure
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    resolve_active_resume,
    set_active,
    working_dir,
)
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.canonical import Resume
from resume_kit_schemas.shape import ContentFate, ShapeFinding, ShapeFindingFamily
from resume_kit_scoring import content_ledger_ok

FIXTURE = Path(__file__).parent / "fixtures" / "resumes" / "resume-a-original.json"


def _install_fixture(root: Path) -> Path:
    init_project(root)
    target = working_dir(root) / "resumes" / FIXTURE.name
    target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    set_active(root, resume=f"resumes/{FIXTURE.name}")
    return target


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _finding_families(findings: Iterable[ShapeFinding]) -> set[ShapeFindingFamily]:
    return {finding.family for finding in findings}


def test_original_base_structure_standard_lineage_e2e(tmp_path: Path) -> None:
    original_path = _install_fixture(tmp_path)
    original = ResumeDocument.model_validate(_load_json(original_path))
    assert "Core Skills" in {meta.displayName for meta in original.sectionMeta}

    base_result = build_base(tmp_path, mode="auto")
    assert base_result.base_path == "resumes/resume-a-base.json"
    base_path = working_dir(tmp_path) / base_result.base_path
    base = ResumeDocument.model_validate(_load_json(base_path))
    assert base.customSections.keys() == original.customSections.keys()

    structure_result = build_structure(tmp_path)
    assert structure_result.structure_path == "resumes/resume-a-structure.json"
    assert structure_result.structure_path is not None
    assert structure_result.ledger_ok
    assert content_ledger_ok(structure_result.ledger)
    assert structure_result.claims_ok

    structure_path = working_dir(tmp_path) / structure_result.structure_path
    structure = Resume.model_validate(_load_json(structure_path))
    skill_keywords = structure.skills[0].keywords
    assert skill_keywords == ["Python", "React", "AWS", "TypeScript"]
    assert len({skill.casefold() for skill in skill_keywords}) == len(skill_keywords)
    assert "Domains & Industries" not in skill_keywords

    families = _finding_families(structure_result.report.findings)
    assert ShapeFindingFamily.CUSTOM_SECTION_MAPPED in families
    assert ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED in families
    assert ShapeFindingFamily.REDUNDANT_SECTION in families
    assert ShapeFindingFamily.CANONICAL_FIELD_DUPLICATE in families
    assert ShapeFindingFamily.EMBEDDED_HEADING_LINE in families
    assert ShapeFindingFamily.SECTION_ORDER_VIOLATION in families
    assert "custom_section_unmapped" in structure_result.deferred
    assert any(
        finding.section == "Domains & Industries"
        and finding.family is ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED
        for finding in structure_result.report.findings
    )

    domains_entries = [
        entry
        for entry in structure_result.ledger.entries
        if entry.source_path.startswith("customSections.domainsIndustries")
    ]
    assert domains_entries
    assert {entry.fate for entry in domains_entries} <= {
        ContentFate.DROPPED_AS_HEADING,
        ContentFate.DROPPED_AS_PARSER_ARTIFACT,
    }
    assert all(
        entry.fate is not ContentFate.DROPPED_BY_EXPLICIT_DECISION
        for entry in domains_entries
    )

    config = load_config(tmp_path)
    assert config.structure_resume == "resumes/resume-a-structure.json"
    assert config.structure_derived_from == "resumes/resume-a-base.json"
    assert resolve_active_resume(config) == "resumes/resume-a-structure.json"

    standard_result = build_standard(tmp_path)
    assert standard_result.refine_path == "resumes/resume-a-refine.json"
    standard_path = working_dir(tmp_path) / standard_result.refine_path
    standard = ResumeDocument.model_validate(_load_json(standard_path))
    assert "results-driven" not in standard.summary.lower()
    assert "team player" not in standard.summary.lower()
    assert not standard.workExperience[0].description[0].lower().startswith("responsible for")
    assert standard.additional.technicalSkills == skill_keywords
    assert standard.customSections == {}

    config = load_config(tmp_path)
    assert config.refine_resume == "resumes/resume-a-refine.json"
    assert config.refine_derived_from == "resumes/resume-a-structure.json"
    assert resolve_active_resume(config) == "resumes/resume-a-refine.json"
