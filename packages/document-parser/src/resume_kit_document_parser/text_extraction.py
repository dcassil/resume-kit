# Derived from apps/backend/app/services/parser.py at upstream SHA
# 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc, Apache-2.0.
"""Deterministic, no-LLM text extraction from resume documents.

Supports PDF and DOCX via MarkItDown, and plain-text / Markdown via direct
UTF-8 decode.  No network calls are made; no LLM provider is contacted.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from markitdown import MarkItDown
from pydantic import BaseModel, Field
from resume_kit_core.errors import CoreWarning, WarningCode

# WarningCode.INVALID_INPUT does not exist in the current core taxonomy;
# use UNKNOWN as the stable catch-all for input-quality warnings until core
# adds a dedicated code.
_INPUT_WARNING_CODE = WarningCode.UNKNOWN

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported extension sets
# ---------------------------------------------------------------------------

_MARKITDOWN_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx"})
_PLAINTEXT_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown", ".txt"})

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class TextExtractionResult(BaseModel):
    """Result of a no-LLM text extraction operation.

    Carries the extracted text, any non-fatal warnings, and lightweight
    metadata sufficient for downstream reconciliation.  This model is
    intentionally narrow — a richer result model is defined in a separate
    task.
    """

    text: str = Field(description="Extracted plain-text / Markdown content.")
    warnings: list[CoreWarning] = Field(
        default_factory=list,
        description="Non-fatal advisory notices produced during extraction.",
    )
    filename: str = Field(description="Original filename supplied by the caller.")
    extraction_method: str = Field(
        description=(
            "How the text was obtained: 'markitdown' for PDF/DOCX, "
            "'decode' for plain-text or Markdown files."
        )
    )


# ---------------------------------------------------------------------------
# Low-level converter (ported from upstream parser.py, sync variant)
# ---------------------------------------------------------------------------


def parse_document(content: bytes, filename: str) -> str:
    """Convert PDF or DOCX bytes to Markdown text using MarkItDown.

    The function writes content to a temporary file (suffix preserved from
    *filename*), converts it with :class:`markitdown.MarkItDown`, then
    removes the temp file unconditionally.

    Args:
        content: Raw file bytes.
        filename: Original filename; the extension is used to choose the
            correct MarkItDown converter.

    Returns:
        Markdown text produced by MarkItDown.

    Raises:
        Exception: Re-raises any exception from MarkItDown after cleaning up
            the temporary file.
    """
    suffix = Path(filename).suffix.lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        md = MarkItDown()
        result = md.convert(str(tmp_path))
        return result.text_content
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# First-class no-LLM entrypoint
# ---------------------------------------------------------------------------


def extract_resume_text(content: bytes, filename: str) -> TextExtractionResult:
    """Extract resume text without contacting any LLM provider.

    Dispatch rules:
    - ``.md`` / ``.markdown`` / ``.txt`` — decoded directly from UTF-8
      (replacement character on errors) using the ``decode`` method.
    - ``.pdf`` / ``.docx`` — converted via :func:`parse_document` using
      MarkItDown (the ``markitdown`` method).
    - Any other extension, empty *content*, or decode/conversion failure —
      returns an empty string accompanied by a :attr:`WarningCode.INVALID_INPUT`
      warning.  Never raises; never contacts a provider.

    Args:
        content: Raw file bytes.
        filename: Original filename; the extension drives dispatch.

    Returns:
        :class:`TextExtractionResult` with ``text``, ``warnings``,
        ``filename``, and ``extraction_method`` populated.
    """
    warnings: list[CoreWarning] = []
    ext = Path(filename).suffix.lower()

    # ---- Guard: empty input ------------------------------------------------
    if not content:
        warnings.append(
            CoreWarning(
                code=_INPUT_WARNING_CODE,
                message=f"Empty content supplied for '{filename}'; returning empty text.",
            )
        )
        logger.warning("extract_resume_text: empty content for '%s'", filename)
        return TextExtractionResult(
            text="",
            warnings=warnings,
            filename=filename,
            extraction_method="none",
        )

    # ---- Plain-text / Markdown decode path ---------------------------------
    if ext in _PLAINTEXT_EXTENSIONS:
        text = content.decode("utf-8", errors="replace")
        if "�" in text:
            warnings.append(
                CoreWarning(
                    code=_INPUT_WARNING_CODE,
                    message=(
                        f"'{filename}' contained bytes that could not be decoded as UTF-8; "
                        "replacement characters (\\ufffd) were substituted."
                    ),
                )
            )
            logger.warning(
                "extract_resume_text: UTF-8 decode errors in '%s'", filename
            )
        return TextExtractionResult(
            text=text,
            warnings=warnings,
            filename=filename,
            extraction_method="decode",
        )

    # ---- MarkItDown path (PDF / DOCX) --------------------------------------
    if ext in _MARKITDOWN_EXTENSIONS:
        try:
            text = parse_document(content, filename)
            return TextExtractionResult(
                text=text,
                warnings=warnings,
                filename=filename,
                extraction_method="markitdown",
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(
                CoreWarning(
                    code=_INPUT_WARNING_CODE,
                    message=(
                        f"MarkItDown conversion failed for '{filename}': {exc}. "
                        "Returning empty text."
                    ),
                    details={"exception_type": type(exc).__name__, "filename": filename},
                )
            )
            logger.warning(
                "extract_resume_text: MarkItDown failed for '%s': %s", filename, exc
            )
            return TextExtractionResult(
                text="",
                warnings=warnings,
                filename=filename,
                extraction_method="markitdown",
            )

    # ---- Unsupported extension ---------------------------------------------
    warnings.append(
        CoreWarning(
            code=_INPUT_WARNING_CODE,
            message=(
                f"Unsupported file extension '{ext}' for '{filename}'. "
                "Supported extensions: "
                + ", ".join(sorted(_PLAINTEXT_EXTENSIONS | _MARKITDOWN_EXTENSIONS))
                + ". Returning empty text."
            ),
            details={"extension": ext, "filename": filename},
        )
    )
    logger.warning(
        "extract_resume_text: unsupported extension '%s' for '%s'", ext, filename
    )
    return TextExtractionResult(
        text="",
        warnings=warnings,
        filename=filename,
        extraction_method="none",
    )
