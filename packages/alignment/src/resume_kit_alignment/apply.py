"""Deterministic diff-application engine for controlled resume alignment.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/improver.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Ported the diff APPLICATION engine (apply_diffs, _resolve_path,
#   _set_at_path, _verify_original_matches, the malformed/unsupported rejection
#   branches, the reorder salvage + omitted-content preservation, and the
#   skill-addition gating) out of the improver mega-module. The path allow/block
#   gates and the verified-skill-target gate are NO LONGER reimplemented here:
#   they are delegated to resume_kit_policy.path_policy.evaluate_change_policy
#   and resume_kit_policy.skill_targets.build_allowed_skill_target_keys, so the
#   freedom-aware policy and the skill-target verifier are the single source of
#   truth. Uses schema ChangeProposal / ChangeSet / PolicyRejection instead of
#   upstream ResumeChange. _resolve_path / _set_at_path stay private to
#   alignment. Deep-copies the caller input; never mutates it. No LLM, no app.*
#   imports.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from typing import Any

from resume_kit_policy.path_policy import FREEDOM_MAX, evaluate_change_policy
from resume_kit_policy.skill_targets import (
    AllowedSkillTargetInput,
    build_allowed_skill_target_keys,
)
from resume_kit_schemas.change import ChangeProposal, ChangeSet
from resume_kit_schemas.results import (
    PolicyDecision,
    PolicyReasonCode,
    PolicyRejection,
    SkillTargetPlan,
)
from resume_kit_schemas.resume import ResumeDocument

__all__ = ["apply_diffs"]

_PATH_SEGMENT_RE = re.compile(r"([a-zA-Z_]+)(?:\[(\d+)\])?")

_SKILLS_PATH = "additional.technicalSkills"


def _normalize_skill_key(skill: str) -> str:
    """Normalize a skill for case-insensitive comparison (upstream parity)."""

    return re.sub(r"\s+", " ", skill.strip()).casefold()


def _resolve_path(data: dict[str, Any], path: str) -> tuple[Any, bool]:
    """Resolve a dot+bracket path to a value in the data dict.

    Returns ``(value, success)``; on failure returns ``(None, False)``.
    Ported verbatim from upstream ``improver._resolve_path``.
    """

    current: Any = data
    for segment_match in _PATH_SEGMENT_RE.finditer(path):
        key = segment_match.group(1)
        index_str = segment_match.group(2)

        if not isinstance(current, dict) or key not in current:
            return None, False
        current = current[key]

        if index_str is not None:
            index = int(index_str)
            if not isinstance(current, list) or index < 0 or index >= len(current):
                return None, False
            current = current[index]

    return current, True


def _set_at_path(data: dict[str, Any], path: str, value: Any) -> bool:
    """Set a value at the given path. Returns ``True`` on success.

    Ported verbatim from upstream ``improver._set_at_path``.
    """

    segments = list(_PATH_SEGMENT_RE.finditer(path))
    if not segments:
        return False

    # Navigate to parent of the target.
    current: Any = data
    for seg in segments[:-1]:
        key = seg.group(1)
        index_str = seg.group(2)

        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]

        if index_str is not None:
            index = int(index_str)
            if not isinstance(current, list) or index < 0 or index >= len(current):
                return False
            current = current[index]

    # Set on the final segment.
    last = segments[-1]
    key = last.group(1)
    index_str = last.group(2)

    if index_str is not None:
        if not isinstance(current, dict) or key not in current:
            return False
        target = current[key]
        index = int(index_str)
        if not isinstance(target, list) or index < 0 or index >= len(target):
            return False
        target[index] = value
    else:
        if not isinstance(current, dict):
            return False
        current[key] = value

    return True


def _verify_original_matches(
    actual: Any, expected: str | list[str] | None
) -> bool:
    """Verify that the original text from the diff matches the actual value.

    Ported verbatim from upstream ``improver._verify_original_matches``:
    a missing original passes, a non-string expected fails, a non-string actual
    fails, and the string comparison is stripped and casefolded.
    """

    if expected is None:
        return True  # no original provided (e.g. append) — nothing to verify
    if not isinstance(expected, str):
        return False  # a non-str original on a text action is malformed — reject
    if not isinstance(actual, str):
        return False
    return actual.strip().casefold() == expected.strip().casefold()


def _to_resume_dict(original: ResumeDocument | dict[str, Any]) -> dict[str, Any]:
    if isinstance(original, ResumeDocument):
        return original.model_dump()
    return dict(original)


def _to_change_list(
    changes: ChangeSet | Sequence[ChangeProposal],
) -> list[ChangeProposal]:
    if isinstance(changes, ChangeSet):
        return list(changes.changes)
    return list(changes)


def _rejection(
    change: ChangeProposal,
    reason_code: PolicyReasonCode,
    explanation: str,
) -> PolicyRejection:
    return PolicyRejection(
        path=change.path,
        action=change.action,
        reason_code=reason_code,
        explanation=explanation,
        change=change,
    )


def _rejection_from_decision(
    change: ChangeProposal, decision: PolicyDecision
) -> PolicyRejection:
    return PolicyRejection(
        path=change.path,
        action=change.action,
        reason_code=decision.reason_code,
        explanation=decision.explanation,
        change=change,
    )


def _apply_reorder(
    actual_value: list[Any],
    proposed: list[Any],
    path: str,
    allowed_skill_keys: set[str],
) -> list[str]:
    """Compute the reordered list, salvaging item-set mismatches.

    Ported from upstream ``improver.apply_diffs`` reorder branch (incl. issue
    #736 salvage): a pure permutation maps the new order back to original
    casing; otherwise existing items are placed in the requested position, new
    technical skills are inserted only when verified, and every omitted original
    is appended so a real item is never silently lost.
    """

    orig_set = sorted(s.casefold() for s in actual_value if isinstance(s, str))
    new_set = sorted(s.casefold() for s in proposed if isinstance(s, str))
    reordered: list[str] = []

    if orig_set == new_set:
        # Pure permutation: map the new order back to original casing.
        casefold_to_originals: dict[str, list[str]] = {}
        for item in actual_value:
            if isinstance(item, str):
                casefold_to_originals.setdefault(item.casefold(), []).append(item)
        for item in proposed:
            if isinstance(item, str):
                originals = casefold_to_originals.get(item.casefold(), [])
                reordered.append(originals.pop(0) if originals else item)
        return reordered

    # Salvage (issue #736): apply the SAFE subset in the requested order.
    casefold_to_originals = {}
    for item in actual_value:
        if isinstance(item, str):
            casefold_to_originals.setdefault(item.casefold(), []).append(item)
    original_cfs = set(casefold_to_originals)
    is_skills = path == _SKILLS_PATH
    added_new: set[str] = set()
    for item in proposed:
        if not isinstance(item, str):
            continue
        cf = item.casefold()
        if cf in original_cfs:
            bucket = casefold_to_originals[cf]
            if bucket:  # place original in requested position (dupes preserved)
                reordered.append(bucket.pop(0))
            # else: a duplicate of an already-placed original — skip
        elif is_skills and cf not in added_new:
            skill = item.strip()
            if skill and _normalize_skill_key(skill) in allowed_skill_keys:
                reordered.append(skill)  # verified new skill, requested position
                added_new.add(cf)
            # else: unverified new skill → dropped
        # else: non-skills new item → dropped (no verifier to ground it)
    for item in actual_value:  # append any originals the model omitted
        if isinstance(item, str):
            bucket = casefold_to_originals[item.casefold()]
            if bucket:
                reordered.append(bucket.pop(0))
    return reordered


def apply_diffs(
    original_resume: ResumeDocument | dict[str, Any],
    changes: ChangeSet | Sequence[ChangeProposal],
    *,
    freedom: int = FREEDOM_MAX,
    allowed_skill_targets: (
        SkillTargetPlan | Sequence[AllowedSkillTargetInput] | None
    ) = None,
) -> tuple[dict[str, Any], list[ChangeProposal], list[PolicyRejection]]:
    """Apply verified diffs to a resume, gating every change through policy.

    Every proposed change must pass the freedom-aware path policy gate
    (``resume_kit_policy.path_policy.evaluate_change_policy``) BEFORE any
    mutation. ``add_skill`` changes additionally pass the verified-skill-target
    gate (``resume_kit_policy.skill_targets``). Blocked factual fields
    (company / title / role / date / name / degree / institution / location /
    URL / id) are rejected at every freedom level, including ``freedom=10``, so
    identity facts can never be fabricated.

    Args:
        original_resume: The original resume (``ResumeDocument`` or dict). It is
            deep-copied; the caller's input is never mutated.
        changes: A ``ChangeSet`` or a list of ``ChangeProposal``.
        freedom: Editorial freedom level (0-10) handed to the path policy.
        allowed_skill_targets: Verified skill targets allowed for ``add_skill``.

    Returns:
        ``(result_dict, applied_changes, rejected_changes)`` where rejections
        carry policy/application reason detail as ``PolicyRejection`` records.
    """

    result = copy.deepcopy(_to_resume_dict(original_resume))
    applied: list[ChangeProposal] = []
    rejected: list[PolicyRejection] = []
    allowed_skill_keys = build_allowed_skill_target_keys(allowed_skill_targets)

    for change in _to_change_list(changes):
        path = change.path
        action = change.action

        # Gate 1+2: freedom-aware path policy (allowed + blocked + freedom).
        decision = evaluate_change_policy(change, freedom)
        if not decision.allowed:
            rejected.append(_rejection_from_decision(change, decision))
            continue

        # Gate 3: path must resolve to a real value in the resume.
        actual_value, resolved = _resolve_path(result, path)
        if not resolved:
            rejected.append(
                _rejection(
                    change,
                    PolicyReasonCode.MALFORMED_PATH,
                    f"Path '{path}' did not resolve to a value in the resume.",
                )
            )
            continue

        if action == "replace":
            # Gate 4: original text must match what's actually there.
            if not _verify_original_matches(actual_value, change.original):
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.ORIGINAL_MISMATCH,
                        (
                            f"Original text for '{path}' did not match the current "
                            "resume value."
                        ),
                    )
                )
                continue
            # Replace must use a string value (not a list).
            if not isinstance(change.value, str):
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_ACTION,
                        f"Replace on '{path}' requires a string value.",
                    )
                )
                continue
            if not _set_at_path(result, path, change.value):
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.MALFORMED_PATH,
                        f"Could not set replacement value at '{path}'.",
                    )
                )
                continue
            applied.append(change)

        elif action == "append":
            if not isinstance(actual_value, list):
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_ACTION,
                        f"Append target '{path}' is not a list.",
                    )
                )
                continue
            if not isinstance(change.value, str) or not change.value.strip():
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_ACTION,
                        f"Append on '{path}' requires a non-empty string value.",
                    )
                )
                continue
            actual_value.append(change.value)
            applied.append(change)

        elif action == "reorder":
            if not isinstance(actual_value, list) or not isinstance(
                change.value, list
            ):
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_ACTION,
                        f"Reorder on '{path}' requires a list target and value.",
                    )
                )
                continue
            reordered = _apply_reorder(
                actual_value, change.value, path, allowed_skill_keys
            )
            if not _set_at_path(result, path, reordered):
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.MALFORMED_PATH,
                        f"Could not set reordered list at '{path}'.",
                    )
                )
                continue
            applied.append(change)

        elif action == "add_skill":
            if path != _SKILLS_PATH:
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_ACTION,
                        "add_skill is only allowed on additional.technicalSkills.",
                    )
                )
                continue
            if not isinstance(actual_value, list):
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_ACTION,
                        f"add_skill target '{path}' is not a list.",
                    )
                )
                continue
            if not isinstance(change.value, str) or not change.value.strip():
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_ACTION,
                        "add_skill requires a non-empty string value.",
                    )
                )
                continue
            new_skill = change.value.strip()
            existing = {
                item.casefold()
                for item in actual_value
                if isinstance(item, str)
            }
            if new_skill.casefold() in existing:
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.DUPLICATE_SKILL,
                        f"Skill '{new_skill}' is already present.",
                    )
                )
                continue
            if _normalize_skill_key(new_skill) not in allowed_skill_keys:
                rejected.append(
                    _rejection(
                        change,
                        PolicyReasonCode.UNSUPPORTED_SKILL,
                        f"Skill '{new_skill}' is not a verified skill target.",
                    )
                )
                continue
            actual_value.append(new_skill)
            applied.append(change)

        else:  # pragma: no cover - ChangeAction Literal precludes other actions
            rejected.append(
                _rejection(
                    change,
                    PolicyReasonCode.UNSUPPORTED_ACTION,
                    f"Unsupported action '{action}'.",
                )
            )

    return result, applied, rejected
