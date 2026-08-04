"""Integration + anti-over-match tests for the synonym-aware engines (RIT-I-0008).

Exercises the deterministic ``matching`` and ``ats`` engines end-to-end against a
synthetic, representative Staff-Full-Stack fixture. The original motivating resume
(``resume-d``) is NOT checked into this repository, so the fixtures below are a
minimal hand-built stand-in that reproduces the same alias-bridge scenarios:

  - resume says ``mentoring`` / JD says ``mentorship``  (alias, canonical ``mentor``)
  - resume says ``Kubernetes`` / JD says ``k8s``        (alias, canonical ``kubernet``)
  - resume says ``linting`` / JD says ``ESLint``        (alias, canonical ``lint``)

Policy under test (product decision, post-spec): stemming is DISABLED. The engines
match on EXACT + ALIAS only. There are therefore NO ``stem`` hits anywhere in these
assertions; ``python``/``pythonic`` must stay distinct (anti-over-match).

The alias pairs above were verified against
``packages/terms/src/resume_kit_terms/data/aliases.json``.
"""

from __future__ import annotations

from typing import Any

from resume_kit_ats.engine import _compute_skills_coverage, compute_ats_score
from resume_kit_matching.keywords import analyze_keyword_gaps, calculate_keyword_match
from resume_kit_schemas import KeywordGapAnalysis, MatchedKeyword

# ---------------------------------------------------------------------------
# Synthetic representative fixtures (resume-d / Staff-FS stand-in)
# ---------------------------------------------------------------------------

# Canonical alias-group normalized forms (verified against aliases.json):
#   mentoring / mentorship -> "mentor"
#   linting   / eslint     -> "lint"
#   Kubernetes / k8s       -> "kubernet"
_CANONICAL_MENTOR = "mentor"
_CANONICAL_LINT = "lint"
_CANONICAL_KUBERNETES = "kubernet"


def _staff_fs_resume() -> dict[str, Any]:
    """A Staff-Full-Stack resume that carries the RESUME-side alias terms.

    Contains ``mentoring``, ``Kubernetes``, and ``linting`` (the resume-side of
    each alias bridge) plus exact skills (``React``, ``TypeScript``). It contains
    ``pythonic`` but NOT ``python`` (to guard against stem over-collapse) and
    ``JavaScript`` but NOT ``Java``.
    """
    return {
        "personalInfo": {
            "name": "Sam Staff",
            "email": "sam@example.com",
            "phone": "555-0100",
        },
        "summary": (
            "Staff full-stack engineer focused on mentoring junior developers, "
            "shipping React front-ends, and writing pythonic tooling."
        ),
        "workExperience": [
            {
                "title": "Staff Engineer",
                "company": "Acme",
                "years": "2020 - Present",
                "description": [
                    "Led mentoring programs across three teams.",
                    "Operated services on Kubernetes in production.",
                    "Enforced code quality with linting in CI.",
                ],
            }
        ],
        "education": [
            {"degree": "BS Computer Science", "institution": "State University"}
        ],
        "additional": {
            "technicalSkills": [
                "React",
                "TypeScript",
                "JavaScript",
                "Kubernetes",
                "linting",
                "mentoring",
                "pythonic",
            ]
        },
    }


def _baseline_resume_without_synonyms() -> dict[str, Any]:
    """The same resume with the synonym-bearing terms stripped entirely.

    Removes ``mentoring``, ``Kubernetes``, and ``linting`` from both text and the
    skills list so the alias bridge cannot fire. Used to prove score direction:
    the synonym-aware resume must score HIGHER than this baseline.
    """
    return {
        "personalInfo": {
            "name": "Sam Staff",
            "email": "sam@example.com",
            "phone": "555-0100",
        },
        "summary": (
            "Staff full-stack engineer shipping React front-ends and writing "
            "pythonic tooling."
        ),
        "workExperience": [
            {
                "title": "Staff Engineer",
                "company": "Acme",
                "years": "2020 - Present",
                "description": [
                    "Delivered features for three teams.",
                ],
            }
        ],
        "education": [
            {"degree": "BS Computer Science", "institution": "State University"}
        ],
        "additional": {
            "technicalSkills": [
                "React",
                "TypeScript",
                "JavaScript",
                "pythonic",
            ]
        },
    }


