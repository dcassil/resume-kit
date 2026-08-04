"""Resume Kit Policy — freedom-aware path policy, sanitizer, truthfulness, and skill targets."""

from .path_policy import (
    ALLOWED_PATH_PATTERNS,
    BLOCKED_FIELD_NAMES,
    BLOCKED_PATH_PREFIXES,
    FREEDOM_MAX,
    FREEDOM_MIN,
    evaluate_change_policy,
    is_path_allowed,
    is_path_allowed_at_freedom,
    is_path_blocked,
)
from .sanitizer import INJECTION_PATTERNS, REDACTION, sanitize_user_input
from .skill_targets import (
    AllowedSkillTargetInput,
    JobKeywordsInput,
    PlannerOutput,
    ResumeInput,
    build_allowed_skill_target_keys,
    verify_skill_target_plan,
)
from .truthfulness import (
    CRITICAL_TRUTHFULNESS_RULES,
    CRITICAL_TRUTHFULNESS_RULES_TEMPLATE,
    build_truthfulness_rules,
)

__version__ = "0.0.0"

__all__ = [
    # path_policy
    "ALLOWED_PATH_PATTERNS",
    "BLOCKED_FIELD_NAMES",
    "BLOCKED_PATH_PREFIXES",
    "FREEDOM_MAX",
    "FREEDOM_MIN",
    "evaluate_change_policy",
    "is_path_allowed",
    "is_path_allowed_at_freedom",
    "is_path_blocked",
    # sanitizer
    "INJECTION_PATTERNS",
    "REDACTION",
    "sanitize_user_input",
    # skill_targets
    "AllowedSkillTargetInput",
    "JobKeywordsInput",
    "PlannerOutput",
    "ResumeInput",
    "build_allowed_skill_target_keys",
    "verify_skill_target_plan",
    # truthfulness
    "CRITICAL_TRUTHFULNESS_RULES",
    "CRITICAL_TRUTHFULNESS_RULES_TEMPLATE",
    "build_truthfulness_rules",
]
