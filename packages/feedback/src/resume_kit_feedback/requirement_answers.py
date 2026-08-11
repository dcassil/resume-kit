"""Append-only ``RequirementAnswer`` learning rail (extends RIT-I-0013).

Records the user's durable answers to "do you have this requirement?" so a
future interview can pre-filter items that were already answered and never
re-ask them. The log lives at
``<base_path>/learning/requirement-answers.jsonl`` — the same ``learning/``
DATA convention and append-only JSONL pattern as ``edit-feedback.jsonl`` /
``preference-pairs.jsonl`` (see :mod:`resume_kit_feedback.log`). One JSON object
per line; appends NEVER rewrite or reorder prior lines; reads tolerate a missing
file (return ``[]``).

``requirement_key`` normalization reuses the shared matching/keyword normalizer
(:func:`resume_kit_terms.surface_form`) — the single source of truth used by
``resume_kit_matching`` — so no second divergent scheme is introduced here.

The dedupe rule lives in :func:`is_already_answered`, which is pure and
deterministic (it operates on a provided list; :func:`load_and_check` is the thin
load-then-delegate wrapper) so it is trivially testable.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from resume_kit_schemas import RequirementAnswer, RequirementAnswerValue
from resume_kit_terms import surface_form

# Default working directory per the resume-kit/ DATA convention. Relative so the
# caller's current working directory anchors it; tests pass an explicit base_path.
_DEFAULT_BASE_PATH = Path("resume-kit")

# Subpath of the JSONL log beneath the base path.
_LOG_RELATIVE_PATH = Path("learning") / "requirement-answers.jsonl"


def normalize_requirement_key(requirement: str) -> str:
    """Normalize requirement/term text into the comparable ``requirement_key``.

    Delegates to :func:`resume_kit_terms.surface_form` — the shared normalizer
    that ``resume_kit_matching`` keyword/gap analysis already uses — so a key
    minted here matches a key derived from the matching side.
    """
    return surface_form(requirement)


def _resolve_log_path(base_path: Path | None) -> Path:
    """Resolve the requirement-answers JSONL path beneath ``base_path``."""
    root = _DEFAULT_BASE_PATH if base_path is None else base_path
    return root / _LOG_RELATIVE_PATH


def append_requirement_answer(
    record: RequirementAnswer, *, base_path: Path | None = None
) -> None:
    """Append one :class:`RequirementAnswer` record as a single JSON line.

    Creates the ``learning/`` directory and the file if absent. Only ever appends
    — prior lines are never rewritten or reordered. Serialization uses sorted keys
    for a stable, human-readable line.
    """
    log_path = _resolve_log_path(base_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.model_dump(mode="json"), sort_keys=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def load_requirement_answers(*, base_path: Path | None = None) -> list[RequirementAnswer]:
    """Read every :class:`RequirementAnswer` record from the log, in file order.

    Tolerates a missing file (returns ``[]``). Blank lines are skipped.
    """
    log_path = _resolve_log_path(base_path)
    if not log_path.exists():
        return []
    records: list[RequirementAnswer] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(RequirementAnswer.model_validate_json(stripped))
    return records


def is_already_answered(
    requirement_key: str,
    context_tag: str | None,
    answers: Iterable[RequirementAnswer],
) -> RequirementAnswerValue | None:
    """Return the durable answer that suppresses re-asking, or ``None`` if eligible.

    Pure and deterministic — operates only on the provided ``answers`` iterable
    (no I/O). Encapsulates the dedupe rule:

    - A global ``yes``/``no`` on the same ``requirement_key`` suppresses and its
      answer is returned.
    - A ``not_in_context`` suppresses ONLY on an exact ``requirement_key`` match
      AND a matching ``context_tag``; a differing/absent context stays eligible.
    - Otherwise returns ``None`` (eligible to ask).

    Last-write-wins: if the same key is answered more than once, the LAST matching
    record in ``answers`` (file/insertion order) decides. Answers for other keys
    are ignored.
    """
    result: RequirementAnswerValue | None = None
    for record in answers:
        if record.requirement_key != requirement_key:
            continue
        if record.answer in ("yes", "no"):
            # Global durable answer: always suppresses this key.
            result = record.answer
        elif context_tag is not None and record.context_tag == context_tag:
            # Context-scoped negative: suppresses only on a matching context tag.
            result = record.answer
        else:
            # not_in_context with a differing/absent context: eligible to ask.
            result = None
    return result


def load_and_check(
    requirement_key: str,
    context_tag: str | None,
    *,
    base_path: Path | None = None,
) -> RequirementAnswerValue | None:
    """Thin wrapper: load the log then delegate to :func:`is_already_answered`."""
    return is_already_answered(
        requirement_key,
        context_tag,
        load_requirement_answers(base_path=base_path),
    )
