"""REQ-606: Prove the umbrella ``resume-kit`` wheel is self-contained.

The test builds the root wheel, installs it into a *fresh* throwaway
virtualenv that has no PYTHONPATH pointing at the repo, and then asserts:

1. ``import resume_kit_facade; import resume_kit_export`` exits 0.
2. ``resume-tool --help`` exits 0 and its stdout contains ``"export"``.

Skip gate
---------
Set ``RESUME_KIT_SKIP_INSTALL_TEST=1`` to skip the whole module in CI
environments that cannot run pip (air-gapped without a warm cache, etc.).
The test runs by default and is also skipped gracefully when ``uv`` is not
found on PATH.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Skip gate
# ---------------------------------------------------------------------------
_SKIP_ENV = os.environ.get("RESUME_KIT_SKIP_INSTALL_TEST") == "1"
_UW_FOUND = shutil.which("uv") is not None

pytestmark = pytest.mark.skipif(
    _SKIP_ENV or not _UW_FOUND,
    reason=(
        "Skipped: set RESUME_KIT_SKIP_INSTALL_TEST=1 to skip explicitly, "
        "or 'uv' was not found on PATH."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
REPO_ROOT: Path = Path(__file__).parents[2]
_SCRIPTS = "Scripts" if os.name == "nt" else "bin"

_TIMEOUT_BUILD = 120  # seconds — wheel build
_TIMEOUT_VENV = 60   # seconds — venv creation
_TIMEOUT_PIP = 300   # seconds — pip install (may pull deps from PyPI)
_TIMEOUT_RUN = 30    # seconds — import / CLI check


def _sanitized_env() -> dict[str, str]:
    """Return os.environ minus any PYTHONPATH entries that point at the repo."""
    env = dict(os.environ)
    raw = env.get("PYTHONPATH", "")
    if raw:
        filtered = [
            p for p in raw.split(os.pathsep)
            if str(REPO_ROOT) not in p
        ]
        if filtered:
            env["PYTHONPATH"] = os.pathsep.join(filtered)
        else:
            env.pop("PYTHONPATH", None)
    # Unset VIRTUAL_ENV so venv is truly independent
    env.pop("VIRTUAL_ENV", None)
    env.pop("CONDA_PREFIX", None)
    return env


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

def test_umbrella_wheel_clean_venv_install(tmp_path: Path) -> None:
    """Build the umbrella wheel and install it into a throwaway venv."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    env = _sanitized_env()
    cwd_outside = tmp_path  # never CWD=repo for subprocess calls inside the venv

    # ------------------------------------------------------------------
    # 1. Build the umbrella wheel
    # ------------------------------------------------------------------
    build_result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_BUILD,
    )
    assert build_result.returncode == 0, (
        f"uv build failed:\nSTDOUT:\n{build_result.stdout}\nSTDERR:\n{build_result.stderr}"
    )

    wheels = glob.glob(str(dist_dir / "resume_kit-*.whl"))
    assert wheels, (
        f"No resume_kit-*.whl found in {dist_dir}.\n"
        f"uv build stdout:\n{build_result.stdout}\n"
        f"uv build stderr:\n{build_result.stderr}"
    )
    wheel_path = wheels[0]

    # ------------------------------------------------------------------
    # 2. Create a fresh throwaway virtualenv
    # ------------------------------------------------------------------
    venv_dir = tmp_path / "venv"
    venv_result = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_VENV,
    )
    assert venv_result.returncode == 0, (
        f"python -m venv failed:\nSTDOUT:\n{venv_result.stdout}\nSTDERR:\n{venv_result.stderr}"
    )

    venv_python = str(venv_dir / _SCRIPTS / "python")
    venv_resume_tool = str(venv_dir / _SCRIPTS / "resume-tool")

    # ------------------------------------------------------------------
    # 3. pip install '<wheel>[cli]' into the clean venv
    # ------------------------------------------------------------------
    install_result = subprocess.run(
        [
            venv_python, "-m", "pip", "install",
            "--no-input",
            f"{wheel_path}[cli]",
        ],
        cwd=str(cwd_outside),
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_PIP,
    )
    assert install_result.returncode == 0, (
        f"pip install failed:\nSTDOUT:\n{install_result.stdout}\nSTDERR:\n{install_result.stderr}"
    )

    # ------------------------------------------------------------------
    # 4a. Assert imports work inside the clean venv
    # ------------------------------------------------------------------
    import_result = subprocess.run(
        [
            venv_python, "-c",
            "import resume_kit_facade; import resume_kit_export",
        ],
        cwd=str(cwd_outside),
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_RUN,
    )
    assert import_result.returncode == 0, (
        "import resume_kit_facade / resume_kit_export failed inside clean venv.\n"
        f"STDOUT:\n{import_result.stdout}\nSTDERR:\n{import_result.stderr}"
    )

    # ------------------------------------------------------------------
    # 4b. Assert resume-tool --help works and lists the export command
    # ------------------------------------------------------------------
    help_result = subprocess.run(
        [venv_resume_tool, "--help"],
        cwd=str(cwd_outside),
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_RUN,
    )
    assert help_result.returncode == 0, (
        "resume-tool --help failed inside clean venv.\n"
        f"STDOUT:\n{help_result.stdout}\nSTDERR:\n{help_result.stderr}"
    )
    combined = (help_result.stdout + help_result.stderr).lower()
    assert "export" in combined, (
        f"'export' command not found in resume-tool --help output.\n"
        f"STDOUT:\n{help_result.stdout}\nSTDERR:\n{help_result.stderr}"
    )
