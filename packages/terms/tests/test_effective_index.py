"""Tests for the project-alias merge hook (``load_effective_alias_index``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from resume_kit_terms import (
    AliasIndex,
    LexiconError,
    load_alias_lexicon,
    load_effective_alias_index,
    normalize,
)
from resume_kit_terms.aliases import (
    DEFAULT_LEXICON_PATH,
    PROJECT_ALIAS_ENV_VAR,
)


def _write_project(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "project_aliases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_no_arg_no_env_is_seed_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PROJECT_ALIAS_ENV_VAR, raising=False)
    effective = load_effective_alias_index()
    seed = AliasIndex(load_alias_lexicon(DEFAULT_LEXICON_PATH))
    # A term absent from the seed must be absent from a seed-only effective index.
    assert effective.canonical_for("wibblewobble") is None
    assert seed.canonical_for("wibblewobble") is None


def test_missing_file_is_noop(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.json"
    effective = load_effective_alias_index(missing)
    assert effective.canonical_for("wibblewobble") is None


def test_empty_env_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PROJECT_ALIAS_ENV_VAR, "   ")
    effective = load_effective_alias_index()
    assert effective.canonical_for("wibblewobble") is None


def test_project_alias_creates_new_group(tmp_path: Path) -> None:
    path = _write_project(
        tmp_path, {"version": 1, "aliases": {"WibbleWobble": ["wobblewibble"]}}
    )
    effective = load_effective_alias_index(path)
    assert effective.canonical_for("wobblewibble") == effective.canonical_for("WibbleWobble")
    assert effective.canonical_for("WibbleWobble") == normalize("WibbleWobble")


def test_project_alias_extends_existing_seed_group(tmp_path: Path) -> None:
    # Union onto an existing seed canonical: add a fresh alias to a seed group.
    seed = load_alias_lexicon(DEFAULT_LEXICON_PATH)
    seed_canonical = next(iter(seed))
    path = _write_project(
        tmp_path,
        {"version": 1, "aliases": {seed_canonical: ["projectonlyaliasxyz"]}},
    )
    effective = load_effective_alias_index(path)
    assert effective.canonical_for("projectonlyaliasxyz") == normalize(seed_canonical)
    # And the pre-existing seed aliases still resolve to the same group.
    for alias in seed[seed_canonical]:
        assert effective.canonical_for(alias) == normalize(seed_canonical)


def test_justifications_are_ignored_metadata(tmp_path: Path) -> None:
    path = _write_project(
        tmp_path,
        {
            "version": 1,
            "aliases": {"WibbleWobble": ["wobblewibble"]},
            "justifications": {"WibbleWobble": "internal jargon"},
        },
    )
    # Justifications never surface in the raw mapping nor affect matching.
    mapping = load_alias_lexicon(path)
    assert "justifications" not in mapping
    effective = load_effective_alias_index(path)
    assert effective.canonical_for("wobblewibble") == effective.canonical_for("WibbleWobble")


def test_conflict_across_two_canonicals_raises(tmp_path: Path) -> None:
    # A project file that maps one term to two distinct canonicals is ambiguous.
    path = _write_project(
        tmp_path,
        {"version": 1, "aliases": {"AlphaThing": ["shared"], "BetaThing": ["shared"]}},
    )
    with pytest.raises(LexiconError):
        load_effective_alias_index(path)


def test_malformed_project_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 1}), encoding="utf-8")
    with pytest.raises(LexiconError):
        load_effective_alias_index(path)


def test_malformed_justifications_raises(tmp_path: Path) -> None:
    path = _write_project(
        tmp_path,
        {
            "version": 1,
            "aliases": {"WibbleWobble": ["wobblewibble"]},
            "justifications": {"WibbleWobble": 123},
        },
    )
    with pytest.raises(LexiconError):
        load_effective_alias_index(path)


def test_env_var_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_project(
        tmp_path, {"version": 1, "aliases": {"WibbleWobble": ["wobblewibble"]}}
    )
    monkeypatch.setenv(PROJECT_ALIAS_ENV_VAR, str(path))
    effective = load_effective_alias_index()
    assert effective.canonical_for("wobblewibble") == normalize("WibbleWobble")


def test_explicit_arg_beats_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    arg_path = _write_project(
        tmp_path, {"version": 1, "aliases": {"ArgThing": ["argalias"]}}
    )
    env_path = tmp_path / "env_aliases.json"
    env_path.write_text(
        json.dumps({"version": 1, "aliases": {"EnvThing": ["envalias"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv(PROJECT_ALIAS_ENV_VAR, str(env_path))
    effective = load_effective_alias_index(arg_path)
    # Explicit arg wins: arg alias present, env alias absent.
    assert effective.canonical_for("argalias") == normalize("ArgThing")
    assert effective.canonical_for("envalias") is None


def test_determinism_fixed_inputs(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "aliases": {
            "WibbleWobble": ["wobblewibble", "wib"],
            "FooBar": ["foob", "barf"],
        },
    }
    path = _write_project(tmp_path, payload)
    first = load_effective_alias_index(path)
    second = load_effective_alias_index(path)
    for term in ["wobblewibble", "wib", "foob", "barf", "WibbleWobble", "FooBar"]:
        assert first.canonical_for(term) == second.canonical_for(term)
        assert first.expand(term) == second.expand(term)
