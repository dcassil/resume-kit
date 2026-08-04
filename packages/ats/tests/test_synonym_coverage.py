"""Synonym-aware coverage tests for the ATS engine (RIT-I-0008).

These tests prove that ``skills_coverage`` and ``keyword_match`` route through the
shared ``resume_kit_terms`` matcher with the exact+alias policy (stemming disabled,
``allow_stem=False``): curated aliases (``mentoring`` ↔ ``mentorship``, ``k8s`` ↔
``Kubernetes``) count as present while stem-only pairs do not, provenance is carried
on ``ATSScore.matched_keywords`` with the shared ``kind`` shape, the composite
weighting stays exactly 0.55/0.25/0.20, and results are deterministic.
"""

from __future__ import annotations

from resume_kit_ats.engine import _compute_skills_coverage, compute_ats_score
from resume_kit_schemas import ATSScore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RESUME_WITH_SYNONYMS: dict[str, object] = {
    "personalInfo": {
        "name": "Sam Rivera",
        "email": "sam@example.com",
        "phone": "555-9876",
    },
    "summary": "Staff engineer focused on mentorship and platform reliability.",
    "workExperience": [
        {
            "title": "Staff Engineer",
            "company": "Globex",
            "years": "2019-Present",
            "description": [
                "Ran k8s clusters in production",
                "Championed mentorship across the org",
            ],
        }
    ],
    "education": [{"institution": "UCLA", "degree": "BS CS", "years": "2013"}],
    "additional": {"technicalSkills": ["Python", "Docker"]},
    "personalProjects": [],
    "sectionMeta": [],
    "customSections": {},
}


# ---------------------------------------------------------------------------
# Skills coverage — synonym awareness
# ---------------------------------------------------------------------------


def test_skills_coverage_counts_alias_k8s_kubernetes() -> None:
    """A JD asking for ``Kubernetes`` matches a resume mentioning ``k8s`` (alias)."""
    job = {"required_skills": ["Kubernetes"], "preferred_skills": []}
    score, matched = _compute_skills_coverage(RESUME_WITH_SYNONYMS, job)
    assert score == 100.0
    assert len(matched) == 1
    assert matched[0].keyword == "Kubernetes"
    assert matched[0].kind == "alias"
    assert matched[0].canonical == "kubernet"
    assert matched[0].annotation == "alias:kubernet"


def test_skills_coverage_counts_alias_mentoring_mentorship() -> None:
    """A JD asking for ``mentoring`` matches a resume saying ``mentorship``.

    Snowball leaves ``mentorship`` un-stemmed (stays ``mentorship``), so this
    pair matches through the curated alias lexicon, not stemming.
    """
    job = {"required_skills": ["mentoring"], "preferred_skills": []}
    score, matched = _compute_skills_coverage(RESUME_WITH_SYNONYMS, job)
    assert score == 100.0
    assert len(matched) == 1
    assert matched[0].keyword == "mentoring"
    assert matched[0].kind == "alias"
    assert matched[0].canonical == "mentor"
    assert matched[0].annotation == "alias:mentor"


def test_skills_coverage_stem_only_variant_not_counted() -> None:
    """Stem-only morphological pairs do NOT match (RIT-I-0008 policy).

    The engines run with ``allow_stem=False`` — Snowball stemming is all-or-
    nothing and over-collapses ``python``/``pythonic`` and ``go``/``going``, so
    the product opts out of stemming and relies solely on the curated alias
    lexicon. ``python`` and ``pythonic`` share only a stem (no alias group), so
    with stemming off they must NOT match — this is the anti-over-match guard,
    and keeps ``ats`` identical to the ``matching`` engine's exact+alias policy.
    """
    resume: dict[str, object] = {
        "summary": "Writing pythonic code and idiomatic patterns daily.",
        "additional": {"technicalSkills": []},
    }
    job = {"required_skills": ["python"], "preferred_skills": []}
    score, matched = _compute_skills_coverage(resume, job)
    assert score == 0.0
    assert matched == []


def test_skills_coverage_exact_still_matches() -> None:
    """Exact skills still score and are annotated ``exact``."""
    job = {"required_skills": ["Python"], "preferred_skills": []}
    score, matched = _compute_skills_coverage(RESUME_WITH_SYNONYMS, job)
    assert score == 100.0
    assert matched[0].kind == "exact"
    assert matched[0].canonical is None


def test_skills_coverage_mixed_kinds_sum() -> None:
    """Exact + alias skills all count toward coverage together."""
    job = {
        "required_skills": ["Python", "mentoring"],
        "preferred_skills": ["Kubernetes", "Rust"],
    }
    score, matched = _compute_skills_coverage(RESUME_WITH_SYNONYMS, job)
    # Python (exact) + mentoring (alias) + Kubernetes (alias) present; Rust absent.
    assert score == 75.0
    kinds = {mk.keyword: mk.kind for mk in matched}
    assert kinds == {"Python": "exact", "mentoring": "alias", "Kubernetes": "alias"}


def test_skills_coverage_no_substring_overmatch() -> None:
    """Whole-term matching must not match a keyword inside a larger word."""
    resume: dict[str, object] = {
        "summary": "Worked on javascripting frameworks and containerization.",
        "additional": {"technicalSkills": []},
    }
    # "java" must NOT match inside "javascripting"; "container" not in "containerization"
    # as a whole word.
    job = {"required_skills": ["java", "container"], "preferred_skills": []}
    score, matched = _compute_skills_coverage(resume, job)
    assert score == 0.0
    assert matched == []


# ---------------------------------------------------------------------------
# Composite score — weights untouched, provenance surfaced
# ---------------------------------------------------------------------------


def test_composite_weights_unchanged_with_synonyms() -> None:
    """Synonym-aware skills_coverage still feeds the 0.55/0.25/0.20 composite."""
    job = {
        "required_skills": ["Python", "mentoring"],
        "preferred_skills": ["Kubernetes", "Rust"],
    }
    result = compute_ats_score(
        refined_resume=RESUME_WITH_SYNONYMS,
        job_keywords=job,
        keyword_match_percentage=80.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    kw = 80.0
    sk = 75.0  # 3 of 4 present via exact/stem/alias
    sec = 100.0  # full resume
    expected = round(kw * 0.55 + sk * 0.25 + sec * 0.20, 1)
    assert result.overall_score == expected
    assert result.sub_scores.keyword_match == 80.0
    assert result.sub_scores.skills_coverage == 75.0
    assert result.sub_scores.section_completeness == 100.0


def test_matched_keywords_surfaced_on_ats_score() -> None:
    """``ATSScore.matched_keywords`` carries provenance for found JD skills."""
    job = {"required_skills": ["Kubernetes"], "preferred_skills": []}
    result = compute_ats_score(
        refined_resume=RESUME_WITH_SYNONYMS,
        job_keywords=job,
        keyword_match_percentage=50.0,
        missing_keywords=[],
        injectable_keywords=[],
    )
    assert isinstance(result, ATSScore)
    assert [mk.annotation for mk in result.matched_keywords] == ["alias:kubernet"]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_score_and_annotations() -> None:
    """Identical inputs yield identical score and identical matched_keywords."""
    job = {
        "required_skills": ["Python", "mentoring"],
        "preferred_skills": ["Kubernetes", "Docker"],
    }
    results = [
        compute_ats_score(
            refined_resume=RESUME_WITH_SYNONYMS,
            job_keywords=job,
            keyword_match_percentage=72.0,
            missing_keywords=[],
            injectable_keywords=[],
        )
        for _ in range(5)
    ]
    first = results[0].model_dump()
    for other in results[1:]:
        assert other.model_dump() == first
