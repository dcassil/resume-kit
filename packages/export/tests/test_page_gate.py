"""Tests for rendered page-count export gating."""

from __future__ import annotations

from io import BytesIO

import pytest
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]
from resume_kit_export import page_gate
from resume_kit_export.models import ExportFormat, ExportOptions
from resume_kit_policy.shape_policy import (
    InformationalShapeBudgets,
    ResumeShapePolicy,
)
from resume_kit_schemas.canonical import CanonicalSection
from resume_kit_schemas.resume import ResumeDocument


def _policy(max_pages: int | None) -> ResumeShapePolicy:
    return ResumeShapePolicy(
        section_order=[CanonicalSection.BASICS],
        section_aliases={},
        informational_budgets=InformationalShapeBudgets(max_pages=max_pages),
    )


def _patch_render_and_count(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pages: int,
) -> None:
    def fake_render(
        resume: ResumeDocument,
        fmt: ExportFormat,
        options: ExportOptions | None = None,
    ) -> bytes:
        assert resume == ResumeDocument()
        assert fmt is ExportFormat.pdf
        assert options is None
        return b"%PDF-fake"

    def fake_count_pdf_pages(pdf_bytes: bytes) -> int:
        assert pdf_bytes == b"%PDF-fake"
        return pages

    monkeypatch.setattr(page_gate, "render", fake_render)
    monkeypatch.setattr(page_gate, "count_pdf_pages", fake_count_pdf_pages)


def test_check_page_budget_blocks_over_length_without_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_render_and_count(monkeypatch, pages=3)

    result = page_gate.check_page_budget(ResumeDocument(), _policy(max_pages=2))

    assert result.pages == 3
    assert result.max_pages == 2
    assert result.within_budget is False
    assert result.blocked is True
    assert result.overridden is False
    assert "3 pages" in result.message
    assert "2-page maximum" in result.message
    assert "blocked" in result.message.lower()


def test_check_page_budget_allows_within_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_render_and_count(monkeypatch, pages=2)

    result = page_gate.check_page_budget(ResumeDocument(), _policy(max_pages=2))

    assert result.pages == 2
    assert result.max_pages == 2
    assert result.within_budget is True
    assert result.blocked is False
    assert result.overridden is False
    assert "within" in result.message


def test_check_page_budget_allows_over_length_with_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_render_and_count(monkeypatch, pages=4)

    result = page_gate.check_page_budget(
        ResumeDocument(), _policy(max_pages=2), override=True
    )

    assert result.pages == 4
    assert result.max_pages == 2
    assert result.within_budget is False
    assert result.blocked is False
    assert result.overridden is True
    assert "override" in result.message
    assert "4 pages" in result.message
    assert "2-page maximum" in result.message


def test_check_page_budget_allows_when_max_pages_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_render_and_count(monkeypatch, pages=9)

    result = page_gate.check_page_budget(ResumeDocument(), _policy(max_pages=None))

    assert result.pages == 9
    assert result.max_pages is None
    assert result.within_budget is True
    assert result.blocked is False
    assert result.overridden is False
    assert "no page maximum" in result.message


def test_count_pdf_pages_counts_tiny_real_pdf() -> None:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, "one page")
    pdf.save()

    assert page_gate.count_pdf_pages(buffer.getvalue()) == 1
