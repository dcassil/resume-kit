"""Deterministic ``ScoreDoc -> AtsViewReport`` assembly (RIT-T-0109).

Builds the read-only "what the ATS sees" report from an already-projected
:class:`~resume_kit_schemas.ScoreDoc`. This is pure assembly: it re-exposes the
ScoreDoc's sections, entities, and zoned keyword index unchanged — no scoring,
no advice, no clock reads. Identical ScoreDocs yield byte-identical reports.
"""

from __future__ import annotations

from resume_kit_schemas import AtsViewReport, ScoreDoc


def build_ats_view(scoredoc: ScoreDoc) -> AtsViewReport:
    """Assemble the read-only ATS-view report from a projected ScoreDoc."""
    return AtsViewReport(
        sections=list(scoredoc.sections),
        entities=scoredoc.entities,
        keyword_zones=dict(scoredoc.zoned_index.zone_tokens),
    )
