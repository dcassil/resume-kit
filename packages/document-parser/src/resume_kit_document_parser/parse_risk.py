"""Bounded, deterministic source parse-risk detector (RIT-T-0122).

Inspects a SOURCE PDF/DOCX file (raw bytes, NOT parsed JSON) at ingest and
emits WARNING-severity structural findings that surface in the ``base``
structural report. These findings are advisory only: they are
``NEEDS_JUDGMENT`` and therefore land in the deferred list — they NEVER block
writing ``base`` and never mutate the resume.

The detector is deterministic (same bytes -> same findings), bounded, and never
raises: any parsing failure yields ``[]`` so a detector fault cannot break
ingest. It does NOT reconstruct layout or implement a renderer.

DOCX is inspected with the standard-library :mod:`zipfile` + light XML string
scanning (a ``.docx`` is a zip of WordprocessingML parts). This deliberately
avoids importing ``python-docx``: render libraries are confined to
``packages/export`` (REQ-604/NFR-602), and a bounded structural scan needs only
the raw XML, not a document object model. PDF image-only detection reuses this
package's own deterministic text extractor.

Cut line (RIT-T-0122):
  SHIP: all four DOCX detectors (table content, text box, header/footer,
    multi-column) + PDF image-only / scanned-page detection.
  DEFER to a follow-on initiative (require layout reconstruction, out of this
    bounded task's scope): PDF multi-column, PDF table-content, and PDF
    text-box detection.
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path

from resume_kit_schemas import (
    AtsStructureFinding,
    FindingSeverity,
    FixAffordance,
)

from resume_kit_document_parser.text_extraction import extract_resume_text

# ---------------------------------------------------------------------------
# Finding codes
# ---------------------------------------------------------------------------

SOURCE_LAYOUT_TABLE = "SOURCE_LAYOUT_TABLE"
SOURCE_LAYOUT_TEXTBOX = "SOURCE_LAYOUT_TEXTBOX"
SOURCE_LAYOUT_HEADER_FOOTER = "SOURCE_LAYOUT_HEADER_FOOTER"
SOURCE_LAYOUT_MULTICOLUMN = "SOURCE_LAYOUT_MULTICOLUMN"
SOURCE_LAYOUT_IMAGE_ONLY = "SOURCE_LAYOUT_IMAGE_ONLY"

_MESSAGES: dict[str, str] = {
    SOURCE_LAYOUT_TABLE: (
        "The source document lays out content in tables. Many ATS parsers "
        "flatten or scramble tabular content; verify the parsed resume reads "
        "in the intended order."
    ),
    SOURCE_LAYOUT_TEXTBOX: (
        "The source document contains text boxes. Text-box content is often "
        "dropped or reordered by ATS parsers; confirm nothing important was "
        "lost."
    ),
    SOURCE_LAYOUT_HEADER_FOOTER: (
        "The source document places content in a header or footer. ATS parsers "
        "commonly ignore header/footer text (including contact details); move "
        "essential information into the document body."
    ),
    SOURCE_LAYOUT_MULTICOLUMN: (
        "The source document uses a multi-column layout. Multi-column layouts "
        "are frequently read out of order by ATS parsers; a single-column "
        "layout parses more reliably."
    ),
    SOURCE_LAYOUT_IMAGE_ONLY: (
        "The source PDF yielded no extractable text — it appears to be a "
        "scanned or image-only document. ATS parsers cannot read image-only "
        "resumes; export a text-based PDF instead."
    ),
}


def _finding(code: str) -> AtsStructureFinding:
    return AtsStructureFinding(
        code=code,
        message=_MESSAGES[code],
        severity=FindingSeverity.WARNING,
        fix_affordance=FixAffordance.NEEDS_JUDGMENT,
    )


# ---------------------------------------------------------------------------
# DOCX detection (stdlib zipfile + XML string scan — no python-docx)
# ---------------------------------------------------------------------------

# A ``<w:t>...text...</w:t>`` run carrying at least one non-whitespace char.
_NONEMPTY_TEXT_RUN = re.compile(r"<w:t\b[^>]*>([^<]*\S[^<]*)</w:t>")
# The ``w:num`` attribute of a ``<w:cols ...>`` element (column count).
_COLS_NUM = re.compile(r"<w:cols\b[^>]*\bw:num=\"(\d+)\"")


def _read_part(zf: zipfile.ZipFile, name: str) -> str:
    try:
        return zf.read(name).decode("utf-8", errors="replace")
    except KeyError:
        return ""


def _detect_docx_risks(content: bytes) -> list[AtsStructureFinding]:
    findings: list[AtsStructureFinding] = []
    with zipfile.ZipFile(BytesIO(content)) as zf:
        names = set(zf.namelist())
        document_xml = _read_part(zf, "word/document.xml")

        if "<w:tbl>" in document_xml or "<w:tbl " in document_xml:
            findings.append(_finding(SOURCE_LAYOUT_TABLE))
        if "txbxContent" in document_xml:
            findings.append(_finding(SOURCE_LAYOUT_TEXTBOX))

        # Header/footer content: any header*/footer* part carrying real text.
        header_footer_parts = [
            n
            for n in names
            if re.fullmatch(r"word/(header|footer)\d*\.xml", n) is not None
        ]
        if any(
            _NONEMPTY_TEXT_RUN.search(_read_part(zf, part)) is not None
            for part in header_footer_parts
        ):
            findings.append(_finding(SOURCE_LAYOUT_HEADER_FOOTER))

        # Multi-column: a ``<w:cols>`` with an explicit ``w:num`` greater than 1
        # (absent ``w:num`` means a single column).
        if any(int(n) > 1 for n in _COLS_NUM.findall(document_xml)):
            findings.append(_finding(SOURCE_LAYOUT_MULTICOLUMN))

    return findings


# ---------------------------------------------------------------------------
# PDF detection (image-only / scanned only — see cut line)
# ---------------------------------------------------------------------------


def _detect_pdf_risks(content: bytes, filename: str) -> list[AtsStructureFinding]:
    result = extract_resume_text(content, filename)
    if not result.text.strip():
        return [_finding(SOURCE_LAYOUT_IMAGE_ONLY)]
    return []


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def detect_source_parse_risks(content: bytes, filename: str) -> list[AtsStructureFinding]:
    """Detect ATS parse-risk signals in a raw source ``.pdf`` / ``.docx`` file.

    Returns WARNING-severity, ``NEEDS_JUDGMENT`` findings (at most one per code).
    Deterministic and bounded; never raises — any failure yields ``[]``. Any
    extension other than ``.pdf`` / ``.docx`` yields ``[]``.
    """
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".docx":
            return _detect_docx_risks(content)
        if suffix == ".pdf":
            return _detect_pdf_risks(content, filename)
    except Exception:
        # A detector fault must never break ingest — swallow and return no risks.
        return []
    return []


__all__ = [
    "SOURCE_LAYOUT_HEADER_FOOTER",
    "SOURCE_LAYOUT_IMAGE_ONLY",
    "SOURCE_LAYOUT_MULTICOLUMN",
    "SOURCE_LAYOUT_TABLE",
    "SOURCE_LAYOUT_TEXTBOX",
    "detect_source_parse_risks",
]
