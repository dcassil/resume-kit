"""Structured AtsStructureFinding channel (RIT-T-0114)."""

from __future__ import annotations

from resume_kit_ats.engine import check_ats_structure
from resume_kit_schemas import FindingSeverity, FixAffordance

_COMPLETE = {
    "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "555"},
    "summary": "Engineer.",
    "workExperience": [{"title": "E", "company": "X", "years": "2020-2022", "description": ["Built."]}],
    "education": [{"institution": "MIT", "degree": "BS", "years": "2016"}],
    "additional": {"technicalSkills": ["Python"]},
    "customSections": {},
}


def _codes(report):
    return {f.code for f in report.findings}


def _find(report, code):
    return next(f for f in report.findings if f.code == code)


def test_recommendations_derived_from_findings():
    report = check_ats_structure({**_COMPLETE, "personalInfo": {"name": "J"}})
    assert report.recommendations == [f.message for f in report.findings]
    assert report.findings  # something flagged (missing email/phone)


def test_ssn_finding_is_auto_safe_strip_with_metadata():
    report = check_ats_structure({**_COMPLETE, "summary": "SSN 123-45-6789."})
    f = _find(report, "PII_SSN")
    assert f.severity is FindingSeverity.WARNING
    assert f.fix_affordance is FixAffordance.AUTO_SAFE_STRIP
    assert f.metadata["match"] == "123-45-6789"


def test_nonstandard_section_needs_judgment():
    report = check_ats_structure(
        {**_COMPLETE, "customSections": {"My Superpowers": {"sectionType": "text", "text": "x"}}}
    )
    f = _find(report, "NONSTANDARD_SECTION")
    assert f.fix_affordance is FixAffordance.NEEDS_JUDGMENT
    assert "My Superpowers" in f.metadata["sections"]


def test_inconsistent_dates_auto_safe_normalize():
    report = check_ats_structure(
        {
            **_COMPLETE,
            "workExperience": [
                {"title": "A", "company": "X", "years": "Jan 2020 - Present", "description": []},
                {"title": "B", "company": "Y", "years": "2016 - 2019", "description": []},
            ],
        }
    )
    f = _find(report, "INCONSISTENT_DATES")
    assert f.fix_affordance is FixAffordance.AUTO_SAFE_NORMALIZE


def test_street_address_needs_judgment():
    report = check_ats_structure(
        {**_COMPLETE, "personalInfo": {**_COMPLETE["personalInfo"], "location": "123 Main Street"}}
    )
    assert _find(report, "PII_STREET_ADDRESS").fix_affordance is FixAffordance.NEEDS_JUDGMENT


def test_complete_resume_has_no_findings():
    report = check_ats_structure(_COMPLETE)
    assert report.findings == []
    assert report.recommendations == []


def test_missing_contact_needs_judgment():
    report = check_ats_structure({**_COMPLETE, "personalInfo": {"name": "J", "phone": "555"}})
    assert _find(report, "MISSING_EMAIL").fix_affordance is FixAffordance.NEEDS_JUDGMENT
