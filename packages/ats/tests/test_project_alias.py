"""Proof that a project alias file yields an ATS skills match the seed misses."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from resume_kit_ats.engine import _compute_skills_coverage, _effective_alias_index
from resume_kit_terms.aliases import PROJECT_ALIAS_ENV_VAR


@pytest.fixture(autouse=True)
def _clear_index_cache() -> Iterator[None]:
    _effective_alias_index.cache_clear()
    yield
    _effective_alias_index.cache_clear()


def test_project_alias_produces_skills_match_seed_misses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resume = {"additional": {"technicalSkills": ["zorbulator"]}}
    jd = {"required_skills": ["quibblewidget"]}

    monkeypatch.delenv(PROJECT_ALIAS_ENV_VAR, raising=False)
    _effective_alias_index.cache_clear()
    score_seed, matched_seed = _compute_skills_coverage(resume, jd)
    assert score_seed == 0.0
    assert matched_seed == []

    alias_file = tmp_path / "project_aliases.json"
    alias_file.write_text(
        json.dumps({"version": 1, "aliases": {"quibblewidget": ["zorbulator"]}}),
        encoding="utf-8",
    )
    monkeypatch.setenv(PROJECT_ALIAS_ENV_VAR, str(alias_file))
    _effective_alias_index.cache_clear()
    score_project, matched_project = _compute_skills_coverage(resume, jd)
    assert score_project == 100.0
    assert len(matched_project) == 1
    assert matched_project[0].kind == "alias"
