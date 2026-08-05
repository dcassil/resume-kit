"""Deterministic Preference-RAG retrieval over the edit-feedback log.

Given a pending edit ``context`` and the history, surfaces the most relevant
past outcomes plus the derived preference profile as a compact, injectable
context block that the improve skills paste into their prompt. No embeddings, no
model, no network — similarity is a transparent, additive score:

- ``+SECTION_WEIGHT`` when the record's ``section`` equals the context section.
- ``+TERM_OVERLAP_WEIGHT * overlap_ratio`` where ``overlap_ratio`` is the
  Jaccard overlap of the context ``target_terms`` and the record's
  ``target_terms`` (0 when either side is empty).
- ``+EDIT_TYPE_WEIGHT`` when the record's ``edit_type`` equals the context
  ``edit_type``.
- ``+AGGRESSIVENESS_WEIGHT * (1 - bucket_distance)`` where ``bucket_distance`` is
  the normalized distance between the two aggressiveness buckets.

Records are ranked by score descending with a stable secondary sort — recency
(newer first, by timestamp) then ``edit_id`` ascending — so a fixed input always
produces identical ordering (NFR-1301). Empty / malformed input yields an empty
context, never a crash.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field
from resume_kit_schemas import EditFeedback, UserPreferenceProfile

# Additive similarity weights. Section and edit_type are the strongest signals;
# term overlap and aggressiveness closeness refine within a section/type.
SECTION_WEIGHT = 3.0
EDIT_TYPE_WEIGHT = 2.0
TERM_OVERLAP_WEIGHT = 2.0
AGGRESSIVENESS_WEIGHT = 1.0

# Ordered aggressiveness buckets; index distance drives bucket closeness.
_AGGRESSIVENESS_BUCKETS = ("minimal", "moderate", "aggressive")

_TERM_RE = re.compile(r"\w+")


class EditContext(BaseModel):
    """The pending edit for which relevant history is retrieved.

    All fields are plain DATA supplied by the caller (the improve skill); no
    clock or model is consulted.
    """

    model_config = ConfigDict(frozen=True)

    section: str = Field(description="Resume section the pending edit targets.")
    target_terms: list[str] = Field(
        default_factory=list, description="Terms the pending edit aims to surface."
    )
    edit_type: str = Field(description="Kind of edit strategy being considered.")
    aggressiveness: str = Field(
        default="moderate",
        description="Intended edit strength: 'minimal', 'moderate', or 'aggressive'.",
    )


class RetrievedEdit(BaseModel):
    """A single past edit ranked as relevant to the pending edit."""

    model_config = ConfigDict(frozen=True)

    edit_id: str = Field(description="Identifier of the past edit.")
    section: str = Field(description="Section the past edit targeted.")
    edit_type: str = Field(description="Edit strategy of the past edit.")
    outcome: str = Field(description="How the user responded to the past edit.")
    original_text: str = Field(description="Text before the past edit.")
    proposed_text: str = Field(description="Text the system proposed.")
    final_text: str | None = Field(
        default=None, description="Text the user kept, if any."
    )
    score: float = Field(description="Transparent additive similarity score.")


class PreferenceContext(BaseModel):
    """The compact, injectable result of Preference-RAG retrieval.

    Contains the top-K accepted and rejected exemplars most similar to the
    pending edit plus a short natural-language ``summary`` the improve skills can
    paste directly. Frozen and deterministic.
    """

    model_config = ConfigDict(frozen=True)

    accepted_exemplars: list[RetrievedEdit] = Field(
        default_factory=list, description="Top-K similar edits the user accepted."
    )
    rejected_exemplars: list[RetrievedEdit] = Field(
        default_factory=list,
        description="Top-K similar edits the user rejected or undid.",
    )
    summary: str = Field(
        default="", description="Compact, injectable preference/context summary."
    )


def _terms(values: list[str]) -> set[str]:
    """Lowercased term set from a list of raw term strings."""
    out: set[str] = set()
    for value in values:
        out.update(match.lower() for match in _TERM_RE.findall(value))
    return out


def _overlap_ratio(a: set[str], b: set[str]) -> float:
    """Jaccard overlap of two term sets; 0 when either side is empty."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _bucket_index(value: str) -> int:
    """Index of an aggressiveness bucket; unknown values map to the middle."""
    key = value.strip().lower()
    if key in _AGGRESSIVENESS_BUCKETS:
        return _AGGRESSIVENESS_BUCKETS.index(key)
    return 1


def _aggressiveness_closeness(context_value: str, record_value: str) -> float:
    """Return ``1 - normalized bucket distance`` in ``[0, 1]``."""
    span = len(_AGGRESSIVENESS_BUCKETS) - 1
    distance = abs(_bucket_index(context_value) - _bucket_index(record_value))
    return 1.0 - (distance / span if span else 0.0)


