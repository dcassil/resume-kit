"""Claim-provenance domain models.

New resume-kit subsystem (no upstream equivalent — upstream only carried
no-fabrication *prompt clauses*, not a structured provenance classification).
This module defines how strongly a resume claim is grounded in candidate
evidence.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ProvenanceStatus(StrEnum):
    """How well a resume claim is supported by candidate evidence.

    Ordered from strongest to weakest support, with two failure states at the
    end (unsupported/contradicted).
    """

    VERIFIED = "verified"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially-supported"
    USER_CONFIRMED = "user-confirmed"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


class ClaimProvenance(BaseModel):
    """The provenance classification for a single resume claim.

    Links a claim (identified by its resume field path and text) to a
    provenance status and the supporting evidence references, if any.
    """

    claim: str = Field(description="The claim text being assessed.")
    status: ProvenanceStatus = Field(
        description="How well the claim is grounded in candidate evidence."
    )
    field_path: str | None = Field(
        default=None,
        description="Dot+bracket path to the resume field carrying the claim, if any.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Identifiers of candidate-evidence records that support the claim.",
    )
    rationale: str | None = Field(
        default=None,
        description="Human-readable explanation for the assigned status.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the classification (1.0 = certain).",
    )
