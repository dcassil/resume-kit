"""The ``original -> base`` build step (RIT-I-0016, RIT-T-0115).

Composes the deterministic pieces into the write path that produces the ``base``
version: run the structural check, apply auto-safe fixes, enforce the
**claim-preservation gate** (RIT-A-0003, decided), persist ``<name>-base.json``,
and record the ``base`` pointer in the project config.

The claim-preservation gate — not extraction-faithfulness — is the correct gate
for an *edited* base: the fix intentionally removes PII and normalizes
presentation, so a source-file faithfulness check would wrongly reject it. What
must hold is that no employer/title/degree/skill claim was added, dropped, or
altered (:func:`resume_kit_scoring.claims_preserved`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from resume_kit_ats.engine import check_ats_structure
from resume_kit_core import CoreError, ErrorCode
from resume_kit_schemas import ResumeDocument
from resume_kit_scoring import apply_auto_fixes, claim_diff, claims_preserved

from resume_kit_facade.project_config import (
    atomic_write_json,
    load_config,
    set_version,
    working_dir,
)


@dataclass
class BuildBaseResult:
    """Outcome of the ``original -> base`` build."""

    base_path: str
    applied: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


def _base_path_for(original_rel: str) -> str:
    """Derive the ``-base.json`` path from the ``-original.json`` pointer."""
    p = Path(original_rel)
    stem = p.name
    if "-original" in stem:
        base_name = stem.replace("-original", "-base")
    elif stem.endswith(".json"):
        base_name = stem[: -len(".json")] + "-base.json"
    else:
        base_name = stem + "-base"
    return str(p.with_name(base_name))


def build_base(root: str | Path, *, mode: str = "auto") -> BuildBaseResult:
    """Produce the ``base`` version from the active original resume.

    ``mode='auto'`` applies only auto-safe fixes and defers ``needs_judgment``
    findings (reported back for the interactive walkthrough). Writes
    ``<name>-base.json`` behind the claim-preservation gate and points the config
    ``base`` at it. Raises :class:`CoreError` (VALIDATION_ERROR) if the gate
    fails — which, for the deterministic auto pass, indicates a bug rather than
    user data.
    """
    if mode != "auto":
        raise CoreError(
            ErrorCode.VALIDATION_FAILED,
            f"build_base mode {mode!r} not supported yet (only 'auto').",
        )
    config = load_config(root)
    original_rel = config.active_resume
    if not original_rel:
        raise CoreError(ErrorCode.VALIDATION_FAILED, "No active_resume set.")

    original_file = working_dir(root) / original_rel
    if not original_file.exists():
        raise CoreError(ErrorCode.VALIDATION_FAILED, f"Active resume not found: {original_rel}.")

    original = ResumeDocument.model_validate(json.loads(original_file.read_text(encoding="utf-8")))
    report = check_ats_structure(original)
    fix = apply_auto_fixes(original, report)

    # Hard claim-preservation gate (RIT-A-0003).
    if not claims_preserved(original, fix.resume):
        raise CoreError(
            ErrorCode.VALIDATION_FAILED,
            "base build refused: claim-preservation gate failed "
            f"(altered claims: {claim_diff(original, fix.resume)}).",
        )

    base_rel = _base_path_for(original_rel)
    atomic_write_json(working_dir(root) / base_rel, fix.resume.model_dump(mode="json"))
    set_version(root, base=base_rel, base_derived_from=original_rel)

    return BuildBaseResult(base_path=base_rel, applied=fix.applied, deferred=fix.deferred)


__all__ = ["BuildBaseResult", "build_base"]
