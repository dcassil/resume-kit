"""Phase 4 human-in-the-loop review controller.

A deterministic, interface-agnostic state machine for section-by-section
human review of proposed resume changes (RIT-I-0005 REQ-408). It does NOT
perform generation, apply changes, call any LLM/provider, touch the network,
or read from a terminal/CLI/MCP surface. The only transport-facing types it
emits are :class:`~resume_kit_core.response.InterfaceResponse` and
:class:`~resume_kit_core.response.Question` from ``resume_kit_core``.

New resume-kit code (no upstream port; no attribution marker needed).

State model
-----------
The controller operates over a :class:`~resume_kit_schemas.results.ReviewSession`.
Sections are reviewed strictly in order. For the ``current_section`` the
controller surfaces the current/proposed content, the change explanation,
supporting evidence for material claims, and the expected score impact, then
blocks with ``requires_human_input=True`` until that section receives a
*terminal* decision. ``retry``, ``reduce_freedom`` and ``increase_freedom``
reopen the SAME section (they are non-terminal); ``approve``, ``reject``,
``edit`` and ``skip`` are terminal and advance to the next section.
"""

from __future__ import annotations

from resume_kit_core.response import InterfaceResponse, Question
from resume_kit_schemas.analysis import ScoreDelta
from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.evidence import CandidateEvidence
from resume_kit_schemas.provenance import ClaimProvenance
from resume_kit_schemas.results import ReviewAction, ReviewDecision, ReviewSession

# Actions that terminate review of the current section and advance the cursor.
_TERMINAL_ACTIONS: frozenset[ReviewAction] = frozenset(
    {
        ReviewAction.APPROVE,
        ReviewAction.REJECT,
        ReviewAction.EDIT,
        ReviewAction.SKIP,
    }
)

# Actions that reopen (keep) the current section for another round.
_REOPEN_ACTIONS: frozenset[ReviewAction] = frozenset(
    {
        ReviewAction.RETRY,
        ReviewAction.REDUCE_FREEDOM,
        ReviewAction.INCREASE_FREEDOM,
    }
)


def _section_of(change: ChangeProposal) -> str:
    """Return the top-level section token of a change path.

    ``"workExperience[0].description[1]"`` -> ``"workExperience"``. The section
    is the path prefix up to the first ``.`` or ``[``. Empty paths map to the
    empty string.
    """

    path = change.path
    for index, character in enumerate(path):
        if character in (".", "["):
            return path[:index]
    return path


def _ordered_sections(changes: list[ChangeProposal]) -> list[str]:
    """Deterministic first-seen ordering of sections across ``changes``."""

    seen: dict[str, None] = {}
    for change in changes:
        seen.setdefault(_section_of(change), None)
    return list(seen.keys())


