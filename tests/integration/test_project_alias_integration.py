"""Integration tests proving project-added domain synonyms match end-to-end (RIT-I-0009).

Exercises the full pipeline: a domain synonym pair ABSENT from the packaged seed
lexicon is added via a project alias JSON file and makes a previously-missed JD
keyword match in both the ``matching`` and ``ats`` engines, and at the facade
surface layer. All seed-only baseline assertions confirm the gap genuinely exists
before the project file is introduced, so the test proves a real effect rather
than a pre-existing match.

Fabricated pair under test (not in aliases.json seed):
  canonical: ``"zephyrflow"``  (resume-side term)
  alias:     ``"zflow"``       (JD-side term)

Neither term appears in
``packages/terms/src/resume_kit_terms/data/aliases.json``, so the baseline
genuinely misses "zflow" without a project file.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest
from resume_kit_ats.engine import _compute_skills_coverage, compute_ats_score
from resume_kit_facade.alias_scope import use_alias_file
from resume_kit_facade.capabilities import check_resume_ats, identify_resume_gaps
from resume_kit_facade.models import (
    CapabilityOptions,
    CheckResumeAtsRequest,
    IdentifyResumeGapsRequest,
)
from resume_kit_matching.keywords import analyze_keyword_gaps, calculate_keyword_match
from resume_kit_schemas import JobDescription, KeywordGapAnalysis, MatchedKeyword, ResumeDocument
from resume_kit_schemas.job import Requirement
from resume_kit_terms.aliases import PROJECT_ALIAS_ENV_VAR, LexiconError

# ---------------------------------------------------------------------------
# Fabricated domain pair (absent from seed)
#   canonical "zephyrflow" -> alias "zflow"
# ---------------------------------------------------------------------------

_CANONICAL = "zephyrflow"
_ALIAS = "zflow"
_JUSTIFICATION = "ZFlow is the common shorthand for ZephyrFlow used in field deployments."

# A second fabricated term that does NOT alias to either side, used to ensure
# unrelated keywords stay as gaps.
_UNRELATED_TERM = "turbowidget"

# Two real seed canonicals used for the anti-inflation conflict test.
# "Kubernetes" and "JavaScript" are distinct seed groups; trying to bridge them
# under a single canonical must be rejected.
_SEED_CANONICAL_A = "Kubernetes"
_SEED_ALIAS_A = "k8s"          # already a member of the Kubernetes group
_SEED_CANONICAL_B = "JavaScript"  # a different seed group entirely


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_alias_file(tmp_path: Path) -> Path:
    """Write a valid project alias JSON for the zephyrflow/zflow pair."""
    data: dict[str, Any] = {
        "version": 1,
        "aliases": {_CANONICAL: [_ALIAS]},
        "justifications": {_CANONICAL: _JUSTIFICATION},
    }
    p = tmp_path / "project_aliases.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def scoped_alias_env(project_alias_file: Path) -> Any:
    """Set RESUME_KIT_ALIAS_FILE for a test, then restore the prior value."""
    previous = os.environ.get(PROJECT_ALIAS_ENV_VAR)
    os.environ[PROJECT_ALIAS_ENV_VAR] = str(project_alias_file)
    yield project_alias_file
    if previous is None:
        os.environ.pop(PROJECT_ALIAS_ENV_VAR, None)
    else:
        os.environ[PROJECT_ALIAS_ENV_VAR] = previous


# ---------------------------------------------------------------------------
# Synthetic resume and JD (plain-dict form for matching/ats engines)
# ---------------------------------------------------------------------------


def _resume_with_canonical() -> dict[str, Any]:
    """Resume carrying the resume-side term (zephyrflow) in text and skills."""
    return {
        "personalInfo": {
            "name": "Jordan Dev",
            "email": "jordan@example.com",
            "phone": "555-0200",
        },
        "summary": (
            "Senior platform engineer experienced with zephyrflow deployments "
            "and distributed workflow orchestration."
        ),
        "workExperience": [
            {
                "title": "Platform Engineer",
                "company": "Acme Corp",
                "years": "2021 - Present",
                "description": [
                    "Deployed and operated zephyrflow across three production clusters.",
                    "Built CI automation for workflow validation.",
                ],
            }
        ],
        "education": [
            {"degree": "BS Software Engineering", "institution": "Tech University"}
        ],
        "additional": {
            "technicalSkills": [
                "zephyrflow",
                "Python",
                "Docker",
            ]
        },
    }


def _job_with_alias_keyword() -> dict[str, Any]:
    """JD carrying the JD-side alias (zflow) plus an unrelated gap term."""
    return {
        "required_skills": [_ALIAS, _UNRELATED_TERM],
        "preferred_skills": [],
        "keywords": [_ALIAS, _UNRELATED_TERM],
    }


# ---------------------------------------------------------------------------
# Schema-model forms for facade surface tests
# ---------------------------------------------------------------------------


def _resume_document() -> ResumeDocument:
    """Minimal ResumeDocument carrying 'zephyrflow' in skills and summary."""
    return ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jordan Dev",
                "email": "jordan@example.com",
                "phone": "555-0200",
            },
            "summary": "Senior platform engineer with zephyrflow expertise.",
            "workExperience": [
                {
                    "title": "Platform Engineer",
                    "company": "Acme Corp",
                    "years": "2021 - Present",
                    "description": ["Deployed zephyrflow across production clusters."],
                }
            ],
            "education": [
                {"degree": "BS Software Engineering", "institution": "Tech University"}
            ],
            "additional": {
                "technicalSkills": ["zephyrflow", "Python", "Docker"],
            },
        }
    )


def _job_description() -> JobDescription:
    """JobDescription asking for 'zflow' (the alias) and an unrelated term."""
    return JobDescription(
        title="Senior Platform Engineer",
        requirements=[
            Requirement(text=_ALIAS, keywords=[_ALIAS]),
            Requirement(text=_UNRELATED_TERM, keywords=[_UNRELATED_TERM]),
        ],
        keywords=[_ALIAS, _UNRELATED_TERM],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _missing_lower(result: KeywordGapAnalysis) -> set[str]:
    return {kw.lower() for kw in result.missing_keywords}


def _annotations_by_keyword(matched: list[MatchedKeyword]) -> dict[str, str]:
    return {mk.keyword.lower(): mk.annotation for mk in matched}


# ---------------------------------------------------------------------------
# 1. Baseline (seed-only, no project file)
# ---------------------------------------------------------------------------


def test_baseline_alias_is_a_gap_in_matching() -> None:
    """Without a project file the JD alias 'zflow' is a gap in matching.

    This is the foundational guard: if 'zflow' already matched seed-only, every
    subsequent test would prove nothing.
    """
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    result = analyze_keyword_gaps(job, resume, resume)
    missing = _missing_lower(result)

    assert _ALIAS.lower() in missing, (
        f"Expected '{_ALIAS}' to be a gap in seed-only scoring but it matched. "
        "The fabricated term may have collided with a seed entry — pick a different term."
    )
    matched_kwds = [mk.keyword.lower() for mk in result.matched_keywords]
    assert _ALIAS.lower() not in matched_kwds


def test_baseline_alias_is_a_gap_in_ats() -> None:
    """Without a project file 'zflow' is also a gap in the ATS skills-coverage path."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    _, matched_keywords = _compute_skills_coverage(resume, job)
    matched_kwds_lower = {mk.keyword.lower() for mk in matched_keywords}

    assert _ALIAS.lower() not in matched_kwds_lower, (
        f"Expected '{_ALIAS}' to be absent in seed-only ATS coverage but it matched."
    )


