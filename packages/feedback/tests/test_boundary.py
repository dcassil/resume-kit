"""Import-boundary test for the feedback package.

Asserts ``resume_kit_feedback`` depends only on stdlib, ``pydantic``, the
``resume_kit_schemas`` domain package, the deterministic scoring engines it
REUSES for candidate-feature extraction (``resume_kit_ats``,
``resume_kit_matching``, ``resume_kit_evidence`` — RIT-T-0087), and the shared
term lexicon (``resume_kit_terms``) — never on a transport/LLM package or a
forbidden concrete dependency. Reads source as text so nothing is executed.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).parents[1] / "src" / "resume_kit_feedback"

# resume_kit_schemas plus deterministic scoring/term engines are allowed; any
# OTHER resume-kit workspace package is disallowed.
_ALLOWED_RESUME_KIT = frozenset(
    {
        "resume_kit_schemas",
        "resume_kit_ats",
        "resume_kit_matching",
        "resume_kit_evidence",
        "resume_kit_terms",
    }
)
_RESUME_KIT_IMPORT = re.compile(r"^\s*(?:from|import)\s+(resume_kit_\w+)", re.MULTILINE)

# Concrete deps that must never appear (LLM SDKs, ORM, transport frameworks).
_FORBIDDEN_DEPS = re.compile(
    r"^\s*(?:from|import)\s+"
    r"(app|litellm|openai|anthropic|sqlalchemy|fastapi|typer|click|mcp|"
    r"uvicorn|httpx|starlette|requests)(?:\s|\.|$)",
    re.MULTILINE,
)


def _source_files() -> list[Path]:
    return sorted(SRC_ROOT.glob("**/*.py"))


def test_source_files_present() -> None:
    assert _source_files(), f"No source files under {SRC_ROOT}"


def test_no_sibling_package_imports() -> None:
    """Only schemas + reused deterministic engines may be imported."""
    offenders: list[str] = []
    for path in _source_files():
        for match in _RESUME_KIT_IMPORT.findall(path.read_text(encoding="utf-8")):
            if match not in _ALLOWED_RESUME_KIT:
                offenders.append(f"{path.name}: {match}")
    assert not offenders, (
        "feedback may only import "
        + ", ".join(sorted(_ALLOWED_RESUME_KIT))
        + " from the workspace; found: "
        + ", ".join(offenders)
    )


def test_no_forbidden_dependency_imports() -> None:
    """No LLM SDK, ORM, or transport-framework imports may leak in."""
    offenders: list[str] = []
    for path in _source_files():
        for match in _FORBIDDEN_DEPS.findall(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {match}")
    assert not offenders, "forbidden dependency import(s) found: " + ", ".join(offenders)
