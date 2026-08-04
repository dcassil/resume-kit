"""Resume Kit Alignment — Phase 4 controlled alignment: apply, diff, verify, generation, review."""

from .accept import (
    AcceptResult,
    ScoreDelta,
    accept_terminology_alignment,
    build_terminology_change,
    minimal_freedom_for_path,
)
from .apply import apply_diffs
from .diff import DiffConfidence, calculate_resume_diff
from .generation import generate_change_proposals, generate_skill_target_plan
from .orchestrator import align_resume
from .review import ReviewController
from .verify import verify_diff_result

__version__ = "0.0.0"

__all__ = [
    # accept
    "AcceptResult",
    "ScoreDelta",
    "accept_terminology_alignment",
    "build_terminology_change",
    "minimal_freedom_for_path",
    # apply
    "apply_diffs",
    # diff
    "DiffConfidence",
    "calculate_resume_diff",
    # generation
    "generate_change_proposals",
    "generate_skill_target_plan",
    # orchestrator
    "align_resume",
    # review
    "ReviewController",
    # verify
    "verify_diff_result",
]
