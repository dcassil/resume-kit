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
import os
from pathlib import Path

from .normalize import normalize

# Environment variable a surface (RIT-T-0069) sets to point the engine at a
# project alias file. Read only when no explicit path is passed to
# :func:`load_effective_alias_index`. Precedence: explicit arg > env var >
# seed-only.
PROJECT_ALIAS_ENV_VAR = "RESUME_KIT_ALIAS_FILE"

# Default lexicon path: package data shipped alongside this module. RIT-T-0063
# populates this file with the full seed set; the loader here is agnostic to its
# contents.
DEFAULT_LEXICON_PATH = Path(__file__).parent / "data" / "aliases.json"


class LexiconError(ValueError):
    """Raised when the alias lexicon is malformed or ambiguous."""


def load_alias_lexicon(path: Path | None = None) -> dict[str, list[str]]:
    """Load and validate the raw canonical → aliases mapping from *path*.

    Reads BOTH the packaged seed file and a project alias file: they share the
    same ``{"version": 1, "aliases": {canonical: [alias, ...]}}`` shape. A
    project file MAY additionally carry a top-level ``"justifications"`` object
    (``{canonical: "why"}``). Justifications are metadata for human review only —
    they are validated for shape but dropped here so they can NEVER affect
    matching. The returned mapping is the human-readable canonical → aliases
    mapping exactly as stored (no normalization).

    Raises :class:`LexiconError` if the file is not the expected shape.
    """
    lexicon_path = path if path is not None else DEFAULT_LEXICON_PATH
    raw = json.loads(lexicon_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "aliases" not in raw:
        raise LexiconError(f"lexicon at {lexicon_path} must be an object with an 'aliases' key")
    aliases = raw["aliases"]
    if not isinstance(aliases, dict):
        raise LexiconError("'aliases' must be a mapping of canonical -> [alias, ...]")
    # Justifications channel (project files only): optional metadata, shape-checked
    # but intentionally not returned — it must never influence the index.
    justifications = raw.get("justifications")
    if justifications is not None:
        if not isinstance(justifications, dict):
            raise LexiconError("'justifications' must be a mapping of canonical -> reason string")
        for canonical, reason in justifications.items():
            if not isinstance(canonical, str) or not isinstance(reason, str):
                raise LexiconError(
                    f"justification entry {canonical!r} must map a string to a string"
                )
    result: dict[str, list[str]] = {}
    for canonical, alias_list in aliases.items():
        if not isinstance(canonical, str) or not isinstance(alias_list, list):
            raise LexiconError(f"entry {canonical!r} must map a string to a list of strings")
        if not all(isinstance(a, str) for a in alias_list):
            raise LexiconError(f"all aliases for {canonical!r} must be strings")
        result[canonical] = list(alias_list)
    return result


def _resolve_project_path(project_path: Path | None) -> Path | None:
    """Resolve the effective project alias path.

    Precedence: explicit *project_path* argument > ``RESUME_KIT_ALIAS_FILE`` env
    var > ``None`` (seed-only). An absent, empty, or whitespace-only env value is
    treated as unset. This keeps ``calculate_keyword_match`` / ``compute_ats_score``
    signatures unchanged while letting surfaces point at a file via the env var.
    """
    if project_path is not None:
        return project_path
    env_value = os.environ.get(PROJECT_ALIAS_ENV_VAR)
    if env_value is None or not env_value.strip():
        return None
    return Path(env_value)


def _merge_mappings(
    seed: dict[str, list[str]],
    project: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Union *project* onto *seed*, keyed by normalized canonical.

    Merge semantics (documented in ``data/FORMAT.md``):

    - UNION by default. A project entry whose canonical normalizes to an existing
      seed canonical has its aliases added to that group. A project entry with a
      new canonical creates a new group.
    - A project alias that normalizes to a member of an existing seed group is
      folded into that group.
    - Conflict: if merging a project entry would place a term into two DISTINCT
      canonicals, that is genuinely ambiguous and is rejected by the downstream
      :class:`AliasIndex` build via the existing "term maps to two canonicals"
      guard — never silently or order-dependently resolved.

    The result maps each normalized canonical to a sorted list of its
    human-readable members. Sorting makes group membership and downstream
    provenance reproducible regardless of dict/set iteration order (NFR-902).
    """
    # Group human-readable members by normalized canonical. Members are kept in a
    # set (human-readable strings) and sorted at the end for determinism.
    members_by_canonical: dict[str, set[str]] = {}

    def _absorb(mapping: dict[str, list[str]]) -> None:
        for raw_canonical, raw_aliases in mapping.items():
            key = normalize(raw_canonical)
            if not key:
                raise LexiconError(f"canonical {raw_canonical!r} normalizes to empty")
            bucket = members_by_canonical.setdefault(key, set())
            bucket.add(raw_canonical)
            bucket.update(raw_aliases)

    _absorb(seed)
    _absorb(project)

    return {
        canonical: sorted(members)
        for canonical, members in sorted(members_by_canonical.items())
    }


def load_effective_alias_index(project_path: Path | None = None) -> AliasIndex:
    """Build the effective :class:`AliasIndex` from the seed plus an optional project file.

    Loads the packaged seed mapping, then — if a project file is resolved and
    exists — loads and UNIONs it on top, building a single index. Path resolution
    precedence: explicit *project_path* > ``RESUME_KIT_ALIAS_FILE`` env var >
    seed-only.

    No-op cases (effective index == seed):

    - *project_path* is ``None`` and the env var is unset / empty / whitespace.
    - The resolved path does not exist.

    A malformed project file raises :class:`LexiconError` (never a silent partial
    load), and a project entry that would make a term ambiguous across two
    canonicals is rejected at build time.
    """
    seed = load_alias_lexicon(DEFAULT_LEXICON_PATH)
    resolved = _resolve_project_path(project_path)
    if resolved is None or not resolved.exists():
        return AliasIndex(seed)
    project = load_alias_lexicon(resolved)
    return AliasIndex(_merge_mappings(seed, project))


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
        # Largest token-count of any member surface form in this index. Callers
        # that scan text with an n-gram window use this to BOUND the window to
        # exactly what the lexicon can match — never wider — so multi-token
        # aliases (e.g. ``responsive design``) can be assembled while a
        # single-token lexicon still scans one token at a time.
        self._max_member_tokens: int = 1

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
                # normalize() is per-token, so a member's token count is stable
                # between its normalized and surface forms — count it here.
                token_count = len(member.split(" ")) if member else 1
                if token_count > self._max_member_tokens:
                    self._max_member_tokens = token_count

    @classmethod
    def load(cls, path: Path | None = None) -> AliasIndex:
        """Build an :class:`AliasIndex` from the lexicon file at *path*."""
        return cls(load_alias_lexicon(path))

    @property
    def max_member_tokens(self) -> int:
        """Return the largest token-count of any member surface form.

        A single-token-only index returns ``1``. Callers scanning text with an
        n-gram window multiply nothing beyond this: the window is bounded BY THE
        INDEX, so it can assemble multi-token aliases the lexicon actually holds
        while never widening past them (which would risk substring/derivational
        false positives).
        """
        return self._max_member_tokens

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
