"""
Resume Kit ATS — Phase 3 deterministic ATS engine.

Provides ATS evaluation and scoring services for resume parsing and matching
based on deterministic rules and keyword extraction.
"""

from .engine import check_ats_structure, compute_ats_score
from .faithfulness import check_faithfulness

__version__ = "0.0.0"

__all__ = [
    "check_ats_structure",
    "check_faithfulness",
    "compute_ats_score",
]
