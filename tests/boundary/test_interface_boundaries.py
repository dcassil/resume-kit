"""Interface boundary tests (NFR-502 / NFR-503).

Enforces the Phase 5 layering rules by scanning source files as TEXT (never
importing target modules, so no import side effects and no upstream execution):

* Engine packages (``packages/*`` except the transport packages cli/mcp/api) must
  not import any interface package: ``resume_kit_cli``, ``resume_kit_mcp``,
  ``resume_kit_api``, ``resume_kit_facade``, or ``resume_kit_job_hunter_bridge``.
  The facade is engine-side and must not reach up into the transports or the bridge.
* ``resume_kit_facade`` must not import CLI/MCP/API/plugin or job-hunter bridge code
  (the facade sits below the transports).
* The job-hunter bridge (``integrations/job-hunter/src``) is a pure library and must
  not import any transport framework or transport package.
* Engine package ``pyproject.toml`` files must not declare transport dependencies.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[2]
PACKAGES_ROOT = REPO_ROOT / "packages"
FACADE_SRC = PACKAGES_ROOT / "facade" / "src"
BRIDGE_SRC = REPO_ROOT / "integrations" / "job-hunter" / "src"

# Phase 5 transport packages — excluded from the "engine" scans.
TRANSPORT_PACKAGES = {"cli", "mcp", "api"}

# Engine packages that ship a pyproject.toml we assert transport-dep-free against.
ENGINE_PACKAGES = (
    "core",
    "schemas",
    "document-parser",
    "matching",
    "ats",
    "job-parser",
    "policy",
    "evidence",
    "alignment",
    "facade",
)

# Interface / transport package modules an engine file must never import.
INTERFACE_MODULES = (
    "resume_kit_cli",
    "resume_kit_mcp",
    "resume_kit_api",
    "resume_kit_facade",
    "resume_kit_job_hunter_bridge",
)

# What the facade itself must never import (transports + plugin + bridge).
FACADE_FORBIDDEN_MODULES = (
    "resume_kit_cli",
    "resume_kit_mcp",
    "resume_kit_api",
    "resume_kit_plugin",
    "resume_kit_job_hunter_bridge",
)

# Transport frameworks/packages the pure-library bridge must never import.
BRIDGE_FORBIDDEN_MODULES = (
    "typer",
    "click",
    "mcp",
    "fastapi",
    "uvicorn",
    "httpx",
    "starlette",
    "requests",
    "resume_kit_cli",
    "resume_kit_mcp",
    "resume_kit_api",
)

# Transport deps that must not appear in engine pyproject.toml requirement lists.
FORBIDDEN_PYPROJECT_DEPS = (
    "typer",
    "click",
    "mcp",
    "fastapi",
    "uvicorn",
    "httpx",
    "starlette",
    "requests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_pattern(module: str) -> re.Pattern[str]:
    """Match ``import <module>`` / ``from <module> ...`` at line start (text scan)."""
    mod = re.escape(module)
    return re.compile(
        rf"^\s*(from\s+{mod}(\s*\.|\s|$)|import\s+{mod}(\s*\.|\s|$))",
        re.MULTILINE,
    )


def _collect_py(root: Path) -> list[Path]:
    """Return all .py files under ``root`` (excluding __pycache__), or empty list."""
    if not root.exists():
        return []
    return [p for p in root.glob("**/*.py") if "__pycache__" not in p.parts]


def _engine_py_files(exclude: frozenset[str] = frozenset()) -> list[Path]:
    """.py files under packages/*/src EXCEPT transport packages (and any ``exclude``)."""
    files: list[Path] = []
    for pkg_dir in sorted(PACKAGES_ROOT.glob("*")):
        if not pkg_dir.is_dir() or pkg_dir.name in TRANSPORT_PACKAGES:
            continue
        if pkg_dir.name in exclude:
            continue
        files.extend(_collect_py(pkg_dir / "src"))
    return files


def _dep_name(requirement: str) -> str:
    """Extract the bare distribution name from a PEP 508 requirement string."""
    return re.split(r"[<>=!~;\[\s]", requirement.strip(), maxsplit=1)[0].lower()


def _declared_deps(pyproject: Path) -> set[str]:
    """Return the set of distribution names declared in a pyproject.toml."""
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    deps: set[str] = set()
    project = data.get("project", {})
    for req in project.get("dependencies", []):
        deps.add(_dep_name(req))
    for group in project.get("optional-dependencies", {}).values():
        for req in group:
            deps.add(_dep_name(req))
    for group in data.get("dependency-groups", {}).values():
        for req in group:
            if isinstance(req, str):
                deps.add(_dep_name(req))
    return deps


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


# Precomputed parametrization inputs.
# Facade is scanned separately (test #2) so it can import itself; here we assert the
# rest of the engine does not import any interface package (including the facade).
_ENGINE_FILES = _engine_py_files(exclude=frozenset({"facade"}))
_FACADE_FILES = _collect_py(FACADE_SRC)
_BRIDGE_FILES = _collect_py(BRIDGE_SRC)


# ---------------------------------------------------------------------------
# 1. Engine must not import interface packages (NFR-502)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("py_file", _ENGINE_FILES, ids=_rel)
@pytest.mark.parametrize("module", INTERFACE_MODULES)
def test_engine_does_not_import_interface(py_file: Path, module: str) -> None:
    """Engine source must not import any interface/transport/bridge package."""
    source = py_file.read_text(encoding="utf-8")
    matches = _import_pattern(module).findall(source)
    assert not matches, (
        f"engine file {_rel(py_file)} imports interface package {module!r} "
        "(NFR-502: engine must not depend on interfaces)"
    )


# ---------------------------------------------------------------------------
# 2. Facade must not import transports / plugin / bridge
# ---------------------------------------------------------------------------


def test_facade_src_present() -> None:
    """Sanity: the facade source tree exists and has Python files to scan."""
    assert _FACADE_FILES, f"No facade source files found under {FACADE_SRC}"


@pytest.mark.parametrize("py_file", _FACADE_FILES, ids=_rel)
@pytest.mark.parametrize("module", FACADE_FORBIDDEN_MODULES)
def test_facade_does_not_import_upward(py_file: Path, module: str) -> None:
    """Facade must not import CLI/MCP/API/plugin/bridge (it sits below transports)."""
    source = py_file.read_text(encoding="utf-8")
    matches = _import_pattern(module).findall(source)
    assert not matches, (
        f"facade file {_rel(py_file)} imports forbidden module {module!r} "
        "(facade sits below the transports and must not reach upward)"
    )


# ---------------------------------------------------------------------------
# 3. Job-hunter bridge is a pure library — no transport deps
# ---------------------------------------------------------------------------


def test_bridge_src_present() -> None:
    """Sanity: the job-hunter bridge source tree exists and has Python files."""
    assert _BRIDGE_FILES, f"No bridge source files found under {BRIDGE_SRC}"


@pytest.mark.parametrize("py_file", _BRIDGE_FILES, ids=_rel)
@pytest.mark.parametrize("module", BRIDGE_FORBIDDEN_MODULES)
def test_bridge_does_not_import_transport(py_file: Path, module: str) -> None:
    """Bridge is a pure library and must not import transport frameworks/packages."""
    source = py_file.read_text(encoding="utf-8")
    matches = _import_pattern(module).findall(source)
    assert not matches, (
        f"bridge file {_rel(py_file)} imports transport module {module!r} "
        "(the job-hunter bridge must remain a pure library)"
    )


# ---------------------------------------------------------------------------
# 4. Engine pyproject.toml files must not declare transport deps (NFR-503)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pkg", ENGINE_PACKAGES)
def test_engine_pyproject_has_no_transport_deps(pkg: str) -> None:
    """Engine pyproject.toml must not declare a transport framework dependency."""
    pyproject = PACKAGES_ROOT / pkg / "pyproject.toml"
    assert pyproject.exists(), f"expected pyproject.toml for engine package {pkg!r}"
    declared = _declared_deps(pyproject)
    offending = sorted(declared & set(FORBIDDEN_PYPROJECT_DEPS))
    assert not offending, (
        f"engine package {pkg!r} ({_rel(pyproject)}) declares forbidden "
        f"transport dependency/dependencies {offending} (NFR-503)"
    )
