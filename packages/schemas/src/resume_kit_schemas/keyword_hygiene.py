"""Deterministic keyword hygiene for the scored keyword denominator.

The parse-job interpretation step can misclassify a full requirement sentence
(e.g. "4-6+ years of professional experience building modern, large-scale web
applications") as a "skill". If such prose reaches the keyword-scoring
denominator it depresses the match score and clutters the missing / non-injectable
lists with phrases no resume would ever match verbatim.

This module is the single, deterministic gate that keeps ONLY concrete tokens.
It is pure (no I/O, no external deps) so identical inputs always produce
identical output — matching the deterministic-by-default contract of the
matching / job-parser layers that consume it.

Design note: we FILTER whole entries rather than splitting prose on commas.
Splitting a sentence on its commas would yield short fragments that falsely pass
the word cap; whole-entry filtering cleanly drops sentences (word count far over
the cap) while retaining the short skill tokens/phrases the subagent emits as
individual JSON array elements.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# A concrete keyword is a short token or noun phrase. Real skill phrases
# ("distributed systems design", "large-scale web application development") sit
# well under this cap; requirement prose runs far past it.
_MAX_KEYWORD_WORDS = 6

# Experience-year clauses ("5+ years", "4-6+ years of ...") are requirements,
# never matchable skill tokens — reject regardless of length.
_YEARS_CLAUSE = re.compile(r"\d+\s*\+?\s*(?:[-–]\s*\d+\s*\+?\s*)?years?", re.IGNORECASE)

# Terminal sentence punctuation followed by whitespace or end-of-string signals
# prose. The trailing (\s|$) guard means dotted tokens like "Node.js" are NOT
# rejected (the "." there is followed by "js", not whitespace/end).
_TERMINAL_PUNCT = re.compile(r"[.!?](\s|$)")


def is_concrete_keyword(text: str) -> bool:
    """Return True when *text* is a concrete, matchable keyword token/phrase.

    Rejects empty strings, multi-clause prose (over the word cap), experience-year
    clauses, and anything carrying terminal sentence punctuation. Everything else
    — short skill tokens and noun phrases — is accepted.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped.split()) > _MAX_KEYWORD_WORDS:
        return False
    if _YEARS_CLAUSE.search(stripped):
        return False
    # Terminal sentence punctuation → prose, not a keyword.
    return _TERMINAL_PUNCT.search(stripped) is None


def sanitize_keywords(entries: Iterable[str]) -> list[str]:
    """Return the concrete keywords from *entries*, deduped case-insensitively.

    Order-preserving (first occurrence wins). Non-concrete entries (prose,
    year clauses) are dropped. Deterministic: identical input → identical output.
    """
    out: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, str):
            continue
        candidate = entry.strip()
        if not is_concrete_keyword(candidate):
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out
