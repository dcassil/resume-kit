"""Tests for deterministic preference derivation: tiers, decay, undone weight."""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_feedback import append_preference_pair
from resume_kit_feedback.preferences import (
    MODERATE_THRESHOLD,
    derive_preferences,
)
from resume_kit_schemas import EditFeedback, PreferencePair

NOW = "2026-08-04T00:00:00Z"


def _rec(
    edit_id: str,
    *,
    outcome: str = "accepted",
    timestamp: str = "2026-08-04T00:00:00Z",
    original: str = "Built things",
    proposed: str = "Built scalable services",
    final: str | None = "Built scalable services",
    edit_type: str = "keyword_substitution",
    removed: list[str] | None = None,
) -> EditFeedback:
    return EditFeedback(
        edit_id=edit_id,
        resume_id="r1",
        job_id="j1",
        section="experience",
        edit_type=edit_type,
        original_text=original,
        proposed_text=proposed,
        final_text=final,
        target_terms=["scalable"],
        predicted_ats_gain=0.1,
        confidence=0.8,
        outcome=outcome,  # type: ignore[arg-type]
        removed_terms=removed or [],
        timestamp=timestamp,
    )


def test_empty_log_returns_empty_profile(tmp_path: Path) -> None:
    profile = derive_preferences([], now=NOW, base_path=tmp_path)
    assert profile.accepted_phrases == []
    assert profile.rejected_phrases == []
    assert profile.disliked_patterns == []
    assert profile.confidence == 0.0
    assert profile.max_length_growth is None


def test_persisted_preference_pairs_contribute_confidence(tmp_path: Path) -> None:
    append_preference_pair(
        PreferencePair(
            preferred_candidate="no-edit",
            rejected_candidate="cand-a",
            strength=MODERATE_THRESHOLD,
            timestamp=NOW,
        ),
        base_path=tmp_path,
    )

    profile = derive_preferences([], now=NOW, base_path=tmp_path)

    assert profile.confidence > 0.0
    assert profile.accepted_phrases == []


def test_single_action_never_sets_preference(tmp_path: Path) -> None:
    profile = derive_preferences([_rec("e1")], now=NOW, base_path=tmp_path)
    # One fresh accepted record => weight 1.0 < MODERATE => nothing emitted.
    assert profile.accepted_phrases == []
    assert profile.preferred_tone is None


def test_moderate_tier_emits_preference(tmp_path: Path) -> None:
    records = [_rec(f"e{i}") for i in range(3)]
    profile = derive_preferences(records, now=NOW, base_path=tmp_path)
    # 3 fresh corroborations reach MODERATE => accepted phrases emitted.
    assert "scalable" in profile.accepted_phrases
    assert profile.confidence > 0.0


def test_decay_reduces_weight_below_threshold(tmp_path: Path) -> None:
    # Three corroborations but all very old (> many half-lives) => decayed away.
    old = "2020-01-01T00:00:00Z"
    records = [_rec(f"e{i}", timestamp=old) for i in range(3)]
    profile = derive_preferences(records, now=NOW, base_path=tmp_path)
    assert profile.accepted_phrases == []


def test_undone_weighs_stronger_than_rejected(tmp_path: Path) -> None:
    # Two rejected of type A, two undone of type B; undone reaches MODERATE first.
    rejected = [
        _rec(f"r{i}", outcome="rejected", edit_type="pattern_a", final=None) for i in range(2)
    ]
    undone = [_rec(f"u{i}", outcome="undone", edit_type="pattern_b", final=None) for i in range(2)]
    profile = derive_preferences(rejected + undone, now=NOW, base_path=tmp_path)
    # rejected weight = 2*1.0 = 2.0 < 3.0 (not emitted).
    # undone weight = 2*1.0*2.0 = 4.0 >= 3.0 (emitted).
    assert "pattern_b" in profile.disliked_patterns
    assert "pattern_a" not in profile.disliked_patterns


def test_decay_ordering_recent_outranks_old(tmp_path: Path) -> None:
    # Recent term "alpha" strongly corroborated; old term "omega" less so.
    recent = [_rec(f"a{i}", proposed="alpha", final="alpha", original="") for i in range(4)]
    old = [
        _rec(
            f"o{i}",
            proposed="omega",
            final="omega",
            original="",
            timestamp="2020-01-01T00:00:00Z",
        )
        for i in range(4)
    ]
    profile = derive_preferences(recent + old, now=NOW, base_path=tmp_path)
    assert "alpha" in profile.accepted_phrases
    # Recent alpha ranks before decayed omega if omega even survives.
    assert profile.accepted_phrases[0] == "alpha"


def test_persistence_writes_pretty_json(tmp_path: Path) -> None:
    derive_preferences([_rec(f"e{i}") for i in range(3)], now=NOW, base_path=tmp_path)
    out = tmp_path / "learning" / "preferences.json"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "\n  " in text  # indented / pretty
    data = json.loads(text)
    assert "scalable" in data["accepted_phrases"]


def test_reproducible_for_fixed_inputs(tmp_path: Path) -> None:
    records = [_rec(f"e{i}") for i in range(5)]
    a = derive_preferences(records, now=NOW, base_path=tmp_path / "a")
    b = derive_preferences(records, now=NOW, base_path=tmp_path / "b")
    assert a == b


def test_malformed_timestamp_tolerated(tmp_path: Path) -> None:
    records = [_rec(f"e{i}", timestamp="not-a-date") for i in range(3)]
    profile = derive_preferences(records, now=NOW, base_path=tmp_path)
    # Neutral weight 1.0 each => 3.0 reaches MODERATE, no crash.
    assert "scalable" in profile.accepted_phrases


def test_moderate_threshold_constant_boundary(tmp_path: Path) -> None:
    # Exactly MODERATE_THRESHOLD corroborating fresh records emits.
    n = int(MODERATE_THRESHOLD)
    profile = derive_preferences([_rec(f"e{i}") for i in range(n)], now=NOW, base_path=tmp_path)
    assert "scalable" in profile.accepted_phrases
