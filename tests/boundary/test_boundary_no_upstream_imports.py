"""Boundary: packages/ must not import from upstream app or forbidden concrete deps.

Guards against:
- ``from app`` / ``import app`` (upstream application namespace)
- ``litellm`` (concrete LLM provider SDK)
- ``sqlalchemy`` (ORM / persistence)
- ``fastapi`` (web framework — disallowed in core/schema packages)

Reads source files as text so upstream is never executed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PACKAGES_ROOT = Path(__file__).parents[2] / "packages"

# Patterns that must not appear anywhere in packages/*/src/**/*.py
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # upstream app namespace
    (
        "upstream 'app' import",
        re.compile(r"^\s*(from\s+app(\s*\.|$)|import\s+app(\s+|$))", re.MULTILINE),
    ),
    # concrete provider SDK
    (
        "litellm import",
        re.compile(r"^\s*(from\s+litellm|import\s+litellm)", re.MULTILINE),
    ),
    # ORM
    (
        "sqlalchemy import",
        re.compile(r"^\s*(from\s+sqlalchemy|import\s+sqlalchemy)", re.MULTILINE),
    ),
    # web framework
    (
        "fastapi import",
        re.compile(r"^\s*(from\s+fastapi|import\s+fastapi)", re.MULTILINE),
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_python_files() -> list[Path]:
    """Return all .py files under packages/*/src/."""
    if not PACKAGES_ROOT.exists():
        pytest.fail(f"packages/ directory not found at {PACKAGES_ROOT}")
    files = list(PACKAGES_ROOT.glob("*/src/**/*.py"))
    if not files:
        pytest.fail(f"No Python source files found under {PACKAGES_ROOT}")
    return files


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_packages_root_exists() -> None:
    """Sanity: the packages/ directory exists and is a directory."""
    assert PACKAGES_ROOT.is_dir(), f"Expected packages/ directory at {PACKAGES_ROOT}"


def test_known_packages_present() -> None:
    """Only known workspace packages exist under packages/.

    Phase 1 shipped ``core`` + ``schemas``; Phase 2 (RIT-I-0003) adds
    ``document-parser``. New packages must be added here as later phases land, so
    an accidental/unreviewed package under ``packages/`` is still caught.
    """
    package_dirs = sorted(
        p.name for p in PACKAGES_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    expected = {"core", "schemas", "document-parser", "matching", "ats", "job-parser"}
    unexpected = set(package_dirs) - expected
    assert not unexpected, (
        f"Unexpected package(s) found under packages/: {sorted(unexpected)}. "
        "Add the package to the expected set here once it is an intended phase deliverable."
    )


@pytest.mark.parametrize(
    "py_file",
    _collect_python_files(),
    ids=lambda p: str(p.relative_to(PACKAGES_ROOT.parent)),
)
@pytest.mark.parametrize(
    "label,pattern",
    FORBIDDEN_PATTERNS,
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_no_forbidden_import(py_file: Path, label: str, pattern: re.Pattern[str]) -> None:
    """Source file must not contain a forbidden import pattern."""
    source = py_file.read_text(encoding="utf-8")
    matches = pattern.findall(source)
    assert not matches, (
        f"{label!r} found in {py_file.relative_to(PACKAGES_ROOT.parent)!s}:\n"
        + "\n".join(f"  {m!r}" for m in matches)
    )


def test_py_typed_markers_present() -> None:
    """Both packages must ship a py.typed PEP-561 marker."""
    for pkg_name in ("core", "schemas"):
        pkg_dir = PACKAGES_ROOT / pkg_name
        # py.typed is usually placed in the src/<package>/ directory
        markers = list(pkg_dir.glob("**/py.typed"))
        assert markers, (
            f"No py.typed marker found in packages/{pkg_name}/. "
            "Both packages must be typed (PEP-561 compliant)."
        )


def test_workspace_members_via_pyproject() -> None:
    """Root pyproject.toml declares packages/* as workspace members."""
    import tomllib

    root_pyproject = PACKAGES_ROOT.parent / "pyproject.toml"
    assert root_pyproject.exists(), "root pyproject.toml not found"

    with root_pyproject.open("rb") as f:
        config = tomllib.load(f)

    members: list[str] = (
        config.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
        or config.get("tool", {}).get("hatch", {}).get("workspace", {}).get("members", [])
        or config.get("workspace", {}).get("members", [])
    )
    assert members, "No workspace members found in root pyproject.toml"

    # Accept either 'packages/*' glob or explicit entries for core and schemas
    has_glob = any("packages" in m for m in members)
    has_core = any("core" in m for m in members)
    has_schemas = any("schemas" in m for m in members)

    assert has_glob or (has_core and has_schemas), (
        f"Expected packages/* (or explicit core/schemas) in workspace members; got {members}"
    )
