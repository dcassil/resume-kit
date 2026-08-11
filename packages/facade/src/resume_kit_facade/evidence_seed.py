"""Shared full-resume evidence seeding for facade write paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resume_kit_evidence import build_candidate_evidence
from resume_kit_schemas import CandidateEvidence, ResumeDocument

from resume_kit_facade.project_config import (
    DEFAULT_FULL_RESUME_EVIDENCE_FILE,
    ProjectConfig,
    load_config,
    merge_evidence_file,
    save_config,
    working_dir,
)


@dataclass(frozen=True)
class FullResumeEvidenceSeed:
    """Result of idempotently seeding full-resume evidence."""

    evidence_file: str
    active_evidence: str | None
    extracted_count: int
    total_count: int
    evidence: list[CandidateEvidence]
    config: ProjectConfig


def normalize_evidence_file(value: str) -> str:
    """Return a relative evidence path safe to join under ``resume-kit/``."""
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("evidence_file must be relative to resume-kit/.")
    return path.as_posix()


def seed_full_resume_evidence(
    root: str | Path,
    *,
    resume: ResumeDocument,
    approved_claims: list[CandidateEvidence] | list[str] | None = None,
    evidence_file: str | None = None,
    update_active: bool = True,
) -> FullResumeEvidenceSeed:
    """Extract and idempotently merge durable evidence for ``resume``."""

    config = load_config(root)
    evidence_rel = normalize_evidence_file(
        evidence_file
        or config.active_evidence
        or config.evidence_file
        or DEFAULT_FULL_RESUME_EVIDENCE_FILE
    )
    extracted = build_candidate_evidence(resume, approved_claims=approved_claims)
    merged = merge_evidence_file(working_dir(root) / evidence_rel, extracted)

    config.evidence_file = evidence_rel
    if update_active:
        config.active_evidence = evidence_rel
    save_config(root, config)

    return FullResumeEvidenceSeed(
        evidence_file=evidence_rel,
        active_evidence=config.active_evidence,
        extracted_count=len(extracted),
        total_count=len(merged),
        evidence=merged,
        config=config,
    )
