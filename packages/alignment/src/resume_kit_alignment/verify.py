"""Local structural verification for applied resume diffs.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/services/improver.py
#   (_METRIC_RE:115, _count_description_words:430-445,
#    verify_diff_result:448-504)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Extracted the local verifier into the alignment package, retargeted
#   upstream bare string warnings to resume_kit_schemas.common.Warning, removed
#   unused app/LLM dependencies, and kept the checks deterministic and usable
#   from alignment orchestration without importing policy/evidence/provider code.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.common import Warning

ResumeMapping = Mapping[str, object]

__all__ = ["verify_diff_result"]

_METRIC_RE = re.compile(r"\d+%|\d+x|\$\d+")


def _warning(message: str, *, code: str, field_path: str | None = None) -> Warning:
    return Warning(message=message, code=code, field_path=field_path)


def _sequence_value(data: ResumeMapping, key: str) -> Sequence[object]:
    value = data.get(key)
    if isinstance(value, list):
        return value
    return ()


def _mapping_entries(data: ResumeMapping, key: str) -> list[ResumeMapping]:
    return [item for item in _sequence_value(data, key) if isinstance(item, Mapping)]


def _count_description_words(data: ResumeMapping) -> int:
    """Count total words in all description and summary fields."""

    total = 0
    for key in ("workExperience", "personalProjects"):
        for entry in _mapping_entries(data, key):
            description = entry.get("description", [])
            if isinstance(description, list):
                total += sum(len(str(item).split()) for item in description)
            elif isinstance(description, str):
                total += len(description.split())
    summary = data.get("summary", "")
    if isinstance(summary, str):
        total += len(summary.split())
    return total


def _identity_value(entry: ResumeMapping, field: str) -> str:
    return str(entry.get(field, "")).strip()


def verify_diff_result(
    original: ResumeMapping,
    result: ResumeMapping,
    applied_changes: Sequence[ChangeProposal],
    job_keywords: Mapping[str, object] | None = None,
) -> list[Warning]:
    """Run local quality checks on an applied diff result."""

    del job_keywords
    warnings: list[Warning] = []

    if not applied_changes:
        return [
            _warning(
                "No changes were applied - resume returned unchanged",
                code="no_applied_changes",
            )
        ]

    for key, label in [
        ("workExperience", "work experience"),
        ("education", "education"),
        ("personalProjects", "project"),
    ]:
        original_count = len(_sequence_value(original, key))
        result_count = len(_sequence_value(result, key))
        if original_count != result_count:
            warnings.append(
                _warning(
                    f"Section count changed: {label} ({original_count} -> {result_count})",
                    code="section_count_changed",
                    field_path=key,
                )
            )

    for key, identity_fields in [
        ("workExperience", ("company", "title")),
        ("education", ("institution", "degree")),
    ]:
        original_entries = _mapping_entries(original, key)
        result_entries = _mapping_entries(result, key)
        for index, (original_entry, result_entry) in enumerate(
            zip(original_entries, result_entries, strict=False)
        ):
            for field in identity_fields:
                original_value = _identity_value(original_entry, field)
                result_value = _identity_value(result_entry, field)
                if original_value and original_value != result_value:
                    field_path = f"{key}[{index}].{field}"
                    warnings.append(
                        _warning(
                            f"Identity field changed: {field_path} "
                            f"('{original_value}' -> '{result_value}')",
                            code="identity_field_changed",
                            field_path=field_path,
                        )
                    )

    original_words = _count_description_words(original)
    result_words = _count_description_words(result)
    if original_words > 0 and result_words > original_words * 1.8:
        warnings.append(
            _warning(
                f"Word count increased significantly: "
                f"{original_words} -> {result_words} ({result_words / original_words:.1f}x)",
                code="word_count_explosion",
            )
        )

    for change in applied_changes:
        if change.action not in ("replace", "append") or not isinstance(change.value, str):
            continue
        new_metrics = set(_METRIC_RE.findall(change.value))
        original_text = change.original if isinstance(change.original, str) else ""
        old_metrics = set(_METRIC_RE.findall(original_text))
        invented = sorted(new_metrics - old_metrics)
        if invented:
            warnings.append(
                _warning(
                    f"Possible invented metric in {change.path}: "
                    f"{', '.join(invented)} (not in original)",
                    code="invented_metric",
                    field_path=change.path,
                )
            )

    return warnings
