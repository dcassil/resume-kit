"""Characterization tests for the ATS engine seed composite.

These tests lock the upstream seed behavior: weights 0.55/0.25/0.20, rounding
to one decimal place, and the exact field structure of the returned ATSScore.
A failure here means a regression in the ported logic.
"""

from __future__ import annotations

import math

from resume_kit_ats.engine import (
    _compute_section_completeness,
    _compute_skills_coverage,
    compute_ats_score,
)
from resume_kit_schemas import ATSScore, ATSSubScores

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_RESUME: dict[str, object] = {
    "personalInfo": {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
    },
    "summary": "Senior Python engineer with 10 years of experience.",
    "workExperience": [
        {
            "title": "Software Engineer",
            "company": "Acme",
            "years": "2018-Present",
            "description": ["Built REST APIs", "Led a team of 5 engineers"],
        }
    ],
    "education": [{"institution": "MIT", "degree": "BS Computer Science", "years": "2014"}],
    "additional": {"technicalSkills": ["Python", "FastAPI", "PostgreSQL", "Docker"]},
    "personalProjects": [],
    "sectionMeta": [],
    "customSections": {},
}

EMPTY_RESUME: dict[str, object] = {
    "personalInfo": {},
    "summary": "",
    "workExperience": [],
    "education": [],
    "additional": {"technicalSkills": []},
    "personalProjects": [],
    "sectionMeta": [],
    "customSections": {},
}

JOB_KEYWORDS_FULL: dict[str, list[str]] = {
    "required_skills": ["Python", "FastAPI"],
    "preferred_skills": ["Docker", "Kubernetes"],
}

JOB_KEYWORDS_EMPTY: dict[str, list[str]] = {
    "required_skills": [],
    "preferred_skills": [],
}


# ---------------------------------------------------------------------------
# Section completeness — isolated unit
# ---------------------------------------------------------------------------


def test_section_completeness_full_resume() -> None:
    score = _compute_section_completeness(FULL_RESUME)
    assert score == 100.0


def test_section_completeness_empty_resume() -> None:
    score = _compute_section_completeness(EMPTY_RESUME)
    assert score == 0.0


def test_section_completeness_partial() -> None:
    resume = {**EMPTY_RESUME, "summary": "Hello", "workExperience": [{"title": "Dev"}]}
    score = _compute_section_completeness(resume)
    assert score == 50.0  # 2 of 4 sections


def test_section_completeness_text_fallback() -> None:
    """If structured data is empty, fall back to text scanning."""
    text_only: dict[str, str] = {
        "raw": "Summary: objective profile Experience employment Education skills technical"
    }
    score = _compute_section_completeness(text_only)
    # All four pattern groups should match
    assert score == 100.0


# ---------------------------------------------------------------------------
# Skills coverage — isolated unit
# ---------------------------------------------------------------------------


def test_skills_coverage_exact_match() -> None:
    score, _matched = _compute_skills_coverage(FULL_RESUME, JOB_KEYWORDS_FULL)
    # Python, FastAPI, Docker all present; Kubernetes not → 3/4 = 75.0
    assert score == 75.0


def test_skills_coverage_no_jd_skills() -> None:
    score, matched = _compute_skills_coverage(FULL_RESUME, JOB_KEYWORDS_EMPTY)
    assert score == 0.0
    assert matched == []


def test_skills_coverage_no_resume_skills_text_fallback() -> None:
    resume: dict[str, object] = {
        "summary": "Experienced Python developer using FastAPI and Docker.",
        "additional": {"technicalSkills": []},
    }
    score, _matched = _compute_skills_coverage(resume, JOB_KEYWORDS_FULL)
    # Python, FastAPI, Docker found in text; Kubernetes not → 3/4 = 75.0
    assert score == 75.0


def test_skills_coverage_full_match() -> None:
    resume = {
        "additional": {
            "technicalSkills": ["Python", "FastAPI", "Docker", "Kubernetes"]
        }
    }
    score, _matched = _compute_skills_coverage(resume, JOB_KEYWORDS_FULL)
    assert score == 100.0


# ---------------------------------------------------------------------------
# compute_ats_score — composite + field contract
# ---------------------------------------------------------------------------


