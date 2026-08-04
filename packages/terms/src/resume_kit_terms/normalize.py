"""Deterministic term normalization.

The single normalization pipeline used by every synonym-aware comparison in the
resume-kit engine. Applied, in order:

1. Unicode/ASCII fold  — NFKD-decompose then drop non-ASCII, so ``·`` (middle
   dot), curly quotes, and en/em dashes cannot defeat matching.
2. Casefold            — aggressive lowercasing for case-insensitive comparison.
3. Punctuation/space   — non-alphanumerics collapse to single spaces; the result
   is trimmed. ``Node.js`` and ``node js`` normalize the same.
4. Snowball stem       — English stemming, per whitespace token, so
   ``mentor / mentoring / mentorship / mentored`` collapse to a shared stem.

The function is pure and deterministic: identical input always yields identical
output. It performs no I/O and depends only on the stdlib plus ``snowballstemmer``.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import snowballstemmer  # type: ignore[import-untyped]

# A single, module-level English stemmer. ``snowballstemmer.stemmer`` builds a
# fresh object with compiled rules; instantiating it per call would be wasteful,
# so it is created once here and reused.
_STEMMER = snowballstemmer.stemmer("english")

# Anything that is not an ASCII letter or digit is treated as a separator.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _ascii_fold(text: str) -> str:
    """NFKD-decompose *text* and strip combining marks so accents fold to ASCII.

    ``unicodedata.normalize("NFKD", ...)`` splits accented characters into a base
    char plus combining marks (``é`` → ``e`` + ´); dropping the marks yields the
    ASCII base letter (``café`` → ``cafe``). Non-decomposing punctuation such as
    ``·``, curly quotes, and en/em dashes is intentionally left in place here — it
    is neutralized in the next step, where the punctuation/whitespace collapse
    turns every non-``[a-z0-9]`` character into a separator. Doing it this way
    (rather than ``encode("ascii", "ignore")``) means such glyphs act as word
    boundaries instead of silently vanishing and fusing adjacent tokens.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _stem_token(token: str) -> str:
    """Snowball-stem a single already-normalized token."""
    # snowballstemmer is untyped, so stemWord() returns Any; pin it to str.
    return str(_STEMMER.stemWord(token))


@lru_cache(maxsize=4096)
def surface_form(term: str) -> str:
    """Return *term* folded to a canonical surface form, WITHOUT stemming.

    This is :func:`normalize` minus the final Snowball step: ascii-fold →
    casefold → punctuation/space collapse. Two terms sharing a surface form are
    the *same* term modulo case/punctuation/Unicode noise; comparing surface
    forms lets callers tell an exact match apart from a stem-only match.

    >>> surface_form("Node.js")
    'node js'
    >>> surface_form("Mentoring")
    'mentoring'
    """
    folded = _ascii_fold(term)
    lowered = folded.casefold()
    return _NON_ALNUM.sub(" ", lowered).strip()


@lru_cache(maxsize=4096)
def normalize(term: str) -> str:
    """Return the canonical comparison form of *term*.

    Runs ascii-fold → casefold → punctuation/space collapse → per-token Snowball
    stem. Result is a single-spaced, lowercase, stemmed string (possibly empty
    if *term* held no alphanumerics).

    >>> normalize("Mentoring")
    'mentor'
    >>> normalize("Node.js")
    'node js'
    >>> normalize("  RESTful   APIs ")
    'rest api'
    """
    spaced = surface_form(term)
    if not spaced:
        return ""
    return " ".join(_stem_token(tok) for tok in spaced.split(" "))
