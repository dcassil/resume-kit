"""Generic (job-independent) resume best-practices report schema (RIT-I-0016).

Pure, transport-agnostic data models emitted by the best-practices analyzer
(RIT-T-0117) when it scores the ``base`` resume for generic structure + wording
quality — distinct from the job-keyword-driven composite score. No engine, I/O,
or LLM imports live here; this module is purely declarative.

Two framework decisions are embodied here:

* **The shared grooming-finding severity taxonomy** — :class:`FindingSeverity` — is
  defined ONCE in this module and re-exported. It is OWNED by RIT-A-0003 (the
  resume-baselining decision) and ADOPTED by RIT-A-0004 / RIT-I-0018 (the
  industry-guidance audit). No second severity enum may exist elsewhere; any
  grooming/guidance finding across the system uses this vocabulary so findings
  produced by the best-practices engine and the guidance audit can be merged and
  surfaced together.

* **Per-item resolution classification** — :class:`ResolutionKind` — separates
  findings the system can fix truthfully on its own (``auto_suggestible``, with
  a concrete ``suggested_change``) from findings whose fix needs facts the
  system does not have (``needs_user_input``, with an ``elicitation_prompt``,
  e.g. a real metric to turn a duty into a quantified accomplishment).

FindingSeverity mapping guidance (aligned with RIT-A-0004's lane routing):

* wording-quality findings — buzzwords, weak/duty openers, missing
  quantification, bullet-quality — map to ``warning`` / ``recommendation``
  (RIT-A-0004 lane 1);
* soft, LLM-assisted judgments (is this really an accomplishment?) map to
  ``review_note`` (lane 2), never into a deterministic blocker;
* layout / parse-risk items that need source-file inspection (RIT-I-0016
  REQ-011) map to ``out_of_scope_future`` (lane 6);
* ``hard_gate`` is **reserved** for truth/faithfulness-class failures and
  requires explicit per-item justification (``severity_justification``).
  Generic best-practices advice must NEVER be silently promoted to a blocker —
  the core anti-goal of RIT-A-0004.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

#: Schema/format version for the best-practices report envelope.
BEST_PRACTICES_SCHEMA_VERSION = 1


class FindingSeverity(StrEnum):
    """The single shared grooming-finding severity taxonomy.

    Owned by RIT-A-0003; adopted (not re-defined) by RIT-A-0004 / RIT-I-0018.
    Defined once here and re-exported — there must be no second severity enum.
    """

    HARD_GATE = "hard-gate"
    WARNING = "warning"
    RECOMMENDATION = "recommendation"
    REVIEW_NOTE = "review-note"
    OUT_OF_SCOPE_FUTURE = "out-of-scope-future"


class ResolutionKind(StrEnum):
    """How a finding can be resolved.

    ``auto_suggestible``: a concrete, truthful rewrite is available now
    (carried in ``suggested_change``). ``needs_user_input``: the fix requires
    facts the system does not have (e.g. a real metric); the item carries an
    ``elicitation_prompt`` to ask the user for them.
    """

    AUTO_SUGGESTIBLE = "auto_suggestible"
    NEEDS_USER_INPUT = "needs_user_input"


class ProvenanceKind(StrEnum):
    """Whether a finding came from the deterministic core or an LLM assist.

    Mirrors the engine's "deterministic seed, enriched recommendations"
    contract so the reproducible core is distinguishable from any assisted
    (non-deterministic) finding.
    """

    DETERMINISTIC = "deterministic"
    ASSISTED = "assisted"


class FindingLocation(BaseModel):
    """Structured locator for where a finding applies.

    Uses the stable ScoreDoc segmentation vocabulary (section / zone / entity /
    bullet index) rather than a free-text guess, so the ``standard`` walkthrough
    (RIT-T-0118) can resolve exactly which element the finding targets. All
    fields are optional so a locator can be as coarse (a whole section) or as
    fine (a specific bullet within an experience entry) as the rule needs.
    """

    section: str | None = Field(
        default=None,
        description="Canonical section name, e.g. 'summary', 'experience', 'skills'.",
    )
    zone: str | None = Field(
        default=None,
        description="ScoreDoc keyword zone, e.g. 'experience', 'skills_list', 'summary'.",
    )
    entity_id: str | None = Field(
        default=None,
        description="Identifier of the entity (e.g. a specific experience/role) the finding targets.",
    )
    bullet_index: int | None = Field(
        default=None,
        description="Zero-based bullet index within the located entity, when the finding is bullet-scoped.",
    )
    json_path: str | None = Field(
        default=None,
        description="Optional canonical JSON path into the resume document for precise application.",
    )


class BestPracticesFinding(BaseModel):
    """A single flagged generic best-practices item.

    Invariant (enforced by a model validator): exactly one of
    ``suggested_change`` / ``elicitation_prompt`` is present, correctly paired
    with ``resolution_kind`` — ``auto_suggestible`` carries ``suggested_change``
    and no prompt; ``needs_user_input`` carries ``elicitation_prompt`` and no
    suggested change. ``hard-gate`` severity requires a non-empty
    ``severity_justification``.
    """

    rule_code: str = Field(
        description="Stable rule identifier, e.g. 'WEAK_OPENER', 'BUZZWORD', 'MISSING_QUANTIFICATION'.",
    )
    message: str = Field(description="Human-readable explanation of the finding.")
    location: FindingLocation = Field(
        default_factory=FindingLocation,
        description="Structured locator for where the finding applies.",
    )
    severity: FindingSeverity = Field(description="Shared-taxonomy severity of the finding.")
    resolution_kind: ResolutionKind = Field(
        description="Whether the fix is auto-suggestible or needs user-supplied facts.",
    )
    provenance: ProvenanceKind = Field(
        default=ProvenanceKind.DETERMINISTIC,
        description="Deterministic core vs. LLM-assisted origin of this finding.",
    )
    suggested_change: str | None = Field(
        default=None,
        description="Concrete truthful rewrite (present iff resolution_kind is auto_suggestible).",
    )
    elicitation_prompt: str | None = Field(
        default=None,
        description="Targeted question for the user (present iff resolution_kind is needs_user_input).",
    )
    severity_justification: str | None = Field(
        default=None,
        description="Required, non-empty rationale when severity is hard-gate (reserved for truth-class failures).",
    )

    @model_validator(mode="after")
    def _check_resolution_and_severity(self) -> BestPracticesFinding:
        if self.resolution_kind is ResolutionKind.AUTO_SUGGESTIBLE:
            if not self.suggested_change:
                raise ValueError(
                    "auto_suggestible findings must carry a suggested_change."
                )
            if self.elicitation_prompt is not None:
                raise ValueError(
                    "auto_suggestible findings must not carry an elicitation_prompt."
                )
        else:  # NEEDS_USER_INPUT
            if not self.elicitation_prompt:
                raise ValueError(
                    "needs_user_input findings must carry an elicitation_prompt."
                )
            if self.suggested_change is not None:
                raise ValueError(
                    "needs_user_input findings must not carry a suggested_change."
                )
        if self.severity is FindingSeverity.HARD_GATE and not (
            self.severity_justification and self.severity_justification.strip()
        ):
            raise ValueError(
                "hard-gate severity is reserved and requires a non-empty severity_justification."
            )
        return self


class BestPracticesReport(BaseModel):
    """Envelope of generic best-practices findings for one resume version.

    Data only: no analyzer/engine imports. ``report_provenance`` records whether
    the report as a whole is purely deterministic or includes assisted findings,
    complementing the per-finding ``provenance`` marker.
    """

    schema_version: int = Field(
        default=BEST_PRACTICES_SCHEMA_VERSION,
        description="Best-practices report schema/format version.",
    )
    resume_version: str | None = Field(
        default=None,
        description="Identity of the resume version scored (e.g. the base/standard pointer or a document id).",
    )
    report_provenance: ProvenanceKind = Field(
        default=ProvenanceKind.DETERMINISTIC,
        description="Deterministic if every finding is deterministic; assisted if any finding is assisted.",
    )
    findings: list[BestPracticesFinding] = Field(
        default_factory=list,
        description="Ordered list of flagged best-practices items.",
    )