def test_compute_ats_score_returns_ats_score_instance() -> None:
    result = compute_ats_score(
        refined_resume=FULL_RESUME,
        job_keywords=JOB_KEYWORDS_FULL,
        keyword_match_percentage=80.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert isinstance(result, ATSScore)
    assert isinstance(result.sub_scores, ATSSubScores)


def test_compute_ats_score_seed_weights() -> None:
    """Verify the seed composite matches the upstream 0.55/0.25/0.20 weights."""
    kw = 80.0
    sk, _matched = _compute_skills_coverage(FULL_RESUME, JOB_KEYWORDS_FULL)  # 75.0
    sec = _compute_section_completeness(FULL_RESUME)  # 100.0
    expected_overall = round(kw * 0.55 + sk * 0.25 + sec * 0.20, 1)

    result = compute_ats_score(
        refined_resume=FULL_RESUME,
        job_keywords=JOB_KEYWORDS_FULL,
        keyword_match_percentage=kw,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert result.overall_score == expected_overall
    assert result.sub_scores.keyword_match == round(kw, 1)
    assert result.sub_scores.skills_coverage == round(sk, 1)
    assert result.sub_scores.section_completeness == round(sec, 1)


def test_compute_ats_score_rounding() -> None:
    """Composite should be rounded to one decimal place."""
    result = compute_ats_score(
        refined_resume=FULL_RESUME,
        job_keywords=JOB_KEYWORDS_FULL,
        keyword_match_percentage=33.33,
        missing_keywords=[],
        injectable_keywords=[],
    )
    # Verify one-decimal rounding
    assert result.overall_score == round(result.overall_score, 1)
    assert not math.isnan(result.overall_score)


def test_compute_ats_score_zero_inputs() -> None:
    result = compute_ats_score(
        refined_resume=EMPTY_RESUME,
        job_keywords=JOB_KEYWORDS_EMPTY,
        keyword_match_percentage=0.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert result.overall_score == 0.0
    assert result.sub_scores.keyword_match == 0.0
    assert result.sub_scores.skills_coverage == 0.0
    assert result.sub_scores.section_completeness == 0.0


def test_compute_ats_score_clamps_keyword_match_above_100() -> None:
    result = compute_ats_score(
        refined_resume=FULL_RESUME,
        job_keywords=JOB_KEYWORDS_FULL,
        keyword_match_percentage=150.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert result.sub_scores.keyword_match == 100.0
    assert result.overall_score <= 100.0


def test_compute_ats_score_clamps_keyword_match_below_0() -> None:
    result = compute_ats_score(
        refined_resume=FULL_RESUME,
        job_keywords=JOB_KEYWORDS_FULL,
        keyword_match_percentage=-10.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert result.sub_scores.keyword_match == 0.0


def test_compute_ats_score_missing_keywords_capped_at_10() -> None:
    missing = [f"kw{i}" for i in range(20)]
    result = compute_ats_score(
        refined_resume=EMPTY_RESUME,
        job_keywords=JOB_KEYWORDS_EMPTY,
        keyword_match_percentage=0.0,
        missing_keywords=missing,
        injectable_keywords=[],
    )
    assert len(result.missing_keywords) == 10


def test_compute_ats_score_injectable_keywords_capped_at_10() -> None:
    injectable = [f"kw{i}" for i in range(20)]
    result = compute_ats_score(
        refined_resume=EMPTY_RESUME,
        job_keywords=JOB_KEYWORDS_EMPTY,
        keyword_match_percentage=0.0,
        missing_keywords=[],
        injectable_keywords=injectable,
    )
    assert len(result.injectable_keywords) == 10


def test_compute_ats_score_recommendations_not_empty() -> None:
    result = compute_ats_score(
        refined_resume=FULL_RESUME,
        job_keywords=JOB_KEYWORDS_FULL,
        keyword_match_percentage=80.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert len(result.recommendations) >= 1


# ---------------------------------------------------------------------------
# Regression: changing weights must break this test
# ---------------------------------------------------------------------------


def test_regression_weight_change_detected() -> None:
    """If the weights change from 0.55/0.25/0.20, this test must fail.

    Uses a deterministic input where kw=100, sk=0, sec=0 so the overall
    score equals exactly the keyword_match weight × 100.
    """
    result = compute_ats_score(
        refined_resume=EMPTY_RESUME,
        job_keywords=JOB_KEYWORDS_EMPTY,
        keyword_match_percentage=100.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    # With kw=100, sk=0, sec=0 → overall = 100*0.55 + 0*0.25 + 0*0.20 = 55.0
    assert result.overall_score == 55.0, (
        "Overall score does not match the seed weight of 0.55 for keyword_match. "
        "Weights may have been changed — this is a regression."
    )


def test_regression_section_weight_detected() -> None:
    """If the section_completeness weight changes from 0.20, this test fails."""
    result = compute_ats_score(
        refined_resume=FULL_RESUME,  # sec_score = 100
        job_keywords=JOB_KEYWORDS_EMPTY,  # sk_score = 0
        keyword_match_percentage=0.0,  # kw_score = 0
        missing_keywords=[],
        injectable_keywords=[],
    )
    # overall = 0*0.55 + 0*0.25 + 100*0.20 = 20.0
    assert result.overall_score == 20.0, (
        "Overall score does not match the seed weight of 0.20 for section_completeness."
    )


# ---------------------------------------------------------------------------
# ResumeDocument model acceptance
# ---------------------------------------------------------------------------


def test_compute_ats_score_accepts_resume_document() -> None:
    from resume_kit_schemas.resume import ResumeDocument

    doc = ResumeDocument.model_validate(FULL_RESUME)
    result = compute_ats_score(
        refined_resume=doc,
        job_keywords=JOB_KEYWORDS_FULL,
        keyword_match_percentage=70.0,
        missing_keywords=["Kubernetes"],
        injectable_keywords=[],
    )
    assert isinstance(result, ATSScore)
    assert result.overall_score > 0.0


def test_compute_ats_score_accepts_job_description() -> None:
    from resume_kit_schemas.job import JobDescription, Requirement, RequirementKind

    jd = JobDescription(
        title="Python Engineer",
        requirements=[
            Requirement(text="Python experience", keywords=["Python", "FastAPI"]),
        ],
        qualifications=[
            Requirement(
                text="Docker preferred",
                kind=RequirementKind.PREFERRED,
                keywords=["Docker"],
            ),
        ],
    )
    result = compute_ats_score(
        refined_resume=FULL_RESUME,
        job_keywords=jd,
        keyword_match_percentage=75.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert isinstance(result, ATSScore)
    assert result.sub_scores.skills_coverage > 0.0