def _score(context: EditContext, record: EditFeedback) -> float:
    """Transparent additive similarity between the context and a past record."""
    score = 0.0
    if record.section == context.section:
        score += SECTION_WEIGHT
    if record.edit_type == context.edit_type:
        score += EDIT_TYPE_WEIGHT
    score += TERM_OVERLAP_WEIGHT * _overlap_ratio(
        _terms(context.target_terms), _terms(record.target_terms)
    )
    score += AGGRESSIVENESS_WEIGHT * _aggressiveness_closeness(
        context.aggressiveness, _record_aggressiveness(record)
    )
    return score


def _record_aggressiveness(record: EditFeedback) -> str:
    """Infer a record's aggressiveness bucket from its size/edit_distance.

    Deterministic: uses caller-computed ``edit_distance`` when present, else the
    proposed-vs-original length change ratio.
    """
    if record.edit_distance is not None:
        if record.edit_distance >= 0.5:
            return "aggressive"
        if record.edit_distance <= 0.15:
            return "minimal"
        return "moderate"
    if not record.original_text:
        return "aggressive"
    change = abs(len(record.proposed_text) - len(record.original_text)) / len(
        record.original_text
    )
    if change >= 0.5:
        return "aggressive"
    if change <= 0.15:
        return "minimal"
    return "moderate"


def _sort_key(item: tuple[float, EditFeedback]) -> tuple[float, str, str]:
    """Stable ordering: score desc, then recency (newer first), then edit_id asc."""
    score, record = item
    # Ascending sort: negate score for descending; recency key puts newer first;
    # edit_id ascending is the final deterministic tie-break.
    return (-score, _recency_key(record.timestamp), record.edit_id)


def _recency_key(timestamp: str) -> str:
    """Return a key that sorts NEWER timestamps first under ascending order.

    ISO-8601 timestamps sort lexicographically by time; to put newer first under
    an ascending sort we invert each character against a high code point. This is
    deterministic and needs no clock or datetime parsing.
    """
    return "".join(chr(0x10FFFF - ord(ch)) for ch in timestamp)


def retrieve_preference_context(
    context: EditContext,
    records: list[EditFeedback],
    profile: UserPreferenceProfile,
    *,
    k: int = 3,
) -> PreferenceContext:
    """Retrieve the top-K relevant accepted/rejected exemplars + a summary.

    Scores every record by the transparent additive similarity documented in the
    module docstring, keeps only records with a positive score, and splits them
    into accepted (``accepted``/``accepted_modified``) and rejected
    (``rejected``/``undone``) exemplars, each truncated to ``k`` under the stable
    ordering. Builds a compact, injectable ``summary`` string from the profile
    plus the retrieved outcomes. Deterministic; tolerates an empty/malformed log
    (returns an empty context, never crashes).
    """
    limit = max(0, k)
    scored: list[tuple[float, EditFeedback]] = [
        (_score(context, record), record) for record in records
    ]
    scored = [pair for pair in scored if pair[0] > 0.0]
    scored.sort(key=_sort_key)

    accepted: list[RetrievedEdit] = []
    rejected: list[RetrievedEdit] = []
    for score, record in scored:
        exemplar = RetrievedEdit(
            edit_id=record.edit_id,
            section=record.section,
            edit_type=record.edit_type,
            outcome=record.outcome,
            original_text=record.original_text,
            proposed_text=record.proposed_text,
            final_text=record.final_text,
            score=score,
        )
        if record.outcome in ("accepted", "accepted_modified") and len(accepted) < limit:
            accepted.append(exemplar)
        elif record.outcome in ("rejected", "undone") and len(rejected) < limit:
            rejected.append(exemplar)

    summary = _build_summary(context, profile, accepted, rejected)
    return PreferenceContext(
        accepted_exemplars=accepted,
        rejected_exemplars=rejected,
        summary=summary,
    )


def _build_summary(
    context: EditContext,
    profile: UserPreferenceProfile,
    accepted: list[RetrievedEdit],
    rejected: list[RetrievedEdit],
) -> str:
    """Assemble a compact, deterministic, injectable summary block."""
    lines: list[str] = [f"Editing section '{context.section}' ({context.edit_type})."]

    prefs: list[str] = []
    if profile.preferred_tone:
        prefs.append(f"tone={profile.preferred_tone}")
    if profile.preferred_length:
        prefs.append(f"length={profile.preferred_length}")
    if profile.preferred_edit_strength:
        prefs.append(f"strength={profile.preferred_edit_strength}")
    if profile.max_length_growth is not None:
        prefs.append(f"max_growth={profile.max_length_growth:.2f}")
    if prefs:
        lines.append("Preferences: " + ", ".join(prefs) + ".")

    if profile.accepted_phrases:
        lines.append("Keep phrases: " + ", ".join(profile.accepted_phrases) + ".")
    if profile.rejected_phrases:
        lines.append("Avoid phrases: " + ", ".join(profile.rejected_phrases) + ".")
    if profile.disliked_patterns:
        lines.append("Avoid patterns: " + ", ".join(profile.disliked_patterns) + ".")

    if accepted:
        lines.append(f"{len(accepted)} similar past edit(s) were accepted.")
    if rejected:
        lines.append(f"{len(rejected)} similar past edit(s) were rejected/undone.")

    return "\n".join(lines)
