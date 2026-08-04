"""Tests for the Phase 4 review controller state machine."""

from __future__ import annotations

import pytest
from resume_kit_alignment.review import ReviewController
from resume_kit_schemas.analysis import ScoreDelta
from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.provenance import ClaimProvenance, ProvenanceStatus
from resume_kit_schemas.results import ReviewAction, ReviewDecision, ReviewSession


def _changes() -> list[ChangeProposal]:
    return [
        ChangeProposal(
            path="summary",
            action="replace",
            original="Old summary.",
            value="New summary.",
            reason="Matches JD focus.",
        ),
        ChangeProposal(
            path="workExperience[0].description[1]",
            action="replace",
            original="Did stuff.",
            value="Led migration.",
            reason="Adds impact keyword.",
        ),
        ChangeProposal(
            path="skills",
            action="add_skill",
            value="Kubernetes",
            reason="Required by JD.",
        ),
    ]


def _evidence() -> list[CandidateEvidence]:
    return [CandidateEvidence(id="ev1", kind=EvidenceKind.SKILL, content="k8s work")]


def _deltas() -> list[ScoreDelta]:
    return [ScoreDelta(metric="ats.overall", before=60.0, after=75.0, delta=15.0)]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_initialize_positions_at_first_section_without_applying() -> None:
    session = ReviewController.initialize(
        _changes(),
        evidence=_evidence(),
        claim_provenance=[
            ClaimProvenance(claim="Led migration.", status=ProvenanceStatus.SUPPORTED)
        ],
        expected_score_deltas=_deltas(),
    )
    assert session.sections == ["summary", "workExperience", "skills"]
    assert session.current_section == "summary"
    assert session.awaiting_input is True
    assert session.complete is False
    assert session.decisions == []
    # Nothing applied: pending changes retained verbatim.
    assert len(session.pending_changes) == 3
    assert len(session.evidence) == 1
    assert len(session.expected_score_deltas) == 1


def test_initialize_empty_is_immediately_complete() -> None:
    session = ReviewController.initialize([])
    assert session.sections == []
    assert session.current_section is None
    assert session.awaiting_input is False
    assert session.complete is True


# ---------------------------------------------------------------------------
# Blocking / human-input surface
# ---------------------------------------------------------------------------


def test_prompt_blocks_on_unresolved_section() -> None:
    session = ReviewController.initialize(
        _changes(), evidence=_evidence(), expected_score_deltas=_deltas()
    )
    resp = ReviewController.prompt(session)
    assert resp.requires_human_input is True
    assert resp.ok is False
    assert len(resp.questions) == 1  # one change in 'summary'
    q = resp.questions[0]
    assert q.metadata["section"] == "summary"
    assert q.metadata["current_content"] == "Old summary."
    assert q.metadata["proposed_content"] == "New summary."
    assert q.metadata["explanation"] == "Matches JD focus."
    assert q.metadata["evidence_ids"] == ["ev1"]
    assert q.metadata["expected_score_impact"][0]["delta"] == 15.0
    assert "approve" in q.metadata["options"]


def test_prompt_on_complete_session_needs_no_input() -> None:
    session = ReviewController.initialize([])
    resp = ReviewController.prompt(session)
    assert resp.requires_human_input is False
    assert resp.questions == []


# ---------------------------------------------------------------------------
# Decision actions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        ReviewAction.APPROVE,
        ReviewAction.REJECT,
        ReviewAction.EDIT,
        ReviewAction.SKIP,
    ],
)
def test_terminal_actions_advance_section(action: ReviewAction) -> None:
    session = ReviewController.initialize(_changes())
    nxt = ReviewController.apply_decision(
        session, ReviewDecision(section="summary", action=action)
    )
    assert nxt.current_section == "workExperience"
    assert nxt.awaiting_input is True
    assert nxt.complete is False
    assert len(nxt.decisions) == 1
    assert nxt.decisions[0].action == action
    # Original session untouched.
    assert session.current_section == "summary"
    assert session.decisions == []


@pytest.mark.parametrize(
    "action",
    [
        ReviewAction.RETRY,
        ReviewAction.REDUCE_FREEDOM,
        ReviewAction.INCREASE_FREEDOM,
    ],
)
def test_reopen_actions_keep_same_section(action: ReviewAction) -> None:
    session = ReviewController.initialize(_changes())
    nxt = ReviewController.apply_decision(
        session, ReviewDecision(section="summary", action=action, freedom_target=3)
    )
    assert nxt.current_section == "summary"
    assert nxt.awaiting_input is True
    assert nxt.complete is False
    assert len(nxt.decisions) == 1


