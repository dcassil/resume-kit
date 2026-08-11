"""Preference-learning domain models.

New resume-kit subsystem (no upstream equivalent). These frozen models are the
shared contracts for deterministic, offline, no-LLM preference learning:

- :class:`EditFeedback` — one append-only record per proposed edit + its outcome.
- :class:`UserPreferenceProfile` — a per-project profile derived from the log.
- :class:`CandidateFeatures` — deterministic signals scored by the heuristic ranker.
- :class:`PreferencePair` — a preferred-vs-rejected comparison learned from outcomes.

All models are frozen (immutable). Timestamps are CALLER-provided ISO strings so
the models themselves never read the clock; determinism is preserved end-to-end.
Single-user, per-project scope: there is intentionally no ``user_id`` field.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EditOutcome = Literal["accepted", "accepted_modified", "rejected", "undone"]
"""How the user responded to a proposed edit."""


class EditFeedbackReasonCode(StrEnum):
    """Structured reason for rejecting or modifying a proposed edit."""

    FABRICATION = "fabrication"
    OVERCLAIM = "overclaim"
    UNSUPPORTED = "unsupported"
    GRAMMAR = "grammar"
    FORMATTING = "formatting"
    NOT_MY_VOICE = "not_my_voice"
    TOO_VERBOSE = "too_verbose"
    TOO_VAGUE = "too_vague"
    WRONG_EMPHASIS = "wrong_emphasis"
    DUPLICATE = "duplicate"
    OTHER = "other"


class EditFeedback(BaseModel):
    """A single append-only record of a proposed edit and the user's outcome.

    Persisted one-per-line to ``resume-kit/learning/edit-feedback.jsonl``. Every
    field is data the caller supplies (including ``timestamp``); the record is
    immutable once constructed so history is never mutated in place.
    """

    model_config = ConfigDict(frozen=True)

    edit_id: str = Field(description="Stable identifier for this edit event.")
    resume_id: str = Field(description="Identifier of the resume the edit applies to.")
    job_id: str = Field(description="Identifier of the job the edit was tailored for.")
    section: str = Field(description="Resume section the edit targets, e.g. 'experience'.")
    edit_type: str = Field(description="Kind of edit strategy, e.g. 'keyword_substitution'.")
    original_text: str = Field(description="Text before the edit was proposed.")
    proposed_text: str = Field(description="Text the system proposed.")
    final_text: str | None = Field(
        default=None,
        description="Text the user kept; None when the edit was rejected or undone.",
    )
    target_terms: list[str] = Field(
        default_factory=list, description="Terms the edit was trying to surface."
    )
    matched_job_requirements: list[str] = Field(
        default_factory=list, description="Job requirement identifiers the edit addresses."
    )
    predicted_ats_gain: float = Field(
        description="Predicted ATS-score gain from applying the edit."
    )
    confidence: float = Field(description="System confidence in the proposal, 0..1.")
    outcome: EditOutcome = Field(description="How the user responded to the proposal.")
    reason_code: EditFeedbackReasonCode | None = Field(
        default=None,
        description="Optional structured reason for rejecting or modifying the edit.",
    )
    reason_note: str | None = Field(
        default=None,
        description="Optional free-text reason supplied by the user.",
    )
    rejection_reason: str | None = Field(
        default=None,
        description="Deprecated legacy free-text reason; accepted for old JSONL records.",
    )
    edit_distance: float | None = Field(
        default=None,
        description="Optional distance between proposed and final text (caller-computed).",
    )
    preserved_terms: list[str] = Field(
        default_factory=list, description="Terms present in both proposed and final text."
    )
    removed_terms: list[str] = Field(
        default_factory=list, description="Terms in proposed text the user removed."
    )
    added_terms: list[str] = Field(
        default_factory=list, description="Terms the user added that were not proposed."
    )
    timestamp: str = Field(
        description="Caller-provided ISO-8601 timestamp of the outcome (never read from a clock)."
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_rejection_reason(cls, data: Any) -> Any:
        """Copy legacy ``rejection_reason`` into ``reason_note`` when needed."""
        if not isinstance(data, dict):
            return data
        if data.get("reason_note") is not None or data.get("rejection_reason") is None:
            return data
        migrated = dict(data)
        migrated["reason_note"] = migrated["rejection_reason"]
        return migrated


class UserPreferenceProfile(BaseModel):
    """A per-project preference profile derived deterministically from the log.

    Populated by the preference-memory task (RIT-T-0086) with confidence
    thresholds + time decay; kept minimal-but-complete here so downstream tasks
    share stable field names. Persisted to ``resume-kit/learning/preferences.json``.
    """

    model_config = ConfigDict(frozen=True)

    preferred_tone: str | None = Field(
        default=None, description="Learned tone preference, e.g. 'concise' or 'impactful'."
    )
    preferred_length: str | None = Field(
        default=None, description="Learned length preference, e.g. 'shorter' or 'detailed'."
    )
    preferred_edit_strength: str | None = Field(
        default=None,
        description="Learned aggressiveness preference, e.g. 'minimal' or 'aggressive'.",
    )
    accepted_phrases: list[str] = Field(
        default_factory=list, description="Phrases the user has repeatedly kept."
    )
    rejected_phrases: list[str] = Field(
        default_factory=list, description="Phrases the user has repeatedly removed."
    )
    disliked_patterns: list[str] = Field(
        default_factory=list, description="Edit patterns the user consistently rejects."
    )
    max_length_growth: float | None = Field(
        default=None,
        description="Learned ceiling on how much text growth the user tolerates.",
    )
    confidence: float = Field(
        default=0.0, description="Aggregate confidence in the profile from observed signals."
    )


class CandidateFeatures(BaseModel):
    """Deterministic per-candidate signals scored by the heuristic ranker.

    Computed from existing scorers (matching/ats) + truth validation; the ranker
    (RIT-T-0088) applies a transparent weighted formula over these signals. Kept
    minimal-but-complete so scorer and ranker agree on field names.
    """

    model_config = ConfigDict(frozen=True)

    ats_gain: float = Field(description="Predicted ATS-score gain for this candidate.")
    keyword_gain: float = Field(description="Net job-keyword coverage gain.")
    unsupported_claim_risk: float = Field(
        description="Risk that the candidate introduces an unsupported claim, 0..1."
    )
    voice_match: float = Field(
        description="How well the candidate matches learned voice/preferences, 0..1."
    )
    length_delta: float = Field(description="Change in text length (final minus original).")
    specificity: float = Field(description="Specificity signal, higher is more specific.")
    repetition: float = Field(description="Repetition penalty signal, higher is more repetitive.")
    section_fit: float = Field(description="How well the candidate fits its section, 0..1.")
    historical_success: float = Field(
        description="Historical acceptance rate for similar edits, 0..1."
    )


class PreferencePair(BaseModel):
    """A preferred-vs-rejected candidate comparison learned from an outcome.

    Stored so ranking is conceptually trained-by-comparison (REQ-1306). The two
    candidates are referenced by identifier; ``strength`` encodes how strong the
    observed preference is.
    """

    model_config = ConfigDict(frozen=True)

    preferred_candidate: str = Field(description="Identifier of the candidate the user preferred.")
    rejected_candidate: str = Field(description="Identifier of the candidate the user rejected.")
    strength: float = Field(description="Strength of the observed preference, higher is stronger.")
    timestamp: str | None = Field(
        default=None,
        description="Optional caller-provided ISO-8601 timestamp for persistence.",
    )


RequirementAnswerValue = Literal["yes", "no", "not_in_context"]
"""The candidate's durable answer to 'do you have this requirement?'."""


