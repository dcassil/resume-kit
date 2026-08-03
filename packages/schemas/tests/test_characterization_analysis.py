"""Characterization tests locking upstream refinement/ATS schema bounds.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/schemas/refinement.py and
#   apps/backend/app/schemas/models.py:577-616 (ATS score bounds)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Retargeted to canonical ``resume_kit_schemas.analysis`` names; locks
#   the 0-100 percentage bounds, the 1-5 refinement-pass bound, and default
#   filling of the ported refinement/ATS primitives.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import (
    AlignmentReport,
    ATSScore,
    KeywordGapAnalysis,
    RefinementConfig,
    RefinementStats,
)


def test_refinement_config_defaults() -> None:
    cfg = RefinementConfig()
    assert cfg.max_refinement_passes == 2
    assert cfg.enable_keyword_injection is True


@pytest.mark.parametrize("passes", [0, 6])
def test_refinement_config_rejects_out_of_range_passes(passes: int) -> None:
    with pytest.raises(ValidationError):
        RefinementConfig(max_refinement_passes=passes)


def test_keyword_gap_percentage_bounds() -> None:
    with pytest.raises(ValidationError):
        KeywordGapAnalysis(current_match_percentage=101.0)
    ok = KeywordGapAnalysis(current_match_percentage=100.0)
    assert ok.potential_match_percentage == 0.0


def test_ats_score_bounds_and_defaults() -> None:
    score = ATSScore()
    assert score.overall_score == 0.0
    assert score.sub_scores.keyword_match == 0.0
    with pytest.raises(ValidationError):
        ATSScore(overall_score=-1.0)


def test_alignment_report_confidence_bounds() -> None:
    assert AlignmentReport().is_aligned is True
    with pytest.raises(ValidationError):
        AlignmentReport(confidence_score=1.5)


def test_refinement_stats_non_negative() -> None:
    with pytest.raises(ValidationError):
        RefinementStats(passes_completed=-1)
