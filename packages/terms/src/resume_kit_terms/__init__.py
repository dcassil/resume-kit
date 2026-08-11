"""Resume Kit Terms — deterministic term normalization + synonym matching.

The single source of truth for how the ATS and matching engines compare terms.
Exposes a normalization pipeline (``normalize`` / ``surface_form``), a curated
alias lexicon index (``AliasIndex``), and a provenance-carrying comparison
(``match`` → ``MatchResult``). Pure, offline, deterministic — no LLM, no network.
"""

from .aliases import (
    AliasIndex,
    LexiconError,
    build_effective_alias_index,
    load_alias_lexicon,
    load_effective_alias_index,
)
from .match import MatchKind, MatchResult, match
from .normalize import normalize, surface_form

__version__ = "0.0.0"

__all__ = [
    "AliasIndex",
    "LexiconError",
    "MatchKind",
    "MatchResult",
    "build_effective_alias_index",
    "load_alias_lexicon",
    "load_effective_alias_index",
    "match",
    "normalize",
    "surface_form",
]
