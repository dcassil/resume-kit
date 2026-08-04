"""Proof that a project alias file yields a match the seed alone misses."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from resume_kit_matching.keywords import _effective_alias_index, calculate_keyword_match
from resume_kit_terms.aliases import PROJECT_ALIAS_ENV_VAR


@pytest.fixture(autouse=True)
def _clear_index_cache() -> Iterator[None]:
    # The effective index is path-keyed and cached; clear it so each test's
    # env/file is honored and no stale index leaks across tests.
    _effective_alias_index.cache_clear()
    yield
    _effective_alias_index.cache_clear()


def _resume_with(skill: str) -> dict[str, object]:
    return {
        "summary": f"Experienced engineer skilled in {skill}.",
        "additional": {"technicalSkills": [skill]},
    }


def test_project_alias_produces_match_seed_misses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A wholly invented synonym pair the seed cannot possibly contain.
    resume = _resume_with("zorbulator")
    jd = {"keywords": ["quibblewidget"]}

    monkeypatch.delenv(PROJECT_ALIAS_ENV_VAR, raising=False)
    _effective_alias_index.cache_clear()
    assert calculate_keyword_match(resume, jd) == 0.0

    alias_file = tmp_path / "project_aliases.json"
    alias_file.write_text(
        json.dumps({"version": 1, "aliases": {"quibblewidget": ["zorbulator"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv(PROJECT_ALIAS_ENV_VAR, str(alias_file))
    _effective_alias_index.cache_clear()
    assert calculate_keyword_match(resume, jd) == 100.0
