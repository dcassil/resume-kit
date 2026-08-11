"""Deterministic base auto-fix engine (RIT-T-0115)."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from resume_kit_ats.engine import check_ats_structure
from resume_kit_policy import default_shape_policy
from resume_kit_schemas import (
    AtsStructureFinding,
    AtsStructureReport,
    FindingSeverity,
    FixAffordance,
    ResumeDocument,
)
from resume_kit_schemas.shape import ShapeFindingFamily
from resume_kit_scoring import analyze_resume_shape, apply_auto_fixes, content_preserved


def _fix(resume: ResumeDocument):
    report = check_ats_structure(resume)
    return apply_auto_fixes(resume, report)


def test_strips_ssn_and_placeholder_but_keeps_claims() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "555"},
            "summary": "Engineer. SSN 123-45-6789. Lorem ipsum filler.",
            "workExperience": [
                {"title": "Staff Engineer", "company": "Acme", "years": "2020-2022",
                 "description": ["Built billing."]}
            ],
            "education": [{"institution": "MIT", "degree": "BS CS", "years": "2016"}],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    result = _fix(resume)
    assert "123-45-6789" not in result.resume.summary
    assert "lorem ipsum" not in result.resume.summary.lower()
    assert "PII_SSN" in result.applied
    # claims preserved
    assert result.resume.workExperience[0].company == "Acme"
    assert result.resume.additional.technicalSkills == ["Python"]


def test_normalizes_inconsistent_dates_to_year_ranges() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "J", "email": "j@x.com", "phone": "5"},
            "summary": "E.",
            "workExperience": [
                {"title": "A", "company": "X", "years": "Jan 2020 - Present", "description": []},
                {"title": "B", "company": "Y", "years": "2016 - 2019", "description": []},
            ],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    result = _fix(resume)
    assert "INCONSISTENT_DATES" in result.applied
    assert "Jan" not in result.resume.workExperience[0].years
    assert "2020" in result.resume.workExperience[0].years  # year preserved


def test_needs_judgment_findings_are_deferred_not_applied() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "J", "phone": "5"},  # missing email -> needs_judgment
            "summary": "E.",
            "workExperience": [
                {"title": "A", "company": "X", "years": "2020-2022", "description": []}
            ],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
            "customSections": {"My Superpowers": {"sectionType": "text", "text": "x"}},
        }
    )
    result = _fix(resume)
    assert result.deferred == ["MISSING_EMAIL"]
    assert "MISSING_EMAIL" not in result.applied
    shape_report = analyze_resume_shape(resume, default_shape_policy())
    assert any(
        finding.family is ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED
        and finding.section == "My Superpowers"
        for finding in shape_report.findings
    )


def test_deterministic_and_idempotent() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "J", "email": "j@x.com", "phone": "5"},
            "summary": "E. SSN 123-45-6789.",
            "workExperience": [
                {"title": "A", "company": "X", "years": "2020-2022", "description": []}
            ],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    once = _fix(resume).resume
    # re-running the fixer on an already-fixed base yields no SSN finding -> no change
    twice = _fix(once).resume
    assert once.model_dump() == twice.model_dump()


def test_clean_resume_no_fixes() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "J", "email": "j@x.com", "phone": "5"},
            "summary": "Engineer.",
            "workExperience": [
                {"title": "A", "company": "X", "years": "2020-2022", "description": ["Built."]}
            ],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    result = _fix(resume)
    assert result.applied == []
    assert result.resume.model_dump() == resume.model_dump()


def test_non_ascii_formatting_is_preserved_at_base() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "J", "email": "j@x.com", "phone": "5"},
            "summary": "Jane’s résumé work — São Paulo systems · precise.",
            "workExperience": [
                {"title": "A", "company": "X", "years": "2020-2022", "description": []}
            ],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    result = _fix(resume)

    assert "FORMATTING_NON_ASCII" not in result.applied
    assert "FORMATTING_NON_ASCII" in result.deferred
    assert result.resume.summary == resume.summary


def test_claim_altering_auto_fix_still_fails() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "J", "email": "j@x.com", "phone": "5"},
            "summary": "Engineer.",
            "workExperience": [
                {"title": "A", "company": "Acme", "years": "2020-2022", "description": []}
            ],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    report = AtsStructureReport(
        findings=[
            AtsStructureFinding(
                code="BAD_AUTO_STRIP",
                message="Bad auto strip.",
                severity=FindingSeverity.RECOMMENDATION,
                fix_affordance=FixAffordance.AUTO_SAFE_STRIP,
                metadata={"match": "Acme"},
            )
        ]
    )

    with pytest.raises(ValueError, match="altered a claim"):
        apply_auto_fixes(resume, report)


def test_content_preserved_only_allows_summary_and_experience_bullet_rewrites() -> None:
    base = {
        "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "5"},
        "summary": "Engineer.",
        "workExperience": [
            {
                "id": 1,
                "title": "Engineer",
                "company": "Acme",
                "years": "2020-2022",
                "description": ["Responsible for maintaining billing."],
            }
        ],
        "education": [{"institution": "MIT", "degree": "BS CS", "years": "2016"}],
        "additional": {"technicalSkills": ["Python"], "languages": ["English"]},
    }
    cases = [
        ("summary wording", ("summary",), "Senior engineer.", True),
        (
            "experience bullet wording",
            ("workExperience", 0, "description", 0),
            "Maintained billing.",
            True,
        ),
        ("skill content", ("additional", "technicalSkills"), ["Python", "SQL"], False),
        ("bullet dropped", ("workExperience", 0, "description"), [], False),
        ("experience title", ("workExperience", 0, "title"), "Staff Engineer", False),
    ]
    before = ResumeDocument.model_validate(base)
    for _name, path, value, expected in cases:
        changed = copy.deepcopy(base)
        target: Any = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        after = ResumeDocument.model_validate(changed)
        assert content_preserved(before, after) is expected