def test_missing_file_is_noop_for_matching() -> None:
    """No env var and no project file yields results identical to seed-only baseline."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    assert PROJECT_ALIAS_ENV_VAR not in os.environ, (
        "RESUME_KIT_ALIAS_FILE is set in the environment, which would invalidate this test."
    )

    result = analyze_keyword_gaps(job, resume, resume)
    kw = calculate_keyword_match(resume, job)

    assert _ALIAS.lower() in _missing_lower(result)
    assert kw < 100.0


def test_missing_file_is_noop_for_ats() -> None:
    """No env var and no project file: ATS skills-coverage does not match 'zflow'."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    assert PROJECT_ALIAS_ENV_VAR not in os.environ

    _, matched_keywords = _compute_skills_coverage(resume, job)
    matched_kwds_lower = {mk.keyword.lower() for mk in matched_keywords}
    assert _ALIAS.lower() not in matched_kwds_lower


# ---------------------------------------------------------------------------
# 2. With project file: alias resolves the previously-missing keyword
# ---------------------------------------------------------------------------


def test_project_alias_resolves_gap_in_matching(scoped_alias_env: Path) -> None:
    """With the project file active, 'zflow' is no longer a gap in matching."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    result = analyze_keyword_gaps(job, resume, resume)
    missing = _missing_lower(result)

    assert _ALIAS.lower() not in missing, (
        f"Expected '{_ALIAS}' to match via project alias but it is still a gap."
    )
    matched_kwds = [mk.keyword.lower() for mk in result.matched_keywords]
    assert _ALIAS.lower() in matched_kwds


def test_project_alias_raises_keyword_match_vs_baseline(
    project_alias_file: Path,
) -> None:
    """keyword_match rises vs seed-only baseline when the project alias file is active."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    # Baseline score (seed-only, no env set in this test)
    baseline_kw = calculate_keyword_match(resume, job)

    # Score with project file (set env directly, distinct path from scoped_alias_env fixture)
    previous = os.environ.get(PROJECT_ALIAS_ENV_VAR)
    os.environ[PROJECT_ALIAS_ENV_VAR] = str(project_alias_file)
    try:
        project_kw = calculate_keyword_match(resume, job)
    finally:
        if previous is None:
            os.environ.pop(PROJECT_ALIAS_ENV_VAR, None)
        else:
            os.environ[PROJECT_ALIAS_ENV_VAR] = previous

    assert project_kw > baseline_kw, (
        f"Expected keyword_match to rise with project alias but got "
        f"baseline={baseline_kw}, project={project_kw}"
    )


