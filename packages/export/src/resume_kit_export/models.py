"""Export models: ExportFormat enum, ExportOptions, and MIME helpers."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ExportFormat(StrEnum):
    """Supported export output formats."""

    pdf = "pdf"
    docx = "docx"


MIME_TYPES: dict[ExportFormat, str] = {
    ExportFormat.pdf: "application/pdf",
    ExportFormat.docx: (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}


def mime_type(fmt: ExportFormat) -> str:
    """Return the MIME type string for *fmt*.

    Args:
        fmt: An :class:`ExportFormat` member.

    Returns:
        The corresponding MIME type string.
    """
    return MIME_TYPES[fmt]


class ExportOptions(BaseModel):
    """Deterministic, transport-agnostic export options.

    All fields have fixed, reproducible defaults — no timestamps, locale
    queries, UUIDs, random values, or filesystem path defaults.
    """

    font_family: str = Field(default="Helvetica", description="Base font family name.")
    font_size_pt: int = Field(default=11, description="Body font size in points.", gt=0)
    margin_mm: float = Field(
        default=20.0, description="Page margin in millimetres (all sides).", gt=0
    )
    include_hyperlinks: bool = Field(
        default=True, description="Render URLs as clickable hyperlinks when supported."
    )
    page_size: str = Field(
        default="letter",
        description="Page size identifier: 'letter' or 'a4'.",
    )