class RequirementAnswer(BaseModel):
    """A durable, append-only record of the user's answer to a job requirement.

    Persisted one-per-line to ``resume-kit/learning/requirement-answers.jsonl``
    (extends the RIT-I-0013 learning substrate). Records whether the candidate
    genuinely has a requirement so a future interview can pre-filter items that
    were already answered and never re-ask them.

    Deliberately minimal — exactly five fields, no notes/confidence/decay:

    - ``requirement_key`` — the normalized requirement/term text, produced by the
      shared matching-side normalizer so keys are comparable across runs.
    - ``answer`` — ``yes`` / ``no`` (both durable, global) or ``not_in_context``
      (a ``no`` scoped to this job's coarse context).
    - ``context_tag`` — coarse role/industry tag; populated only for
      ``not_in_context`` so suppression can be context-aware.
    - ``evidence_ref`` — link to the ``CandidateEvidence`` record backing a ``yes``.
    - ``ts`` — caller-provided ISO-8601 timestamp (the model never reads the clock).
    """

    model_config = ConfigDict(frozen=True)

    requirement_key: str = Field(
        description="Normalized requirement/term text (shared matching normalizer)."
    )
    answer: RequirementAnswerValue = Field(
        description="Durable answer: 'yes', 'no', or context-scoped 'not_in_context'."
    )
    context_tag: str | None = Field(
        default=None,
        description="Coarse role/industry tag; set only for 'not_in_context' answers.",
    )
    evidence_ref: str | None = Field(
        default=None,
        description="Optional link to the CandidateEvidence record backing a 'yes'.",
    )
    ts: str = Field(description="Caller-provided ISO-8601 timestamp for persistence.")
