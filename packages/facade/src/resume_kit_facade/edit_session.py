"""Code-owned edit-session persistence and write gate.

This is deliberately a thin wrapper over ``ReviewController`` and
``apply_diffs``. It owns the on-disk envelope, feedback records that callers
append through the facade capability, and the commit preconditions from
RIT-A-0001.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from resume_kit_alignment import ReviewController, apply_diffs
from resume_kit_core import CoreError, ErrorCode, ResumeKitError
from resume_kit_evidence import validate_resume_truth
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
from resume_kit_terms import load_effective_alias_index, normalize, surface_form

from resume_kit_facade.models import (
    AliasGrowthEntry,
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
_TERMINOLOGY_REASON_PREFIX = "Mirror the employer's exact terminology:"
_TOKEN_RE = re.compile(r"\w+")


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
    alias_timestamp: str | None = None,
) -> CommitSessionResult:
    """Run the hard write gate, apply approved diffs, and persist the result.

    Freshness contract for the truth gate: the AUTHORITATIVE truth check is
    always computed over the assembled post-apply document (the exact bytes that
    would be persisted), via :func:`_assembled_contradicted_paths`. The
    per-change provenance check (:func:`_contradicted_paths`) is only an advisory
    fast pre-gate over provenance seeded at proposal time. No version is ever
    persisted whose assembled form fails truth validation, so a claim that
    becomes ``CONTRADICTED`` only in the COMBINATION of accepted changes is still
    refused here even though each change looked supported in isolation.
    """
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
    assembled_contradicted = _assembled_contradicted_paths(root, state, updated_resume)
    if assembled_contradicted:
        _raise_gate(
            "truth_contradicted_assembled",
            "Assembled resume fails truth validation (contradicted claims).",
            {"paths": assembled_contradicted},
        )
    grown_aliases = grow_aliases_from_accepted_terminology(
        root=root,
        state=state,
        timestamp=alias_timestamp or datetime.now(UTC).isoformat(),
    )
    after_match, after_ats = _score(root, updated_resume, state.active_job)
    working_path = _state_working_path(root, state)
    atomic_write_json(working_path, updated_resume.model_dump(mode="json"))
    state = state.model_copy(update={"committed_hash": _sha256_file(working_path)})
    _write_state(working_dir(root), state)
    return CommitSessionResult(
        state=state,
        applied=applied,
        rejected=rejected,
        grown_aliases=grown_aliases,
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


def grow_aliases_from_accepted_terminology(
    *,
    root: str | Path,
    state: EditSessionState,
    timestamp: str,
) -> list[AliasGrowthEntry]:
    """Append aliases learned from human-accepted terminology decisions."""
    if state.mode == "auto":
        return []
    config = load_config(root)
    if config.alias_file is None or not config.alias_file.strip():
        return []

    alias_file = _project_file(root, config.alias_file)
    candidates = _accepted_terminology_alias_candidates(
        state=state,
        timestamp=timestamp,
        alias_file=alias_file,
    )
    if not candidates:
        return []
    grown = _append_project_aliases(alias_file, candidates)
    if grown:
        _clear_alias_index_caches()
    return grown


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


def _accepted_terminology_alias_candidates(
    *,
    state: EditSessionState,
    timestamp: str,
    alias_file: Path,
) -> list[AliasGrowthEntry]:
    candidates: list[AliasGrowthEntry] = []
    for decision in state.review_session.decisions:
        if decision.action not in _APPLYING:
            continue
        for change in decision.changes:
            if not _is_terminology_change(change):
                continue
            accepted_text = (
                decision.edited_content
                if decision.action == ReviewAction.EDIT and decision.edited_content is not None
                else change.value
            )
            if not isinstance(change.original, str) or not isinstance(accepted_text, str):
                continue
            candidate = _candidate_from_text_swap(
                original_text=change.original,
                accepted_text=accepted_text,
                timestamp=timestamp,
                alias_file=alias_file,
            )
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _is_terminology_change(change: ChangeProposal) -> bool:
    return (
        change.action == "replace"
        and isinstance(change.original, str)
        and isinstance(change.value, str)
        and change.reason.startswith(_TERMINOLOGY_REASON_PREFIX)
    )


def _candidate_from_text_swap(
    *,
    original_text: str,
    accepted_text: str,
    timestamp: str,
    alias_file: Path,
) -> AliasGrowthEntry | None:
    original_tokens = _TOKEN_RE.findall(original_text)
    accepted_tokens = _TOKEN_RE.findall(accepted_text)
    if len(original_tokens) != len(accepted_tokens):
        return None

    changed_pairs = [
        (old, new)
        for old, new in zip(original_tokens, accepted_tokens, strict=True)
        if surface_form(old) != surface_form(new)
    ]
    if not changed_pairs:
        return None

    original_by_norm = {normalize(old) for old, _new in changed_pairs}
    accepted_by_norm = {normalize(new) for _old, new in changed_pairs}
    original_by_norm.discard("")
    accepted_by_norm.discard("")
    if len(original_by_norm) != 1 or len(accepted_by_norm) != 1:
        return None
    if original_by_norm == accepted_by_norm:
        return None

    original_term = changed_pairs[0][0]
    accepted_term = changed_pairs[0][1]
    return AliasGrowthEntry(
        canonical=accepted_term,
        alias=original_term,
        original_term=original_term,
        accepted_term=accepted_term,
        timestamp=timestamp,
        alias_file=alias_file.as_posix(),
    )


def _append_project_aliases(
    alias_file: Path,
    candidates: list[AliasGrowthEntry],
) -> list[AliasGrowthEntry]:
    payload = _load_project_alias_payload(alias_file)
    aliases = payload["aliases"]
    assert isinstance(aliases, dict)
    provenance = payload.setdefault("provenance", [])
    if not isinstance(provenance, list):
        provenance = []
        payload["provenance"] = provenance

    grown: list[AliasGrowthEntry] = []
    effective = load_effective_alias_index(alias_file if alias_file.exists() else None)
    for candidate in candidates:
        existing_alias = effective.canonical_for(candidate.alias)
        existing_canonical = effective.canonical_for(candidate.canonical)
        if existing_alias is not None and existing_canonical is not None:
            if existing_alias != existing_canonical:
                continue
            continue

        canonical_norm = existing_canonical or normalize(candidate.canonical)
        alias_norm = normalize(candidate.alias)
        if not canonical_norm or not alias_norm or canonical_norm == alias_norm:
            continue

        canonical_key = _canonical_key_for(aliases, canonical_norm, candidate.canonical)
        alias_values = aliases.setdefault(canonical_key, [])
        if not isinstance(alias_values, list):
            continue
        group_norms = {normalize(canonical_key)}
        group_norms.update(normalize(str(value)) for value in alias_values)
        if alias_norm in group_norms:
            continue

        alias_values.append(candidate.alias)
        alias_values.sort(key=lambda value: surface_form(str(value)))
        grown.append(
            candidate.model_copy(
                update={
                    "canonical": canonical_key,
                    "alias_file": alias_file.as_posix(),
                }
            )
        )

    if not grown:
        return []

    existing_provenance = {
        (
            str(item.get("source", "")),
            str(item.get("canonical_normalized", "")),
            str(item.get("alias_normalized", "")),
        )
        for item in provenance
        if isinstance(item, dict)
    }
    for entry in grown:
        key = ("accepted_edit", normalize(entry.canonical), normalize(entry.alias))
        if key in existing_provenance:
            continue
        provenance.append(
            {
                "accepted_term": entry.accepted_term,
                "alias": entry.alias,
                "alias_normalized": normalize(entry.alias),
                "canonical": entry.canonical,
                "canonical_normalized": normalize(entry.canonical),
                "original_term": entry.original_term,
                "source": "accepted_edit",
                "timestamp": entry.timestamp,
            }
        )
        existing_provenance.add(key)

    atomic_write_json(alias_file, payload)
    load_effective_alias_index(alias_file)
    return grown


def _load_project_alias_payload(alias_file: Path) -> dict[str, object]:
    if not alias_file.exists():
        return {"version": 1, "aliases": {}, "justifications": {}, "provenance": []}
    raw = json.loads(alias_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{alias_file} must contain a JSON object.")
    aliases = raw.setdefault("aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError(f"{alias_file} must contain an aliases object.")
    raw.setdefault("version", 1)
    return raw


def _canonical_key_for(
    aliases: dict[object, object],
    canonical_norm: str,
    fallback: str,
) -> str:
    for key in aliases:
        if isinstance(key, str) and normalize(key) == canonical_norm:
            return key
    if normalize(fallback) == canonical_norm:
        return fallback
    return canonical_norm


def _clear_alias_index_caches() -> None:
    try:
        from resume_kit_matching.keywords import _effective_alias_index as matching_cache

        matching_cache.cache_clear()
    except Exception:  # noqa: BLE001 - cache invalidation is best-effort
        pass
    try:
        from resume_kit_ats.engine import _effective_alias_index as ats_cache

        ats_cache.cache_clear()
    except Exception:  # noqa: BLE001 - cache invalidation is best-effort
        pass


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


def _key_for_change(change_keys: dict[str, ChangeProposal], target: ChangeProposal) -> str | None:
    for key, change in change_keys.items():
        if change == target:
            return key
    for key, change in change_keys.items():
        if change.path == target.path and change.action == target.action:
            return key
    return None


def _matching_provenance(state: EditSessionState, change: ChangeProposal) -> list[ClaimProvenance]:
    value = change.value if isinstance(change.value, str) else ""
    return [
        item
        for item in state.review_session.claim_provenance
        if item.field_path == change.path or (value and item.claim == value)
    ]


def _assembled_contradicted_paths(
    root: str | Path,
    state: EditSessionState,
    resume: ResumeDocument,
) -> list[str]:
    """Freshly recompute truth over the ASSEMBLED post-apply resume.

    This is the write gate's *authoritative* truth check. Unlike
    :func:`_contradicted_paths` — a fast pre-gate that only inspects per-change
    ``claim_provenance`` seeded when each change was individually proposed — this
    runs the deterministic ``validate_resume_truth`` validator over the exact
    document ``apply_diffs`` produced. A claim that only becomes contradicted in
    the COMBINATION of accepted changes is therefore caught here. Deterministic
    and offline (no network/LLM); returns every field path classified
    ``CONTRADICTED``. ``UNSUPPORTED`` retains its existing (non-blocking-here)
    handling and is intentionally not escalated by this task.
    """
    config = load_config(root)
    alias_file = (
        str(_project_file(root, config.alias_file))
        if config.alias_file and config.alias_file.strip()
        else None
    )
    report = validate_resume_truth(
        resume,
        state.review_session.evidence,
        alias_file=alias_file,
    )
    return [
        provenance.field_path
        for provenance in report.claims
        if provenance.status is ProvenanceStatus.CONTRADICTED
    ]


def _contradicted_paths(state: EditSessionState, changes: list[ChangeProposal]) -> list[str]:
    """Fast advisory pre-gate: per-change provenance seeded at proposal time.

    This is NOT the authoritative truth check — it only inspects the
    ``claim_provenance`` computed when each change was individually proposed. The
    authoritative gate is :func:`_assembled_contradicted_paths`, which recomputes
    truth over the assembled post-apply document. Keeping this pre-check preserves
    the existing fast refusal for already-known contradictions before the more
    expensive assembly + revalidation runs.
    """
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
        final_text if final_text is not None else proposed if outcome == "accepted" else None
    )
    removed_terms, added_terms, preserved_terms = _feedback_diff_terms(
        action=action,
        original=original,
        proposed=proposed,
        final=kept_text,
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
        removed_terms=removed_terms,
        added_terms=added_terms,
        preserved_terms=preserved_terms,
        timestamp=datetime.now(UTC).isoformat(),
    )


def _feedback_diff_terms(
    *,
    action: ReviewAction,
    original: str,
    proposed: str,
    final: str | None,
) -> tuple[list[str], list[str], list[str]]:
    if action == ReviewAction.EDIT and final is not None:
        return _term_delta(proposed, final)
    if action == ReviewAction.APPROVE:
        return _term_delta(original, proposed)
    if action in {ReviewAction.REJECT, ReviewAction.SKIP}:
        removed, added, preserved = _term_delta(original, proposed)
        return removed, added or preserved, []
    return [], [], []


def _term_delta(before: str, after: str) -> tuple[list[str], list[str], list[str]]:
    before_terms = _ordered_terms(before)
    after_terms = _ordered_terms(after)
    before_set = set(before_terms)
    after_set = set(after_terms)
    removed = [term for term in before_terms if term not in after_set]
    added = [term for term in after_terms if term not in before_set]
    preserved = [term for term in after_terms if term in before_set]
    return removed, added, preserved


def _ordered_terms(text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(text):
        term = surface_form(token)
        if not term or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


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

        from resume_kit_facade.alias_scope import use_alias_file

        job = JobDescription.model_validate_json(
            _project_file(root, active_job).read_text(encoding="utf-8")
        )
        config = load_config(root)
        alias_file = _project_file(root, config.alias_file) if config.alias_file else None
        with use_alias_file(alias_file):
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