def test_project_alias_raises_skills_coverage_vs_baseline(
    project_alias_file: Path,
) -> None:
    """skills_coverage rises vs seed-only baseline when the project alias file is active."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    baseline_cov, _ = _compute_skills_coverage(resume, job)

    previous = os.environ.get(PROJECT_ALIAS_ENV_VAR)
    os.environ[PROJECT_ALIAS_ENV_VAR] = str(project_alias_file)
    try:
        project_cov, _ = _compute_skills_coverage(resume, job)
    finally:
        if previous is None:
            os.environ.pop(PROJECT_ALIAS_ENV_VAR, None)
        else:
            os.environ[PROJECT_ALIAS_ENV_VAR] = previous

    assert project_cov > baseline_cov, (
        f"Expected skills_coverage to rise with project alias but got "
        f"baseline={baseline_cov}, project={project_cov}"
    )


# ---------------------------------------------------------------------------
# 3. Match kind: project-added synonym reports alias:<canonical>
# ---------------------------------------------------------------------------


def test_project_alias_match_kind_is_alias_with_canonical(
    scoped_alias_env: Path,
) -> None:
    """The project-added alias hit reports annotation == 'alias:<canonical>'."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    result = analyze_keyword_gaps(job, resume, resume)
    annotations = _annotations_by_keyword(result.matched_keywords)

    assert _ALIAS.lower() in annotations, (
        f"'{_ALIAS}' not in matched_keywords after project alias activated."
    )

    # The canonical reported must be the normalized form of _CANONICAL.
    # resume_kit_terms.surface_form / normalize folds to lowercase alphanumeric,
    # so "zephyrflow" stays "zephyrflow".
    annotation = annotations[_ALIAS.lower()]
    assert annotation.startswith("alias:"), (
        f"Expected annotation to start with 'alias:' but got {annotation!r}"
    )
    reported_canonical = annotation[len("alias:"):]
    assert reported_canonical == _CANONICAL.lower(), (
        f"Expected canonical {_CANONICAL.lower()!r} but got {reported_canonical!r}"
    )