def _staff_fs_job() -> dict[str, Any]:
    """A Staff-FS job-keywords dict carrying the JD-side alias terms.

    JD-side of each bridge: ``mentorship`` (resume: mentoring), ``k8s`` (resume:
    Kubernetes), ``ESLint`` (resume: linting). Plus an exact-hit skill (``React``)
    and terms designed to STAY gaps for the anti-over-match guards.
    """
    return {
        "required_skills": [
            "mentorship",  # alias -> resume "mentoring"
            "k8s",  # alias -> resume "Kubernetes"
            "ESLint",  # alias -> resume "linting"
            "React",  # exact
        ],
        "preferred_skills": [],
        "keywords": [
            "mentorship",
            "k8s",
            "ESLint",
            "React",
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _annotations_by_keyword(matched: list[MatchedKeyword]) -> dict[str, str]:
    """Map each matched keyword (lowercased) to its provenance annotation."""
    return {mk.keyword.lower(): mk.annotation for mk in matched}


def _assert_no_stem(matched: list[MatchedKeyword]) -> None:
    """Assert none of the matched keywords report a ``stem`` provenance."""
    for mk in matched:
        assert mk.kind != "stem", f"unexpected stem hit: {mk.keyword}"
        assert not mk.annotation.startswith("stem"), mk.annotation


# ---------------------------------------------------------------------------
# 1. Synonym integration
# ---------------------------------------------------------------------------


def test_synonyms_are_not_reported_as_gaps() -> None:
    """mentorship / ESLint / k8s must NOT be gaps when the resume has the alias."""
    resume = _staff_fs_resume()
    job = _staff_fs_job()

    result: KeywordGapAnalysis = analyze_keyword_gaps(job, resume, resume)

    missing_lower = {m.lower() for m in result.missing_keywords}
    assert "mentorship" not in missing_lower
    assert "eslint" not in missing_lower
    assert "k8s" not in missing_lower
    assert "react" not in missing_lower

    # All four JD keywords resolved -> nothing missing at all here.
    assert result.missing_keywords == []
    _assert_no_stem(result.matched_keywords)


def test_synonym_resume_scores_higher_than_baseline() -> None:
    """skills_coverage and keyword_match rise vs a resume lacking the synonyms."""
    job = _staff_fs_job()
    synonym_resume = _staff_fs_resume()
    baseline_resume = _baseline_resume_without_synonyms()

    syn_kw = calculate_keyword_match(synonym_resume, job)
    base_kw = calculate_keyword_match(baseline_resume, job)
    assert syn_kw > base_kw, (syn_kw, base_kw)

    syn_cov, _ = _compute_skills_coverage(synonym_resume, job)
    base_cov, _ = _compute_skills_coverage(baseline_resume, job)
    assert syn_cov > base_cov, (syn_cov, base_cov)


def test_synonym_computation_is_deterministic() -> None:
    """Same inputs -> identical scores AND identical matched_keywords twice."""
    resume = _staff_fs_resume()
    job = _staff_fs_job()

    first = analyze_keyword_gaps(job, resume, resume)
    second = analyze_keyword_gaps(job, resume, resume)

    assert first.current_match_percentage == second.current_match_percentage
    assert first.potential_match_percentage == second.potential_match_percentage
    assert first.missing_keywords == second.missing_keywords
    assert [(m.keyword, m.kind, m.canonical) for m in first.matched_keywords] == [
        (m.keyword, m.kind, m.canonical) for m in second.matched_keywords
    ]

    cov1, mk1 = _compute_skills_coverage(resume, job)
    cov2, mk2 = _compute_skills_coverage(resume, job)
    assert cov1 == cov2
    assert [(m.keyword, m.kind, m.canonical) for m in mk1] == [
        (m.keyword, m.kind, m.canonical) for m in mk2
    ]


# ---------------------------------------------------------------------------
# 2. Anti-over-match guards (must genuinely FAIL if over-matching is introduced)
# ---------------------------------------------------------------------------


def test_react_in_jd_not_satisfied_by_vue() -> None:
    """React must stay a gap when the resume only has Vue."""
    resume: dict[str, Any] = {
        "summary": "Front-end engineer.",
        "additional": {"technicalSkills": ["Vue"]},
    }
    job: dict[str, Any] = {"required_skills": ["React"], "keywords": ["React"]}

    result = analyze_keyword_gaps(job, resume, resume)
    assert {m.lower() for m in result.missing_keywords} == {"react"}
    assert result.matched_keywords == []


def test_absent_kubernetes_stays_a_gap() -> None:
    """Kubernetes stays a gap when the resume has neither Kubernetes nor k8s."""
    resume: dict[str, Any] = {
        "summary": "Backend engineer.",
        "additional": {"technicalSkills": ["Docker"]},
    }
    job: dict[str, Any] = {
        "required_skills": ["Kubernetes"],
        "keywords": ["Kubernetes"],
    }

    result = analyze_keyword_gaps(job, resume, resume)
    assert "kubernetes" in {m.lower() for m in result.missing_keywords}
    assert result.matched_keywords == []


def test_java_not_collapsed_into_javascript() -> None:
    """Java in the JD must NOT be satisfied by JavaScript in the resume."""
    resume: dict[str, Any] = {
        "summary": "Full-stack engineer.",
        "additional": {"technicalSkills": ["JavaScript"]},
    }
    job: dict[str, Any] = {"required_skills": ["Java"], "keywords": ["Java"]}

    result = analyze_keyword_gaps(job, resume, resume)
    assert "java" in {m.lower() for m in result.missing_keywords}
    # JavaScript is not a JD keyword here, so nothing should match.
    assert result.matched_keywords == []


def test_python_and_pythonic_do_not_collapse() -> None:
    """python (JD) must stay a gap when the resume only has pythonic (stem guard)."""
    resume: dict[str, Any] = {
        "summary": "Writes pythonic code.",
        "additional": {"technicalSkills": ["pythonic"]},
    }
    job: dict[str, Any] = {"required_skills": ["python"], "keywords": ["python"]}

    result = analyze_keyword_gaps(job, resume, resume)
    assert "python" in {m.lower() for m in result.missing_keywords}
    assert result.matched_keywords == []
    _assert_no_stem(result.matched_keywords)


# ---------------------------------------------------------------------------
# 3. Match-kind end-to-end
# ---------------------------------------------------------------------------


def test_exact_hit_annotation_is_exact() -> None:
    """An exact JD/resume overlap yields annotation == 'exact'."""
    resume = _staff_fs_resume()
    job = _staff_fs_job()

    result = analyze_keyword_gaps(job, resume, resume)
    annotations = _annotations_by_keyword(result.matched_keywords)
    assert annotations["react"] == "exact"


def test_alias_hits_report_alias_with_canonical() -> None:
    """Alias JD/resume bridges yield annotation == 'alias:<canonical>'."""
    resume = _staff_fs_resume()
    job = _staff_fs_job()

    result = analyze_keyword_gaps(job, resume, resume)
    annotations = _annotations_by_keyword(result.matched_keywords)

    assert annotations["mentorship"] == f"alias:{_CANONICAL_MENTOR}"
    assert annotations["k8s"] == f"alias:{_CANONICAL_KUBERNETES}"
    assert annotations["eslint"] == f"alias:{_CANONICAL_LINT}"

    _assert_no_stem(result.matched_keywords)


# ---------------------------------------------------------------------------
# 4. Cross-package consistency (matching vs ats agree on match + kind)
# ---------------------------------------------------------------------------


def test_matching_and_ats_agree_on_provenance() -> None:
    """Both engines must agree on which shared terms match and their kind."""
    resume = _staff_fs_resume()
    job = _staff_fs_job()

    gap = analyze_keyword_gaps(job, resume, resume)
    _, ats_matched = _compute_skills_coverage(resume, job)

    matching_ann = _annotations_by_keyword(gap.matched_keywords)
    ats_ann = _annotations_by_keyword(ats_matched)

    shared = {"mentorship", "k8s", "eslint", "react"}
    for term in shared:
        assert term in matching_ann, term
        assert term in ats_ann, term
        assert matching_ann[term] == ats_ann[term], (
            term,
            matching_ann[term],
            ats_ann[term],
        )

    _assert_no_stem(gap.matched_keywords)
    _assert_no_stem(ats_matched)


def test_full_ats_score_is_synonym_aware_and_deterministic() -> None:
    """compute_ats_score exposes synonym-aware matched_keywords, no stem hits."""
    resume = _staff_fs_resume()
    job = _staff_fs_job()

    gap = analyze_keyword_gaps(job, resume, resume)
    kw_pct = calculate_keyword_match(resume, job)

    score_a = compute_ats_score(
        resume,
        job,
        kw_pct,
        gap.non_injectable_keywords,
        gap.injectable_keywords,
    )
    score_b = compute_ats_score(
        resume,
        job,
        kw_pct,
        gap.non_injectable_keywords,
        gap.injectable_keywords,
    )

    assert score_a.overall_score == score_b.overall_score
    assert [(m.keyword, m.kind, m.canonical) for m in score_a.matched_keywords] == [
        (m.keyword, m.kind, m.canonical) for m in score_b.matched_keywords
    ]
    _assert_no_stem(score_a.matched_keywords)

    ann = _annotations_by_keyword(score_a.matched_keywords)
    assert ann["mentorship"] == f"alias:{_CANONICAL_MENTOR}"
    assert ann["react"] == "exact"
