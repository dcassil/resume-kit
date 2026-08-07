"""Read-only shape analyzer tests (RIT-T-0135)."""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from resume_kit_policy import (
    InformationalShapeBudgets,
    ResumeShapePolicy,
    default_shape_policy,
)
from resume_kit_schemas.canonical import CanonicalSection
from resume_kit_schemas.resume import ResumeDocument
from resume_kit_schemas.shape import ShapeFinding, ShapeFindingFamily
from resume_kit_scoring import analyze_resume_shape


def _resume(
    *,
    summary: str = "Built reliable platforms.",
    skills: list[str] | None = None,
    custom_sections: dict[str, object] | None = None,
    section_meta: list[dict[str, object]] | None = None,
    work_bullets: list[str] | None = None,
    projects: bool = False,
) -> ResumeDocument:
    data: dict[str, object] = {
        "personalInfo": {"name": "Jane Engineer", "email": "jane@example.com"},
        "summary": summary,
        "workExperience": [
            {
                "id": 1,
                "title": "Staff Engineer",
                "company": "Acme",
                "years": "2020-2024",
                "description": work_bullets or ["Built billing services."],
            }
        ],
        "education": [
            {"institution": "State University", "degree": "BS Computer Science", "years": "2016"}
        ],
        "additional": {"technicalSkills": skills or []},
        "customSections": custom_sections or {},
    }
    if projects:
        data["personalProjects"] = [
            {"name": "Launchpad", "role": "Creator", "description": ["Built deploy tooling."]}
        ]
    if section_meta is not None:
        data["sectionMeta"] = section_meta
    return ResumeDocument.model_validate(data)


def _policy(
    *,
    budgets: InformationalShapeBudgets | None = None,
) -> ResumeShapePolicy:
    policy = default_shape_policy()
    if budgets is None:
        return policy
    return policy.model_copy(update={"informational_budgets": budgets})


def _families(resume: ResumeDocument, policy: ResumeShapePolicy | None = None) -> list[str]:
    report = analyze_resume_shape(resume, policy or _policy())
    return [finding.family.value for finding in report.findings]


def _findings(
    resume: ResumeDocument,
    family: ShapeFindingFamily,
    policy: ResumeShapePolicy | None = None,
) -> list[ShapeFinding]:
    return [
        finding
        for finding in analyze_resume_shape(resume, policy or _policy()).findings
        if finding.family is family
    ]


@pytest.mark.parametrize(
    ("family", "positive", "clean"),
    [
        (
            ShapeFindingFamily.CUSTOM_SECTION_MAPPED,
            _resume(
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React"],
                    }
                }
            ),
            _resume(),
        ),
        (
            ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED,
            _resume(
                custom_sections={
                    "Domains & Industries": {
                        "sectionType": "stringList",
                        "strings": ["Media", "Fintech"],
                    }
                }
            ),
            _resume(
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React"],
                    }
                }
            ),
        ),
        (
            ShapeFindingFamily.REDUNDANT_SECTION,
            _resume(
                custom_sections={
                    "Core Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React", "AWS"],
                    },
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React", "AWS", "TypeScript"],
                    },
                }
            ),
            _resume(
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React"],
                    },
                    "Certifications": {
                        "sectionType": "stringList",
                        "strings": ["AWS Certified Developer"],
                    },
                }
            ),
        ),
        (
            ShapeFindingFamily.DUPLICATE_SECTION_CONTENT,
            _resume(
                custom_sections={
                    "Core Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React", "AWS"],
                    },
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["AWS", "React", "Python"],
                    },
                }
            ),
            _resume(
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React"],
                    },
                    "Awards": {
                        "sectionType": "stringList",
                        "strings": ["Engineering Excellence"],
                    },
                }
            ),
        ),
        (
            ShapeFindingFamily.CANONICAL_FIELD_DUPLICATE,
            _resume(
                skills=["Python", "React", "AWS"],
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React", "AWS"],
                    }
                },
            ),
            _resume(
                skills=["Python", "React", "AWS"],
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Go", "Rust", "Kubernetes"],
                    }
                },
            ),
        ),
        (
            ShapeFindingFamily.EMBEDDED_HEADING_LINE,
            _resume(
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Technical Skills", "Python"],
                    }
                }
            ),
            _resume(
                custom_sections={
                    "Technical Skills": {
                        "sectionType": "stringList",
                        "strings": ["Python", "React"],
                    }
                }
            ),
        ),
        (
            ShapeFindingFamily.SECTION_ORDER_VIOLATION,
            _resume(
                section_meta=[
                    {
                        "id": "education",
                        "key": "education",
                        "displayName": "Education",
                        "sectionType": "itemList",
                        "order": 1,
                    },
                    {
                        "id": "workExperience",
                        "key": "workExperience",
                        "displayName": "Experience",
                        "sectionType": "itemList",
                        "order": 2,
                    },
                ]
            ),
            _resume(),
        ),
        (
            ShapeFindingFamily.BUDGET_INFO,
            _resume(skills=["Python", "React", "AWS"]),
            _resume(skills=["Python"]),
        ),
    ],
)
def test_each_family_has_positive_and_clean_case(
    family: ShapeFindingFamily,
    positive: ResumeDocument,
    clean: ResumeDocument,
) -> None:
    policy = (
        _policy(budgets=InformationalShapeBudgets(max_skills=2))
        if family is ShapeFindingFamily.BUDGET_INFO
        else _policy()
    )

    assert family.value in _families(positive, policy)
    assert family.value not in _families(clean, policy)


