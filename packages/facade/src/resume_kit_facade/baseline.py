"""The ``original -> base`` build step (RIT-I-0016, RIT-T-0115).

Composes the deterministic pieces into the write path that produces the ``base``
version: run the structural check, apply auto-safe fixes, enforce the
**claim-preservation gate** (RIT-A-0003, decided), persist ``<name>-base.json``,
and record the ``base`` pointer in the project config.

The claim-preservation gate — not extraction-faithfulness — is the correct gate
for an *edited* base: the fix intentionally removes PII and normalizes
presentation, so a source-file faithfulness check would wrongly reject it. What
must hold is that no employer/title/degree/skill claim was added, dropped, or
altered (:func:`resume_kit_scoring.claims_preserved`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from resume_kit_ats.engine import check_ats_structure
from resume_kit_core import ErrorCode, ResumeKitError
from resume_kit_document_parser import detect_source_parse_risks
from resume_kit_policy import load_shape_policy
from resume_kit_schemas import AtsStructureFinding, AtsStructureReport, ResumeDocument
from resume_kit_schemas.canonical import CanonicalSection, Resume
from resume_kit_schemas.shape import ContentLedger, SectionMapping, ShapeReport
from resume_kit_scoring import (
    analyze_best_practices,
    analyze_resume_shape,
    apply_auto_fixes,
    apply_best_practices_edits,
    apply_shape_transforms,
    claim_diff,
    claims_preserved,
    claims_preserved_across_sections,
    content_ledger_ok,
    content_preserved,
    project_builddoc_from_canonical,
    project_scoredoc,
)

from resume_kit_facade.project_config import (
    atomic_write_json,
    load_config,
    set_version,
    working_dir,
)

_PLACEMENT_REF_DATE = date(2000, 1, 1)  # dates irrelevant to best-practices analysis


@dataclass
class BuildBaseResult:
    """Outcome of the ``original -> base`` build."""

    base_path: str
    applied: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


@dataclass
class BuildStandardResult:
    """Outcome of the ``base -> standard`` walkthrough build."""

    standard_path: str
    applied: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


@dataclass
class BuildStructureResult:
    """Outcome of the ``base -> structure`` canonical shape build."""

    structure_path: str | None
    report: ShapeReport
    ledger: ContentLedger
    ledger_ok: bool
    claims_ok: bool
    applied: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


def _version_path_for(rel: str, suffix: str) -> str:
    """Derive a ``-<suffix>.json`` sibling path from a version pointer."""
    p = Path(rel)
    stem = p.name
    for known in ("-original", "-base", "-structure", "-standard"):
        if known in stem:
            return str(p.with_name(stem.replace(known, f"-{suffix}")))
    if stem.endswith(".json"):
        return str(p.with_name(stem[: -len(".json")] + f"-{suffix}.json"))
    return str(p.with_name(stem + f"-{suffix}"))


def _base_path_for(original_rel: str) -> str:
    """Derive the ``-base.json`` path from the ``-original.json`` pointer."""
    p = Path(original_rel)
    stem = p.name
    if "-original" in stem:
        base_name = stem.replace("-original", "-base")
    elif stem.endswith(".json"):
        base_name = stem[: -len(".json")] + "-base.json"
    else:
        base_name = stem + "-base"
    return str(p.with_name(base_name))


_PARSE_RISK_SUFFIXES = frozenset({".pdf", ".docx"})


def _source_parse_risk_findings(
    root: str | Path, source_rel: str | None
) -> list[AtsStructureFinding]:
    """Resolve the active source file and detect its ATS parse risks.

    Returns ``[]`` when no source is configured, the file is missing, or its
    suffix is not a supported source type. Never raises (the detector is
    bounded and swallows its own failures).
    """
    if not source_rel:
        return []
    source_path = Path(source_rel)
    if not source_path.is_absolute():
        source_path = working_dir(root) / source_path
    if not source_path.exists():
        return []
    if source_path.suffix.lower() not in _PARSE_RISK_SUFFIXES:
        return []
    return detect_source_parse_risks(source_path.read_bytes(), source_path.name)


def build_base(root: str | Path, *, mode: str = "auto") -> BuildBaseResult:
    """Produce the ``base`` version from the active original resume.

    ``mode='auto'`` applies only auto-safe fixes and defers ``needs_judgment``
    findings (reported back for the interactive walkthrough). Writes
    ``<name>-base.json`` behind the claim-preservation gate and points the config
    ``base`` at it. Raises :class:`ResumeKitError` (VALIDATION_FAILED) if the gate
    fails — which, for the deterministic auto pass, indicates a bug rather than
    user data.
    """
    if mode != "auto":
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED,
            f"build_base mode {mode!r} not supported yet (only 'auto').",
        )
    config = load_config(root)
    original_rel = config.active_resume
    if not original_rel:
        raise ResumeKitError.from_code(ErrorCode.VALIDATION_FAILED, "No active_resume set.")

    original_file = working_dir(root) / original_rel
    if not original_file.exists():
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED, f"Active resume not found: {original_rel}."
        )

    original = ResumeDocument.model_validate(json.loads(original_file.read_text(encoding="utf-8")))
    report = check_ats_structure(original)

    # Merge in bounded, deterministic source parse-risk findings (RIT-T-0122).
    # These are WARNING / NEEDS_JUDGMENT — they surface in the structural report
    # and land in ``deferred`` but never gate the write.
    risk_findings = _source_parse_risk_findings(root, config.active_resume_source)
    if risk_findings:
        report = AtsStructureReport(
            section_completeness=report.section_completeness,
            findings=[*report.findings, *risk_findings],
            recommendations=[*report.recommendations, *(f.message for f in risk_findings)],
        )

    fix = apply_auto_fixes(original, report)

    # Hard claim-preservation gate (RIT-A-0003).
    if not claims_preserved(original, fix.resume):
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED,
            "base build refused: claim-preservation gate failed "
            f"(altered claims: {claim_diff(original, fix.resume)}).",
        )

    base_rel = _base_path_for(original_rel)
    atomic_write_json(working_dir(root) / base_rel, fix.resume.model_dump(mode="json"))
    set_version(root, base=base_rel, base_derived_from=original_rel)

    return BuildBaseResult(base_path=base_rel, applied=fix.applied, deferred=fix.deferred)


type ShapeDecision = CanonicalSection | SectionMapping | str


def build_structure(
    root: str | Path,
    *,
    answers: Mapping[str, str] | None = None,
    decisions: Mapping[str, ShapeDecision] | None = None,
) -> BuildStructureResult:
    """Produce the canonical ``structure`` version from ``base`` or original.

    The structure pass is deterministic and non-destructive. It resolves
    ``base ?? original``, applies report-driven shape transforms, and writes the
    canonical ``Resume`` only when both hard gates pass. Gate failure returns the
    report and ledger details without writing an artifact or mutating config.
    """
    config = load_config(root)
    source_rel = config.base_resume or config.active_resume
    if not source_rel:
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED, "No base or active_resume set."
        )

    source_file = working_dir(root) / source_rel
    if not source_file.exists():
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED, f"Source resume not found: {source_rel}."
        )

    source = ResumeDocument.model_validate(json.loads(source_file.read_text(encoding="utf-8")))
    report = analyze_resume_shape(source, load_shape_policy(root))
    decision_map: Mapping[str, ShapeDecision] = (
        decisions if decisions is not None else answers or {}
    )
    fix = apply_shape_transforms(source, report, decision_map)
    ledger_ok = content_ledger_ok(fix.ledger)
    claims_ok = claims_preserved_across_sections(source, fix.resume)
    applied = [finding.code for finding in fix.applied_findings]
    deferred = [finding.code for finding in fix.deferred_findings]

    if not ledger_ok or not claims_ok:
        return BuildStructureResult(
            structure_path=None,
            report=report,
            ledger=fix.ledger,
            ledger_ok=ledger_ok,
            claims_ok=claims_ok,
            applied=applied,
            deferred=deferred,
        )

    structure_rel = _version_path_for(source_rel, "structure")
    atomic_write_json(working_dir(root) / structure_rel, fix.resume.model_dump(mode="json"))
    set_version(root, structure=structure_rel, structure_derived_from=source_rel)

    return BuildStructureResult(
        structure_path=structure_rel,
        report=report,
        ledger=fix.ledger,
        ledger_ok=True,
        claims_ok=True,
        applied=applied,
        deferred=deferred,
    )


def build_standard(
    root: str | Path,
    *,
    answers: dict[str, str] | None = None,
) -> BuildStandardResult:
    """Produce the ``standard`` version from ``base`` via the best-practices pass.

    Resolves the ``base`` (or original) resume, runs the best-practices analyzer,
    applies auto-suggestible edits plus any user-supplied rewrites in ``answers``
    (keyed by ``resume_kit_scoring.finding_key``), and writes
    ``<name>-standard.json`` behind the **claim-preservation gate** and a
    content-preservation gate — the wording pass may reword summary/experience
    bullets but must not add/drop/alter an employer/title/degree/skill claim or
    drift into other resume content. Records the config ``standard`` pointer;
    resolution then prefers it.
    Findings needing user input that were not answered are returned as
    ``deferred`` for the caller to elicit and re-run.
    """
    config = load_config(root)
    source_rel = config.structure_resume or config.base_resume or config.active_resume
    if not source_rel:
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED, "No base or active_resume set."
        )

    source_file = working_dir(root) / source_rel
    if not source_file.exists():
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED, f"Source resume not found: {source_rel}."
        )

    source_raw = json.loads(source_file.read_text(encoding="utf-8"))
    source = (
        project_builddoc_from_canonical(Resume.model_validate(source_raw))
        if source_rel == config.structure_resume
        else ResumeDocument.model_validate(source_raw)
    )
    scoredoc = project_scoredoc(source, reference_date=_PLACEMENT_REF_DATE)
    report = analyze_best_practices(source, scoredoc)
    edit = apply_best_practices_edits(source, report, answers or {})

    if not claims_preserved(source, edit.resume):
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED,
            "standard build refused: claim-preservation gate failed "
            f"(altered claims: {claim_diff(source, edit.resume)}).",
        )
    if not content_preserved(source, edit.resume):
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED,
            "standard build refused: content-preservation gate failed "
            "(standard may only rewrite summary and experience bullet text).",
        )

    standard_rel = _version_path_for(source_rel, "standard")
    atomic_write_json(working_dir(root) / standard_rel, edit.resume.model_dump(mode="json"))
    set_version(root, standard=standard_rel, standard_derived_from=source_rel)

    return BuildStandardResult(
        standard_path=standard_rel, applied=edit.applied, deferred=edit.deferred
    )


__all__ = [
    "BuildBaseResult",
    "BuildStandardResult",
    "BuildStructureResult",
    "build_base",
    "build_standard",
    "build_structure",
]
