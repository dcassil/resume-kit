"""Smoke-test that all public symbols are importable from resume_kit_export."""

from __future__ import annotations


def test_all_public_exports_importable() -> None:
    from resume_kit_export import (
        ExportFormat,
        ExportOptions,
        render,
        render_docx,
        render_pdf,
    )

    assert ExportFormat is not None
    assert ExportOptions is not None
    assert callable(render)
    assert callable(render_docx)
    assert callable(render_pdf)


def test_all_names_in_dunder_all() -> None:
    import resume_kit_export

    assert resume_kit_export.__all__ == [
        "ExportFormat",
        "ExportOptions",
        "render",
        "render_docx",
        "render_pdf",
    ]
