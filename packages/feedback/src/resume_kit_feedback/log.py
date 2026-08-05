"""Append-only edit-feedback log I/O + a deterministic term-diff helper.

The log lives at ``<base_path>/learning/edit-feedback.jsonl`` where ``base_path``
defaults to the ``resume-kit/`` working directory (the plugin/agent working-dir
DATA convention). One JSON object per line; appends NEVER rewrite or reorder
prior lines (REQ-1301); reads tolerate a missing file (return ``[]``).

Everything here is pure and deterministic: no clock, no network, no LLM.
Timestamps are supplied by the caller on each :class:`EditFeedback` record.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from resume_kit_schemas import EditFeedback

# Default working directory per the resume-kit/ DATA convention. Relative so the
# caller's current working directory anchors it; tests pass an explicit base_path.
_DEFAULT_BASE_PATH = Path("resume-kit")

# Subpath of the JSONL log beneath the base path.
_LOG_RELATIVE_PATH = Path("learning") / "edit-feedback.jsonl"

# A "term" is a maximal run of word characters (letters, digits, underscore).
_TERM_RE = re.compile(r"\w+")


def _resolve_log_path(base_path: Path | None) -> Path:
    """Resolve the JSONL log path beneath ``base_path`` (default working dir)."""
    root = _DEFAULT_BASE_PATH if base_path is None else base_path
    return root / _LOG_RELATIVE_PATH


def append_edit_feedback(record: EditFeedback, *, base_path: Path | None = None) -> None:
    """Append one :class:`EditFeedback` record to the log as a single JSON line.

    Creates the ``learning/`` directory and the file if absent. Only ever appends
    — prior lines are never rewritten or reordered. Serialization uses sorted keys
    for a stable, human-readable line.
    """
    log_path = _resolve_log_path(base_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.model_dump(mode="json"), sort_keys=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_edit_feedback(*, base_path: Path | None = None) -> list[EditFeedback]:
    """Read every :class:`EditFeedback` record from the log, in file order.

    Tolerates a missing file (returns ``[]``). Blank lines are skipped.
    """
    log_path = _resolve_log_path(base_path)
    if not log_path.exists():
        return []
    records: list[EditFeedback] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(EditFeedback.model_validate_json(stripped))
    return records


def diff_terms(proposed: str, final: str) -> tuple[list[str], list[str], list[str]]:
    """Return ``(preserved, removed, added)`` whole-term sets, sorted and unique.

    Deterministic and pure: tokenizes each text into whole terms (word runs),
    compares the resulting sets, and returns sorted lists.

    - ``preserved``: terms present in both ``proposed`` and ``final``.
    - ``removed``: terms in ``proposed`` but not in ``final``.
    - ``added``: terms in ``final`` but not in ``proposed``.
    """
    proposed_terms = set(_TERM_RE.findall(proposed))
    final_terms = set(_TERM_RE.findall(final))
    preserved = sorted(proposed_terms & final_terms)
    removed = sorted(proposed_terms - final_terms)
    added = sorted(final_terms - proposed_terms)
    return preserved, removed, added
