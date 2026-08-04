"""
Resume Kit Matching — Phase 3 keyword matching and job recommendation.

Provides matching, scoring, and recommendation services for aligning resume content
with job descriptions via keyword analysis, gap detection, and explainable matching.
"""

from .comparison import compare_versions
from .keywords import analyze_keyword_gaps, calculate_keyword_match
from .match import check_job_match
from .predicates import is_valid_resume, jd_keywords_present
from .selection import select_best

__version__ = "0.0.0"

__all__ = [
    "calculate_keyword_match",
    "analyze_keyword_gaps",
    "jd_keywords_present",
    "is_valid_resume",
    "check_job_match",
    "select_best",
    "compare_versions",
]
