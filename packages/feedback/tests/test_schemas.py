"""Construction + immutability tests for the preference-learning schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import (
    CandidateFeatures,
    EditFeedback,
    EditFeedbackReasonCode,
    PreferencePair,
    UserPreferenceProfile,
)


def _make_edit_feedback(**overrides: object) -> EditFeedback:
    base: dict[str, object] = {
        "edit_id": "e1",
        "resume_id": "r1",
        "job_id": "j1",
        "section": "experience",
        "edit_type": "keyword_substitution",
        "original_text": "Built things",
        "proposed_text": "Built scalable services",
        "final_text": "Built scalable services",
        "target_terms": ["scalable", "services"],
        "matched_job_requirements": ["REQ-1"],
        "predicted_ats_gain": 0.12,
        "confidence": 0.8,
        "outcome": "accepted",
        "rejection_reason": None,
        "edit_distance": 1.0,
        "preserved_terms": ["Built"],
        "removed_terms": ["things"],
        "added_terms": ["scalable", "services"],
        "timestamp": "2026-08-04T00:00:00Z",
    }
    base.update(overrides)
    return EditFeedback(**base)  # type: ignore[arg-type]


def test_edit_feedback_construction() -> None:
    record = _make_edit_feedback()
    assert record.outcome == "accepted"
    assert record.target_terms == ["scalable", "services"]


def test_edit_feedback_defaults() -> None:
    record = EditFeedback(
        edit_id="e",
        resume_id="r",
        job_id="j",
        section="summary",
        edit_type="preserve_original",
        original_text="a",
        proposed_text="a",
        predicted_ats_gain=0.0,
        confidence=0.5,
        outcome="rejected",
        timestamp="2026-08-04T00:00:00Z",
    )
    assert record.final_text is None
    assert record.target_terms == []
    assert record.rejection_reason is None
    assert record.reason_code is None
    assert record.reason_note is None
    assert record.edit_distance is None


def test_edit_feedback_reason_code_values() -> None:
    assert {code.value for code in EditFeedbackReasonCode} >= {
        "fabrication",
        "overclaim",
        "unsupported",
        "grammar",
        "formatting",
        "not_my_voice",
        "too_verbose",
        "too_vague",
        "wrong_emphasis",
        "duplicate",
        "other",
    }


def test_edit_feedback_reason_code_round_trips() -> None:
    record = _make_edit_feedback(
        outcome="rejected",
        final_text=None,
        reason_code=EditFeedbackReasonCode.OVERCLAIM,
        reason_note="true but too inflated",
    )
    again = EditFeedback.model_validate_json(record.model_dump_json())
    assert again.reason_code is EditFeedbackReasonCode.OVERCLAIM
    assert again.reason_note == "true but too inflated"


def test_legacy_rejection_reason_loads_as_reason_note() -> None:
    payload = _make_edit_feedback(
        outcome="rejected",
        final_text=None,
        rejection_reason="not my wording",
    ).model_dump(mode="json")
    payload.pop("reason_code")
    payload.pop("reason_note")

    record = EditFeedback.model_validate(payload)

    assert record.reason_code is None
    assert record.reason_note == "not my wording"
    assert record.rejection_reason == "not my wording"


def test_edit_feedback_rejects_bad_reason_code() -> None:
    with pytest.raises(ValidationError):
        _make_edit_feedback(reason_code="too_sparkly")


def test_edit_feedback_is_frozen() -> None:
    record = _make_edit_feedback()
    with pytest.raises(ValidationError):
        record.section = "skills"


def test_edit_feedback_rejects_bad_outcome() -> None:
    with pytest.raises(ValidationError):
        _make_edit_feedback(outcome="maybe")


def test_user_preference_profile_construction_and_frozen() -> None:
    profile = UserPreferenceProfile(
        preferred_tone="concise",
        accepted_phrases=["led"],
        confidence=3.0,
    )
    assert profile.preferred_tone == "concise"
    assert profile.rejected_phrases == []
    with pytest.raises(ValidationError):
        profile.confidence = 5.0


def test_candidate_features_construction_and_frozen() -> None:
    features = CandidateFeatures(
        ats_gain=0.1,
        keyword_gain=0.2,
        unsupported_claim_risk=0.0,
        voice_match=0.9,
        length_delta=3.0,
        specificity=0.7,
        repetition=0.1,
        section_fit=0.8,
        historical_success=0.6,
    )
    assert features.voice_match == 0.9
    with pytest.raises(ValidationError):
        features.ats_gain = 0.5


def test_preference_pair_construction_and_frozen() -> None:
    pair = PreferencePair(
        preferred_candidate="cand-a",
        rejected_candidate="cand-b",
        strength=2.0,
    )
    assert pair.preferred_candidate == "cand-a"
    with pytest.raises(ValidationError):
        pair.strength = 3.0
