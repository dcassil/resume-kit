"""Round-trip and coverage tests for the shipped seed alias lexicon.

These assert the real ``data/aliases.json`` (not a fixture) loads, is
unambiguous, and covers the specific synonym cases the initiative targets.
"""

from __future__ import annotations

import pytest
from resume_kit_terms import AliasIndex, match
from resume_kit_terms.aliases import DEFAULT_LEXICON_PATH, load_alias_lexicon


@pytest.fixture(scope="module")
def index() -> AliasIndex:
    return AliasIndex.load()


def test_seed_loads_and_is_unambiguous() -> None:
    # Building the index enforces no-duplicate / no-ambiguous-alias at load time.
    mapping = load_alias_lexicon(DEFAULT_LEXICON_PATH)
    index = AliasIndex(mapping)
    # Every canonical and alias must resolve back to exactly one canonical.
    for canonical, aliases in mapping.items():
        canon_norm = index.canonical_for(canonical)
        assert canon_norm is not None, canonical
        for alias in aliases:
            assert index.canonical_for(alias) == canon_norm, (alias, canonical)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("k8s", "Kubernetes"),
        ("JS", "JavaScript"),
        ("TS", "TypeScript"),
        ("Node", "Node.js"),
        ("Postgres", "PostgreSQL"),
        ("RLS", "row-level security"),
        ("GH Actions", "GitHub Actions"),
        ("Go", "Golang"),
        ("CI", "continuous integration"),
        ("CD", "continuous delivery"),
        ("AWS", "Amazon Web Services"),
        # The derivational bridge Snowball cannot make:
        ("mentorship", "mentoring"),
        # Tool <-> activity:
        ("ESLint", "linting"),
    ],
)
def test_seed_bridges_target_synonyms(index: AliasIndex, a: str, b: str) -> None:
    result = match(a, b, index)
    assert result.matched, f"{a!r} should match {b!r}"
    assert result.kind == "alias"
    assert result.canonical is not None


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Java", "JavaScript"),
        ("React", "Vue"),
        ("Go", "Golfing"),
        ("Python", "PyTorch"),
    ],
)
def test_seed_does_not_over_match(index: AliasIndex, a: str, b: str) -> None:
    assert not match(a, b, index).matched, f"{a!r} must NOT match {b!r}"


def test_continuous_delivery_and_deployment_share_group(index: AliasIndex) -> None:
    # Merged to avoid the ambiguous 'cd' alias; both resolve to one canonical.
    assert index.canonical_for("continuous deployment") == index.canonical_for("cd")
    assert index.canonical_for("cd") == index.canonical_for("continuous delivery")