def test_edit_records_edited_content() -> None:
    session = ReviewController.initialize(_changes())
    nxt = ReviewController.apply_decision(
        session,
        ReviewDecision(
            section="summary", action=ReviewAction.EDIT, edited_content="Human text."
        ),
    )
    assert nxt.decisions[0].edited_content == "Human text."


def test_decision_defaults_to_current_section() -> None:
    session = ReviewController.initialize(_changes())
    nxt = ReviewController.apply_decision(
        session, ReviewDecision(action=ReviewAction.APPROVE)
    )
    assert nxt.decisions[0].section == "summary"
    assert nxt.current_section == "workExperience"


def test_decision_for_wrong_section_rejected() -> None:
    session = ReviewController.initialize(_changes())
    with pytest.raises(ValueError, match="current section"):
        ReviewController.apply_decision(
            session, ReviewDecision(section="skills", action=ReviewAction.APPROVE)
        )


def test_cannot_decide_on_complete_session() -> None:
    session = ReviewController.initialize([])
    with pytest.raises(ValueError, match="completed"):
        ReviewController.apply_decision(
            session, ReviewDecision(action=ReviewAction.APPROVE)
        )


# ---------------------------------------------------------------------------
# No accidental advancement
# ---------------------------------------------------------------------------


def test_retry_does_not_advance_then_terminal_does() -> None:
    session = ReviewController.initialize(_changes())
    # Two retries stay on 'summary'.
    session = ReviewController.apply_decision(
        session, ReviewDecision(section="summary", action=ReviewAction.RETRY)
    )
    session = ReviewController.apply_decision(
        session, ReviewDecision(section="summary", action=ReviewAction.INCREASE_FREEDOM)
    )
    assert session.current_section == "summary"
    assert len(session.decisions) == 2
    # Terminal finally advances.
    session = ReviewController.apply_decision(
        session, ReviewDecision(section="summary", action=ReviewAction.APPROVE)
    )
    assert session.current_section == "workExperience"


def test_full_walk_completes() -> None:
    session = ReviewController.initialize(_changes())
    for section in ["summary", "workExperience", "skills"]:
        assert session.current_section == section
        assert session.complete is False
        session = ReviewController.apply_decision(
            session, ReviewDecision(section=section, action=ReviewAction.APPROVE)
        )
    assert session.current_section is None
    assert session.complete is True
    assert session.awaiting_input is False
    assert len(session.decisions) == 3
    assert ReviewController.prompt(session).requires_human_input is False


# ---------------------------------------------------------------------------
# Non-human-in-loop bypass mode
# ---------------------------------------------------------------------------


def test_resolve_without_human_completes_all_sections() -> None:
    session = ReviewController.initialize(_changes())
    resolved = ReviewController.resolve_without_human(session)
    assert resolved.complete is True
    assert resolved.awaiting_input is False
    assert resolved.current_section is None
    assert [d.section for d in resolved.decisions] == [
        "summary",
        "workExperience",
        "skills",
    ]
    assert all(d.action == ReviewAction.APPROVE for d in resolved.decisions)


def test_resolve_without_human_from_midway() -> None:
    session = ReviewController.initialize(_changes())
    session = ReviewController.apply_decision(
        session, ReviewDecision(section="summary", action=ReviewAction.APPROVE)
    )
    resolved = ReviewController.resolve_without_human(
        session, action=ReviewAction.SKIP
    )
    assert resolved.complete is True
    # summary already decided; remaining two get bypass action.
    assert [d.section for d in resolved.decisions] == [
        "summary",
        "workExperience",
        "skills",
    ]
    assert resolved.decisions[0].action == ReviewAction.APPROVE
    assert resolved.decisions[1].action == ReviewAction.SKIP


def test_resolve_without_human_rejects_non_terminal_action() -> None:
    session = ReviewController.initialize(_changes())
    with pytest.raises(ValueError, match="terminal"):
        ReviewController.resolve_without_human(session, action=ReviewAction.RETRY)


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def test_review_session_serialization_round_trip() -> None:
    session = ReviewController.initialize(
        _changes(), evidence=_evidence(), expected_score_deltas=_deltas()
    )
    session = ReviewController.apply_decision(
        session,
        ReviewDecision(
            section="summary", action=ReviewAction.EDIT, edited_content="Edited."
        ),
    )
    dumped = session.model_dump_json()
    restored = ReviewSession.model_validate_json(dumped)
    assert restored == session
    # Controller continues correctly from restored state.
    nxt = ReviewController.apply_decision(
        restored, ReviewDecision(section="workExperience", action=ReviewAction.APPROVE)
    )
    assert nxt.current_section == "skills"
