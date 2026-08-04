"""Tests for resume_kit_export.models and scaffold importability."""

from __future__ import annotations

import pytest
from resume_kit_export import ExportFormat, ExportOptions, render
from resume_kit_export.models import MIME_TYPES, mime_type

# ---------------------------------------------------------------------------
# ExportFormat
# ---------------------------------------------------------------------------


def test_export_format_pdf_value() -> None:
    assert ExportFormat.pdf == "pdf"


def test_export_format_docx_value() -> None:
    assert ExportFormat.docx == "docx"


def test_export_format_only_two_members() -> None:
    members = list(ExportFormat)
    assert set(members) == {ExportFormat.pdf, ExportFormat.docx}


def test_export_format_invalid_raises() -> None:
    with pytest.raises(ValueError):
        ExportFormat("xlsx")  # type: ignore[call-arg]


def test_export_format_is_str() -> None:
    assert isinstance(ExportFormat.pdf, str)
    assert isinstance(ExportFormat.docx, str)


# ---------------------------------------------------------------------------
# MIME mapping
# ---------------------------------------------------------------------------


def test_mime_pdf() -> None:
    assert mime_type(ExportFormat.pdf) == "application/pdf"


def test_mime_docx() -> None:
    assert mime_type(ExportFormat.docx) == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_mime_map_covers_all_formats() -> None:
    for fmt in ExportFormat:
        assert fmt in MIME_TYPES, f"MIME_TYPES missing entry for {fmt!r}"


# ---------------------------------------------------------------------------
# ExportOptions defaults are deterministic
# ---------------------------------------------------------------------------


def test_export_options_defaults_are_deterministic() -> None:
    a = ExportOptions()
    b = ExportOptions()
    assert a.model_dump() == b.model_dump()


def test_export_options_custom_values() -> None:
    opts = ExportOptions(font_family="Times", font_size_pt=12, margin_mm=15.0)
    assert opts.font_family == "Times"
    assert opts.font_size_pt == 12
    assert opts.margin_mm == 15.0


# ---------------------------------------------------------------------------
# Scaffold importability — render() raises ImportError (renderer not present)
# ---------------------------------------------------------------------------


def test_render_pdf_dispatches_to_renderer() -> None:
    from resume_kit_schemas.resume import ResumeDocument

    resume = ResumeDocument()
    data = render(resume, ExportFormat.pdf)
    assert data[:5] == b"%PDF-"


def test_render_docx_dispatches_to_renderer() -> None:
    from resume_kit_schemas.resume import ResumeDocument

    resume = ResumeDocument()
    data = render(resume, ExportFormat.docx)
    assert data[:2] == b"PK"


# ---------------------------------------------------------------------------
# Top-level import check
# ---------------------------------------------------------------------------


def test_top_level_exports() -> None:
    import resume_kit_export as pkg

    assert hasattr(pkg, "ExportFormat")
    assert hasattr(pkg, "ExportOptions")
    assert hasattr(pkg, "render")