# ---------------------------------------------------------------------------
# 4. Unrelated keyword stays a gap (no over-inflation)
# ---------------------------------------------------------------------------


def test_unrelated_keyword_stays_a_gap_with_project_alias(
    scoped_alias_env: Path,
) -> None:
    """A JD keyword unrelated to the project alias remains a gap — no inflation."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    result = analyze_keyword_gaps(job, resume, resume)
    missing = _missing_lower(result)

    assert _UNRELATED_TERM.lower() in missing, (
        f"Expected '{_UNRELATED_TERM}' to remain a gap but it matched. "
        "The project alias must not inflate unrelated terms."
    )


# ---------------------------------------------------------------------------
# 5. Determinism: fixed project file produces identical results across two runs
# ---------------------------------------------------------------------------


def test_project_alias_matching_is_deterministic(scoped_alias_env: Path) -> None:
    """Two consecutive calls with the same project file yield identical results."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    first = analyze_keyword_gaps(job, resume, resume)
    second = analyze_keyword_gaps(job, resume, resume)

    assert first.current_match_percentage == second.current_match_percentage
    assert first.potential_match_percentage == second.potential_match_percentage
    assert first.missing_keywords == second.missing_keywords
    assert [(m.keyword, m.kind, m.canonical) for m in first.matched_keywords] == [
        (m.keyword, m.kind, m.canonical) for m in second.matched_keywords
    ]


