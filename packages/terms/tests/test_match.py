"""Unit tests for synonym-aware matching and provenance."""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_terms import AliasIndex, match, normalize


def _index(tmp_path: Path, mapping: dict[str, list[str]]) -> AliasIndex:
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps({"version": 1, "aliases": mapping}), encoding="utf-8")
    return AliasIndex.load(path)


def test_exact_match() -> None:
    result = match("Python", "python")
    assert result.matched
    assert result.kind == "exact"
    assert result.canonical is None


def test_exact_match_through_punctuation() -> None:
    # Same term modulo punctuation/unicode is still exact, not stem.
    result = match("Node.js", "node js")
    assert result.matched
    assert result.kind == "exact"


def test_stem_match() -> None:
    # Inflectional variants collapse via stemming (mentoring / mentored -> mentor).
    result = match("mentoring", "mentored")
    assert result.matched
    assert result.kind == "stem"
    assert result.canonical is None


def test_allow_stem_false_skips_stem_tier() -> None:
    # With stemming disabled, a stem-only pair no longer matches. The engines
    # (matching + ats) run this way to avoid python/pythonic-style over-matching.
    assert not match("mentoring", "mentored", allow_stem=False).matched


def test_allow_stem_false_still_reports_exact() -> None:
    # allow_stem only gates the stem tier; exact still matches.
    assert match("Python", "python", allow_stem=False).kind == "exact"


def test_allow_stem_false_still_resolves_alias(tmp_path: Path) -> None:
    index = _index(tmp_path, {"Kubernetes": ["k8s"]})
    result = match("k8s", "Kubernetes", index, allow_stem=False)
    assert result.matched
    assert result.kind == "alias"


def test_alias_match(tmp_path: Path) -> None:
    index = _index(tmp_path, {"Kubernetes": ["k8s"]})
    result = match("k8s", "Kubernetes", index)
    assert result.matched
    assert result.kind == "alias"
    assert result.canonical == normalize("Kubernetes")


def test_alias_requires_index() -> None:
    # Without an index, an alias-only pair does not match.
    assert not match("k8s", "Kubernetes").matched


def test_precedence_exact_over_stem() -> None:
    # Identical terms report exact even though stemming would also equate them.
    assert match("mentoring", "mentoring").kind == "exact"


def test_no_match_unrelated() -> None:
    assert not match("React", "Vue").matched
    assert not match("Java", "JavaScript").matched


def test_empty_terms_never_match() -> None:
    assert not match("", "").matched
    assert not match("Python", "").matched
    assert not match("!!!", "Python").matched


def test_match_result_is_frozen() -> None:
    result = match("Python", "python")
    try:
        result.matched = False  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("MatchResult should be frozen")
