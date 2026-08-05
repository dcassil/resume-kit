"""Explainable, pluggable ranking of candidate edits.

Defines the :class:`Ranker` protocol (so a learned ranker can later replace the
heuristic without touching callers) and :class:`HeuristicRanker`, a transparent
multi-objective scorer over :class:`~resume_kit_schemas.CandidateFeatures`.

Two invariants are load-bearing:

* **Truth hard-block** — any candidate whose ``unsupported_claim_risk`` reaches
  the truth-gate failure threshold is EXCLUDED before scoring. The ranker can
  never surface a truth-failing candidate regardless of how strong its other
  features are (REQ-1305 / NFR-1303).
* **Multi-objective** — the score balances predicted acceptance, ATS gain,
  fact-support, readability, and voice with documented weights; it is never
  acceptance alone.

Everything is pure and deterministic: fixed inputs yield identical scores,
ordering, and reason strings. No clock, no network, no LLM, no random.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from resume_kit_schemas import CandidateFeatures, UserPreferenceProfile

from .features import Candidate, FeatureContext, extract_features

# ---------------------------------------------------------------------------
# Truth hard-block threshold.
# ---------------------------------------------------------------------------
# A candidate-only truth-gate failure sets unsupported_claim_risk to exactly
# 1.0 (see features._unsupported_claim_risk). Any candidate at or above this
# threshold is excluded before scoring — this is the safety-critical hard block.
TRUTH_BLOCK_THRESHOLD = 1.0

# ---------------------------------------------------------------------------
# Feature normalization bounds.
# ---------------------------------------------------------------------------
# ats_gain / keyword_gain come back on a 0..100 point scale; divide by this to
# land them in roughly 0..1 so they compose with the already-normalized signals.
_POINT_SCALE = 100.0
# length_delta is unbounded characters; treat this many characters of growth as
# a "full" readability penalty when normalizing.
_LENGTH_PENALTY_SCALE = 200.0

# ---------------------------------------------------------------------------
# Default multi-objective weights (sum of magnitudes documented below).
# ---------------------------------------------------------------------------
# Positive weights reward a contribution; negative weights penalize it. These
# are TRANSPARENT and overridable per HeuristicRanker instance.
#
#   acceptance  (historical_success) 0.25  — predicted acceptance, never alone
#   ats         (ats_gain)           0.20  — ATS composite gain
#   keyword     (keyword_gain)       0.15  — job-keyword coverage gain
#   fact        (unsupported risk)  -0.15  — soft fact-support penalty
#   voice       (voice_match)        0.10  — learned voice/preference match
#   specificity (specificity)        0.08  — concrete, quantified detail
#   section_fit (section_fit)        0.07  — shape fits the target section
#   repetition  (repetition)        -0.10  — readability penalty
#   length      (length_delta)      -0.05  — bloat/readability penalty
#
# Acceptance + ats + keyword + voice + specificity + section_fit are the upside;
# fact + repetition + length are the guardrails. No single objective dominates.
DEFAULT_WEIGHTS: dict[str, float] = {
    "acceptance": 0.25,
    "ats": 0.20,
    "keyword": 0.15,
    "fact": -0.15,
    "voice": 0.10,
    "specificity": 0.08,
    "section_fit": 0.07,
    "repetition": -0.10,
    "length": -0.05,
}


class RankedCandidate(BaseModel):
    """A scored candidate plus its features and a human-readable explanation."""

    model_config = ConfigDict(frozen=True)

    candidate: Candidate = Field(description="The candidate that was scored.")
    features: CandidateFeatures = Field(description="Features extracted for the candidate.")
    score: float = Field(description="Weighted multi-objective score; higher ranks first.")
    reason: str = Field(description="Explanation naming the top positive/negative drivers.")


@runtime_checkable
class Ranker(Protocol):
    """Pluggable ranking contract callers depend on (NFR-1302).

    A learned ranker can replace :class:`HeuristicRanker` without changing any
    caller, provided it honors the truth hard-block: a truth-failing candidate
    must never appear in the returned list.
    """

    def rank(
        self,
        candidates: list[Candidate],
        context: FeatureContext,
        *,
        profile: UserPreferenceProfile,
    ) -> list[RankedCandidate]:
        """Return truth-passing candidates, best first, each with a reason."""
        ...


# Human-readable labels for each weighted term, used in reason strings.
_CONTRIBUTION_LABELS: dict[str, str] = {
    "acceptance": "historical acceptance",
    "ats": "ATS gain",
    "keyword": "keyword gain",
    "fact": "fact-support risk",
    "voice": "voice match",
    "specificity": "specificity",
    "section_fit": "section fit",
    "repetition": "repetition",
    "length": "length growth",
}


class HeuristicRanker:
    """Transparent additive weighted ranker over normalized features.

    The score is ``sum(weight[k] * normalized_feature[k])`` across the objectives
    in :data:`DEFAULT_WEIGHTS`. Each candidate's reason string lists the largest
    positive and negative contributors, so every suggestion is explainable.
    Truth-failing candidates are excluded before any scoring occurs.
    """

    def __init__(
        self,
        *,
        weights: dict[str, float] | None = None,
        truth_block_threshold: float = TRUTH_BLOCK_THRESHOLD,
    ) -> None:
        self._weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
        self._truth_block_threshold = truth_block_threshold

    def _normalized_contributions(self, features: CandidateFeatures) -> dict[str, float]:
        """Map raw features onto the weighted, normalized objective terms.

        Each returned value is ``weight * normalized_feature`` so it is directly
        the term's signed contribution to the total score.
        """
        normalized: dict[str, float] = {
            "acceptance": features.historical_success,
            "ats": _clamp01(features.ats_gain / _POINT_SCALE),
            "keyword": _clamp01(features.keyword_gain / _POINT_SCALE),
            # Soft fact-support penalty; the hard block already removed failures.
            "fact": _clamp01(features.unsupported_claim_risk),
            "voice": features.voice_match,
            "specificity": features.specificity,
            "section_fit": features.section_fit,
            "repetition": features.repetition,
            # Only growth is penalized; shrinking text is not rewarded here.
            "length": _clamp01(max(0.0, features.length_delta) / _LENGTH_PENALTY_SCALE),
        }
        return {key: self._weights[key] * value for key, value in normalized.items()}

    def _score_and_reason(self, features: CandidateFeatures) -> tuple[float, str]:
        contributions = self._normalized_contributions(features)
        score = sum(contributions.values())
        reason = _build_reason(contributions)
        return score, reason

    def rank(
        self,
        candidates: list[Candidate],
        context: FeatureContext,
        *,
        profile: UserPreferenceProfile,
    ) -> list[RankedCandidate]:
        """Score truth-passing candidates and return them best-first.

        Candidates failing the truth gate (``unsupported_claim_risk >=``
        threshold) are dropped before scoring — the hard block. Ordering is
        deterministic: descending score, with ties broken by ``candidate_id`` so
        identical inputs always yield an identical list.
        """
        ranked: list[RankedCandidate] = []
        for candidate in candidates:
            features = extract_features(candidate, context, profile=profile)
            if features.unsupported_claim_risk >= self._truth_block_threshold:
                # HARD BLOCK: a truth-failing candidate can never be surfaced.
                continue
            score, reason = self._score_and_reason(features)
            ranked.append(
                RankedCandidate(
                    candidate=candidate,
                    features=features,
                    score=score,
                    reason=reason,
                )
            )
        # Stable, deterministic ordering: highest score first, id as tie-break.
        ranked.sort(key=lambda item: (-item.score, item.candidate.candidate_id))
        return ranked


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _build_reason(contributions: dict[str, float]) -> str:
    """Compose an explanation naming the top positive and negative drivers.

    Deterministic: contributors are ordered by descending magnitude with the
    objective key as a stable tie-break, then rendered with their labels.
    """
    positives = sorted(
        ((k, v) for k, v in contributions.items() if v > 0),
        key=lambda kv: (-kv[1], kv[0]),
    )
    negatives = sorted(
        ((k, v) for k, v in contributions.items() if v < 0),
        key=lambda kv: (kv[1], kv[0]),
    )

    parts: list[str] = []
    if positives:
        top_pos = ", ".join(
            f"{_CONTRIBUTION_LABELS[k]} (+{v:.3f})" for k, v in positives[:3]
        )
        parts.append(f"boosted by {top_pos}")
    if negatives:
        top_neg = ", ".join(
            f"{_CONTRIBUTION_LABELS[k]} ({v:.3f})" for k, v in negatives[:3]
        )
        parts.append(f"reduced by {top_neg}")
    if not parts:
        return "no notable feature contributions"
    return "; ".join(parts)
