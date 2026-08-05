"""Deterministic ``original -> base`` auto-fix engine (RIT-T-0115).

Consumes the structured :class:`~resume_kit_schemas.AtsStructureFinding` list
(from ``check_ats_structure``) and applies ONLY the ``auto_safe_*`` transforms —
faithfulness-preserving by construction: they strip prohibited PII / placeholder
/ formatting noise and normalize date/format *presentation*, never changing a
claim (employer, title, skill, degree, or the substantive year of a date).
Anything marked ``needs_judgment`` is deferred to the interactive walkthrough.

Pure and deterministic: no I/O, no clock reads, no LLM. Returns the fixed
resume plus which findings were applied vs deferred, so a surface layer can
persist ``<name>-base.json`` and report what still needs a human.

Claim-preservation is asserted after the fact (:func:`_assert_claims_preserved`)
as a defensive guard: the set of employers/titles/skills/degrees must be
unchanged by the auto pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from resume_kit_schemas import (
    AtsStructureReport,
    FixAffordance,
    ResumeDocument,
)

_MONTH_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*", re.IGNORECASE
)
_BULLET_RE = re.compile(r"[•‣◦⁃∙]")
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


@dataclass
class BaseFixResult:
    """Outcome of the auto ``original -> base`` pass."""

    resume: ResumeDocument
    applied: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


def _walk_strings(value: Any, fn: Any) -> Any:
    """Recursively apply ``fn`` to every string in a nested JSON structure."""
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_walk_strings(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _walk_strings(v, fn) for k, v in value.items()}
    return value


def _strip_span(data: dict[str, Any], span: str) -> dict[str, Any]:
    """Remove every case-insensitive occurrence of ``span`` from all strings."""
    if not span:
        return data
    pattern = re.compile(re.escape(span), re.IGNORECASE)

    def clean(text: str) -> str:
        return re.sub(r"\s{2,}", " ", pattern.sub("", text)).strip()

    return _walk_strings(data, clean)


def _normalize_formatting(data: dict[str, Any]) -> dict[str, Any]:
    """Tabs -> space, unicode bullets -> '-', drop non-ASCII."""

    def clean(text: str) -> str:
        text = text.replace("\t", " ")
        text = _BULLET_RE.sub("-", text)
        text = _NON_ASCII_RE.sub("", text)
        return re.sub(r"\s{2,}", " ", text)

    return _walk_strings(data, clean)


def _normalize_dates(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize workExperience 'years' to year-only ranges (drop month names).

    Presentation-only: the substantive years are preserved, month granularity is
    dropped so all positions read consistently.
    """
    for exp in data.get("workExperience", []) or []:
        if isinstance(exp, dict) and exp.get("years"):
            exp["years"] = _MONTH_RE.sub("", str(exp["years"])).strip()
    return data


def _claim_set(data: dict[str, Any]) -> dict[str, Any]:
    exps = data.get("workExperience", []) or []
    edus = data.get("education", []) or []
    return {
        "employers": sorted(str(e.get("company", "")) for e in exps if isinstance(e, dict)),
        "titles": sorted(str(e.get("title", "")) for e in exps if isinstance(e, dict)),
        "degrees": sorted(str(e.get("degree", "")) for e in edus if isinstance(e, dict)),
        "skills": sorted((data.get("additional", {}) or {}).get("technicalSkills", [])),
    }


def claim_diff(before: ResumeDocument, after: ResumeDocument) -> dict[str, dict[str, list[str]]]:
    """Return per-field added/removed claims between two resume versions.

    Claims are the load-bearing facts a `base`/`standard` edit must preserve:
    employers, titles, degrees, and skills. An empty diff means claims were
    preserved exactly (only presentation/PII/format changed).
    """
    b = _claim_set(before.model_dump(by_alias=True))
    a = _claim_set(after.model_dump(by_alias=True))
    diff: dict[str, dict[str, list[str]]] = {}
    for key in b:
        added = sorted(set(a[key]) - set(b[key]))
        removed = sorted(set(b[key]) - set(a[key]))
        if added or removed:
            diff[key] = {"added": added, "removed": removed}
    return diff


def claims_preserved(before: ResumeDocument, after: ResumeDocument) -> bool:
    """True iff no employer/title/degree/skill claim was added or removed.

    This is the base/standard write-gate invariant (RIT-A-0003, decided): the
    edit may strip PII, normalize formatting/dates, and reword — but it must not
    add, drop, or alter a claim. Distinct from extraction-faithfulness (which
    compares to the source file and would wrongly reject intentional PII removal).
    """
    return not claim_diff(before, after)


#: Which fix affordances the auto pass applies, and their transform.
_AUTO_AFFORDANCES = {
    FixAffordance.AUTO_SAFE_STRIP,
    FixAffordance.AUTO_SAFE_NORMALIZE,
}


def apply_auto_fixes(
    resume: ResumeDocument, report: AtsStructureReport
) -> BaseFixResult:
    """Apply auto-safe fixes from ``report`` to ``resume`` (the auto ``base`` pass).

    Deterministic and claim-preserving. Findings whose ``fix_affordance`` is not
    auto-safe (e.g. ``needs_judgment``: missing contact info, non-standard
    section rename, street address, AI rewrite) are deferred, not applied.
    """
    data: dict[str, Any] = resume.model_dump(by_alias=True)
    before_claims = _claim_set(data)

    applied: list[str] = []
    deferred: list[str] = []

    for finding in report.findings:
        if finding.fix_affordance not in _AUTO_AFFORDANCES:
            deferred.append(finding.code)
            continue
        if finding.fix_affordance is FixAffordance.AUTO_SAFE_STRIP:
            data = _strip_span(data, finding.metadata.get("match", ""))
        elif finding.fix_affordance is FixAffordance.AUTO_SAFE_NORMALIZE:
            if finding.code == "INCONSISTENT_DATES":
                data = _normalize_dates(data)
            else:  # FORMATTING_*
                data = _normalize_formatting(data)
        applied.append(finding.code)

    if before_claims != _claim_set(data):
        raise ValueError(
            "base auto-fix altered a claim (employer/title/degree/skill) — refusing;"
            " this indicates a non-claim-preserving transform."
        )
    return BaseFixResult(
        resume=ResumeDocument.model_validate(data),
        applied=applied,
        deferred=deferred,
    )


__all__ = ["BaseFixResult", "apply_auto_fixes"]
