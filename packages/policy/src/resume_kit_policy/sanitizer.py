"""Deterministic prompt-injection sanitizer.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/improver.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Extracted _INJECTION_PATTERNS (LLM-011) and _sanitize_user_input out
#   of the improver mega-module into this standalone, provider-free guard.
#   Exposed the private helper as public sanitize_user_input; the injection
#   patterns and case-insensitive [REDACTED] substitution behavior are preserved
#   exactly. No LLM, no app.* imports.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import re

__all__ = ["INJECTION_PATTERNS", "REDACTION", "sanitize_user_input"]

REDACTION = "[REDACTED]"

# LLM-011: Prompt injection patterns to sanitize.
INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?above",
    r"forget\s+(everything|all)",
    r"new\s+instructions?:",
    r"system\s*:",
    r"<\s*/?\s*system\s*>",
    r"\[\s*INST\s*\]",
    r"\[\s*/\s*INST\s*\]",
]

_COMPILED_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, flags=re.IGNORECASE) for pattern in INJECTION_PATTERNS
]


def sanitize_user_input(text: str) -> str:
    """LLM-011: Sanitize user input to prevent prompt injection.

    Removes or redacts common injection patterns that could manipulate LLM
    behavior, replacing each match with ``[REDACTED]`` (case-insensitive).
    """

    sanitized = text
    for pattern in _COMPILED_INJECTION_PATTERNS:
        sanitized = pattern.sub(REDACTION, sanitized)
    return sanitized
