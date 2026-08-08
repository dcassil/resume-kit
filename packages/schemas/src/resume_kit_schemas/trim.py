"""Ranked trim-candidate schemas for budget-aware resume shaping."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class TrimKind(StrEnum):
    """How a budget ranker recommends handling a low-value content unit."""

    TRIM = "trim"
    COMPRESS = "compress"
    DEFER = "defer"


class TrimCandidate(BaseModel):
    """One ranked content unit that could help close a budget violation."""

    kind: TrimKind
    dimension: str
    path: str
    score: float
    rationale: str
    deferred: bool = False
