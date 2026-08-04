"""Synonym-aware matching tests for keywords.py (RIT-T-0064).

Proves that keyword/gap comparison routes through the shared
``resume_kit_terms`` normalize + stem + curated-alias matcher and threads the
match KIND (exact | stem | alias:<canonical>) through the outputs.

Lexicon facts these tests rely on (packages/terms .../data/aliases.json):

- ``Kubernetes``: ["k8s"]        → k8s ↔ Kubernetes matches as ``alias``.
- ``mentoring``:  ["mentorship"] → mentorship ↔ mentoring matches as ``alias``.
- ``linting``:    ["eslint"]     → eslint ↔ linting matches as ``alias``.

A genuine non-synonym pair (React vs Vue) must still NOT match.
"""

from __future__ import annotations

from typing import Any

import pytest
from resume_kit_matching.keywords import (
    _match_keyword_in_text,
    analyze_keyword_gaps,
    calculate_keyword_match,
)


def _resume_dict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "",
        "workExperience": [],
        "education": [],
        "personalProjects": [],
        "additional": {},
        "customSections": {},
    }
    base.update(overrides)
    return base


def _jd_keywords(
    *,
    required: list[str] | None = None,
    preferred: list[str] | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "keywords": keywords or [],
    }


# ---------------------------------------------------------------------------
# _match_keyword_in_text — provenance of the primitive
# ---------------------------------------------------------------------------


class TestMatchKeywordInText:
    def test_exact_match_kind(self) -> None:
        result = _match_keyword_in_text("python", "expert in python and sql")
        assert result is not None
        assert result.kind == "exact"

    def test_stem_only_pair_not_accepted(self) -> None:
        # 'go' ↔ 'going' collapse under Snowball stemming, but stem-only
        # matches are intentionally NOT accepted (they would break the
        # whole-term guarantee, e.g. python ↔ pythonic). Only exact + curated
        # alias hits count.
        assert _match_keyword_in_text("go", "going to the office daily") is None
        assert _match_keyword_in_text("python", "pythonic code style") is None

    def test_alias_match_mentorship_to_mentoring(self) -> None:
        result = _match_keyword_in_text("mentorship", "focused on mentoring juniors")
        assert result is not None
        assert result.kind == "alias"
        assert result.canonical == "mentor"

    def test_alias_match_k8s_to_kubernetes(self) -> None:
        result = _match_keyword_in_text("k8s", "deployed on Kubernetes clusters")
        assert result is not None
        assert result.kind == "alias"
        assert result.canonical == "kubernet"

    def test_alias_match_eslint_to_linting(self) -> None:
        result = _match_keyword_in_text("eslint", "set up linting in CI")
        assert result is not None
        assert result.kind == "alias"
        assert result.canonical == "lint"

    def test_genuine_non_match_returns_none(self) -> None:
        # React and Vue are distinct frameworks — not synonyms.
        assert _match_keyword_in_text("react", "we build with vue") is None

    def test_absent_keyword_returns_none(self) -> None:
        assert _match_keyword_in_text("rust", "java and scala only") is None


# ---------------------------------------------------------------------------
# analyze_keyword_gaps — synonym-aware present/absent + matched_keywords
# ---------------------------------------------------------------------------


class TestSynonymGaps:
    def test_alias_equivalent_not_missing_mentorship(self) -> None:
        # JD 'mentorship' present via alias in tailored → not missing.
        tailored = _resume_dict(summary="I love mentoring engineers")
        master = tailored
        jd = _jd_keywords(required=["mentorship"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []
        annotations = {mk.keyword: mk.annotation for mk in result.matched_keywords}
        assert annotations["mentorship"] == "alias:mentor"

    def test_alias_equivalent_not_missing_k8s(self) -> None:
        tailored = _resume_dict(summary="ran workloads on Kubernetes")
        master = tailored
        jd = _jd_keywords(required=["k8s"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []
        assert result.current_match_percentage == pytest.approx(100.0)
        matched = {mk.keyword: mk for mk in result.matched_keywords}
        assert matched["k8s"].kind == "alias"
        assert matched["k8s"].canonical == "kubernet"
        assert matched["k8s"].annotation == "alias:kubernet"

    def test_alias_equivalent_not_missing_eslint(self) -> None:
        tailored = _resume_dict(summary="introduced linting standards")
        master = tailored
        jd = _jd_keywords(required=["eslint"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []
        matched = {mk.keyword: mk for mk in result.matched_keywords}
        assert matched["eslint"].annotation == "alias:lint"

    def test_genuine_non_match_still_missing(self) -> None:
        tailored = _resume_dict(summary="frontend built with vue")
        master = _resume_dict(summary="frontend built with vue")
        jd = _jd_keywords(required=["react"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert "react" in result.missing_keywords
        assert "react" in result.non_injectable_keywords
        assert all(mk.keyword != "react" for mk in result.matched_keywords)

    def test_exact_match_annotation(self) -> None:
        tailored = _resume_dict(summary="python and sql")
        master = tailored
        jd = _jd_keywords(required=["python"])
        result = analyze_keyword_gaps(jd, tailored, master)
        matched = {mk.keyword: mk for mk in result.matched_keywords}
        assert matched["python"].kind == "exact"
        assert matched["python"].annotation == "exact"
        assert matched["python"].canonical is None

    def test_matched_keywords_deterministic_order(self) -> None:
        tailored = _resume_dict(summary="python java sql on kubernetes")
        master = tailored
        jd = _jd_keywords(required=["sql", "python"], keywords=["k8s", "java"])
        first = [mk.keyword for mk in analyze_keyword_gaps(jd, tailored, master).matched_keywords]
        second = [mk.keyword for mk in analyze_keyword_gaps(jd, tailored, master).matched_keywords]
        assert first == second
        assert first == sorted(first)


class TestSynonymCalculateMatch:
    def test_alias_counts_as_present(self) -> None:
        resume = _resume_dict(summary="managed Kubernetes and linting pipelines")
        jd = _jd_keywords(required=["k8s", "eslint"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(100.0)

    def test_non_synonym_not_counted(self) -> None:
        resume = _resume_dict(summary="frontend in vue")
        jd = _jd_keywords(required=["react"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(0.0)
