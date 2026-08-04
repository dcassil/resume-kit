"""Import-boundary enforcement for packages/matching.

Scans every .py source file under resume_kit_matching and asserts that
none contain direct imports of forbidden namespaces:

- ``from app.`` / ``import app.``  — upstream monolith coupling
- ``import litellm`` / ``from litellm`` — concrete LLM provider
- ``import openai`` / ``from openai`` — concrete LLM provider
- ``import anthropic`` / ``from anthropic`` — concrete LLM provider

Failures report the offending file and the exact line that triggered the check.
This test is deterministic and makes no network calls.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate the package source root
# ---------------------------------------------------------------------------

_PKG_ROOT = (
    Path(__file__).parent.parent
    / "src"
    / "resume_kit_matching"
)

# ---------------------------------------------------------------------------
# Forbidden patterns (compiled once)
# ---------------------------------------------------------------------------

_FORBIDDEN: list[tuple[str, re.Pattern[str]]] = [
    (
        "app.* import (monolith coupling)",
        re.compile(r"^\s*(from app\.|import app\.)"),
    ),
    (
        "litellm import (concrete LLM provider)",
        re.compile(r"^\s*(from litellm\b|import litellm\b)"),
    ),
    (
        "openai import (concrete LLM provider)",
        re.compile(r"^\s*(from openai\b|import openai\b)"),
    ),
    (
        "anthropic import (concrete LLM provider)",
        re.compile(r"^\s*(from anthropic\b|import anthropic\b)"),
    ),
]


def _collect_source_files() -> list[Path]:
    """Return all .py files under the package source root."""
    return sorted(_PKG_ROOT.rglob("*.py"))


def test_no_forbidden_imports() -> None:
    """Every source file must be free of forbidden import patterns."""
    source_files = _collect_source_files()
    assert source_files, f"No .py files found under {_PKG_ROOT} — check path"

    violations: list[str] = []

    for path in source_files:
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            for label, pattern in _FORBIDDEN:
                if pattern.search(line):
                    rel = path.relative_to(_PKG_ROOT.parent.parent)
                    violations.append(
                        f"{rel}:{lineno}: forbidden {label!r} — {line.strip()!r}"
                    )

    assert not violations, (
        "Import boundary violations detected in packages/matching:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_source_files_found() -> None:
    """Sanity check: the package source root contains at least the 5 known modules."""
    expected = {
        "keywords.py",
        "predicates.py",
        "match.py",
        "selection.py",
        "comparison.py",
    }
    found = {f.name for f in _collect_source_files()}
    missing = expected - found
    assert not missing, (
        f"Expected source files not found under {_PKG_ROOT}: {missing!r}"
    )
