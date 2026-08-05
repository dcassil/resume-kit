"""Boundary: packages/ must not import from upstream app or forbidden concrete deps.

Guards against:
- ``from app`` / ``import app`` (upstream application namespace) — everywhere
- ``litellm`` / ``openai`` / ``anthropic`` (concrete LLM provider SDKs) — everywhere
- ``sqlalchemy`` (ORM / persistence) — everywhere
- transport frameworks (``fastapi``, ``typer``, ``click``, ``mcp``, ``uvicorn``,
  ``httpx``, ``starlette``, ``requests``) —
  disallowed in ENGINE packages only. The Phase 5 transport packages (``cli``, ``mcp``,
  ``api``) legitimately depend on these, so they are exempt from the transport-framework
  checks (but never from the app/litellm/sqlalchemy checks). This encodes NFR-503: heavy
  transport deps must not leak into the engine.

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

# Phase 5 transport packages — exempt from the transport-framework checks only.
TRANSPORT_PACKAGES = {"cli", "mcp", "api"}

# Phase 6 render package — the ONLY package permitted to import the render
# libraries (reportlab / python-docx). It is engine-side (not a transport), so
# it is subject to every other check; only the render-lib scan below exempts it.
RENDER_PACKAGES = {"export"}

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
    # concrete provider SDKs (forbidden everywhere; engine and transports alike)
    (
        "openai import",
        re.compile(r"^\s*(from\s+openai(\s*\.|\s)|import\s+openai(\s+|$))", re.MULTILINE),
    ),
    (
        "anthropic import",
        re.compile(
            r"^\s*(from\s+anthropic(\s*\.|\s)|import\s+anthropic(\s+|$))", re.MULTILINE
        ),
    ),
]

# Render libraries (reportlab / python-docx, import name ``docx``): forbidden in
# EVERY engine package EXCEPT ``packages/export``. REQ-604/NFR-602 confines these
# heavy render deps to the export package so the rest of the engine stays free of
# them. Scanned via _collect_render_scoped_engine_files() (transports + export
# excluded); NOT added to ENGINE_ONLY_FORBIDDEN_PATTERNS, whose scan includes
# export and would false-positive on its legitimate render imports.
RENDER_LIB_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "reportlab import",
        re.compile(
            r"^\s*(from\s+reportlab(\s*\.|\s)|import\s+reportlab(\s+|$))", re.MULTILINE
        ),
    ),
    (
        "python-docx (docx) import",
        re.compile(r"^\s*(from\s+docx(\s*\.|\s)|import\s+docx(\s+|$))", re.MULTILINE),
    ),
]

# Transport frameworks: forbidden in ENGINE packages, allowed in TRANSPORT_PACKAGES.
ENGINE_ONLY_FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "fastapi import",
        re.compile(r"^\s*(from\s+fastapi|import\s+fastapi)", re.MULTILINE),
    ),
    (
        "typer import",
        re.compile(r"^\s*(from\s+typer|import\s+typer)", re.MULTILINE),
    ),
    (
        "click import",
        re.compile(r"^\s*(from\s+click(\s*\.|\s)|import\s+click(\s+|$))", re.MULTILINE),
    ),
    (
        "mcp SDK import",
        re.compile(r"^\s*(from\s+mcp(\s*\.|\s)|import\s+mcp(\s+|$))", re.MULTILINE),
    ),
    (
        "uvicorn import",
        re.compile(r"^\s*(from\s+uvicorn|import\s+uvicorn)", re.MULTILINE),
    ),
    (
        "httpx import",
        re.compile(r"^\s*(from\s+httpx|import\s+httpx)", re.MULTILINE),
    ),
    (
        "starlette import",
        re.compile(r"^\s*(from\s+starlette|import\s+starlette)", re.MULTILINE),
    ),
    (
        "requests import",
        re.compile(
            r"^\s*(from\s+requests(\s*\.|\s)|import\s+requests(\s+|$))", re.MULTILINE
        ),
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


def _collect_engine_python_files() -> list[Path]:
    """Return all .py under packages/*/src/ EXCEPT the transport packages."""
    return [
        p
        for p in _collect_python_files()
        if p.relative_to(PACKAGES_ROOT).parts[0] not in TRANSPORT_PACKAGES
    ]


def _collect_render_scoped_engine_files() -> list[Path]:
    """Engine .py files subject to the render-lib ban: exclude transports + export.

    ``packages/export`` legitimately imports reportlab / python-docx; every other
    engine package (schemas/core/document-parser/job-parser/ats/matching/policy/
    evidence/alignment/facade) must not.
    """
    excluded = TRANSPORT_PACKAGES | RENDER_PACKAGES
    return [
        p
        for p in _collect_python_files()
        if p.relative_to(PACKAGES_ROOT).parts[0] not in excluded
    ]


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
    expected = {
        "core",
        "schemas",
        "terms",
        "feedback",
        "document-parser",
        "matching",
        "ats",
        "job-parser",
        "policy",
        "evidence",
        "alignment",
        "facade",
        "cli",
        "mcp",
        "api",
        "export",
    }
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
    """Source file must not contain a forbidden import pattern (everywhere)."""
    source = py_file.read_text(encoding="utf-8")
    matches = pattern.findall(source)
    assert not matches, (
        f"{label!r} found in {py_file.relative_to(PACKAGES_ROOT.parent)!s}:\n"
        + "\n".join(f"  {m!r}" for m in matches)
    )


@pytest.mark.parametrize(
    "py_file",
    _collect_engine_python_files(),
    ids=lambda p: str(p.relative_to(PACKAGES_ROOT.parent)),
)
@pytest.mark.parametrize(
    "label,pattern",
    ENGINE_ONLY_FORBIDDEN_PATTERNS,
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_no_transport_dep_in_engine(
    py_file: Path, label: str, pattern: re.Pattern[str]
) -> None:
    """Engine package source must not import a transport framework (NFR-503).

    Transport packages (cli/mcp/api) legitimately depend on these and are excluded
    from this scan; they remain subject to the always-forbidden patterns above.
    """
    source = py_file.read_text(encoding="utf-8")
    matches = pattern.findall(source)
    assert not matches, (
        f"{label!r} found in ENGINE file {py_file.relative_to(PACKAGES_ROOT.parent)!s}:\n"
        + "\n".join(f"  {m!r}" for m in matches)
    )


@pytest.mark.parametrize(
    "py_file",
    _collect_render_scoped_engine_files(),
    ids=lambda p: str(p.relative_to(PACKAGES_ROOT.parent)),
)
@pytest.mark.parametrize(
    "label,pattern",
    RENDER_LIB_PATTERNS,
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_no_render_lib_in_non_export_engine(
    py_file: Path, label: str, pattern: re.Pattern[str]
) -> None:
    """Render libs (reportlab / python-docx) must live only in packages/export.

    REQ-604/NFR-602: confine heavy render deps to the export package. Transport
    packages and ``packages/export`` are excluded from this scan; every other
    engine package must not import reportlab or ``docx``.
    """
    source = py_file.read_text(encoding="utf-8")
    matches = pattern.findall(source)
    assert not matches, (
        f"{label!r} found in non-export engine file "
        f"{py_file.relative_to(PACKAGES_ROOT.parent)!s} — render libs are "
        "confined to packages/export (REQ-604/NFR-602):\n"
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
