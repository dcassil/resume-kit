"""Rendered page-count gate for resume exports."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from pydantic import BaseModel

from resume_kit_export.models import ExportFormat, ExportOptions
from resume_kit_export.render import render

if TYPE_CHECKING:
    from resume_kit_policy import ResumeShapePolicy
    from resume_kit_schemas.resume import ResumeDocument


class PageBudgetResult(BaseModel):
    """Result of checking rendered pages against the shape policy budget."""

    pages: int
    max_pages: int | None
    within_budget: bool
    blocked: bool
    overridden: bool = False
    message: str


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Count pages in rendered PDF bytes."""
    from pdfminer.high_level import extract_pages

    return sum(1 for _page in extract_pages(BytesIO(pdf_bytes)))


def check_page_budget(
    resume: ResumeDocument,
    policy: ResumeShapePolicy,
    *,
    options: ExportOptions | None = None,
    override: bool = False,
) -> PageBudgetResult:
    """Render *resume* to PDF and enforce the policy's rendered page budget."""
    pdf_bytes = render(resume, ExportFormat.pdf, options)
    pages = count_pdf_pages(pdf_bytes)
    max_pages = policy.informational_budgets.max_pages
    within_budget = max_pages is None or pages <= max_pages

    if within_budget:
        return PageBudgetResult(
            pages=pages,
            max_pages=max_pages,
            within_budget=True,
            blocked=False,
            overridden=False,
            message=_within_budget_message(pages, max_pages),
        )

    if override:
        return PageBudgetResult(
            pages=pages,
            max_pages=max_pages,
            within_budget=False,
            blocked=False,
            overridden=True,
            message=(
                f"Rendered resume is {pages} pages, exceeding the {max_pages}-page "
                "maximum; export allowed because the page budget override was used."
            ),
        )

    return PageBudgetResult(
        pages=pages,
        max_pages=max_pages,
        within_budget=False,
        blocked=True,
        overridden=False,
        message=(
            f"Export blocked: rendered resume is {pages} pages, exceeding the "
            f"{max_pages}-page maximum."
        ),
    )


def _within_budget_message(pages: int, max_pages: int | None) -> str:
    if max_pages is None:
        return f"Rendered resume is {pages} pages; no page maximum is configured."
    return f"Rendered resume is {pages} pages, within the {max_pages}-page maximum."
