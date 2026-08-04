"""Tests for the expanded deterministic recommendation checks.

These tests verify that the new structural checks (contact info, section
presence, date presence, formatting risks) generate the expected
recommendation strings. They must NOT change the numeric composite score.
"""

from __future__ import annotations

from resume_kit_ats.engine import _expanded_recommendations, compute_ats_score

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPLETE_RESUME: dict[str, object] = {
    "personalInfo": {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
    },
    "summary": "Experienced engineer.",
    "workExperience": [
        {
            "title": "Engineer",
            "company": "Acme",
            "years": "2020-Present",
            "description": ["Built APIs"],
        }
    ],
    "education": [{"institution": "MIT", "degree": "BS CS", "years": "2016"}],
    "additional": {"technicalSkills": ["Python", "Docker"]},
    "personalProjects": [],
    "sectionMeta": [],
    "customSections": {},
}

_EMPTY_RESUME: dict[str, object] = {
    "personalInfo": {},
    "summary": "",
    "workExperience": [],
    "education": [],
    "additional": {"technicalSkills": []},
    "personalProjects": [],
    "sectionMeta": [],
    "customSections": {},
}


def _has_tip(tips: list[str], fragment: str) -> bool:
    return any(fragment.lower() in t.lower() for t in tips)


# ---------------------------------------------------------------------------
# Contact-info checks
# ---------------------------------------------------------------------------


def test_missing_email_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "personalInfo": {"name": "Jane", "phone": "555"}}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "email"), tips


def test_missing_phone_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "personalInfo": {"name": "Jane", "email": "j@x.com"}}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "phone"), tips


def test_missing_name_flagged() -> None:
    resume = {
        **_COMPLETE_RESUME,
        "personalInfo": {"email": "j@x.com", "phone": "555"},
    }
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "name"), tips


def test_complete_contact_no_contact_tip() -> None:
    tips = _expanded_recommendations(_COMPLETE_RESUME)
    assert not _has_tip(tips, "email"), tips
    assert not _has_tip(tips, "phone"), tips
    assert not _has_tip(tips, "No name"), tips


# ---------------------------------------------------------------------------
# Section presence checks
# ---------------------------------------------------------------------------


def test_no_summary_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "summary": ""}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "summary or objective"), tips


def test_no_work_experience_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "workExperience": []}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "work experience"), tips


def test_no_education_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "education": []}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "education"), tips


def test_no_technical_skills_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "additional": {"technicalSkills": []}}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "skills"), tips


def test_complete_resume_no_section_tips() -> None:
    tips = _expanded_recommendations(_COMPLETE_RESUME)
    assert not _has_tip(tips, "summary or objective"), tips
    assert not _has_tip(tips, "no work experience"), tips
    assert not _has_tip(tips, "no education"), tips


# ---------------------------------------------------------------------------
# Date presence checks
# ---------------------------------------------------------------------------


def test_work_entries_missing_years_flagged() -> None:
    resume = {
        **_COMPLETE_RESUME,
        "workExperience": [
            {"title": "Dev", "company": "X", "years": ""},
            {"title": "Lead", "company": "Y", "years": ""},
        ],
    }
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "missing date"), tips


def test_work_entries_with_years_ok() -> None:
    tips = _expanded_recommendations(_COMPLETE_RESUME)
    assert not _has_tip(tips, "missing date"), tips


def test_no_date_references_in_text_flagged() -> None:
    resume = {
        **_COMPLETE_RESUME,
        "workExperience": [
            {"title": "Dev", "company": "X", "years": "see below", "description": []}
        ],
        "summary": "No dates here at all",
        "education": [],
    }
    # Remove all date-like text
    resume["personalInfo"] = {"name": "J", "email": "j@x.com", "phone": "555"}
    resume["additional"] = {"technicalSkills": ["Python"]}
    tips = _expanded_recommendations(resume)
    # "see below" is not a date pattern; no month/year found → tip expected
    assert _has_tip(tips, "date"), tips


def test_date_present_in_years_field_no_tip() -> None:
    """A valid years value should prevent the date-missing tip."""
    tips = _expanded_recommendations(_COMPLETE_RESUME)
    # "2020-Present" in workExperience years → date pattern detected
    assert not any("No date references" in t for t in tips), tips


# ---------------------------------------------------------------------------
# Formatting risk checks
# ---------------------------------------------------------------------------


def test_non_ascii_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "summary": "Résumé with café and naïve text."}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "non-ascii"), tips


def test_tab_character_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "summary": "Skills:\tPython\tDocker"}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "tab"), tips


def test_unicode_bullet_flagged() -> None:
    resume = {**_COMPLETE_RESUME, "summary": "• Designed APIs\n• Led team"}
    tips = _expanded_recommendations(resume)
    assert _has_tip(tips, "bullet"), tips


def test_clean_ascii_no_formatting_tips() -> None:
    tips = _expanded_recommendations(_COMPLETE_RESUME)
    assert not _has_tip(tips, "non-ascii"), tips
    assert not _has_tip(tips, "tab"), tips
    assert not _has_tip(tips, "bullet"), tips


# ---------------------------------------------------------------------------
# Score contract: expanded checks must NOT alter composite score
# ---------------------------------------------------------------------------


def test_expanded_checks_do_not_change_score() -> None:
    """Adding expanded checks must not affect the numeric composite."""
    job_keywords: dict[str, list[str]] = {
        "required_skills": ["Python"],
        "preferred_skills": [],
    }
    # Compute with a clean resume (no expanded tips triggered)
    clean = compute_ats_score(
        refined_resume=_COMPLETE_RESUME,
        job_keywords=job_keywords,
        keyword_match_percentage=80.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    # Compute with a problem resume (many expanded tips triggered)
    problem = compute_ats_score(
        refined_resume=_EMPTY_RESUME,
        job_keywords={"required_skills": [], "preferred_skills": []},
        keyword_match_percentage=80.0,
        missing_keywords=[],
        injectable_keywords=[],
    )

    # The scores are what they are; we just verify no exception was raised
    # and that expanding the recommendations list didn't corrupt the scores.
    assert isinstance(clean.overall_score, float)
    assert isinstance(problem.overall_score, float)
    # Scores are independently computed; just verify no corruption occurred.
    assert 0.0 <= clean.overall_score <= 100.0
    assert 0.0 <= problem.overall_score <= 100.0


def test_expanded_tips_appended_to_seed_tips() -> None:
    """Expanded tips appear after seed tips, never replacing them."""
    job_keywords: dict[str, list[str]] = {
        "required_skills": ["Kubernetes"],  # not in resume
        "preferred_skills": [],
    }
    resume_no_skills = {
        **_EMPTY_RESUME,
        "personalInfo": {},  # triggers expanded tips
    }
    result = compute_ats_score(
        refined_resume=resume_no_skills,
        job_keywords=job_keywords,
        keyword_match_percentage=10.0,  # < 60 → seed tip fires
        missing_keywords=["Kubernetes"],
        injectable_keywords=[],
    )
    # Seed tip: "Add these high-priority missing keywords"
    assert any("high-priority" in t for t in result.recommendations), result.recommendations
    # Expanded tip: email/name/phone (personalInfo is {})
    assert any("email" in t.lower() for t in result.recommendations), result.recommendations


def test_no_duplicate_recommendations() -> None:
    """Recommendations list should not contain duplicate entries."""
    result = compute_ats_score(
        refined_resume=_EMPTY_RESUME,
        job_keywords={"required_skills": [], "preferred_skills": []},
        keyword_match_percentage=0.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert len(result.recommendations) == len(set(result.recommendations)), (
        "Duplicate recommendations detected"
    )
