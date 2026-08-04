"""Smoke-test that all public symbols are importable from resume_kit_api."""

from __future__ import annotations


def test_all_public_exports_importable() -> None:
    from resume_kit_api import app, create_app

    assert callable(create_app)
    assert app is not None


def test_all_names_in_dunder_all() -> None:
    import resume_kit_api

    assert hasattr(resume_kit_api, "__all__")
    assert "app" in resume_kit_api.__all__
    assert "create_app" in resume_kit_api.__all__
