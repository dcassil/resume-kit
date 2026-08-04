"""Resume Kit Evidence — candidate evidence building, truth validation, predicates, fabrication."""

from .builder import build_candidate_evidence, make_evidence_id, normalize_text
from .fabrication import fix_alignment_violations, validate_master_alignment
from .predicates import (
    flatten_resume_text,
    no_fabricated_employers,
    personal_info_unchanged,
    sections_preserved,
)
from .truth import validate_resume_truth

__version__ = "0.0.0"

__all__ = [
    # builder
    "build_candidate_evidence",
    "make_evidence_id",
    "normalize_text",
    # fabrication
    "fix_alignment_violations",
    "validate_master_alignment",
    # predicates
    "flatten_resume_text",
    "no_fabricated_employers",
    "personal_info_unchanged",
    "sections_preserved",
    # truth
    "validate_resume_truth",
]
