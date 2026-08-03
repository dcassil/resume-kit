"""Text/description coercion helpers for canonical resume models.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/schemas/models.py
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Extracted the private ``_extract_text_fragments`` / ``_coerce_text`` /
#   ``_coerce_optional_text`` / ``_split_description_lines`` / ``_coerce_string_list`` /
#   ``_coerce_description_styles`` / ``_align_description_styles`` helpers verbatim in
#   behavior into a standalone module (no HTTP/DB coupling); logic preserved so
#   upstream coercion/alignment behavior is reproduced exactly.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import re
from typing import Any, Literal

DescriptionStyle = Literal["bullet", "plain"]

_TEXT_VALUE_KEYS = (
    "text",
    "summary",
    "description",
    "value",
    "content",
    "title",
    "subtitle",
    "name",
    "label",
)
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")


def extract_text_fragments(value: Any, depth: int = 0, max_depth: int = 10) -> list[str]:
    """Extract text-like content from nested list/dict values."""
    if depth >= max_depth or value is None:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []

    if isinstance(value, (int, float)):
        return [str(value)]

    if isinstance(value, list):
        fragments: list[str] = []
        for item in value:
            fragments.extend(extract_text_fragments(item, depth + 1, max_depth))
        return fragments

    if isinstance(value, dict):
        fragments = []
        for key in _TEXT_VALUE_KEYS:
            if key in value:
                fragments.extend(extract_text_fragments(value.get(key), depth + 1, max_depth))
        if fragments:
            return fragments
        for nested in value.values():
            fragments.extend(extract_text_fragments(nested, depth + 1, max_depth))
        return fragments

    return []


def coerce_text(value: Any, joiner: str = " ") -> str:
    """Coerce nested values into a single text string."""
    return joiner.join(extract_text_fragments(value)).strip()


def coerce_optional_text(value: Any) -> str | None:
    """Coerce nested values into optional text."""
    if value is None:
        return None
    text = coerce_text(value)
    return text or None


def split_description_lines(value: str) -> list[str]:
    """Split a description block into clean bullet lines."""
    items: list[str] = []
    for raw_line in re.split(r"\r?\n+", value):
        line = _BULLET_PREFIX_RE.sub("", raw_line.strip())
        if line:
            items.append(line)
    return items


def coerce_string_list(value: Any) -> list[str]:
    """Coerce nested/string values into a list of strings."""
    if value is None:
        return []

    if isinstance(value, str):
        return split_description_lines(value)

    if isinstance(value, list):
        items: list[str] = []
        for entry in value:
            if isinstance(entry, str):
                items.extend(split_description_lines(entry))
                continue
            coerced = coerce_text(entry)
            if coerced:
                items.append(coerced)
        return items

    coerced = coerce_text(value)
    return [coerced] if coerced else []


def coerce_description_styles(value: Any) -> list[DescriptionStyle]:
    """Coerce description style values into supported row styles."""
    if not isinstance(value, list):
        return []
    return ["plain" if entry == "plain" else "bullet" for entry in value]


def align_description_styles(
    description: list[str],
    description_styles: list[DescriptionStyle],
) -> list[DescriptionStyle]:
    """Keep description styles aligned with description rows."""
    return [
        description_styles[index] if index < len(description_styles) else "bullet"
        for index, _ in enumerate(description)
    ]
