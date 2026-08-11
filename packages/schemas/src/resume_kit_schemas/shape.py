"""Shape-pass schemas for canonical resume structure analysis and fixes."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .canonical import CanonicalSection, Resume


class ShapeFindingFamily(StrEnum):
    """Stable shape-finding families."""

    CUSTOM_SECTION_MAPPED = "CUSTOM_SECTION_MAPPED"
    CUSTOM_SECTION_UNMAPPED = "CUSTOM_SECTION_UNMAPPED"
    REDUNDANT_SECTION = "REDUNDANT_SECTION"
    DUPLICATE_SECTION_CONTENT = "DUPLICATE_SECTION_CONTENT"
    CANONICAL_FIELD_DUPLICATE = "CANONICAL_FIELD_DUPLICATE"
    EMBEDDED_HEADING_LINE = "EMBEDDED_HEADING_LINE"
    SECTION_ORDER_VIOLATION = "SECTION_ORDER_VIOLATION"
    BUDGET_INFO = "BUDGET_INFO"


class SectionMappingStatus(StrEnum):
    """Status for a source-section mapping decision."""

    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    NEEDS_USER_INPUT = "needs_user_input"
    PRESERVED_AS_OTHER = "preserved_as_other"


class ContentFate(StrEnum):
    """Per-token outcome recorded by the shape content ledger."""

    PRESENT_AFTER = "present_after"
    MOVED = "moved"
    DEDUPED = "deduped"
    DROPPED_AS_HEADING = "dropped_as_heading"
    DROPPED_AS_PARSER_ARTIFACT = "dropped_as_parser_artifact"
    DROPPED_BY_EXPLICIT_DECISION = "dropped_by_explicit_decision"
    DROPPED_BY_RANKED_BUDGET = "dropped_by_ranked_budget"
    COMPRESSED = "compressed"
    # Accounted: content the canonical schema does not model with a first-class
    # section is faithfully preserved in the canonical ``Resume.custom`` holding
    # slot rather than dropped. Distinct from UNRESOLVED, which means the content
    # genuinely still needs a user mapping decision (RIT-T-0161).
    PRESERVED_AS_OTHER = "preserved_as_other"
    # Accounted: Flow 1 prepared output intentionally omits custom holding
    # sections, while the original text is retained in candidate evidence /
    # learning. This is not a fabrication bypass and not an unresolved drop.
    PRESERVED_IN_EVIDENCE = "preserved_in_evidence"
    UNRESOLVED = "unresolved"


class ShapeFinding(BaseModel):
    """One read-only shape finding."""

    family: ShapeFindingFamily
    code: str
    message: str
    section: str
    proposed_target: CanonicalSection | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ShapeReport(BaseModel):
    """Collection of shape findings plus a caller-facing summary."""

    findings: list[ShapeFinding] = Field(default_factory=list)
    summary: str = ""


class SectionMapping(BaseModel):
    """Mapping from a source section name to a canonical section."""

    source_section: str
    target: CanonicalSection = CanonicalSection.OTHER
    status: SectionMappingStatus = SectionMappingStatus.UNMAPPED


class ContentLedgerEntry(BaseModel):
    """One token fate recorded during shape canonicalization."""

    token: str
    fate: ContentFate
    source_path: str = ""
    target_path: str | None = None
    reason: str | None = None


class ContentLedger(BaseModel):
    """Per-token accounting for a shape transform."""

    entries: list[ContentLedgerEntry] = Field(default_factory=list)


class ShapeFixResult(BaseModel):
    """Result of applying shape transforms."""

    resume: Resume
    ledger: ContentLedger = Field(default_factory=ContentLedger)
    applied_findings: list[ShapeFinding] = Field(default_factory=list)
    deferred_findings: list[ShapeFinding] = Field(default_factory=list)