def test_mapped_custom_section_carries_target_and_confidence() -> None:
    resume = _resume(
        custom_sections={
            "Technical Skills": {
                "sectionType": "stringList",
                "strings": ["Python"],
            }
        }
    )

    finding = _findings(resume, ShapeFindingFamily.CUSTOM_SECTION_MAPPED)[0]

    assert finding.proposed_target is CanonicalSection.SKILLS
    assert finding.confidence == 1.0


def test_unmapped_custom_section_falls_back_to_other() -> None:
    resume = _resume(
        custom_sections={
            "Domains & Industries": {
                "sectionType": "stringList",
                "strings": ["Media"],
            }
        }
    )

    finding = _findings(resume, ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED)[0]

    assert finding.proposed_target is CanonicalSection.OTHER
    assert finding.confidence == 0.0


def test_core_skills_technical_skills_domains_scenario_reports_expected_shape() -> None:
    resume = _resume(
        skills=["Python", "TypeScript", "React", "AWS"],
        custom_sections={
            "Core Skills": {
                "sectionType": "stringList",
                "strings": ["Python", "React", "AWS"],
            },
            "Technical Skills": {
                "sectionType": "stringList",
                "strings": ["Python", "TypeScript", "React", "AWS"],
            },
            "Domains & Industries": {
                "sectionType": "stringList",
                "strings": ["Media platforms", "Fintech"],
            },
        },
    )

    report = analyze_resume_shape(resume, _policy())
    redundant_sections = _sections_for(report.findings, ShapeFindingFamily.REDUNDANT_SECTION)
    duplicate_sections = _sections_for(
        report.findings,
        ShapeFindingFamily.CANONICAL_FIELD_DUPLICATE,
    )
    unmapped_sections = _sections_for(report.findings, ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED)

    assert "Core Skills <-> Technical Skills" in redundant_sections
    assert "Technical Skills <-> additional.technicalSkills" in duplicate_sections
    assert "Domains & Industries" in unmapped_sections


def test_fully_canonical_resume_yields_clean_report() -> None:
    resume = _resume(
        skills=["Python", "React"],
        projects=True,
    )

    report = analyze_resume_shape(resume, _policy())

    assert report.findings == []


def test_analyzer_is_deterministic_and_does_not_mutate_input() -> None:
    resume = _resume(
        skills=["Python", "React", "AWS"],
        custom_sections={
            "Technical Skills": {
                "sectionType": "stringList",
                "strings": ["Python", "React", "AWS"],
            },
            "Domains & Industries": {
                "sectionType": "stringList",
                "strings": ["Media"],
            },
        },
    )
    before = resume.model_dump(mode="json")

    first = analyze_resume_shape(resume, _policy()).model_dump_json()
    second = analyze_resume_shape(resume, _policy()).model_dump_json()

    assert first == second
    assert resume.model_dump(mode="json") == before


def _sections_for(findings: Iterable[ShapeFinding], family: ShapeFindingFamily) -> list[str]:
    return [
        finding.section
        for finding in findings
        if finding.family is family
    ]
