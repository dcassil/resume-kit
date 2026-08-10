"""Regression tests for multi-token / hyphenated alias matching (RIT-T-0166).

Before the fix, alias widening in ``keywords.py`` iterated SINGLE whole tokens
of the resume text, so any alias whose resume SURFACE form spans more than one
token could never be assembled and never matched. Only single-token aliases
(``k8s`` -> ``kubernetes``) fired; bigram / hyphenated aliases silently failed.

Lexicon facts these tests rely on (packages/terms .../data/aliases.json):

- ``continuous integration``: ["ci"]           -> bigram surface form.
- ``machine learning``:       ["ml"]           -> bigram surface form.
- ``test-driven development``:["tdd"]          -> hyphenated -> "test driven development".

Each pair proves a JD keyword (the short alias) matches a resume that spells out
the multi-token surface form, while an unrelated multi-word phrase must NOT
falsely match, preserving the curated-synonym (no false positive) guarantee.
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


class TestMultiTokenAliasPrimitive:
    def test_bigram_surface_form_matches_short_alias(self) -> None:
        # JD 'ci'; resume spells the bigram 'continuous integration'.
        result = _match_keyword_in_text(
            "ci", "we ran continuous integration for every merge"
        )
        assert result is not None
        assert result.kind == "alias"
        assert result.canonical == "continu integr"

    def test_hyphenated_surface_form_matches_short_alias(self) -> None:
        # 'test-driven development' normalizes to the 3-token 'test driven
        # development'; JD 'tdd' must still match it.
        result = _match_keyword_in_text(
            "tdd", "practiced test-driven development throughout"
        )
        assert result is not None
        assert result.kind == "alias"

    def test_short_alias_in_resume_matches_bigram_jd_keyword(self) -> None:
        # Direction reversed: JD keyword is the bigram, resume has the short form.
        result = _match_keyword_in_text("machine learning", "shipped ml models")
        assert result is not None
        assert result.kind == "alias"

    def test_unrelated_multiword_phrase_does_not_match(self) -> None:
        # A contiguous multi-word phrase that is NOT an alias of the keyword
        # must not falsely match — the window stays bounded to real alias forms.
        assert (
            _match_keyword_in_text("ci", "continuous learning and integration tests")
            is None
        )
        assert (
            _match_keyword_in_text("ml", "we value machine safety and learning culture")
            is None
        )


class TestMultiTokenAliasGaps:
    def test_bigram_alias_not_missing(self) -> None:
        tailored = _resume_dict(summary="drove continuous integration pipelines")
        master = tailored
        jd = _jd_keywords(required=["ci"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []
        assert result.current_match_percentage == pytest.approx(100.0)
        matched = {mk.keyword: mk for mk in result.matched_keywords}
        assert matched["ci"].kind == "alias"

    def test_unrelated_phrase_still_missing(self) -> None:
        tailored = _resume_dict(summary="continuous learning and integration tests")
        master = _resume_dict(summary="continuous learning and integration tests")
        jd = _jd_keywords(required=["ci"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert "ci" in result.missing_keywords


class TestMultiTokenCalculateMatch:
    def test_bigram_alias_counts_as_present(self) -> None:
        resume = _resume_dict(summary="owned machine learning platform")
        jd = _jd_keywords(required=["ml"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(100.0)
