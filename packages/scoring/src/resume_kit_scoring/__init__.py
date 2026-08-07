"""Deterministic scoring projections + analyses (RIT-I-0017 / RIT-I-0016)."""

from __future__ import annotations

from resume_kit_scoring.ats_view import build_ats_view
from resume_kit_scoring.base_fix import (
    BaseFixResult,
    apply_auto_fixes,
    claim_diff,
    claims_preserved,
    content_preserved,
)
from resume_kit_scoring.best_practices import (
    analyze_best_practices,
    detect_foundational_skills,
    detect_summary_too_long,
    foundational_skills,
    summary_too_long,
)
from resume_kit_scoring.projection import project_scoredoc
from resume_kit_scoring.standard_fix import (
    StandardFixResult,
    apply_best_practices_edits,
    finding_key,
)

__all__ = [
    "BaseFixResult",
    "StandardFixResult",
    "analyze_best_practices",
    "apply_auto_fixes",
    "apply_best_practices_edits",
    "build_ats_view",
    "claim_diff",
    "claims_preserved",
    "content_preserved",
    "detect_foundational_skills",
    "detect_summary_too_long",
    "finding_key",
    "foundational_skills",
    "project_scoredoc",
    "summary_too_long",
]
