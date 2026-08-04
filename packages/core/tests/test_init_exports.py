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


def test_interface_substrate_importable() -> None:
    """New interface substrate symbols are importable from the package root."""
    from resume_kit_core import (
        ExitCode,
        build_needs_input,
        build_provider_not_configured,
        build_success,
        escalate_warnings,
        exit_code_for,
        from_exception,
        from_resume_kit_error,
    )

    assert ExitCode is not None
    assert callable(build_success)
    assert callable(build_provider_not_configured)
    assert callable(from_resume_kit_error)
    assert callable(from_exception)
    assert callable(build_needs_input)
    assert callable(exit_code_for)
    assert callable(escalate_warnings)


def test_no_forbidden_imports() -> None:
    """Importing core in a clean interpreter pulls in no forbidden dependency.

    Runs in a subprocess so the check reflects only what importing core actually
    imports — an in-process ``sys.modules`` scan would be polluted by other test
    modules (e.g. the Phase 5 CLI/API tests legitimately import typer/fastapi).
    """
    import subprocess
    import sys

    script = (
        "import sys\n"
        "import resume_kit_core\n"
        "import resume_kit_core.errors\n"
        "import resume_kit_core.providers\n"
        "import resume_kit_core.storage\n"
        "import resume_kit_core.response\n"
        "forbidden = {'litellm', 'sqlalchemy', 'fastapi', 'click', 'typer'}\n"
        "hit = sorted(forbidden & set(sys.modules))\n"
        "assert not hit, hit\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
