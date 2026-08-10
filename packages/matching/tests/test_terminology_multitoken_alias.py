"""Regression: terminology alignment surfaces multi-token alias hits (RIT-T-0166).

``terminology.py`` reuses the same token-window lookup as ``keywords.py``, so it
inherited the same limitation: a JD keyword whose resume surface form is a
bigram / hyphenated term never produced a mirror suggestion. This proves the
fix propagates to the suggestion side, and that an unrelated multi-word phrase
does not falsely produce a suggestion.
"""

from __future__ import annotations

from typing import Any

from resume_kit_matching import analyze_terminology_alignment


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


def _jd(
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


def test_bigram_alias_produces_suggestion() -> None:
    # JD wants 'ci'; resume spells 'continuous integration' -> mirror suggestion.
    resume = _resume_dict(summary="owned continuous integration pipelines")
    jd = _jd(required=["ci"])
    result = analyze_terminology_alignment(jd, resume)
    assert len(result) == 1
    sug = result[0]
    assert sug.jd_keyword == "ci"
    assert sug.current_wording == "continuous integration"
    assert sug.canonical == "continu integr"
    assert sug.match_kind == "alias"
    assert sug.locations == ["summary"]


def test_unrelated_multiword_phrase_no_suggestion() -> None:
    resume = _resume_dict(summary="continuous learning and integration tests")
    jd = _jd(required=["ci"])
    assert analyze_terminology_alignment(jd, resume) == []