def test_project_alias_ats_is_deterministic(scoped_alias_env: Path) -> None:
    """ATS scores and matched_keywords are identical across two runs with the same project file."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

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


# ---------------------------------------------------------------------------
# 6. Surface assertion: facade use_alias_file context manager
# ---------------------------------------------------------------------------


def test_facade_use_alias_file_resolves_gap_in_matching(
    project_alias_file: Path,
) -> None:
    """use_alias_file context manager scopes the alias so 'zflow' resolves in matching."""
    resume = _resume_with_canonical()
    job = _job_with_alias_keyword()

    # Baseline: no alias file active
    baseline = analyze_keyword_gaps(job, resume, resume)
    assert _ALIAS.lower() in _missing_lower(baseline)

    # With facade use_alias_file scope
    with use_alias_file(project_alias_file):
        result = analyze_keyword_gaps(job, resume, resume)

    assert _ALIAS.lower() not in _missing_lower(result), (
        "Expected 'zflow' to match inside use_alias_file scope."
    )
    annotations = _annotations_by_keyword(result.matched_keywords)
    assert _ALIAS.lower() in annotations
    assert annotations[_ALIAS.lower()].startswith("alias:")


def test_facade_capability_identify_resume_gaps_with_alias_file(
    project_alias_file: Path,
) -> None:
    """IdentifyResumeGapsRequest.alias_file makes 'zflow' match at the facade surface."""
    resume_doc = _resume_document()
    job_doc = _job_description()

    request_baseline = IdentifyResumeGapsRequest(
        job=job_doc,
        tailored=resume_doc,
        master=resume_doc,
        alias_file=None,
    )
    options = CapabilityOptions(no_llm=True)

    baseline_resp = asyncio.run(identify_resume_gaps(request_baseline, options))
    assert baseline_resp.data is not None
    assert isinstance(baseline_resp.data, KeywordGapAnalysis)
    baseline_gap: KeywordGapAnalysis = baseline_resp.data
    assert _ALIAS.lower() in _missing_lower(baseline_gap), (
        "Expected 'zflow' to be a gap in seed-only facade call."
    )

    request_with_alias = IdentifyResumeGapsRequest(
        job=job_doc,
        tailored=resume_doc,
        master=resume_doc,
        alias_file=project_alias_file,
    )
    alias_resp = asyncio.run(identify_resume_gaps(request_with_alias, options))
    assert alias_resp.data is not None
    assert isinstance(alias_resp.data, KeywordGapAnalysis)
    alias_gap: KeywordGapAnalysis = alias_resp.data
    assert _ALIAS.lower() not in _missing_lower(alias_gap), (
        "Expected 'zflow' to match via project alias at the facade surface."
    )
    ann = _annotations_by_keyword(alias_gap.matched_keywords)
    assert _ALIAS.lower() in ann
    assert ann[_ALIAS.lower()].startswith("alias:")


def test_facade_capability_check_resume_ats_with_alias_file(
    project_alias_file: Path,
) -> None:
    """CheckResumeAtsRequest.alias_file makes the project alias reach the ATS surface."""
    resume_doc = _resume_document()
    job_doc = _job_description()
    options = CapabilityOptions(no_llm=True)

    req_baseline = CheckResumeAtsRequest(
        resume=resume_doc,
        job=job_doc,
        alias_file=None,
    )
    baseline_resp = asyncio.run(check_resume_ats(req_baseline, options))
    assert baseline_resp.data is not None

    # With alias file: skills_coverage should rise
    req_alias = CheckResumeAtsRequest(
        resume=resume_doc,
        job=job_doc,
        alias_file=project_alias_file,
    )
    alias_resp = asyncio.run(check_resume_ats(req_alias, options))
    assert alias_resp.data is not None
    from resume_kit_schemas import ATSScore

    assert isinstance(baseline_resp.data, ATSScore)
    assert isinstance(alias_resp.data, ATSScore)
    baseline_score: ATSScore = baseline_resp.data
    alias_score: ATSScore = alias_resp.data

    assert alias_score.sub_scores.skills_coverage >= baseline_score.sub_scores.skills_coverage, (
        "Expected skills_coverage to rise or remain equal with project alias at facade layer."
    )
    # The alias-aware call must not have MORE missing keywords than baseline.
    assert len(alias_score.missing_keywords) <= len(baseline_score.missing_keywords)


# ---------------------------------------------------------------------------
# 7. Anti-inflation guard: conflict between distinct seed groups raises LexiconError
# ---------------------------------------------------------------------------


def test_project_alias_conflict_between_distinct_seed_groups_raises(
    tmp_path: Path,
) -> None:
    """A project file bridging two DISTINCT seed canonicals raises LexiconError.

    Attempt to alias 'k8s' (already a member of the Kubernetes group) as if it
    belongs to a new group 'JavaScript2'. When the AliasIndex is built, the
    merger detects that 'k8s' already maps to 'kubernet' (Kubernetes) and would
    be forced into a second distinct canonical, triggering the ambiguity guard.
    """
    # Build a project file that re-canonicalizes a seed alias under a new name.
    # "k8s" is already in the Kubernetes group; aliasing it to a different canonical
    # creates a term-maps-to-two-canonicals conflict.
    conflict_data: dict[str, Any] = {
        "version": 1,
        "aliases": {
            # k8s is already the Kubernetes alias; a new canonical for it conflicts
            "zephyrflowK8sConflict": [_SEED_ALIAS_A],
        },
    }
    conflict_file = tmp_path / "conflict_aliases.json"
    conflict_file.write_text(json.dumps(conflict_data), encoding="utf-8")

    from resume_kit_terms import load_effective_alias_index

    with pytest.raises(LexiconError):
        load_effective_alias_index(conflict_file)
