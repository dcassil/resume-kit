"""Budget enforcement schemas for resume shape constraints."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class BudgetViolation(BaseModel):
    """One quantified resume budget violation."""

    dimension: str
    location: str | None = None
    limit: int
    actual: int
    overage: int

    @model_validator(mode="after")
    def _overage_matches_counts(self) -> BudgetViolation:
        if self.overage != self.actual - self.limit:
            raise ValueError("overage must equal actual - limit")
        if self.overage <= 0:
            raise ValueError("overage must be greater than zero")
        return self
