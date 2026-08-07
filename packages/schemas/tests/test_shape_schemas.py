"""Tests for shape-pass schema contracts."""

from __future__ import annotations

from resume_kit_schemas.canonical import Basics, CanonicalSection, Resume
from resume_kit_schemas.shape import (
    ContentFate,
    ContentLedger,
    ContentLedgerEntry,
    SectionMapping,
    SectionMappingStatus,
    ShapeFinding,
    ShapeFindingFamily,
    ShapeFixResult,
    ShapeReport,
)


def test_shape_finding_constructs_and_serializes() -> None:
    finding = ShapeFinding(
        family=ShapeFindingFamily.CUSTOM_SECTION_MAPPED,
        code="custom_section_mapped",
        section="Technical Skills",
        message="Mapped custom skills section.",
        proposed_target=CanonicalSection.SKILLS,
        confidence=0.95,
    )
    dumped = finding.model_dump(mode="json")
    assert dumped["family"] == "CUSTOM_SECTION_MAPPED"
    assert dumped["proposed_target"] == "skills"


def test_shape_report_constructs_and_serializes() -> None:
    report = ShapeReport(
        findings=[
            ShapeFinding(
                family=ShapeFindingFamily.BUDGET_INFO,
                code="skill_count",
                section="skills",
                message="Skill count recorded for later budget pass.",
            )
        ],
        summary="1 informational finding",
    )
    dumped = report.model_dump(mode="json")
    assert dumped["summary"] == "1 informational finding"
    assert dumped["findings"][0]["family"] == "BUDGET_INFO"


def test_section_mapping_constructs_and_serializes() -> None:
    mapping = SectionMapping(
        source_section="Certifications",
        target=CanonicalSection.CERTIFICATIONS,
        status=SectionMappingStatus.MAPPED,
    )
    assert mapping.model_dump(mode="json") == {
        "source_section": "Certifications",
        "target": "certifications",
        "status": "mapped",
    }


def test_content_ledger_constructs_and_serializes() -> None:
    ledger = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="Python",
                fate=ContentFate.MOVED,
                source_path="customSections.skills[0]",
                target_path="skills[0].keywords[0]",
            )
        ]
    )
    dumped = ledger.model_dump(mode="json")
    assert dumped["entries"][0]["fate"] == "moved"
    assert dumped["entries"][0]["token"] == "Python"


def test_shape_fix_result_constructs_and_serializes() -> None:
    resume = Resume(basics=Basics(name="Daniel Cassil", email="daniel@example.com"))
    finding = ShapeFinding(
        family=ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED,
        code="custom_section_unmapped",
        section="Ventures",
        message="Needs a decision.",
    )
    result = ShapeFixResult(
        resume=resume,
        ledger=ContentLedger(
            entries=[
                ContentLedgerEntry(
                    token="Ventures",
                    fate=ContentFate.UNRESOLVED,
                    source_path="customSections.ventures",
                )
            ]
        ),
        deferred_findings=[finding],
    )
    dumped = result.model_dump(mode="json")
    assert dumped["resume"]["basics"]["name"] == "Daniel Cassil"
    assert dumped["ledger"]["entries"][0]["fate"] == "unresolved"
    assert dumped["deferred_findings"][0]["family"] == "CUSTOM_SECTION_UNMAPPED"
