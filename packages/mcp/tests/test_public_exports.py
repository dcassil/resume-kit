"""Smoke-test that all public symbols are importable from resume_kit_mcp."""

from __future__ import annotations


def test_all_public_exports_importable() -> None:
    from resume_kit_mcp import HANDLERS, TOOL_NAMES, server

    assert isinstance(HANDLERS, dict)
    assert isinstance(TOOL_NAMES, tuple)
    assert server is not None


def test_all_names_in_dunder_all() -> None:
    import resume_kit_mcp

    assert hasattr(resume_kit_mcp, "__all__")
    assert "server" in resume_kit_mcp.__all__
    assert "HANDLERS" in resume_kit_mcp.__all__
    assert "TOOL_NAMES" in resume_kit_mcp.__all__
