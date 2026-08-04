"""Synonym-aware term matching with explainable provenance.

:func:`match` is the primitive the ATS and matching engines call instead of a
bare casefold-equality check. It returns not just *whether* two terms match but
*why* — ``exact``, ``stem``, or ``alias`` — so downstream consumers (RIT-I-0010,
terminology alignment) can tell an exact hit apart from a synonym hit.

Match precedence, highest first:

- ``exact``  — the terms share a surface form (equal modulo case/punctuation/
  Unicode noise), no stemming or alias needed.
- ``stem``   — the terms are equal only after Snowball stemming
  (``mentoring`` ↔ ``mentorship``).
- ``alias``  — the terms are equal only through the curated alias index
  (``k8s`` ↔ ``Kubernetes``); ``canonical`` names the group.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .aliases import AliasIndex
from .normalize import normalize, surface_form

MatchKind = Literal["exact", "stem", "alias"]


class MatchResult(BaseModel):
    """The outcome of comparing two terms, with provenance.

    ``matched`` is whether the terms are considered equivalent; ``kind`` explains
    how (``None`` when they do not match). ``canonical`` is populated only for
    ``alias`` matches, naming the normalized canonical of the alias group.
    """

    model_config = {"frozen": True}

    matched: bool
    kind: MatchKind | None = None
    canonical: str | None = None


_NO_MATCH = MatchResult(matched=False)


def match(
    a: str,
    b: str,
    alias_index: AliasIndex | None = None,
    *,
    allow_stem: bool = True,
) -> MatchResult:
    """Compare *a* and *b* and return a :class:`MatchResult` with provenance.

    Alias resolution is only attempted when *alias_index* is supplied. Empty /
    whitespace-only terms never match.

    When *allow_stem* is ``False`` the ``stem`` tier is skipped entirely: only
    ``exact`` and ``alias`` matches are reported. This exists because Snowball
    stemming is all-or-nothing — it correctly collapses ``test``/``testing`` but
    also over-collapses ``python``/``pythonic`` and ``go``/``going``. The resume
    engines (RIT-I-0008) opt out of stemming and rely on the curated alias
    lexicon for genuine synonyms so the score never over-matches (NFR-803). Both
    the ``matching`` and ``ats`` engines pass ``allow_stem=False`` — this is the
    single knob that keeps their behavior identical.
    """
    surface_a = surface_form(a)
    surface_b = surface_form(b)
    if not surface_a or not surface_b:
        return _NO_MATCH

    # exact — same surface form, no stemming needed.
    if surface_a == surface_b:
        return MatchResult(matched=True, kind="exact")

    # stem — equal only after stemming.
    if allow_stem:
        norm_a = normalize(a)
        norm_b = normalize(b)
        if norm_a and norm_a == norm_b:
            return MatchResult(matched=True, kind="stem")

    # alias — equal only through the curated lexicon.
    if alias_index is not None:
        canonical_a = alias_index.canonical_for(a)
        canonical_b = alias_index.canonical_for(b)
        if canonical_a is not None and canonical_a == canonical_b:
            return MatchResult(matched=True, kind="alias", canonical=canonical_a)

    return _NO_MATCH
