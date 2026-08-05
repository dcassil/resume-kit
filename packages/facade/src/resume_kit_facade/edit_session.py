"""Code-owned edit-session persistence and write gate.

This is deliberately a thin wrapper over ``ReviewController`` and
``apply_diffs``. It owns the on-disk envelope, feedback records that callers
append through the facade capability, and the commit preconditions from
RIT-A-0001.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from resume_kit_alignment import ReviewController, apply_diffs
from resume_kit_core import CoreError, ErrorCode, ResumeKitError
from resume_kit_schemas import (
    ATSScore,
    CandidateEvidence,
    ChangeProposal,
    ClaimProvenance,
    EditFeedback,
    EditFeedbackReasonCode,
    EditOutcome,
    JobDescription,
    JobMatchReport,
    ProvenanceStatus,
    ResumeDocument,
    ReviewAction,
    ReviewDecision,
    ScoreDelta,
)

from resume_kit_facade.models import (
    CommitSessionResult,
    EditSessionState,
    EditSessionStatus,
    ReconcileSessionResult,
)
from resume_kit_facade.project_config import atomic_write_json, load_config, working_dir

_SESSION_RELATIVE = Path("working") / "edit-session.json"
_TERMINAL = {
    ReviewAction.APPROVE,
    ReviewAction.REJECT,
    ReviewAction.EDIT,
    ReviewAction.SKIP,
}
_APPLYING = {ReviewAction.APPROVE, ReviewAction.EDIT}
_AUTO_ALLOWED = {
    ProvenanceStatus.VERIFIED,
    ProvenanceStatus.SUPPORTED,
    ProvenanceStatus.USER_CONFIRMED,
}
_MODES = {"interactive", "review_at_end", "auto"}


def open_session(
    *,
    root: str | Path,
    mode: str,
    changes: list[ChangeProposal],
    evidence: list[CandidateEvidence],
    claim_provenance: list[ClaimProvenance],
    expected_score_deltas: list[ScoreDelta],
) -> tuple[EditSessionState, list[EditFeedback]]:
    """Create and persist the single active edit session."""
    if mode not in _MODES:
        _raise_gate("invalid_mode", f"Unsupported edit-session mode: {mode!r}.")
    config = load_config(root)
    active_resume = config.active_resume
    active_job = config.active_job
    if active_resume is None or active_job is None:
        _raise_gate(
            "missing_active_document",
            "active_resume and active_job must be set before opening an edit session.",
        )
    assert active_resume is not None
    assert active_job is not None

    base = working_dir(root)
    original_path = _project_file(root, active_resume)
    if not original_path.exists():
        _raise_gate("missing_active_resume", f"Active resume not found: {active_resume}.")
    if not _project_file(root, active_job).exists():
        _raise_gate("missing_active_job", f"Active job not found: {active_job}.")

    archive_session(root)
    review = ReviewController.initialize(
        changes,
        evidence=evidence,
        claim_provenance=list(claim_provenance),
        expected_score_deltas=list(expected_score_deltas),
    )
    state = EditSessionState(
        session_id=f"edit-{uuid4().hex}",
        mode=mode,
        active_resume=active_resume,
        active_job=active_job,
        working_path=_working_path_string(active_resume),
        review_session=review,
        original_hash=_sha256_file(original_path),
        committed_hash=None,
    )
    feedback: list[EditFeedback] = []
    if mode == "auto":
        state, feedback = _auto_resolve(state)
    _write_state(base, state)
    return state, feedback


def archive_session(root: str | Path) -> Path | None:
    """Archive the prior active session, if present, under ``learning/``."""
    base = working_dir(root)
    path = _session_path(root)
    if not path.exists():
        return None
    try:
        existing = EditSessionState.model_validate_json(path.read_text(encoding="utf-8"))
        suffix = existing.session_id
    except Exception:  # noqa: BLE001 - archive even malformed legacy state
        suffix = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    archive = base / "learning" / f"edit-session-{suffix}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(path, archive)
    return archive


def load_session(root: str | Path, *, check_tamper: bool = True) -> EditSessionState:
    """Load the active session, optionally enforcing tamper detection."""
    path = _session_path(root)
    if not path.exists():
        _raise_gate("missing_session", "No active edit session exists.")
    state = EditSessionState.model_validate_json(path.read_text(encoding="utf-8"))
    _ensure_bound_to_active(root, state)
    if check_tamper:
        _check_tamper(root, state)
    return state


def prompt_session(root: str | Path) -> object:
    """Return the next review prompt from ``ReviewController``."""
    state = load_session(root)
    return ReviewController.prompt(state.review_session)


def decide_change(
    *,
    root: str | Path,
    path: str,
    action: ReviewAction,
    reason_code: EditFeedbackReasonCode | None,
    note: str | None,
    edited_content: str | None,
) -> tuple[EditSessionState, EditFeedback]:
    """Record one decision through ``ReviewController`` and persist it."""
    state = load_session(root)
    change = _find_change(state, path)
    section = state.review_session.current_section
    target_section = _section_of(change)
    if section != target_section:
        _raise_gate(
            "wrong_section",
            f"Change '{path}' is in section '{target_section}', current section is '{section}'.",
            {"path": path, "current_section": section, "target_section": target_section},
        )

    decision = ReviewDecision(
        section=target_section,
        action=action,
        edited_content=edited_content,
        explanation=note or "",
        changes=[change],
    )
    updated_review = ReviewController.apply_decision(state.review_session, decision)
    if action in _TERMINAL and _section_has_undecided_change(
        updated_review.pending_changes,
        updated_review.decisions,
        target_section,
    ):
        # ReviewController is intentionally section-cursor based, while the ADR
        # requires path-correlated decisions. Keep the controller's recorded
        # decision, then hold the cursor on the same section until every change
        # in that section has its own logged decision.
        updated_review = updated_review.model_copy(
            update={
                "current_section": target_section,
                "awaiting_input": True,
                "complete": False,
            }
        )
    state = state.model_copy(update={"review_session": updated_review})
    _write_state(working_dir(root), state)
    return state, _feedback_for_decision(
        state=state,
        change=change,
        action=action,
        reason_code=reason_code,
        note=note,
        final_text=edited_content,
    )


def commit_session(
    *,
    root: str | Path,
    freedom: int,
) -> CommitSessionResult:
    """Run the hard write gate, apply approved diffs, and persist the result."""
    state = load_session(root)
    unlogged = _unlogged_changes(state)
    if unlogged:
        _raise_gate(
            "unlogged_decision",
            "Every applied change must have a terminal logged decision.",
            {"paths": unlogged},
        )
    accepted = _accepted_changes(state)
    contradicted = _contradicted_paths(state, accepted)
    if contradicted:
        _raise_gate(
            "truth_contradicted",
            "Approved changes include contradicted claims.",
            {"paths": contradicted},
        )
    if not accepted:
        _raise_gate(
            "no_applicable_changes",
            "No approved or edited changes are ready to commit.",
        )

    original = _load_resume(_project_file(root, state.active_resume))
    before_match, before_ats = _score(root, original, state.active_job)
    result_dict, applied, rejected = apply_diffs(original, accepted, freedom=freedom)
    updated_resume = ResumeDocument.model_validate(result_dict)
    after_match, after_ats = _score(root, updated_resume, state.active_job)
    working_path = _state_working_path(root, state)
    atomic_write_json(working_path, updated_resume.model_dump(mode="json"))
    state = state.model_copy(update={"committed_hash": _sha256_file(working_path)})
    _write_state(working_dir(root), state)
    return CommitSessionResult(
        state=state,
        applied=applied,
        rejected=rejected,
        before_match_report=before_match,
        after_match_report=after_match,
        before_ats_score=before_ats,
        after_ats_score=after_ats,
    )


def session_status(root: str | Path) -> EditSessionStatus:
    """Return progress for the active edit session."""
    state = load_session(root)
    return _status(state)


def reconcile_session(root: str | Path) -> ReconcileSessionResult:
    """Accept the current working file hash as intentional manual state."""
    state = load_session(root, check_tamper=False)
    working_path = _state_working_path(root, state)
    previous = state.committed_hash
    current = _sha256_file(working_path) if working_path.exists() else None
    state = state.model_copy(update={"committed_hash": current})
    _write_state(working_dir(root), state)
    return ReconcileSessionResult(
        state=state,
        previous_hash=previous,
        reconciled_hash=current,
    )


def _auto_resolve(state: EditSessionState) -> tuple[EditSessionState, list[EditFeedback]]:
    feedback: list[EditFeedback] = []
    review = state.review_session
    for change in review.pending_changes:
        if not _auto_can_apply(state, change):
            continue
        section = _section_of(change)
        if review.complete or review.current_section != section:
            review = review.model_copy(
                update={
                    "current_section": section,
                    "awaiting_input": True,
                    "complete": False,
                }
            )
        decision = ReviewDecision(
            section=section,
            action=ReviewAction.APPROVE,
            explanation="Auto-approved by edit-session policy.",
            changes=[change],
        )
        review = ReviewController.apply_decision(review, decision)
        if _section_has_undecided_change(review.pending_changes, review.decisions, section):
            review = review.model_copy(
                update={
                    "current_section": section,
                    "awaiting_input": True,
                    "complete": False,
                }
            )
        auto_state = state.model_copy(update={"review_session": review})
        feedback.append(
            _feedback_for_decision(
                state=auto_state,
                change=change,
                action=ReviewAction.APPROVE,
                reason_code=None,
                note="auto",
                final_text=str(change.value) if isinstance(change.value, str) else None,
            )
        )
        state = auto_state
    return state, feedback


def _auto_can_apply(state: EditSessionState, change: ChangeProposal) -> bool:
    if _is_addition(change):
        return False
    provenances = _matching_provenance(state, change)
    if not provenances:
        return False
    return all(item.status in _AUTO_ALLOWED for item in provenances)


def _is_addition(change: ChangeProposal) -> bool:
    lowered = change.path.casefold()
    return change.action in {"append", "add_skill"} and any(
        token in lowered for token in ("technicalskills", "certification", "company")
    )


def _unlogged_changes(state: EditSessionState) -> list[str]:
    logged = _terminal_decision_keys(state)
    paths: list[str] = []
    for key, change in _change_keys(state).items():
        if key in logged:
            continue
        if state.mode == "auto" and not _auto_can_apply(state, change):
            continue
        paths.append(change.path)
    return paths


def _accepted_changes(state: EditSessionState) -> list[ChangeProposal]:
    changes: list[ChangeProposal] = []
    for decision in state.review_session.decisions:
        if decision.action not in _APPLYING:
            continue
        for change in decision.changes:
            if decision.action == ReviewAction.EDIT and decision.edited_content is not None:
                changes.append(change.model_copy(update={"value": decision.edited_content}))
            else:
                changes.append(change)
    return changes


def _terminal_decision_keys(state: EditSessionState) -> set[str]:
    keys: set[str] = set()
    change_keys = _change_keys(state)
    for decision in state.review_session.decisions:
        if decision.action not in _TERMINAL:
            continue
        for change in decision.changes:
            key = _key_for_change(change_keys, change)
            if key is not None:
                keys.add(key)
    return keys


def _change_keys(state: EditSessionState) -> dict[str, ChangeProposal]:
    seen: dict[tuple[str, str], int] = {}
    keyed: dict[str, ChangeProposal] = {}
    for change in state.review_session.pending_changes:
        base = (change.path, change.action)
        index = seen.get(base, 0)
        seen[base] = index + 1
        suffix = "" if index == 0 else f"#{index + 1}"
        keyed[f"{change.path}|{change.action}{suffix}"] = change
    return keyed


def _key_for_change(
    change_keys: dict[str, ChangeProposal], target: ChangeProposal
) -> str | None:
    for key, change in change_keys.items():
        if change == target:
            return key
    for key, change in change_keys.items():
        if change.path == target.path and change.action == target.action:
            return key
    return None


def _matching_provenance(
    state: EditSessionState, change: ChangeProposal
) -> list[ClaimProvenance]:
    value = change.value if isinstance(change.value, str) else ""
    return [
        item
        for item in state.review_session.claim_provenance
        if item.field_path == change.path or (value and item.claim == value)
    ]


def _contradicted_paths(
    state: EditSessionState, changes: list[ChangeProposal]
) -> list[str]:
    paths: list[str] = []
    for change in changes:
        if any(
            item.status is ProvenanceStatus.CONTRADICTED
            for item in _matching_provenance(state, change)
        ):
            paths.append(change.path)
    return paths


def _section_has_undecided_change(
    changes: list[ChangeProposal],
    decisions: list[ReviewDecision],
    section: str,
) -> bool:
    decided = {
        (change.path, change.action)
        for decision in decisions
        if decision.action in _TERMINAL
        for change in decision.changes
    }
    return any(
        _section_of(change) == section and (change.path, change.action) not in decided
        for change in changes
    )


def _find_change(state: EditSessionState, path: str) -> ChangeProposal:
    matches = [change for change in state.review_session.pending_changes if change.path == path]
    if not matches:
        _raise_gate("unknown_change", f"No pending change targets path '{path}'.")
    for change in matches:
        if _key_for_change(_change_keys(state), change) not in _terminal_decision_keys(state):
            return change
    return matches[0]


def _feedback_for_decision(
    *,
    state: EditSessionState,
    change: ChangeProposal,
    action: ReviewAction,
    reason_code: EditFeedbackReasonCode | None,
    note: str | None,
    final_text: str | None,
) -> EditFeedback:
    proposed = change.value if isinstance(change.value, str) else json.dumps(change.value)
    original = (
        change.original
        if isinstance(change.original, str)
        else json.dumps(change.original)
        if change.original is not None
        else ""
    )
    outcome: EditOutcome = "accepted"
    if action == ReviewAction.EDIT:
        outcome = "accepted_modified"
    elif action in {ReviewAction.REJECT, ReviewAction.SKIP}:
        outcome = "rejected"
    kept_text = (
        final_text
        if final_text is not None
        else proposed
        if outcome == "accepted"
        else None
    )
    return EditFeedback(
        edit_id=_edit_id(state, change, action),
        resume_id=state.active_resume,
        job_id=state.active_job,
        section=_section_of(change),
        edit_type=change.action,
        original_text=original,
        proposed_text=proposed,
        final_text=kept_text,
        target_terms=[],
        matched_job_requirements=[],
        predicted_ats_gain=0.0,
        confidence=1.0,
        outcome=outcome,
        reason_code=reason_code,
        reason_note=note,
        timestamp=datetime.now(UTC).isoformat(),
    )


def _edit_id(
    state: EditSessionState,
    change: ChangeProposal,
    action: ReviewAction,
) -> str:
    digest = hashlib.sha256(
        f"{state.session_id}\n{change.path}\n{change.action}\n{action.value}".encode()
    ).hexdigest()[:16]
    return f"edit-{digest}"


def _status(state: EditSessionState) -> EditSessionStatus:
    logged = _terminal_decision_keys(state)
    keyed = _change_keys(state)
    decided = [change.path for key, change in keyed.items() if key in logged]
    pending = [
        change.path
        for key, change in keyed.items()
        if key not in logged and not (state.mode == "auto" and not _auto_can_apply(state, change))
    ]
    deferred = [
        change.path
        for key, change in keyed.items()
        if key not in logged and state.mode == "auto" and not _auto_can_apply(state, change)
    ]
    truth: dict[ProvenanceStatus, int] = {status: 0 for status in ProvenanceStatus}
    for item in state.review_session.claim_provenance:
        truth[item.status] += 1
    return EditSessionStatus(
        session_id=state.session_id,
        mode=state.mode,
        active_resume=state.active_resume,
        active_job=state.active_job,
        working_path=state.working_path,
        progress={
            "total": len(keyed),
            "decided": len(decided),
            "pending": len(pending),
            "deferred": len(deferred),
        },
        decided=decided,
        pending=pending,
        deferred=deferred,
        truth_summary=truth,
        committed_hash=state.committed_hash,
    )


def _score(
    root: str | Path,
    resume: ResumeDocument,
    active_job: str,
) -> tuple[JobMatchReport | None, ATSScore | None]:
    try:
        from resume_kit_matching import check_job_match

        job = JobDescription.model_validate_json(
            _project_file(root, active_job).read_text(encoding="utf-8")
        )
        report = check_job_match(resume, job)
        return report, report.ats_score
    except Exception:  # noqa: BLE001 - scoring is advisory for commit results
        return None, None


def _check_tamper(root: str | Path, state: EditSessionState) -> None:
    working_path = _state_working_path(root, state)
    if not working_path.exists():
        return
    expected = state.committed_hash or state.original_hash
    actual = _sha256_file(working_path)
    if actual != expected:
        _raise_gate(
            "working_resume_tampered",
            "working resume was edited outside the session; re-open or reconcile",
            {
                "working_path": state.working_path,
                "expected_hash": expected,
                "actual_hash": actual,
            },
        )


def _ensure_bound_to_active(root: str | Path, state: EditSessionState) -> None:
    config = load_config(root)
    if state.active_resume != config.active_resume or state.active_job != config.active_job:
        _raise_gate(
            "session_active_mismatch",
            "Active edit session does not match active_resume and active_job.",
            {
                "session_active_resume": state.active_resume,
                "session_active_job": state.active_job,
                "config_active_resume": config.active_resume,
                "config_active_job": config.active_job,
            },
        )


def _write_state(base: Path, state: EditSessionState) -> None:
    atomic_write_json(base / _SESSION_RELATIVE, state.model_dump(mode="json"))


def _session_path(root: str | Path) -> Path:
    return working_dir(root) / _SESSION_RELATIVE


def _state_working_path(root: str | Path, state: EditSessionState) -> Path:
    path = Path(state.working_path)
    return path if path.is_absolute() else Path(root) / path


def _project_file(root: str | Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "resume-kit":
        return Path(root) / path
    return working_dir(root) / path


def _working_path_string(active_resume: str) -> str:
    name = Path(active_resume).name
    if name.endswith("-original.json"):
        name = f"{name.removesuffix('-original.json')}.tailored.json"
    elif name.endswith(".json"):
        name = f"{name.removesuffix('.json')}.tailored.json"
    else:
        name = f"{name}.tailored.json"
    return (Path("resume-kit") / "working" / name).as_posix()


def _load_resume(path: Path) -> ResumeDocument:
    return ResumeDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _section_of(change: ChangeProposal) -> str:
    for index, character in enumerate(change.path):
        if character in (".", "["):
            return change.path[:index]
    return change.path


def _raise_gate(
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> None:
    payload = {"gate_code": code, **(details or {})}
    raise ResumeKitError(
        CoreError(
            code=ErrorCode.VALIDATION_FAILED,
            message=message,
            details=payload,
        )
    )
