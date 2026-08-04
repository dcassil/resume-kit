"""Smoke-test that all public symbols are importable from resume_kit_cli."""

from __future__ import annotations


def test_all_public_exports_importable() -> None:
    from resume_kit_cli import app, main

    assert app is not None
    assert callable(main)


def test_all_names_in_dunder_all() -> None:
    import resume_kit_cli

    assert hasattr(resume_kit_cli, "__all__")
    assert "app" in resume_kit_cli.__all__
    assert "main" in resume_kit_cli.__all__
