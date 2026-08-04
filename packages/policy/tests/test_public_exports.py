"""Public-export smoke tests for packages/policy.

Asserts that every name declared in ``resume_kit_policy.__all__`` is importable
directly from the package root. This test is deterministic and makes no network
calls.
"""

from __future__ import annotations

import importlib

import resume_kit_policy


def test_all_names_importable() -> None:
    """Every name in __all__ must be importable from the package root."""
    missing: list[str] = []
    for name in resume_kit_policy.__all__:
        if not hasattr(resume_kit_policy, name):
            missing.append(name)
    assert not missing, (
        "Names declared in resume_kit_policy.__all__ but not importable from the "
        "package root:\n" + "\n".join(f"  {n}" for n in missing)
    )


def test_all_is_defined() -> None:
    """The package must define a non-empty __all__."""
    assert hasattr(resume_kit_policy, "__all__"), "resume_kit_policy has no __all__"
    assert resume_kit_policy.__all__, "resume_kit_policy.__all__ is empty"


def test_package_importable() -> None:
    """The package itself must import cleanly."""
    mod = importlib.import_module("resume_kit_policy")
    assert mod is not None
