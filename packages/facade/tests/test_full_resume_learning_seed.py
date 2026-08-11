"""Full-resume evidence seed and no-custom handoff tests."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from resume_kit_evidence import build_candidate_evidence, make_evidence_id
from resume_kit_export.docx import render_docx
from resume_kit_facade import capabilities as caps
from resume_kit_facade.baseline import build_base, build_structure
from resume_kit_facade.models import (
    CapabilityOptions,
    SeedFullResumeEvidenceRequest,
    ValidateFaithfulnessRequest,
)
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    load_evidence_file,
    save_config,
    save_evidence_file,
    set_active,
    working_dir,
)
from resume_kit_policy import default_shape_policy
from resume_kit_schemas import (
    CandidateEvidence,
    EvidenceKind,
    FaithfulnessCode,
    FaithfulnessReport,
    ResumeDocument,
)
from resume_kit_schemas.canonical import Resume
from resume_kit_schemas.shape import ContentFate
from resume_kit_scoring import (
    CustomHandoffPolicy,
    analyze_resume_shape,
    apply_shape_transforms,
    content_ledger_ok,
    evidence_receipts_from_active_evidence,
    project_builddoc_from_canonical,
)


def _full_source_resume() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Ada Lovelace", "email": "ada@example.com"},
            "summary": "Backend engineer with platform leadership.",
            "workExperience": [
                {
                    "company": "Acme",
                    "title": "Staff Engineer",
                    "description": ["Built a payments API", "Led a team of four"],
                }
            ],
            "personalProjects": [
                {"name": "Ledger", "description": ["Open-source ledger tool"]}
            ],
            "education": [{"degree": "BSc Computer Science", "institution": "MIT"}],
            "additional": {
                "technicalSkills": ["Python", "PostgreSQL"],
                "certificationsTraining": ["AWS Certified Developer"],
                "languages": ["Spanish"],
                "awards": ["Grace Hopper Award"],
            },
            "sectionMeta": [
                {
                    "id": "community",
                    "key": "community",
                    "displayName": "Community",
                    "sectionType": "stringList",
                    "isDefault": False,
                    "isVisible": True,
                    "order": 10,
                },
                {
                    "id": "patents",
                    "key": "patents",
                    "displayName": "Patents",
                    "sectionType": "itemList",
                    "isDefault": False,
                    "isVisible": True,
                    "order": 11,
                },
            ],
            "customSections": {
                "community": {
                    "sectionType": "stringList",
                    "strings": ["Mentored bootcamp students"],
                },
                "patents": {
                    "sectionType": "itemList",
                    "items": [
                        {
                            "title": "Routing optimization patent",
                            "subtitle": "US 12345",
                            "description": ["Reduced routing latency by 30%"],
                        }
                    ],
                },
            },
        }
    )


def _technical_skills_source_text() -> str:
    return (
        "Technical Skills\n"
        "Python\n"
        "PostgreSQL\n"
        "FastAPI\n"
        "Community\n"
        "Mentored bootcamp students\n"
    )


def test_full_resume_evidence_covers_all_source_sections() -> None:
    evidence = build_candidate_evidence(_full_source_resume())
    contents = {item.content for item in evidence}
    kinds = {item.kind for item in evidence}

    assert "Backend engineer with platform leadership." in contents
    assert "Staff Engineer — Acme" in contents
    assert "Built a payments API" in contents
    assert "Ledger" in contents
    assert "Open-source ledger tool" in contents
    assert "BSc Computer Science — MIT" in contents
    assert "Python" in contents
    assert "AWS Certified Developer" in contents
    assert "Spanish" in contents
    assert "Grace Hopper Award" in contents
    assert "Mentored bootcamp students" in contents
    assert "Routing optimization patent" in contents
    assert "US 12345" in contents
    assert "Reduced routing latency by 30%" in contents
    assert EvidenceKind.SOURCE_CUSTOM in kinds

    custom = [item for item in evidence if item.content == "Mentored bootcamp students"]
    assert custom[0].source == "customSections.community.strings[0]"
    assert "custom:Community" in custom[0].tags


@pytest.mark.asyncio
async def test_seed_full_resume_evidence_is_idempotent_and_preserves_existing(
    tmp_path: Path,
) -> None:
    init_project(tmp_path)
    existing_path = working_dir(tmp_path) / "learning" / "candidate-evidence.json"
    confirmed = CandidateEvidence(
        id="ev-confirmed-existing",
        kind=EvidenceKind.USER_STATEMENT,
        content="I can attest to incident response ownership.",
        source="user_confirmed",
        tags=["incident response"],
        user_confirmed=True,
    )
    duplicate_user_record = CandidateEvidence(
        id=make_evidence_id(EvidenceKind.SKILL, "Python"),
        kind=EvidenceKind.SKILL,
        content="Python",
        source="user_confirmed",
        tags=["preserve-me"],
        user_confirmed=True,
    )
    save_evidence_file(existing_path, [confirmed, duplicate_user_record])

    request = SeedFullResumeEvidenceRequest(resume=_full_source_resume(), root=tmp_path)
    first = await caps.seed_full_resume_evidence_capability(
        request,
        CapabilityOptions(no_llm=True),
    )
    second = await caps.seed_full_resume_evidence_capability(
        request,
        CapabilityOptions(no_llm=True),
    )

    assert first.ok
    assert second.ok
    first_ids = [item.id for item in first.data.evidence]
    second_ids = [item.id for item in second.data.evidence]
    assert first_ids == second_ids
    assert len(second_ids) == len(set(second_ids))

    on_disk = load_evidence_file(existing_path)
    preserved = {item.id: item for item in on_disk}
    assert preserved[confirmed.id] == confirmed
    assert preserved[duplicate_user_record.id] == duplicate_user_record
    assert any(item.content == "Mentored bootcamp students" for item in on_disk)

    config = load_config(tmp_path)
    assert config.evidence_file == "learning/candidate-evidence.json"
    assert config.active_evidence == "learning/candidate-evidence.json"


def test_no_custom_handoff_omits_custom_output_and_ledgers_evidence() -> None:
    resume = _full_source_resume()
    report = analyze_resume_shape(resume, default_shape_policy())

    result = apply_shape_transforms(
        resume,
        report,
        custom_handoff_policy=CustomHandoffPolicy.OMIT_AND_LEDGER_TO_EVIDENCE,
    )
    evidence = build_candidate_evidence(resume)

    assert result.resume.custom == []
    assert content_ledger_ok(
        result.ledger,
        evidence_receipts=evidence_receipts_from_active_evidence(evidence),
    )
    assert any(
        entry.fate is ContentFate.PRESERVED_IN_EVIDENCE
        and entry.source_path == "customSections.community.strings[0]"
        for entry in result.ledger.entries
    )
    assert any(item.content == "Mentored bootcamp students" for item in evidence)


def test_flow1_omit_build_fails_when_active_evidence_is_empty(tmp_path: Path) -> None:
    resume = _full_source_resume()
    init_project(tmp_path)
    original_rel = "resumes/ada-original.json"
    (working_dir(tmp_path) / original_rel).write_text(
        resume.model_dump_json(),
        encoding="utf-8",
    )
    set_active(tmp_path, resume=original_rel)
    evidence_rel = "learning/candidate-evidence.json"
    save_evidence_file(working_dir(tmp_path) / evidence_rel, [])
    config = load_config(tmp_path)
    config.evidence_file = evidence_rel
    config.active_evidence = evidence_rel
    save_config(tmp_path, config)
    build_base(tmp_path, mode="auto")

    result = build_structure(tmp_path, omit_custom_sections=True)

    assert result.structure_path is None
    assert not result.ledger_ok
    assert result.claims_ok
    assert any(
        entry.fate is ContentFate.PRESERVED_IN_EVIDENCE
        and entry.source_path == "customSections.community.strings[0]"
        for entry in result.ledger.entries
    )
    assert not (working_dir(tmp_path) / "resumes" / "ada-structure.json").exists()


@pytest.mark.asyncio
async def test_validate_faithfulness_rejects_no_custom_original() -> None:
    faithful = ResumeDocument.model_validate(
        {
            "additional": {"technicalSkills": ["Python", "PostgreSQL", "FastAPI"]},
            "customSections": {
                "Technical Skills": {
                    "sectionType": "stringList",
                    "strings": ["Python", "PostgreSQL", "FastAPI"],
                },
                "Community": {
                    "sectionType": "stringList",
                    "strings": ["Mentored bootcamp students"],
                },
            },
        }
    )
    no_custom = ResumeDocument.model_validate(
        {
            "additional": {"technicalSkills": ["Python", "PostgreSQL", "FastAPI"]},
            "customSections": {},
        }
    )

    faithful_response = await caps.validate_faithfulness_capability(
        ValidateFaithfulnessRequest(
            resume=faithful,
            source_text=_technical_skills_source_text(),
        ),
        CapabilityOptions(no_llm=True),
    )
    no_custom_response = await caps.validate_faithfulness_capability(
        ValidateFaithfulnessRequest(
            resume=no_custom,
            source_text=_technical_skills_source_text(),
        ),
        CapabilityOptions(no_llm=True),
    )

    assert isinstance(faithful_response.data, FaithfulnessReport)
    assert faithful_response.data.passed is True
    assert isinstance(no_custom_response.data, FaithfulnessReport)
    assert no_custom_response.data.passed is False
    errors = {
        finding.code
        for finding in no_custom_response.data.findings
        if finding.severity == "error"
    }
    assert FaithfulnessCode.DROPPED_SPANS in errors


@pytest.mark.asyncio
async def test_flow1_omit_build_exports_one_skills_section_and_preserves_evidence(
    tmp_path: Path,
) -> None:
    payload = _full_source_resume().model_dump(mode="json")
    payload["customSections"] = {
        "Technical Skills": {
            "sectionType": "stringList",
            "strings": [
                "Technical Skills",
                "Python",
                "PostgreSQL",
                "FastAPI",
            ],
        },
        "community": {
            "sectionType": "stringList",
            "strings": ["Mentored bootcamp students"],
        }
    }
    resume = ResumeDocument.model_validate(payload)
    init_project(tmp_path)
    original_rel = "resumes/ada-original.json"
    (working_dir(tmp_path) / original_rel).write_text(
        resume.model_dump_json(),
        encoding="utf-8",
    )
    set_active(tmp_path, resume=original_rel)
    original = ResumeDocument.model_validate_json(
        (working_dir(tmp_path) / original_rel).read_text(encoding="utf-8")
    )
    assert original.customSections.keys() == {"Technical Skills", "community"}
    assert original.customSections["Technical Skills"].strings == [
        "Technical Skills",
        "Python",
        "PostgreSQL",
        "FastAPI",
    ]
    assert original.customSections["community"].strings == [
        "Mentored bootcamp students"
    ]

    seeded = await caps.seed_full_resume_evidence_capability(
        SeedFullResumeEvidenceRequest(root=tmp_path),
        CapabilityOptions(no_llm=True),
    )
    assert seeded.ok
    build_base(tmp_path, mode="auto")

    result = build_structure(tmp_path, omit_custom_sections=True)

    assert result.structure_path == "resumes/ada-structure.json"
    assert result.ledger_ok
    assert result.claims_ok
    assert any(
        entry.fate is ContentFate.PRESERVED_IN_EVIDENCE
        and entry.source_path == "customSections.community.strings[0]"
        for entry in result.ledger.entries
    )

    structure_file = working_dir(tmp_path) / result.structure_path
    structure = Resume.model_validate(json.loads(structure_file.read_text(encoding="utf-8")))
    assert structure.custom == []
    assert structure.skills[0].keywords == ["Python", "PostgreSQL", "FastAPI"]
    after_structure_original = ResumeDocument.model_validate_json(
        (working_dir(tmp_path) / original_rel).read_text(encoding="utf-8")
    )
    assert after_structure_original.customSections == original.customSections

    evidence = load_evidence_file(
        working_dir(tmp_path) / "learning" / "candidate-evidence.json"
    )
    assert any(item.content == "Mentored bootcamp students" for item in evidence)

    renderable = project_builddoc_from_canonical(structure)
    assert renderable.customSections == {}
    document = Document(BytesIO(render_docx(renderable)))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    assert paragraphs.count("Skills & Awards") == 1
    assert "Technical Skills" not in paragraphs
    assert "Community" not in paragraphs
