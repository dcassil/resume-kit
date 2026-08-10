"""Unit tests for the alias lexicon loader and index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from resume_kit_terms import AliasIndex, LexiconError, load_alias_lexicon, normalize
from resume_kit_terms.aliases import DEFAULT_LEXICON_PATH


def _write_lexicon(tmp_path: Path, mapping: dict[str, list[str]]) -> Path:
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps({"version": 1, "aliases": mapping}), encoding="utf-8")
    return path


def test_default_lexicon_loads() -> None:
    # The shipped seed file must always load into a working index.
    index = AliasIndex.load()
    assert isinstance(index, AliasIndex)


def test_alias_and_canonical_share_a_canonical(tmp_path: Path) -> None:
    path = _write_lexicon(tmp_path, {"Kubernetes": ["k8s"]})
    index = AliasIndex.load(path)
    assert index.canonical_for("k8s") == index.canonical_for("Kubernetes")
    assert index.canonical_for("Kubernetes") == normalize("Kubernetes")


def test_expand_returns_whole_group(tmp_path: Path) -> None:
    path = _write_lexicon(tmp_path, {"JavaScript": ["JS", "ECMAScript"]})
    index = AliasIndex.load(path)
    group = index.expand("js")
    assert group == index.expand("JavaScript") == index.expand("ecmascript")
    assert normalize("JavaScript") in group
    assert normalize("JS") in group


def test_expand_unknown_term_returns_singleton(tmp_path: Path) -> None:
    path = _write_lexicon(tmp_path, {"Kubernetes": ["k8s"]})
    index = AliasIndex.load(path)
    assert index.expand("Golang") == {normalize("Golang")}


def test_canonical_for_unknown_is_none(tmp_path: Path) -> None:
    path = _write_lexicon(tmp_path, {"Kubernetes": ["k8s"]})
    index = AliasIndex.load(path)
    assert index.canonical_for("Terraform") is None


def test_multiword_alias_normalizes(tmp_path: Path) -> None:
    path = _write_lexicon(tmp_path, {"RLS": ["row-level security", "row level security"]})
    index = AliasIndex.load(path)
    assert index.canonical_for("row-level security") == index.canonical_for("RLS")


def test_max_member_tokens_single_token_index_is_one(tmp_path: Path) -> None:
    # An index whose members are all single tokens bounds the n-gram window to 1.
    path = _write_lexicon(tmp_path, {"Kubernetes": ["k8s"]})
    index = AliasIndex.load(path)
    assert index.max_member_tokens == 1


def test_max_member_tokens_reflects_longest_member(tmp_path: Path) -> None:
    # A three-token member ('row level security') widens the bound to 3.
    path = _write_lexicon(tmp_path, {"RLS": ["row-level security"]})
    index = AliasIndex.load(path)
    assert index.max_member_tokens == 3


def test_ambiguous_alias_rejected(tmp_path: Path) -> None:
    # An alias resolving to two canonicals would be non-deterministic.
    path = _write_lexicon(tmp_path, {"Go": ["golang"], "Golfing": ["golang"]})
    with pytest.raises(LexiconError):
        AliasIndex.load(path)


def test_malformed_lexicon_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 1}), encoding="utf-8")
    with pytest.raises(LexiconError):
        load_alias_lexicon(path)


def test_default_lexicon_has_no_ambiguous_entries() -> None:
    # Round-trip guard on the shipped file: it must build without raising and
    # every alias must map back to exactly one canonical.
    mapping = load_alias_lexicon(DEFAULT_LEXICON_PATH)
    index = AliasIndex(mapping)
    for canonical, aliases in mapping.items():
        canon_norm = index.canonical_for(canonical)
        assert canon_norm is not None
        for alias in aliases:
            assert index.canonical_for(alias) == canon_norm
