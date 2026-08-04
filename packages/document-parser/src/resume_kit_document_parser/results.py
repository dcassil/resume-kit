"""Parse-result contracts for the document-parser package.

These types define the surface area consumed by the structured-parse adapter
and any downstream caller that receives a :class:`ParseResult`.  They compose
existing ``resume-kit-core`` and ``resume-kit-schemas`` types rather than
duplicating them.

Provenance semantics
--------------------
Every :class:`ParseResult` carries a ``provenance`` list whose entries record:

- ``source_id``: the originating filename or a human-readable identifier for
  the input bytes (e.g. ``"resume.pdf"``).
- ``source_type``: ``"file"`` for deterministic extraction; ``"llm_response"``
  for LLM-assisted structured parsing.
- ``metadata``: a dict that MUST contain at least ``"parser"`` (the parser
  class/identifier) and ``"method"`` (the :class:`ParseMethod` member name).

No-LLM / text-only signaling
-----------------------------
When structured parsing is unavailable (no LLM configured, provider
unreachable, or parse mode is text-only), callers MUST set
``document=None`` and append a :class:`~resume_kit_core.errors.CoreWarning`
with ``code=WarningCode.PROVIDER_FALLBACK_USED`` to the ``warnings`` list.
This convention lets downstream callers distinguish "structured parse
succeeded with no data" from "structured parse was never attempted."
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field
from resume_kit_core.errors import CoreWarning
from resume_kit_core.response import ProvenanceRef
from resume_kit_schemas.resume import ResumeDocument


class ParseMethod(StrEnum):
    """The strategy used to produce a :class:`ParseResult`.

    ``deterministic``
        Text was extracted from the source document using rule-based or
        format-specific parsing (e.g. PDF text extraction, DOCX XML parse).
        No LLM was involved.  The ``text`` field is always populated;
        ``document`` may be ``None`` when structured parsing was skipped or
        unavailable.

    ``llm``
        An LLM was used to convert extracted text into a :class:`ResumeDocument`.
        The ``document`` field is expected to be populated on success.
    """

    deterministic = "deterministic"
    llm = "llm"


class ParseResult(BaseModel):
    """The result of parsing a resume source document.

    Carries raw extracted markdown text, an optional structured resume model,
    confidence, warnings, and provenance — enough information for any
    downstream consumer to decide how to use or escalate the result.

    Fields
    ------
    text:
        Extracted markdown representation of the source document.  Always
        populated; may be an empty string only if the source was blank.
    document:
        Structured :class:`~resume_kit_schemas.resume.ResumeDocument` produced
        by an LLM or a downstream structured-parse step.  ``None`` when
        structured parsing was not attempted or failed gracefully.  Callers
        MUST check ``warnings`` for a ``PROVIDER_FALLBACK_USED`` code to
        distinguish "no LLM configured" from "LLM parse succeeded with empty
        data."
    confidence:
        A ``[0.0, 1.0]`` float representing extraction confidence.  For
        deterministic text extraction this is typically ``1.0``; for LLM
        results it reflects the model's self-reported or heuristic confidence.
    warnings:
        Non-fatal advisory notices (reused from ``resume-kit-core``).  A
        ``WarningCode.PROVIDER_FALLBACK_USED`` entry signals that structured
        parsing was unavailable and ``document`` is ``None`` by design rather
        than due to an error.
    provenance:
        Source-lineage records (reused from ``resume-kit-core``).  Each entry
        SHOULD include a ``metadata`` dict with at minimum ``"parser"``
        (parser identifier) and ``"method"`` (:class:`ParseMethod` member
        name).  Multiple entries are valid when parsing was pipelined (e.g.
        deterministic text extraction followed by LLM structuring).
    """

    text: str = Field(description="Extracted markdown text from the source document.")
    document: ResumeDocument | None = Field(
        default=None,
        description=(
            "Structured resume model.  None when structured parsing was not attempted "
            "or was unavailable (check warnings for PROVIDER_FALLBACK_USED)."
        ),
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Extraction confidence in [0.0, 1.0].  1.0 for deterministic extraction; "
            "model-reported or heuristic value for LLM results."
        ),
    )
    warnings: list[CoreWarning] = Field(
        default_factory=list,
        description="Non-fatal advisory notices from core warning taxonomy.",
    )
    provenance: list[ProvenanceRef] = Field(
        default_factory=list,
        description=(
            "Source lineage records.  Each entry should carry 'parser' and 'method' "
            "keys in its metadata dict."
        ),
    )
