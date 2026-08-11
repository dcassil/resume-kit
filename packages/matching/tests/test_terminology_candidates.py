"""Tests for the conservative fuzzy terminology-candidate PROPOSER (RIT-T-0165).

The closed alias lexicon can only mirror pairs it already knows, so on a fresh
project ``analyze_terminology_alignment`` proposes nothing and coverage is
understated for phrasing differences the resume genuinely satisfies. This
module tests a conservative fuzzy/stemmed PRE-FILTER that PROPOSES candidate
``(jd_keyword, resume_phrase)`` synonym pairs for human + truth-gate review. It
never writes anything and never auto-accepts — it only surfaces plausible
same-skill pairs the deterministic matcher missed.

Invariants under test:

- Only *missing* JD keywords (not already matched exact/stem/alias) are proposed.
- A window must share an anchor token with the keyword AND be near it
  (majority token overlap OR a single small-edit-distance token difference).
- Distinct skills that merely co-occur or share no stem are NOT proposed.
- Output is deterministic and de-duplicated.
"""

from __future__ import annotations

from typing import Any

from resume_kit_matching import propose_terminology_candidates


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


def test_shared_anchor_differing_token_is_proposed() -> None:
    # JD wants 'responsive design'; resume says 'responsive UI'. They share the
    # 'responsive' stem anchor and differ in one token -> a plausible candidate.
    resume = _resume_dict(summary="built responsive UI for the storefront")
    jd = _jd(required=["responsive design"])
    candidates = propose_terminology_candidates(jd, resume)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.jd_keyword == "responsive design"
    assert cand.resume_phrase == "responsive UI"
    assert cand.locations == ["summary"]
    assert cand.reason  # non-empty human-readable reason


def test_single_token_edit_distance_is_proposed() -> None:
    # JD wants 'grafana'; resume misspells 'graphana' -> edit distance 1, and the
    # pair is NOT in the seed lexicon, so it is genuinely missing and proposable.
    resume = _resume_dict(summary="built graphana dashboards")
    jd = _jd(required=["grafana"])
    candidates = propose_terminology_candidates(jd, resume)
    assert [c.resume_phrase for c in candidates] == ["graphana"]
    assert candidates[0].jd_keyword == "grafana"


def test_single_token_already_aliased_is_not_proposed() -> None:
    # 'postgres' ↔ 'postgresql' is already in the seed lexicon, so the keyword is
    # matched (not missing) and the proposer must not re-propose it.
    resume = _resume_dict(summary="ran postgres in production")
    jd = _jd(required=["postgresql"])
    assert propose_terminology_candidates(jd, resume) == []


def test_already_matched_keyword_is_not_proposed() -> None:
    # 'node.js' vs 'node js' already matches via normalize -> not missing.
    resume = _resume_dict(summary="node js services")
    jd = _jd(required=["node.js"])
    assert propose_terminology_candidates(jd, resume) == []


def test_distinct_skill_no_shared_stem_is_not_proposed() -> None:
    # JD wants 'kubernetes'; resume mentions only unrelated words -> no anchor.
    resume = _resume_dict(summary="managed marketing campaigns and budgets")
    jd = _jd(required=["kubernetes"])
    assert propose_terminology_candidates(jd, resume) == []


def test_shared_common_token_but_low_overlap_is_not_proposed() -> None:
    # 'web performance' vs 'web design team' share only 'web' but overlap is
    # too low and the remaining tokens are unrelated -> conservative: skip.
    resume = _resume_dict(summary="led the web design team")
    jd = _jd(required=["web performance"])
    assert propose_terminology_candidates(jd, resume) == []


def test_hyphen_space_variant_missing_is_not_proposed() -> None:
    # JD 'mobile web'; resume 'mobile-web application'. Hyphen/space fold makes
    # these normalize the same, so they ALREADY match -> not a candidate.
    resume = _resume_dict(summary="shipped a mobile-web application")
    jd = _jd(required=["mobile web"])
    assert propose_terminology_candidates(jd, resume) == []


def test_output_is_deterministic_and_deduped() -> None:
    resume = _resume_dict(
        summary="responsive UI work",
        workExperience=[{"description": ["more responsive UI work"]}],
    )
    jd = _jd(required=["responsive design"], keywords=["responsive design"])
    candidates = propose_terminology_candidates(jd, resume)
    # One logical pair, deduped across the duplicated JD keyword; both locations
    # are recorded, sorted.
    assert len(candidates) == 1
    assert candidates[0].jd_keyword == "responsive design"
    assert candidates[0].locations == [
        "summary",
        "workExperience[0].description[0]",
    ]


def test_proposals_never_carry_confirmation() -> None:
    # The proposer only PROPOSES; every candidate is unconfirmed by construction.
    resume = _resume_dict(summary="built responsive UI")
    jd = _jd(required=["responsive design"])
    candidates = propose_terminology_candidates(jd, resume)
    assert candidates
    assert all(c.confirmed is False for c in candidates)
