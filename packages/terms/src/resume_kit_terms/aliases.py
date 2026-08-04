"""Curated alias lexicon loading and lookup.

The alias layer bridges *true synonyms* that stemming cannot reach —
``k8s`` ↔ ``Kubernetes``, ``JS`` ↔ ``JavaScript``, ``RLS`` ↔ ``row-level
security``. It is deliberately separate from :func:`normalize`: morphological
variants are handled by the stemmer, and only genuine synonyms live here.

The lexicon ships as versioned package data (``data/aliases.json``) in an
append-only format::

    {
      "version": 1,
      "aliases": {
        "<canonical>": ["<alias>", "<alias>", ...],
        ...
      }
    }

Canonicals and aliases are stored human-readable; every entry is passed through
:func:`normalize` when the index is built, so the file stays legible while
lookups operate on canonical forms. RIT-I-0009 (agent-grown index) appends to
the same file/format without any schema change.
"""

from __future__ import annotations

import json
from pathlib import Path

from .normalize import normalize

# Default lexicon path: package data shipped alongside this module. RIT-T-0063
# populates this file with the full seed set; the loader here is agnostic to its
# contents.
DEFAULT_LEXICON_PATH = Path(__file__).parent / "data" / "aliases.json"


class LexiconError(ValueError):
    """Raised when the alias lexicon is malformed or ambiguous."""


def load_alias_lexicon(path: Path | None = None) -> dict[str, list[str]]:
    """Load and validate the raw canonical → aliases mapping from *path*.

    Returns the human-readable mapping exactly as stored (no normalization).
    Raises :class:`LexiconError` if the file is not the expected shape.
    """
    lexicon_path = path if path is not None else DEFAULT_LEXICON_PATH
    raw = json.loads(lexicon_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "aliases" not in raw:
        raise LexiconError(f"lexicon at {lexicon_path} must be an object with an 'aliases' key")
    aliases = raw["aliases"]
    if not isinstance(aliases, dict):
        raise LexiconError("'aliases' must be a mapping of canonical -> [alias, ...]")
    result: dict[str, list[str]] = {}
    for canonical, alias_list in aliases.items():
        if not isinstance(canonical, str) or not isinstance(alias_list, list):
            raise LexiconError(f"entry {canonical!r} must map a string to a list of strings")
        if not all(isinstance(a, str) for a in alias_list):
            raise LexiconError(f"all aliases for {canonical!r} must be strings")
        result[canonical] = list(alias_list)
    return result


class AliasIndex:
    """Precompiled, bidirectional index over the curated alias lexicon.

    Built once from the lexicon data and then queried per comparison. All lookups
    operate on :func:`normalize`-d forms so callers need not normalize first.
    """

    def __init__(self, mapping: dict[str, list[str]]):
        # Normalized canonical -> the full set of normalized members (the
        # canonical itself plus every alias). Members of the same group are
        # interchangeable.
        self._group_for_member: dict[str, set[str]] = {}
        # Normalized member -> normalized canonical, for provenance.
        self._canonical_of: dict[str, str] = {}

        for raw_canonical, raw_aliases in mapping.items():
            canonical = normalize(raw_canonical)
            if not canonical:
                raise LexiconError(f"canonical {raw_canonical!r} normalizes to empty")
            members = {canonical}
            for raw_alias in raw_aliases:
                alias = normalize(raw_alias)
                if not alias:
                    raise LexiconError(
                        f"alias {raw_alias!r} of {raw_canonical!r} normalizes to empty"
                    )
                members.add(alias)

            for member in members:
                existing = self._canonical_of.get(member)
                if existing is not None and existing != canonical:
                    # An alias mapping to two different canonicals would make
                    # matching non-deterministic — reject it at build time.
                    raise LexiconError(
                        f"term {member!r} maps to both {existing!r} and {canonical!r}"
                    )
                self._canonical_of[member] = canonical
                self._group_for_member[member] = members

    @classmethod
    def load(cls, path: Path | None = None) -> AliasIndex:
        """Build an :class:`AliasIndex` from the lexicon file at *path*."""
        return cls(load_alias_lexicon(path))

    def canonical_for(self, term: str) -> str | None:
        """Return the normalized canonical for *term*, or ``None`` if unknown.

        A term maps to itself's canonical whether it was listed as the canonical
        or as one of its aliases.
        """
        return self._canonical_of.get(normalize(term))

    def expand(self, term: str) -> set[str]:
        """Return every normalized form equivalent to *term*.

        If *term* is part of an alias group, returns the whole group (canonical +
        all aliases). Otherwise returns just ``{normalize(term)}`` so callers can
        always compare against a non-empty set.
        """
        key = normalize(term)
        group = self._group_for_member.get(key)
        if group is not None:
            return set(group)
        return {key} if key else set()
