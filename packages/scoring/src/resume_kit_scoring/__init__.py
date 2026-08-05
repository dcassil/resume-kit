"""Deterministic scoring projections + analyses (RIT-I-0017 / RIT-I-0016)."""

from __future__ import annotations

from resume_kit_scoring.base_fix import (
    BaseFixResult,
    apply_auto_fixes,
    claim_diff,
    claims_preserved,
)
from resume_kit_scoring.best_practices import analyze_best_practices
from resume_kit_scoring.projection import project_scoredoc

__all__ = [
    "BaseFixResult",
    "analyze_best_practices",
    "apply_auto_fixes",
    "claim_diff",
    "claims_preserved",
    "project_scoredoc",
]
