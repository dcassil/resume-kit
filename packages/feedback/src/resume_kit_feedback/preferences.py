"""Deterministic derivation of a :class:`UserPreferenceProfile` from the log.

Turns the append-only edit-feedback log into a per-project preference profile
using two documented, offline mechanisms:

**Confidence tiers (corroboration).** Each candidate preference (an accepted or
rejected phrase, a disliked edit pattern, a tone/length/edit-strength vote)
accumulates a decayed *weight* from the records that corroborate it. A single
raw action can never establish a firm preference; a preference is only emitted
once its corroboration reaches at least the MODERATE tier. Tiers are defined by
effective (decayed) corroborating weight:

- ``weight < WEAK_THRESHOLD`` (1.0): weak — ignored, never emitted.
- ``WEAK_THRESHOLD <= weight < STRONG_THRESHOLD`` (3.0): moderate — emitted.
- ``weight >= STRONG_THRESHOLD`` (7.0): strong — emitted (and raises aggregate
  confidence).

Because a fresh record contributes weight ``1.0`` (decay factor ``1.0`` at zero
age), the thresholds read as the documented "1 weak / 3 moderate / 7+ strong"
count rule when every corroborating record is recent.

**Exponential time decay.** Each corroborating signal is weighted by
``exp(-DECAY_LAMBDA * age_days)`` where ``age_days`` is the difference between
the caller-supplied ``now`` and the record's ``timestamp`` (both ISO-8601
strings parsed as DATA — the clock is never read). ``DECAY_LAMBDA`` is chosen so
a signal decays to ~half its weight after ``HALF_LIFE_DAYS`` (30) days. Ages are
clamped at zero so a future-dated record cannot exceed unit weight.

**Outcome weighting.** ``undone`` outcomes weigh as a stronger negative than an
immediate ``rejected`` (REQ-1306): an undone edit contributes
``UNDONE_WEIGHT_MULTIPLIER`` (2.0) times the base weight to negative signals,
because the user first accepted the edit and only later reversed it — a costlier
signal of dislike than an up-front rejection.

Everything here is pure and deterministic: fixed ``(records, now)`` always
produce an identical profile. Persistence writes pretty, prunable JSON to
``<base_path>/learning/preferences.json``.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from resume_kit_schemas import EditFeedback, PreferencePair, UserPreferenceProfile
from resume_kit_terms import load_alias_lexicon, surface_form

from .log import read_preference_pairs

# Working-dir DATA convention (mirrors log.py); tests pass an explicit base_path.
_DEFAULT_BASE_PATH = Path("resume-kit")
_PROFILE_RELATIVE_PATH = Path("learning") / "preferences.json"

# Confidence tiers, expressed as effective (decayed) corroborating weight. A
# fresh record contributes 1.0, so these read as the "1 / 3 / 7+" count rule.
WEAK_THRESHOLD = 1.0
MODERATE_THRESHOLD = 3.0
STRONG_THRESHOLD = 7.0

# Exponential decay: half a signal's weight is lost every HALF_LIFE_DAYS days.
HALF_LIFE_DAYS = 30.0
DECAY_LAMBDA = math.log(2.0) / HALF_LIFE_DAYS

# An undone edit is a stronger negative than an up-front rejection.
UNDONE_WEIGHT_MULTIPLIER = 2.0

# Seconds per day, for age computation.
_SECONDS_PER_DAY = 86400.0

# A "phrase" candidate is a maximal run of word characters (matches log.py).
_TERM_RE = re.compile(r"\w+")
_ACRONYM_RE = re.compile(r"^[A-Z0-9][A-Z0-9.+#/-]{1,9}$")

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
)

_GENERIC_ABSTRACT_NOUNS = frozenset(
    {
        "area",
        "change",
        "enhancement",
        "fix",
        "fixes",
        "improvement",
        "improvements",
        "issue",
        "issues",
        "quality",
        "solution",
        "solutions",
        "stuff",
        "thing",
        "things",
        "work",
    }
)

_BUILT_IN_TOOL_TERMS = frozenset(
    {
        "chrome",
        "compatibility",
        "edge",
        "firefox",
        "lighthouse",
        "react",
        "ssr",
    }
)


class _DiffTerms(NamedTuple):
    removed: list[str]
    added: list[str]
    preserved: list[str]


def _parse_iso(value: str) -> datetime | None:
    """Parse an ISO-8601 string to an aware/naive datetime, or None if invalid.

    Accepts a trailing ``Z`` (UTC) as an alias for ``+00:00``. Pure: no clock.
    """
    text = value.strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _decay_weight(record_timestamp: str, now: str) -> float:
    """Return ``exp(-lambda * age_days)`` for a record, clamped to ``(0, 1]``.

    ``age_days`` is ``now - record_timestamp`` in days. A malformed timestamp on
    either side yields a neutral, non-decayed weight of ``1.0`` so bad data never
    silently drops a signal (it is still gated by the confidence thresholds).
    Negative ages (future-dated records) are clamped to zero.
    """
    record_dt = _parse_iso(record_timestamp)
    now_dt = _parse_iso(now)
    if record_dt is None or now_dt is None:
        return 1.0
    # Compare on a common footing: if one side is naive, drop tzinfo from both.
    if (record_dt.tzinfo is None) != (now_dt.tzinfo is None):
        record_dt = record_dt.replace(tzinfo=None)
        now_dt = now_dt.replace(tzinfo=None)
    age_seconds = (now_dt - record_dt).total_seconds()
    age_days = max(0.0, age_seconds / _SECONDS_PER_DAY)
    return math.exp(-DECAY_LAMBDA * age_days)


def _terms(text: str | None) -> set[str]:
    """Return the lowercased whole-term set of ``text`` (empty for None)."""
    if not text:
        return set()
    return {match.lower() for match in _TERM_RE.findall(text)}


def _clean_phrase(value: str) -> str | None:
    """Normalize one learned phrase and drop stopword-only candidates."""
    phrase = surface_form(value)
    if not phrase:
        return None
    tokens = [token for token in phrase.split() if token not in _STOPWORDS]
    if not tokens:
        return None
    return " ".join(tokens)


def _clean_terms(values: list[str]) -> list[str]:
    """Return sorted, unique, normalized terms with stopwords removed."""
    cleaned = {_clean_phrase(value) for value in values}
    return sorted(term for term in cleaned if term is not None)


def _record_diff_terms(record: EditFeedback) -> _DiffTerms:
    """Return explicit diff terms, with target-term fallback for old records."""
    removed = _clean_terms(record.removed_terms)
    added = _clean_terms(record.added_terms)
    preserved = _clean_terms(record.preserved_terms)
    if removed or added or preserved:
        return _DiffTerms(removed=removed, added=added, preserved=preserved)

    fallback = _clean_terms(record.target_terms)
    if record.outcome in ("accepted", "accepted_modified"):
        return _DiffTerms(removed=[], added=[], preserved=fallback)
    if record.outcome in ("rejected", "undone"):
        return _DiffTerms(removed=fallback, added=[], preserved=[])
    return _DiffTerms(removed=[], added=[], preserved=[])


def _tier_selected(weight: float) -> bool:
    """A candidate is emitted once its decayed weight reaches the MODERATE tier."""
    return weight >= MODERATE_THRESHOLD


def _sorted_by_weight(weights: dict[str, float]) -> list[str]:
    """Return emitted keys sorted by weight desc, then key asc (stable ties)."""
    selected = [(key, w) for key, w in weights.items() if _tier_selected(w)]
    selected.sort(key=lambda item: (-item[1], item[0]))
    return [key for key, _ in selected]


def _length_bucket(record: EditFeedback) -> str | None:
    """Classify a kept edit as growing/shrinking length, or None if not kept.

    Uses proposed-vs-final length when the edit was kept; a shrink votes for a
    ``shorter`` length preference, growth for ``detailed``.
    """
    if record.outcome not in ("accepted", "accepted_modified"):
        return None
    kept = record.final_text if record.final_text is not None else record.proposed_text
    if kept is None:
        return None
    delta = len(kept) - len(record.original_text)
    if delta < 0:
        return "shorter"
    if delta > 0:
        return "detailed"
    return None


def derive_preferences(
    records: list[EditFeedback],
    *,
    now: str,
    base_path: Path | None = None,
) -> UserPreferenceProfile:
    """Derive a :class:`UserPreferenceProfile` from the edit-feedback log.

    Deterministic and offline. Aggregates the records into accepted/rejected
    phrases, disliked edit patterns, tone/length/edit-strength preferences and a
    ``max_length_growth`` ceiling, applying confidence tiers and exponential time
    decay (see the module docstring for the exact rules). ``now`` and every
    record timestamp are DATA (ISO-8601 strings); the clock is never read.

    Persists the resulting profile as pretty JSON to
    ``<base_path>/learning/preferences.json`` and returns it. Tolerates an empty
    log by returning (and persisting) an empty, zero-confidence profile.
    """
    accepted_phrase_w: dict[str, float] = defaultdict(float)
    rejected_phrase_w: dict[str, float] = defaultdict(float)
    disliked_pattern_w: dict[str, float] = defaultdict(float)
    tone_w: dict[str, float] = defaultdict(float)
    length_w: dict[str, float] = defaultdict(float)
    strength_w: dict[str, float] = defaultdict(float)
    pair_signal_w: dict[str, float] = defaultdict(float)
    specific_over_vague_w: dict[str, float] = defaultdict(float)
    vague_term_w: dict[str, float] = defaultdict(float)
    specific_term_w: dict[str, float] = defaultdict(float)

    # Length-growth samples: (decayed weight, growth ratio) for kept edits.
    growth_samples: list[tuple[float, float]] = []

    for record in records:
        base = _decay_weight(record.timestamp, now)
        diff = _record_diff_terms(record)
        is_negative = record.outcome in ("rejected", "undone")
        neg_weight = base * (UNDONE_WEIGHT_MULTIPLIER if record.outcome == "undone" else 1.0)

        if record.outcome in ("accepted", "accepted_modified"):
            for term in diff.added:
                accepted_phrase_w[term] += base
            for term in diff.preserved:
                accepted_phrase_w[term] += base
            if record.outcome == "accepted_modified":
                for term in diff.removed:
                    rejected_phrase_w[term] += base
            # Edit-strength vote: accepting an aggressive edit votes 'aggressive'.
            strength_w[_edit_strength_vote(record)] += base
            # Tone vote keyed by edit_type family (transparent, no LLM).
            tone_w[_tone_vote(record)] += base
            bucket = _length_bucket(record)
            if bucket is not None:
                length_w[bucket] += base
            # Length-growth ceiling sample.
            kept_text = record.final_text if record.final_text is not None else record.proposed_text
            if kept_text is not None and record.original_text:
                ratio = (len(kept_text) - len(record.original_text)) / len(record.original_text)
                if ratio > 0:
                    growth_samples.append((base, ratio))
            _add_specificity_signals(
                removed=diff.removed,
                added=diff.added,
                weight=base,
                specific_over_vague_w=specific_over_vague_w,
                vague_term_w=vague_term_w,
                specific_term_w=specific_term_w,
            )

        if is_negative:
            # Rejected/undone outcomes dislike the explicit diff terms, never
            # every token in the proposed text.
            source = diff.added or diff.preserved or diff.removed
            for term in source:
                rejected_phrase_w[term] += neg_weight
            # The edit_type itself becomes a disliked pattern signal.
            disliked_pattern_w[record.edit_type] += neg_weight

    for pair in _read_persisted_preference_pairs(base_path):
        signal = _preference_pair_signal(pair, now)
        if signal is not None:
            key, weight = signal
            pair_signal_w[key] += weight
            terms = _preference_pair_terms(pair)
            if terms is not None:
                preferred, rejected = terms
                _add_specificity_signals(
                    removed=[rejected],
                    added=[preferred],
                    weight=weight,
                    specific_over_vague_w=specific_over_vague_w,
                    vague_term_w=vague_term_w,
                    specific_term_w=specific_term_w,
                )

    accepted_phrases = _sorted_by_weight(accepted_phrase_w)
    rejected_phrases = _sorted_by_weight(rejected_phrase_w)
    disliked_patterns = _sorted_by_weight(disliked_pattern_w)
    _extend_with_specificity_patterns(
        accepted_phrases=accepted_phrases,
        disliked_patterns=disliked_patterns,
        specific_over_vague_w=specific_over_vague_w,
        vague_term_w=vague_term_w,
        specific_term_w=specific_term_w,
    )

    preferred_tone = _top_emitted(tone_w)
    preferred_length = _top_emitted(length_w)
    preferred_edit_strength = _top_emitted(strength_w)

    max_length_growth = _max_length_growth(growth_samples)
    confidence = _aggregate_confidence(
        [
            accepted_phrase_w,
            rejected_phrase_w,
            disliked_pattern_w,
            specific_over_vague_w,
            tone_w,
            length_w,
            strength_w,
            pair_signal_w,
        ]
    )

    profile = UserPreferenceProfile(
        preferred_tone=preferred_tone,
        preferred_length=preferred_length,
        preferred_edit_strength=preferred_edit_strength,
        accepted_phrases=accepted_phrases,
        rejected_phrases=rejected_phrases,
        disliked_patterns=disliked_patterns,
        max_length_growth=max_length_growth,
        confidence=confidence,
    )
    _persist_profile(profile, base_path)
    return profile


def _read_persisted_preference_pairs(base_path: Path | None) -> list[PreferencePair]:
    """Read persisted comparison records for preference-memory confidence."""
    return read_preference_pairs(base_path=base_path)


@lru_cache(maxsize=1)
def _known_tool_terms() -> frozenset[str]:
    """Return normalized known tool/technology terms from the shared lexicon."""
    terms = set(_BUILT_IN_TOOL_TERMS)
    for canonical, aliases in load_alias_lexicon().items():
        values = [canonical, *aliases]
        for value in values:
            phrase = _clean_phrase(value)
            if phrase is not None:
                terms.add(phrase)
    return frozenset(terms)


def _specificity_score(term: str) -> int:
    """Score deterministic specificity for a single term, higher is clearer."""
    cleaned = _clean_phrase(term)
    if cleaned is None:
        return 0
    if cleaned in _GENERIC_ABSTRACT_NOUNS:
        return 0
    tokens = cleaned.split()
    if any(char.isdigit() for char in term):
        return 3
    if term in _known_tool_terms() or cleaned in _known_tool_terms():
        return 3
    if _ACRONYM_RE.fullmatch(term.strip()):
        return 3
    if any(token[:1].isupper() for token in term.split()):
        return 2
    if len(tokens) > 1:
        return 2
    return 1


def _is_specificity_upgrade(removed: str, added: str) -> bool:
    """Return whether ``added`` is more specific than ``removed``.

    The heuristic is intentionally explainable and offline: named tools or
    technologies from ``resume-kit-terms`` and a small web-platform seed list,
    proper names/acronyms, digit-bearing metrics, and concrete non-generic nouns
    outrank generic abstract nouns such as "fixes", "improvements", or "quality".
    """
    removed_score = _specificity_score(removed)
    added_score = _specificity_score(added)
    if removed_score <= 0 < added_score:
        return True
    return removed_score < added_score and added_score >= 2


def _add_specificity_signals(
    *,
    removed: list[str],
    added: list[str],
    weight: float,
    specific_over_vague_w: dict[str, float],
    vague_term_w: dict[str, float],
    specific_term_w: dict[str, float],
) -> None:
    """Accumulate specificity-upgrade signal from removed -> added term pairs."""
    matched = False
    for old_term in removed:
        for new_term in added:
            if not _is_specificity_upgrade(old_term, new_term):
                continue
            matched = True
            vague_term_w[old_term] += weight
            specific_term_w[new_term] += weight
    if matched:
        specific_over_vague_w["prefers specific over vague"] += weight


def _extend_with_specificity_patterns(
    *,
    accepted_phrases: list[str],
    disliked_patterns: list[str],
    specific_over_vague_w: dict[str, float],
    vague_term_w: dict[str, float],
    specific_term_w: dict[str, float],
) -> None:
    """Append aggregate specificity patterns once corroboration is sufficient."""
    if not _tier_selected(specific_over_vague_w["prefers specific over vague"]):
        return

    specific_terms = _sorted_by_weight(specific_term_w)
    vague_terms = _sorted_by_weight(vague_term_w)
    if not specific_terms:
        specific_terms = _top_terms(specific_term_w)
    if not vague_terms:
        vague_terms = _top_terms(vague_term_w)

    accepted_pattern = "specific replacements"
    if specific_terms:
        accepted_pattern = f"{accepted_pattern}: {', '.join(specific_terms)}"
    disliked_pattern = "prefers specific over vague"
    if vague_terms:
        disliked_pattern = f"{disliked_pattern}: {', '.join(vague_terms)}"

    if accepted_pattern not in accepted_phrases:
        accepted_phrases.append(accepted_pattern)
    if disliked_pattern not in disliked_patterns:
        disliked_patterns.append(disliked_pattern)


def _top_terms(weights: dict[str, float], *, limit: int = 6) -> list[str]:
    """Return highest-weight nonzero keys for a supported aggregate pattern."""
    selected = [(key, w) for key, w in weights.items() if w > 0.0]
    selected.sort(key=lambda item: (-item[1], item[0]))
    return [key for key, _ in selected[:limit]]


def _preference_pair_signal(pair: PreferencePair, now: str) -> tuple[str, float] | None:
    """Convert a persisted pair into a decayed aggregate confidence signal."""
    weight = max(0.0, pair.strength)
    if weight <= 0.0:
        return None
    if pair.timestamp is not None:
        weight *= _decay_weight(pair.timestamp, now)
    key = f"{pair.preferred_candidate}>{pair.rejected_candidate}"
    return key, weight


def _preference_pair_terms(pair: PreferencePair) -> tuple[str, str] | None:
    """Return term-like preferred/rejected labels, ignoring opaque candidate IDs."""
    preferred = _clean_phrase(pair.preferred_candidate)
    rejected = _clean_phrase(pair.rejected_candidate)
    if preferred is None or rejected is None:
        return None
    opaque_labels = {"no edit", "no change"}
    if preferred in opaque_labels or rejected in opaque_labels:
        return None
    if _looks_like_candidate_id(preferred) or _looks_like_candidate_id(rejected):
        return None
    return preferred, rejected


def _looks_like_candidate_id(value: str) -> bool:
    """Return whether a pair label is an implementation ID, not a phrase."""
    tokens = value.split()
    if not tokens:
        return True
    if tokens[0] in {"cand", "candidate"}:
        return True
    return len(tokens) == 1 and bool(re.fullmatch(r"[a-z]+[0-9]+", tokens[0]))


def _edit_strength_vote(record: EditFeedback) -> str:
    """Map an accepted edit to a strength vote from its edit_distance/size.

    Uses caller-computed ``edit_distance`` when present, else the proposed-vs-
    original length change, to classify the edit as ``minimal`` or ``aggressive``.
    Deterministic; no clock.
    """
    if record.edit_distance is not None:
        return "aggressive" if record.edit_distance >= 0.5 else "minimal"
    if not record.original_text:
        return "aggressive"
    change = abs(len(record.proposed_text) - len(record.original_text)) / len(record.original_text)
    return "aggressive" if change >= 0.5 else "minimal"


def _tone_vote(record: EditFeedback) -> str:
    """Map an accepted edit's ``edit_type`` to a coarse tone vote.

    Transparent keyword bucketing over the edit_type string; no LLM. Unknown
    types vote ``impactful`` (the neutral default for an accepted improvement).
    """
    kind = record.edit_type.lower()
    if any(token in kind for token in ("trim", "concise", "shorten", "tighten")):
        return "concise"
    if any(token in kind for token in ("metric", "quantif", "impact", "result")):
        return "impactful"
    return "impactful"


def _top_emitted(weights: dict[str, float]) -> str | None:
    """Return the single highest-weight key that clears the MODERATE tier.

    Ties break on key ascending for determinism. Returns None if no key clears.
    """
    ranked = _sorted_by_weight(weights)
    return ranked[0] if ranked else None


def _max_length_growth(samples: list[tuple[float, float]]) -> float | None:
    """Return a decayed-weighted tolerated growth ceiling, or None if too few.

    Requires the total decayed weight of positive-growth samples to reach the
    MODERATE tier before emitting; the ceiling is the weighted mean growth ratio,
    which represents the typical growth the user tolerates.
    """
    total_weight = sum(weight for weight, _ in samples)
    if total_weight < MODERATE_THRESHOLD:
        return None
    weighted_sum = sum(weight * ratio for weight, ratio in samples)
    return weighted_sum / total_weight


def _aggregate_confidence(weight_maps: list[dict[str, float]]) -> float:
    """Return an aggregate 0..1 confidence from all corroborated signals.

    Sums the decayed weight of every emitted (>= MODERATE) key and squashes it
    through ``1 - exp(-total / STRONG_THRESHOLD)`` so a single strong-tier
    signal already yields high confidence while an empty log yields ``0.0``.
    """
    total = 0.0
    for weights in weight_maps:
        for weight in weights.values():
            if _tier_selected(weight):
                total += weight
    if total <= 0.0:
        return 0.0
    return 1.0 - math.exp(-total / STRONG_THRESHOLD)


def _persist_profile(profile: UserPreferenceProfile, base_path: Path | None) -> None:
    """Write the profile as pretty, prunable JSON under ``learning/``."""
    root = _DEFAULT_BASE_PATH if base_path is None else base_path
    path = root / _PROFILE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(profile.model_dump(mode="json"), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")
