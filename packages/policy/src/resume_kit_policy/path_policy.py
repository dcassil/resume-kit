"""Freedom-aware allowed/blocked path policy for resume alignment.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/improver.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Extracted the diff path gates out of the improver mega-module:
#   _ALLOWED_PATH_PATTERNS, _BLOCKED_PATH_PREFIXES, _BLOCKED_FIELD_NAMES,
#   _is_path_allowed, _is_path_blocked (incl. the education-description carve-out)
#   are ported verbatim as pure functions (is_path_allowed / is_path_blocked)
#   and characterization-tested to upstream parity. Generalized on top of that
#   parity substrate into a graduated freedom 0-10 policy: lower freedom exposes a
#   narrower subset of allowed paths, higher freedom exposes more editorial
#   latitude, but the blocked factual-field / blocked-prefix gates are applied at
#   EVERY level (including F10) so identity facts and invented metrics can never
#   be fabricated. Returns a schema PolicyDecision. No LLM, no app.* imports.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import re

from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.results import PolicyDecision, PolicyReasonCode

__all__ = [
    "ALLOWED_PATH_PATTERNS",
    "BLOCKED_FIELD_NAMES",
    "BLOCKED_PATH_PREFIXES",
    "FREEDOM_MAX",
    "FREEDOM_MIN",
    "evaluate_change_policy",
    "is_path_allowed",
    "is_path_blocked",
    "is_path_allowed_at_freedom",
]

FREEDOM_MIN = 0
FREEDOM_MAX = 10

# ---------------------------------------------------------------------------
# Upstream parity substrate (ported verbatim from improver.py)
# ---------------------------------------------------------------------------

# Allowed path patterns — only these can be modified by diffs (upstream full set).
ALLOWED_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^summary$"),
    re.compile(r"^workExperience\[\d+\]\.description(\[\d+\])?$"),
    re.compile(r"^personalProjects\[\d+\]\.description(\[\d+\])?$"),
    # Education description is a single string (Education.description: str | None),
    # so only the scalar path is allowed — not a [j]-indexed bullet form.
    re.compile(r"^education\[\d+\]\.description$"),
    re.compile(r"^additional\.technicalSkills$"),
    re.compile(r"^additional\.languages$"),
    re.compile(r"^additional\.certificationsTraining$"),
    re.compile(r"^additional\.awards$"),
]

# Blocked path prefixes — always rejected.
BLOCKED_PATH_PREFIXES: frozenset[str] = frozenset(
    {
        "personalInfo",
        "customSections",
        "sectionMeta",
    }
)

# Blocked field names — rejected when they appear as the leaf of a path.
BLOCKED_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "years",
        "company",
        "institution",
        "title",
        "degree",
        "name",
        "role",
        "github",
        "website",
        "location",
        "id",
    }
)


def is_path_allowed(path: str) -> bool:
    """Check if a path is in the (full upstream) allowed whitelist."""

    return any(pattern.match(path) for pattern in ALLOWED_PATH_PATTERNS)


def is_path_blocked(path: str) -> bool:
    """Check if a path matches any blocked pattern (upstream parity)."""

    for prefix in BLOCKED_PATH_PREFIXES:
        if (
            path == prefix
            or path.startswith(prefix + ".")
            or path.startswith(prefix + "[")
        ):
            return True

    # Check if the leaf field is blocked.
    segments = path.split(".")
    if segments:
        last_segment = segments[-1]
        field_name = re.sub(r"\[\d+\]$", "", last_segment)
        # "description" is the one allowed field that shares a name pattern.
        if field_name in BLOCKED_FIELD_NAMES and field_name != "description":
            return True

    if path.startswith("education"):
        # Education descriptions may be tailored; degree/institution/years stay
        # blocked (they are also caught by the blocked-leaf-name check above).
        return re.match(r"^education\[\d+\]\.description$", path) is None

    return False


# ---------------------------------------------------------------------------
# Freedom 0-10 ladder
# ---------------------------------------------------------------------------
#
# Each freedom level exposes a cumulative subset of the allowed-path patterns.
# Lower freedom = narrower edits (F0/F1: skills-only correction). Higher freedom
# = broader truthful latitude (summary, descriptions, then education
# description). The blocked-prefix / blocked-field gates below ALWAYS run — no
# freedom level, including F10, can edit a factual identity field or fabricate.

# Named path predicates, ordered from most-conservative to most-permissive.
_SKILLS_ONLY = re.compile(r"^additional\.technicalSkills$")
_OTHER_LISTS = re.compile(
    r"^additional\.(languages|certificationsTraining|awards)$"
)
_EXPERIENCE_DESC = re.compile(
    r"^(workExperience|personalProjects)\[\d+\]\.description(\[\d+\])?$"
)
_SUMMARY = re.compile(r"^summary$")
_EDUCATION_DESC = re.compile(r"^education\[\d+\]\.description$")

# freedom level -> the additional pattern unlocked at that level (cumulative).
_FREEDOM_UNLOCKS: list[tuple[int, re.Pattern[str]]] = [
    (0, _SKILLS_ONLY),
    (2, _OTHER_LISTS),
    (4, _EXPERIENCE_DESC),
    (6, _SUMMARY),
    (8, _EDUCATION_DESC),
]


def _allowed_patterns_at_freedom(freedom: int) -> list[re.Pattern[str]]:
    return [pattern for level, pattern in _FREEDOM_UNLOCKS if freedom >= level]


def is_path_allowed_at_freedom(path: str, freedom: int) -> bool:
    """Whether ``path`` is editable at ``freedom`` (ignores blocked gates)."""

    return any(
        pattern.match(path) for pattern in _allowed_patterns_at_freedom(freedom)
    )


def _clamp_freedom(freedom: int) -> int:
    return max(FREEDOM_MIN, min(FREEDOM_MAX, freedom))


def evaluate_change_policy(
    change: ChangeProposal, freedom: int
) -> PolicyDecision:
    """Return a freedom-aware allow/block decision for one proposed change.

    Evaluation order (block gates win over allow gates at every level):

    1. Blocked prefixes / blocked factual-leaf fields → always blocked, even at
       F10 (employer/company/title/role/date/name/degree/institution/location/
       URL/id).
    2. Malformed / non-editable paths not in the upstream allowed whitelist →
       blocked.
    3. Path is editable in principle but the freedom level is too low → blocked
       with ``FREEDOM_TOO_LOW``.
    4. Otherwise → allowed.
    """

    level = _clamp_freedom(freedom)
    path = change.path
    action = change.action

    def decide(
        allowed: bool, reason_code: PolicyReasonCode, explanation: str
    ) -> PolicyDecision:
        return PolicyDecision(
            freedom_level=level,
            allowed=allowed,
            reason_code=reason_code,
            explanation=explanation,
            path=path,
            action=action,
            change=change,
        )

    # 1. Factual / blocked fields are never editable, at any freedom level.
    if is_path_blocked(path):
        return decide(
            False,
            PolicyReasonCode.BLOCKED_FIELD,
            (
                f"Path '{path}' targets a protected factual field; it is blocked "
                "at every freedom level to prevent fabrication."
            ),
        )

    # 2. Paths outside the upstream allowed whitelist are non-editable.
    if not is_path_allowed(path):
        return decide(
            False,
            PolicyReasonCode.BLOCKED_PATH,
            f"Path '{path}' is not an editable target.",
        )

    # 3. Editable in principle, but this freedom level does not unlock it yet.
    if not is_path_allowed_at_freedom(path, level):
        return decide(
            False,
            PolicyReasonCode.FREEDOM_TOO_LOW,
            (
                f"Path '{path}' requires a higher freedom level than {level} to "
                "edit."
            ),
        )

    # 4. Allowed.
    return decide(
        True,
        PolicyReasonCode.ALLOWED,
        f"Path '{path}' is editable at freedom level {level}.",
    )
