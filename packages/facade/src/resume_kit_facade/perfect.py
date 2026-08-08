"""Perfect-stage budget fitting through the edit-session write gate."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel
from resume_kit_core import ErrorCode, ResumeKitError
from resume_kit_evidence import validate_resume_truth
from resume_kit_policy import ResumeShapePolicy, load_shape_policy
from resume_kit_schemas import (
    CandidateEvidence,
    ChangeProposal,
    ClaimProvenance,
    JobDescription,
    ProvenanceStatus,
    ResumeDocument,
    ReviewAction,
    TrimCandidate,
    TrimKind,
)
from resume_kit_schemas.budget import BudgetViolation
from resume_kit_schemas.shape import (
    ContentFate,
    ContentLedger,
    ContentLedgerEntry,
)
from resume_kit_scoring import (
    CompressionCandidate,
    budget_enforce,
    compress_bullet,
    compress_summary,
    content_ledger_ok_perfect,
    rank_bullets,
    rank_experience,
    rank_skills,
)
from resume_kit_terms import AliasIndex, load_effective_alias_index

from resume_kit_facade.baseline import _version_path_for
from resume_kit_facade.edit_session import commit_session, decide_change, open_session
from resume_kit_facade.project_config import (
    ProjectConfig,
    atomic_write_json,
    load_config,
    load_evidence_file,
    resolve_active_resume,
    set_active,
    set_version,
    working_dir,
)

_WORK_RE = re.compile(r"^workExperience\[(?P<work>\d+)\]$")
_WORK_DESCRIPTION_RE = re.compile(
    r"^workExperience\[(?P<work>\d+)\]\.description$"
)
_BULLET_RE = re.compile(
    r"^workExperience\[(?P<work>\d+)\]\.description\[(?P<bullet>\d+)\]$"
)
_SKILL_RE = re.compile(r"^additional\.technicalSkills\[(?P<skill>\d+)\]$")
_SAFE_JOB_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class BuildPerfectResult(BaseModel):
    """Outcome of fitting a tailored resume to informational budgets."""

    final_path: str | None
    committed: bool
    job_id: str | None
    violations: list[BudgetViolation]
    candidates: list[TrimCandidate]
    compressions: list[CompressionCandidate]
    applied: list[str]
    deferred: list[str]
    ledger: ContentLedger
    ledger_ok: bool


def build_perfect(
    root: str | Path,
    *,
    job: str | None = None,
    decisions: Mapping[str, str] | None = None,
    auto_fit: bool = False,
) -> BuildPerfectResult:
    """Fit the active tailored resume to shape-policy budgets.

    The source resume is the resolved downstream lineage pointer
    (``standard -> structure -> base -> original``). Committed changes are
    applied only through the edit-session orchestrator; the master lineage files
    are read as inputs and never overwritten.
    """

    config = load_config(root)
    source_rel = resolve_active_resume(config)
    if source_rel is None:
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED, "No active resume version is set."
        )

    job_rel = job if job is not None else config.active_job
    if job_rel is None:
        raise ResumeKitError.from_code(
            ErrorCode.VALIDATION_FAILED, "No active job is set."
        )
    if job is not None and job != config.active_job:
        set_active(root, job=job)
        config = load_config(root)
        job_rel = config.active_job
        assert job_rel is not None

    resume = _load_resume(root, source_rel)
    job_doc = _load_job(root, job_rel)
    job_id = _job_id_for(job_rel)
    policy = load_shape_policy(root)
    evidence = _load_evidence(root, config)
    alias_file = _alias_file(root, config.alias_file)
    alias_index = load_effective_alias_index(None if alias_file is None else alias_file)
    truth_report = validate_resume_truth(
        resume,
        evidence,
        alias_file=None if alias_file is None else alias_file.as_posix(),
    )
    claim_provenance = list(truth_report.claims)

    violations = budget_enforce(resume, policy)
    if not violations:
        ledger = ContentLedger()
        return BuildPerfectResult(
            final_path=None,
            committed=False,
            job_id=job_id,
            violations=[],
            candidates=[],
            compressions=[],
            applied=[],
            deferred=[],
            ledger=ledger,
            ledger_ok=True,
        )

    candidates, compressions, deferred = _rank_budget_work(
        resume=resume,
        job=job_doc,
        violations=violations,
        evidence=evidence,
        policy=policy,
        alias_index=alias_index,
    )
    proposals, trim_by_proposal, compression_by_path = _build_proposals(
        resume=resume,
        candidates=candidates,
        compressions=compressions,
        deferred=deferred,
    )

    if not proposals or (not auto_fit and decisions is None):
        ledger = ContentLedger()
        return BuildPerfectResult(
            final_path=None,
            committed=False,
            job_id=job_id,
            violations=violations,
            candidates=candidates,
            compressions=compressions,
            applied=[],
            deferred=_dedupe(deferred),
            ledger=ledger,
            ledger_ok=True,
        )

    mode = "auto" if auto_fit else "review_at_end"
    # A compression REPLACES the text at its path, so any stale provenance the
    # original text carried (e.g. an ``ambiguous`` summary) no longer applies and
    # must not block approval of the rewrite. Drop it and seed the verified
    # provenance the compression already earned by passing its own truth gate.
    compression_paths = set(compression_by_path)
    session_claim_provenance = [
        prov
        for prov in claim_provenance
        if prov.field_path not in compression_paths
    ]
    if auto_fit:
        session_claim_provenance.extend(
            _auto_provenance_for_proposals(
                proposals,
                compression_by_path=compression_by_path,
            )
        )
    else:
        session_claim_provenance.extend(
            _auto_provenance_for_proposals(
                [p for p in proposals if p.path in compression_paths],
                compression_by_path=compression_by_path,
            )
        )

    open_session(
        root=root,
        mode=mode,
        changes=proposals,
        evidence=evidence,
        claim_provenance=session_claim_provenance,
        expected_score_deltas=[],
    )

    if decisions is not None and not auto_fit:
        _apply_explicit_decisions(root, proposals=proposals, decisions=decisions)

    committed = commit_session(root=root, freedom=6)
    applied_changes = list(committed.applied)
    rejected_paths = [rejection.path for rejection in committed.rejected]
    applied_paths, ledger = _ledger_for_applied_changes(
        applied_changes=applied_changes,
        trim_by_proposal=trim_by_proposal,
        compression_by_path=compression_by_path,
        auto_fit=auto_fit,
    )
    deferred = _dedupe([*deferred, *rejected_paths])
    ledger_ok = content_ledger_ok_perfect(ledger)

    final_rel = _final_path_for(source_rel, job_id)
    working_path = _state_working_path(root, committed.state.working_path)
    working_doc = ResumeDocument.model_validate_json(
        working_path.read_text(encoding="utf-8")
    )
    final_doc = working_doc.model_copy(deep=True)
    atomic_write_json(working_dir(root) / final_rel, final_doc.model_dump(mode="json"))
    set_version(
        root,
        final=final_rel,
        final_derived_from=source_rel,
        final_job_id=job_id,
    )

    return BuildPerfectResult(
        final_path=final_rel,
        committed=True,
        job_id=job_id,
        violations=violations,
        candidates=candidates,
        compressions=compressions,
        applied=applied_paths,
        deferred=deferred,
        ledger=ledger,
        ledger_ok=ledger_ok,
    )


def _rank_budget_work(
    *,
    resume: ResumeDocument,
    job: JobDescription,
    violations: list[BudgetViolation],
    evidence: list[CandidateEvidence],
    policy: ResumeShapePolicy,
    alias_index: AliasIndex,
) -> tuple[list[TrimCandidate], list[CompressionCandidate], list[str]]:
    candidates: list[TrimCandidate] = []
    compressions: list[CompressionCandidate] = []
    deferred: list[str] = []

    for violation in violations:
        if violation.dimension == "skills":
            candidates.extend(
                rank_skills(resume, job, count=violation.overage, alias_index=alias_index)
            )
        elif violation.dimension == "experience_entries":
            ranked = rank_experience(
                resume, job, count=violation.overage, alias_index=alias_index
            )
            candidates.extend(ranked)
            for candidate in ranked:
                if candidate.kind is TrimKind.TRIM:
                    deferred.append(candidate.path)
                elif candidate.kind is TrimKind.COMPRESS:
                    work_index = _work_index(candidate.path)
                    if work_index is not None:
                        candidates.extend(
                            _rank_role_bullets(
                                resume=resume,
                                job=job,
                                work_index=work_index,
                                count=1,
                                alias_index=alias_index,
                            )
                        )
        elif violation.dimension == "bullets_per_role":
            work_index = _work_index(violation.location or "")
            if work_index is not None:
                candidates.extend(
                    _rank_role_bullets(
                        resume=resume,
                        job=job,
                        work_index=work_index,
                        count=violation.overage,
                        alias_index=alias_index,
                    )
                )
        elif violation.dimension == "summary_words":
            compression = compress_summary(
                resume,
                evidence,
                policy=policy,
                alias_index=alias_index,
            )
            if compression is not None:
                compressions.append(compression)
                if not compression.claim_preserving:
                    deferred.append(compression.path)
        elif violation.dimension == "bullet_words":
            bullet = _bullet_index(violation.location or "")
            if bullet is not None:
                work_index, achievement_index = bullet
                compression = compress_bullet(
                    resume,
                    evidence,
                    work_index=work_index,
                    achievement_index=achievement_index,
                    policy=policy,
                    alias_index=alias_index,
                )
                if compression is not None:
                    compressions.append(compression)
                    if not compression.claim_preserving:
                        deferred.append(compression.path)

    for candidate in candidates:
        if candidate.deferred or candidate.kind is TrimKind.DEFER:
            deferred.append(candidate.path)

    return _dedupe_candidates(candidates), compressions, _dedupe(deferred)


def _rank_role_bullets(
    *,
    resume: ResumeDocument,
    job: JobDescription,
    work_index: int,
    count: int,
    alias_index: AliasIndex,
) -> list[TrimCandidate]:
    total = sum(len(experience.description) for experience in resume.workExperience)
    ranked = rank_bullets(resume, job, count=total, alias_index=alias_index)
    prefix = f"workExperience[{work_index}].description["
    role_ranked = [candidate for candidate in ranked if candidate.path.startswith(prefix)]
    return role_ranked[:count]


def _build_proposals(
    *,
    resume: ResumeDocument,
    candidates: list[TrimCandidate],
    compressions: list[CompressionCandidate],
    deferred: list[str],
) -> tuple[
    list[ChangeProposal],
    dict[str, list[TrimCandidate]],
    dict[str, CompressionCandidate],
]:
    proposals: list[ChangeProposal] = []
    trim_by_proposal: dict[str, list[TrimCandidate]] = {}
    deferred_paths = set(deferred)

    skill_trims = [
        candidate
        for candidate in candidates
        if candidate.dimension == "skills"
        and candidate.kind is TrimKind.TRIM
        and candidate.path not in deferred_paths
    ]
    skill_indices = {
        index
        for candidate in skill_trims
        for index in [_skill_index(candidate.path)]
        if index is not None
    }
    if skill_indices:
        original = list(resume.additional.technicalSkills)
        value = [
            skill for index, skill in enumerate(original) if index in skill_indices
        ]
        proposal = ChangeProposal(
            path="additional.technicalSkills",
            action="remove",
            original=original,
            value=value,
            reason=_joined_reasons(skill_trims),
        )
        proposals.append(proposal)
        trim_by_proposal[proposal.path] = skill_trims

    bullet_trims_by_role: dict[int, list[TrimCandidate]] = {}
    for candidate in candidates:
        if (
            candidate.dimension != "bullets_per_role"
            or candidate.kind is not TrimKind.TRIM
            or candidate.path in deferred_paths
        ):
            continue
        bullet = _bullet_index(candidate.path)
        if bullet is None:
            continue
        work_index, _achievement_index = bullet
        bullet_trims_by_role.setdefault(work_index, []).append(candidate)

    trimmed_bullet_paths: set[str] = set()
    for work_index, role_trims in sorted(bullet_trims_by_role.items()):
        indices: set[int] = set()
        for candidate in role_trims:
            parsed = _bullet_index(candidate.path)
            if parsed is not None:
                indices.add(parsed[1])
        trimmed_bullet_paths.update(candidate.path for candidate in role_trims)
        original = list(resume.workExperience[work_index].description)
        value = [
            bullet for index, bullet in enumerate(original) if index in indices
        ]
        path = f"workExperience[{work_index}].description"
        proposal = ChangeProposal(
            path=path,
            action="remove",
            original=original,
            value=value,
            reason=_joined_reasons(role_trims),
        )
        proposals.append(proposal)
        trim_by_proposal[path] = role_trims

    compression_by_path: dict[str, CompressionCandidate] = {}
    for compression in compressions:
        if not compression.claim_preserving:
            continue
        if compression.path in trimmed_bullet_paths:
            continue
        proposals.append(
            ChangeProposal(
                path=compression.path,
                action="replace",
                original=compression.original,
                value=compression.rewritten,
                reason=compression.reason,
            )
        )
        compression_by_path[compression.path] = compression

    return proposals, trim_by_proposal, compression_by_path


def _apply_explicit_decisions(
    root: str | Path,
    *,
    proposals: list[ChangeProposal],
    decisions: Mapping[str, str],
) -> None:
    for proposal in proposals:
        action = ReviewAction(decisions.get(proposal.path, ReviewAction.SKIP.value))
        decide_change(
            root=root,
            path=proposal.path,
            action=action,
            reason_code=None,
            note="build_perfect",
            edited_content=None,
        )


def _ledger_for_applied_changes(
    *,
    applied_changes: list[ChangeProposal],
    trim_by_proposal: dict[str, list[TrimCandidate]],
    compression_by_path: dict[str, CompressionCandidate],
    auto_fit: bool,
) -> tuple[list[str], ContentLedger]:
    applied_paths: list[str] = []
    entries: list[ContentLedgerEntry] = []
    fate = (
        ContentFate.DROPPED_BY_RANKED_BUDGET
        if auto_fit
        else ContentFate.DROPPED_BY_EXPLICIT_DECISION
    )

    for change in applied_changes:
        if change.action == "remove":
            for candidate in trim_by_proposal.get(change.path, []):
                token = _removed_token(change, candidate.path)
                if token is None:
                    continue
                applied_paths.append(candidate.path)
                entries.append(
                    ContentLedgerEntry(
                        token=token,
                        fate=fate,
                        source_path=candidate.path,
                        reason=candidate.rationale,
                    )
                )

        compression = compression_by_path.get(change.path)
        if compression is not None:
            applied_paths.append(compression.path)
            entries.append(
                ContentLedgerEntry(
                    token=compression.original,
                    fate=ContentFate.COMPRESSED,
                    source_path=compression.path,
                    target_path=compression.path,
                    reason=compression.reason,
                )
            )

    return applied_paths, ContentLedger(entries=entries)


def _removed_token(change: ChangeProposal, candidate_path: str) -> str | None:
    if change.path == "additional.technicalSkills":
        index = _skill_index(candidate_path)
    else:
        bullet = _bullet_index(candidate_path)
        index = None if bullet is None else bullet[1]
    if index is None or not isinstance(change.original, list):
        return None
    if index < 0 or index >= len(change.original):
        return None
    token = change.original[index]
    return token if isinstance(token, str) and token.strip() else None


def _auto_provenance_for_proposals(
    proposals: list[ChangeProposal],
    *,
    compression_by_path: dict[str, CompressionCandidate],
) -> list[ClaimProvenance]:
    provenances: list[ClaimProvenance] = []
    for proposal in proposals:
        if proposal.action in {"reorder", "remove"}:
            provenances.append(
                ClaimProvenance(
                    claim=f"Budget trim at {proposal.path}",
                    field_path=proposal.path,
                    status=ProvenanceStatus.VERIFIED,
                    rationale=(
                        f"Budget trim at {proposal.path} cannot introduce a new "
                        "unsupported claim."
                    ),
                )
            )
        elif proposal.path in compression_by_path and isinstance(proposal.value, str):
            provenances.append(
                ClaimProvenance(
                    claim=proposal.value,
                    field_path=proposal.path,
                    status=ProvenanceStatus.VERIFIED,
                    rationale="Compression candidate already passed its truth gate.",
                )
            )
    return provenances


def _load_resume(root: str | Path, rel: str) -> ResumeDocument:
    return ResumeDocument.model_validate_json(
        _project_file(root, rel).read_text(encoding="utf-8")
    )


def _load_job(root: str | Path, rel: str) -> JobDescription:
    return JobDescription.model_validate_json(
        _project_file(root, rel).read_text(encoding="utf-8")
    )


def _load_evidence(root: str | Path, config: ProjectConfig) -> list[CandidateEvidence]:
    for pointer in (config.active_evidence, config.evidence_file):
        if pointer:
            return load_evidence_file(_project_file(root, pointer))
    return []


def _project_file(root: str | Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "resume-kit":
        return Path(root) / path
    return working_dir(root) / path


def _state_working_path(root: str | Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(root) / path


def _alias_file(root: str | Path, value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return _project_file(root, value)


def _job_id_for(job_rel: str) -> str:
    stem = Path(job_rel).stem or "job"
    safe = _SAFE_JOB_ID_RE.sub("-", stem).strip("-")
    return safe or "job"


def _final_path_for(source_rel: str, job_id: str) -> str:
    rel = _version_path_for(source_rel, f"{job_id}-final")
    path = Path(rel)
    stem = path.name
    if "-tailored" in stem:
        return str(path.with_name(stem.replace("-tailored", f"-{job_id}-final")))
    return rel


def _work_index(path: str) -> int | None:
    match = _WORK_RE.match(path)
    return None if match is None else int(match.group("work"))


def _bullet_index(path: str) -> tuple[int, int] | None:
    match = _BULLET_RE.match(path)
    if match is None:
        return None
    return int(match.group("work")), int(match.group("bullet"))


def _skill_index(path: str) -> int | None:
    match = _SKILL_RE.match(path)
    return None if match is None else int(match.group("skill"))


def _joined_reasons(candidates: list[TrimCandidate]) -> str:
    reasons = [f"{candidate.path}: {candidate.rationale}" for candidate in candidates]
    return "; ".join(reasons)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_candidates(candidates: list[TrimCandidate]) -> list[TrimCandidate]:
    seen: set[tuple[str, str]] = set()
    result: list[TrimCandidate] = []
    for candidate in candidates:
        key = (candidate.path, candidate.kind.value)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


__all__ = ["BuildPerfectResult", "build_perfect"]
