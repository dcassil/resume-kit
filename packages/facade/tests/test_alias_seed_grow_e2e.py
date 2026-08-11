"""End-to-end seed → grow → dedupe → alias-aware re-score contract (RIT-T-0165).

The alias-seed flow is orchestration: the ``learn-terminology`` skill writes the
project ``synonyms.json`` (RIT-T-0068 format) per its documented append rule, and
``set_active(alias_file=...)`` persists the pointer (RIT-T-0167). These tests pin
the load-bearing behaviors that flow depends on, using the SAME primitives the
flow uses — no new matching logic:

* **Seed**: a fresh project starts with ``config.alias_file`` unset and a
  terminology miss; after seeding one confirmed pair and pointing the config at
  it, ``analyze_keyword_gaps`` honors the alias and coverage rises with no resume
  text change.
* **Grow + dedupe**: appending a second job's pair preserves the first job's
  entry, dedupes an already-present alias, and both pairs are honored on re-score.

The append helper here mirrors the skill's append rule exactly (idempotent,
justified, union, prior-preserving) so the contract is regression-locked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from resume_kit_facade.alias_scope import use_alias_file
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    set_active,
    working_dir,
)
from resume_kit_matching import analyze_keyword_gaps


def _resume_dict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "",
        "workExperience": [],
        "education": [],
        "personalProjects": [],
        "additional": {},
        "customSections": {},
    }
    base.update(overrides)
    return base


def _jd(*, required: list[str]) -> dict[str, Any]:
    return {"required_skills": required, "preferred_skills": [], "keywords": []}


def _append_confirmed_alias(alias_file: Path, canonical: str, alias: str, why: str) -> None:
    """Append one confirmed pair per the learn-terminology append rule.

    Idempotent, justified, union, prior-preserving; creates the empty shell if
    absent. This is the exact data shape the seed/grow flow writes.
    """
    if alias_file.exists():
        payload = json.loads(alias_file.read_text(encoding="utf-8"))
    else:
        payload = {"version": 1, "aliases": {}, "justifications": {}}
    aliases: dict[str, list[str]] = payload.setdefault("aliases", {})
    group = aliases.setdefault(canonical, [])
    # Case-insensitive de-dup: never add a duplicate surface form to a group.
    if all(existing.casefold() != alias.casefold() for existing in group):
        group.append(alias)
    payload.setdefault("justifications", {})[canonical] = why
    payload.setdefault("version", 1)
    alias_file.parent.mkdir(parents=True, exist_ok=True)
    alias_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_seed_creates_alias_and_raises_coverage(tmp_path: Path) -> None:
    init_project(tmp_path)
    # Fresh project: alias_file unset.
    assert load_config(tmp_path).alias_file is None

    resume = _resume_dict(summary="built responsive UI for the storefront")
    job = _jd(required=["responsive design"])

    # Before seeding: 'responsive design' is missing.
    before = analyze_keyword_gaps(job, resume, resume)
    assert "responsive design" in before.missing_keywords

    # Seed: write the confirmed pair, then register it via set_active (RIT-T-0167).
    alias_path = working_dir(tmp_path) / "learning" / "synonyms.json"
    _append_confirmed_alias(
        alias_path,
        canonical="responsive design",
        alias="responsive UI",
        why="responsive UI is the resume's wording for responsive design work",
    )
    config = set_active(tmp_path, alias_file="learning/synonyms.json")
    assert config.alias_file == "learning/synonyms.json"

    # Re-score honoring the alias: coverage rises, resume text unchanged.
    with use_alias_file(alias_path):
        after = analyze_keyword_gaps(job, resume, resume)
    assert "responsive design" not in after.missing_keywords
    assert after.current_match_percentage > before.current_match_percentage


def test_grow_appends_without_dropping_prior_and_dedupes(tmp_path: Path) -> None:
    init_project(tmp_path)
    alias_path = working_dir(tmp_path) / "learning" / "synonyms.json"

    # First job seeds one pair.
    _append_confirmed_alias(
        alias_path,
        canonical="responsive design",
        alias="responsive UI",
        why="same responsive front-end work",
    )
    set_active(tmp_path, alias_file="learning/synonyms.json")

    # Second job grows a NEW pair; re-appending the first pair must dedupe.
    _append_confirmed_alias(
        alias_path,
        canonical="observability",
        alias="monitoring",
        why="the resume's monitoring work is this role's observability",
    )
    _append_confirmed_alias(  # duplicate of the first — must not double-add
        alias_path,
        canonical="responsive design",
        alias="responsive UI",
        why="same responsive front-end work",
    )

    payload = json.loads(alias_path.read_text(encoding="utf-8"))
    # Prior entry preserved, new entry present, no duplicate surface form.
    assert payload["aliases"]["responsive design"] == ["responsive UI"]
    assert payload["aliases"]["observability"] == ["monitoring"]

    # Both pairs honored on re-score.
    resume = _resume_dict(
        summary="built responsive UI and ran monitoring for the platform"
    )
    job = _jd(required=["responsive design", "observability"])
    with use_alias_file(alias_path):
        gaps = analyze_keyword_gaps(job, resume, resume)
    assert gaps.missing_keywords == []
