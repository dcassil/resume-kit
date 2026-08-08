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
from resume_kit_scoring.budget_enforce import budget_enforce, content_ledger_ok_perfect
from resume_kit_scoring.compress import (
    CompressionCandidate,
    compress_bullet,
    compress_summary,
)
from resume_kit_scoring.projection import (
    project_builddoc_from_canonical,
    project_scoredoc,
)
from resume_kit_scoring.rank_bullets import rank_bullets
from resume_kit_scoring.rank_experience import rank_experience
from resume_kit_scoring.rank_skills import rank_skills
from resume_kit_scoring.shape_analyzer import analyze_resume_shape
from resume_kit_scoring.shape_fix import (
    apply_shape_transforms,
    claims_preserved_across_sections,
    content_ledger_ok,
)
from resume_kit_scoring.standard_fix import (
    RefineFixResult,
    StandardFixResult,
    apply_best_practices_edits,
    finding_key,
)

__all__ = [
    "BaseFixResult",
    "CompressionCandidate",
    "RefineFixResult",
    "StandardFixResult",
    "analyze_best_practices",
    "analyze_resume_shape",
    "apply_auto_fixes",
    "apply_best_practices_edits",
    "apply_shape_transforms",
    "build_ats_view",
    "budget_enforce",
    "claim_diff",
    "claims_preserved",
    "claims_preserved_across_sections",
    "compress_bullet",
    "compress_summary",
    "content_ledger_ok_perfect",
    "content_ledger_ok",
    "content_preserved",
    "detect_foundational_skills",
    "detect_summary_too_long",
    "finding_key",
    "foundational_skills",
    "rank_bullets",
    "rank_experience",
    "rank_skills",
    "project_builddoc_from_canonical",
    "project_scoredoc",
    "summary_too_long",
]