class ReviewController:
    """Deterministic section-by-section human review state machine.

    All methods are pure with respect to their inputs: given the same session
    and decision they always produce the same next session. The controller
    never mutates its arguments in place — it returns fresh
    :class:`ReviewSession` copies so callers can serialize/round-trip state
    between turns.
    """

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    @staticmethod
    def initialize(
        changes: list[ChangeProposal],
        *,
        evidence: list[CandidateEvidence] | None = None,
        claim_provenance: list[ClaimProvenance] | None = None,
        expected_score_deltas: list[ScoreDelta] | None = None,
    ) -> ReviewSession:
        """Build a fresh :class:`ReviewSession` from proposed changes.

        No section is applied or resolved. If there are changes the session is
        positioned at the first section and marked ``awaiting_input``. With no
        changes the session is immediately ``complete``.
        """

        sections = _ordered_sections(changes)
        session = ReviewSession(
            sections=sections,
            current_section=sections[0] if sections else None,
            decisions=[],
            awaiting_input=bool(sections),
            complete=not sections,
            pending_changes=list(changes),
            claim_provenance=list(claim_provenance or []),
            evidence=list(evidence or []),
            expected_score_deltas=list(expected_score_deltas or []),
        )
        return session

    # ------------------------------------------------------------------
    # Human-input surface
    # ------------------------------------------------------------------

    @staticmethod
    def changes_for_section(session: ReviewSession, section: str) -> list[ChangeProposal]:
        """All pending changes whose path belongs to ``section``."""

        return [c for c in session.pending_changes if _section_of(c) == section]

    @classmethod
    def prompt(cls, session: ReviewSession) -> InterfaceResponse[None]:
        """Return the human-input response for the current section.

        When the session is complete (or has no current section) this returns a
        response that requires no input. Otherwise it returns
        ``requires_human_input=True`` with a section-specific
        :class:`Question` per pending change in the current section, carrying
        the current/proposed content, change reason, evidence ids, and expected
        score impact in ``metadata`` so any interface can render the review.
        """

        section = session.current_section
        if session.complete or section is None:
            return InterfaceResponse[None]()

        changes = cls.changes_for_section(session, section)
        deltas = [
            {"metric": d.metric, "before": d.before, "after": d.after, "delta": d.delta}
            for d in session.expected_score_deltas
        ]
        evidence_ids = [ev.id for ev in session.evidence]

        questions: list[Question] = []
        for index, change in enumerate(changes):
            questions.append(
                Question(
                    question_id=f"review:{section}:{index}",
                    text=(
                        f"Review section '{section}': decide on the proposed change "
                        f"at '{change.path}'."
                    ),
                    hint=(
                        "Choose one: approve, reject, edit, retry, reduce_freedom, "
                        "increase_freedom, skip."
                    ),
                    metadata={
                        "section": section,
                        "path": change.path,
                        "action": change.action,
                        "current_content": change.original,
                        "proposed_content": change.value,
                        "explanation": change.reason,
                        "evidence_ids": evidence_ids,
                        "expected_score_impact": deltas,
                        "options": [a.value for a in ReviewAction],
                    },
                )
            )

        if not questions:
            # A section with no concrete change still needs a human gate before
            # advancing; emit a single section-level question.
            questions.append(
                Question(
                    question_id=f"review:{section}",
                    text=f"Review section '{section}'.",
                    hint=(
                        "Choose one: approve, reject, edit, retry, reduce_freedom, "
                        "increase_freedom, skip."
                    ),
                    metadata={
                        "section": section,
                        "expected_score_impact": deltas,
                        "evidence_ids": evidence_ids,
                        "options": [a.value for a in ReviewAction],
                    },
                )
            )

        return InterfaceResponse[None].needs_input(questions)

    # ------------------------------------------------------------------
    # Decision application
    # ------------------------------------------------------------------

    @classmethod
    def apply_decision(
        cls, session: ReviewSession, decision: ReviewDecision
    ) -> ReviewSession:
        """Apply ``decision`` to ``session`` and return the next session.

        The decision must target the current section (or leave
        :attr:`ReviewDecision.section` empty to default to it). Terminal
        actions advance the cursor to the next unreviewed section; reopen
        actions (retry / freedom change) record the decision but keep the
        cursor on the same section. The input session is never mutated.
        """

        if session.complete or session.current_section is None:
            raise ValueError("cannot apply a decision to a completed review session")

        current = session.current_section
        target = decision.section or current
        if target != current:
            raise ValueError(
                f"decision targets section '{target}' but current section is '{current}'"
            )

        # Normalize the stored decision so its section is always explicit.
        recorded = decision.model_copy(update={"section": current})
        decisions = [*session.decisions, recorded]

        if decision.action in _TERMINAL_ACTIONS:
            next_section = cls._next_section(session.sections, current)
            return session.model_copy(
                update={
                    "decisions": decisions,
                    "current_section": next_section,
                    "awaiting_input": next_section is not None,
                    "complete": next_section is None,
                }
            )

        if decision.action in _REOPEN_ACTIONS:
            # Same section stays current; still awaiting input for another round.
            return session.model_copy(
                update={
                    "decisions": decisions,
                    "current_section": current,
                    "awaiting_input": True,
                    "complete": False,
                }
            )

        raise ValueError(f"unsupported review action: {decision.action!r}")

    @staticmethod
    def _next_section(sections: list[str], current: str) -> str | None:
        """Section that follows ``current`` in order, or ``None`` at the end."""

        try:
            position = sections.index(current)
        except ValueError:
            return None
        following = position + 1
        if following < len(sections):
            return sections[following]
        return None

    # ------------------------------------------------------------------
    # Non-human-in-loop (bypass) mode
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_without_human(
        session: ReviewSession, *, action: ReviewAction = ReviewAction.APPROVE
    ) -> ReviewSession:
        """Resolve every remaining section with ``action`` in one shot.

        Produces a fully resolved session (``complete=True``, no longer
        awaiting input) that the orchestrator can embed in
        ``AlignmentResult.review_state`` when human review is disabled. The
        supplied ``action`` must be terminal (default ``approve``); reopen
        actions would never terminate and are rejected.
        """

        if action not in _TERMINAL_ACTIONS:
            raise ValueError(
                f"bypass action must be terminal, got {action.value!r}"
            )

        decisions = list(session.decisions)
        start = session.current_section
        remaining: list[str] = (
            [] if start is None else session.sections[session.sections.index(start):]
        )

        for section in remaining:
            decisions.append(ReviewDecision(section=section, action=action))

        return session.model_copy(
            update={
                "decisions": decisions,
                "current_section": None,
                "awaiting_input": False,
                "complete": True,
            }
        )
