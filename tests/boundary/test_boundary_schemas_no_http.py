"""Boundary: resume_kit_schemas must not import HTTP/web frameworks.

Domain models are transport-agnostic. This guard ensures no web framework
sneaks into the schemas package (fastapi, starlette, flask, django, aiohttp,
tornado, bottle, falcon, sanic, litestar, pydantic BaseSettings used for HTTP
config).

Reads source files as text — the upstream app is never imported.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCHEMAS_SRC = Path(__file__).parents[2] / "packages" / "schemas" / "src"

# Patterns forbidden in schemas source files
_HTTP_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "fastapi",
        re.compile(r"^\s*(from\s+fastapi|import\s+fastapi)", re.MULTILINE),
    ),
    (
        "starlette",
        re.compile(r"^\s*(from\s+starlette|import\s+starlette)", re.MULTILINE),
    ),
    (
        "flask",
        re.compile(r"^\s*(from\s+flask|import\s+flask)", re.MULTILINE),
    ),
    (
        "django",
        re.compile(r"^\s*(from\s+django|import\s+django)", re.MULTILINE),
    ),
    (
        "aiohttp",
        re.compile(r"^\s*(from\s+aiohttp|import\s+aiohttp)", re.MULTILINE),
    ),
    (
        "tornado",
        re.compile(r"^\s*(from\s+tornado|import\s+tornado)", re.MULTILINE),
    ),
    (
        "bottle",
        re.compile(r"^\s*(from\s+bottle|import\s+bottle)", re.MULTILINE),
    ),
    (
        "falcon",
        re.compile(r"^\s*(from\s+falcon|import\s+falcon)", re.MULTILINE),
    ),
    (
        "sanic",
        re.compile(r"^\s*(from\s+sanic|import\s+sanic)", re.MULTILINE),
    ),
    (
        "litestar",
        re.compile(r"^\s*(from\s+litestar|import\s+litestar)", re.MULTILINE),
    ),
    (
        "pydantic_settings (HTTP config pattern)",
        re.compile(r"^\s*(from\s+pydantic_settings|import\s+pydantic_settings)", re.MULTILINE),
    ),
    (
        "httpx",
        re.compile(r"^\s*(from\s+httpx|import\s+httpx)", re.MULTILINE),
    ),
    (
        "requests (HTTP client)",
        re.compile(r"^\s*(from\s+requests|import\s+requests)", re.MULTILINE),
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schemas_python_files() -> list[Path]:
    """Return all .py files under packages/schemas/src/."""
    if not SCHEMAS_SRC.exists():
        pytest.fail(f"schemas src directory not found at {SCHEMAS_SRC}")
    files = list(SCHEMAS_SRC.glob("**/*.py"))
    if not files:
        pytest.fail(f"No Python files found under {SCHEMAS_SRC}")
    return files


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_schemas_src_exists() -> None:
    """Sanity: packages/schemas/src exists."""
    assert SCHEMAS_SRC.is_dir(), f"Expected schemas src at {SCHEMAS_SRC}"


@pytest.mark.parametrize(
    "py_file",
    _schemas_python_files(),
    ids=lambda p: str(p.relative_to(SCHEMAS_SRC)),
)
@pytest.mark.parametrize(
    "label,pattern",
    _HTTP_PATTERNS,
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_schemas_no_http_framework(
    py_file: Path, label: str, pattern: re.Pattern[str]
) -> None:
    """Schema source file must not import any HTTP/web framework."""
    source = py_file.read_text(encoding="utf-8")
    matches = pattern.findall(source)
    assert not matches, (
        f"HTTP framework import ({label!r}) found in "
        f"{py_file.relative_to(SCHEMAS_SRC.parent.parent)!s}:\n"
        + "\n".join(f"  {m!r}" for m in matches)
    )


def test_schemas_allowed_deps_only() -> None:
    """All imports in schemas source must come from stdlib or pydantic only.

    Scans every ``from X`` / ``import X`` statement (one per logical line)
    for third-party top-level packages and flags anything that is not pydantic,
    the package's own namespace, or the stdlib.
    """
    import sys

    # Only these third-party top-level namespaces are permitted in schemas.
    ALLOWED_THIRD_PARTY: set[str] = {"pydantic"}
    # Own package namespace(s) — intra-package relative imports are also fine.
    OWN_NAMESPACES: set[str] = {"resume_kit_schemas"}
    # pseudo-stdlib
    ALWAYS_ALLOWED: set[str] = {"__future__"}

    stdlib_top = set(sys.stdlib_module_names)

    # Match "from <top>" or "import <top>" on a single line (no multi-line).
    from_re = re.compile(r"^\s*from\s+([\w]+)", re.MULTILINE)
    import_re = re.compile(r"^\s*import\s+([\w]+)", re.MULTILINE)

    violations: list[str] = []

    for py_file in _schemas_python_files():
        source = py_file.read_text(encoding="utf-8")
        rel = str(py_file.relative_to(SCHEMAS_SRC.parent.parent))

        allowed = stdlib_top | ALLOWED_THIRD_PARTY | OWN_NAMESPACES | ALWAYS_ALLOWED

        for match in from_re.finditer(source):
            mod = match.group(1)
            if mod in allowed:
                continue
            violations.append(f"{rel}: unexpected 'from {mod}' import")

        for match in import_re.finditer(source):
            mod = match.group(1)
            if mod in allowed:
                continue
            violations.append(f"{rel}: unexpected 'import {mod}' import")

    assert not violations, (
        "Unexpected third-party imports found in resume_kit_schemas:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
