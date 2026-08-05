"""Deterministic base auto-fix engine (RIT-T-0115)."""

from __future__ import annotations

from resume_kit_ats.engine import check_ats_structure
from resume_kit_schemas import ResumeDocument
from resume_kit_scoring import apply_auto_fixes


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
            "workExperience": [{"title": "A", "company": "X", "years": "2020-2022", "description": []}],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
            "customSections": {"My Superpowers": {"sectionType": "text", "text": "x"}},
        }
    )
    result = _fix(resume)
    assert "MISSING_EMAIL" in result.deferred
    assert "NONSTANDARD_SECTION" in result.deferred
    assert "MISSING_EMAIL" not in result.applied


def test_deterministic_and_idempotent() -> None:
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "J", "email": "j@x.com", "phone": "5"},
            "summary": "E. SSN 123-45-6789.",
            "workExperience": [{"title": "A", "company": "X", "years": "2020-2022", "description": []}],
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
            "workExperience": [{"title": "A", "company": "X", "years": "2020-2022", "description": ["Built."]}],
            "education": [{"institution": "M", "degree": "BS", "years": "2015"}],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    result = _fix(resume)
    assert result.applied == []
    assert result.resume.model_dump() == resume.model_dump()
