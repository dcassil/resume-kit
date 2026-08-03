"""Smoke-test that all public types are importable from the package root."""

from __future__ import annotations


def test_all_public_types_importable() -> None:
    from resume_kit_core import (
        ArtifactStore,
        CoreError,
        CoreWarning,
        InterfaceResponse,
        ResumeKitError,
        StructuredCompletionProvider,
    )

    # Basic structural checks
    assert StructuredCompletionProvider is not None
    assert ArtifactStore is not None
    assert InterfaceResponse is not None
    assert CoreError is not None
    assert CoreWarning is not None
    assert ResumeKitError is not None

    # Verify Protocols are runtime-checkable via isinstance
    from resume_kit_core.testing import FakeArtifactStore, FakeStructuredCompletionProvider

    assert isinstance(FakeStructuredCompletionProvider(), StructuredCompletionProvider)
    assert isinstance(FakeArtifactStore(), ArtifactStore)


def test_no_forbidden_imports() -> None:
    """Verify core modules don't import forbidden dependencies."""
    import importlib
    import sys

    forbidden = {"litellm", "sqlalchemy", "fastapi", "click", "typer"}

    # Import all core modules
    for mod_name in [
        "resume_kit_core",
        "resume_kit_core.errors",
        "resume_kit_core.providers",
        "resume_kit_core.storage",
        "resume_kit_core.response",
    ]:
        importlib.import_module(mod_name)

    loaded = set(sys.modules.keys())
    for forbidden_pkg in forbidden:
        assert forbidden_pkg not in loaded, f"Forbidden import found: {forbidden_pkg}"
