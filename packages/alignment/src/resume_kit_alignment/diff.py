"""Deterministic resume content diffing.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/services/improver.py
#   (DiffConfidence:42-45, calculate_resume_diff:1224-1457 and helpers)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Extracted deterministic diff helpers into the alignment package,
#   retargeted app.schemas.ResumeFieldDiff/ResumeDiffSummary to canonical
#   resume_kit_schemas.change.Diff/ResumeDiffSummary, removed logging and app
#   dependencies, and made order-ignored set comparisons emit deterministic
#   source-order results instead of relying on hash set iteration.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from resume_kit_schemas.change import ChangeType, Confidence, Diff, FieldType, ResumeDiffSummary

ResumeMapping = Mapping[str, object]

__all__ = ["DiffConfidence", "calculate_resume_diff"]


@dataclass(frozen=True)
class DiffConfidence:
    """Confidence values for list diff insert/remove/modify operations."""

    added: Confidence
    removed: Confidence
    modified: Confidence


def _child_mapping(data: ResumeMapping, key: str) -> ResumeMapping:
    value = data.get(key)
    if isinstance(value, Mapping):
        return value
    return {}


def _mapping_list(data: ResumeMapping, key: str) -> list[ResumeMapping]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _entry_text(entry: ResumeMapping, key: str) -> str:
    value = entry.get(key)
    if value is None:
        return ""
    return str(value)


def _format_entry_label(parts: Sequence[str], fallback: str) -> str:
    label = " | ".join(part for part in parts if part)
    return label if label else fallback


def _format_experience_entry(entry: ResumeMapping, index: int) -> str:
    return _format_entry_label(
        [
            _entry_text(entry, "title"),
            _entry_text(entry, "company"),
            _entry_text(entry, "years"),
        ],
        f"Work experience #{index + 1}",
    )


def _format_education_entry(entry: ResumeMapping, index: int) -> str:
    return _format_entry_label(
        [
            _entry_text(entry, "degree"),
            _entry_text(entry, "institution"),
            _entry_text(entry, "years"),
        ],
        f"Education #{index + 1}",
    )


def _format_project_entry(entry: ResumeMapping, index: int) -> str:
    return _format_entry_label(
        [
            _entry_text(entry, "name"),
            _entry_text(entry, "role"),
            _entry_text(entry, "years"),
        ],
        f"Project #{index + 1}",
    )


def _normalize_entry(
    entry: ResumeMapping,
    ignore_keys: set[str] | None,
) -> dict[str, object]:
    if ignore_keys is None:
        return dict(entry)
    return {key: value for key, value in entry.items() if key not in ignore_keys}


def _append_entry_changes(
    changes: list[Diff],
    field_key: str,
    field_type: FieldType,
    original_items: Sequence[ResumeMapping],
    improved_items: Sequence[ResumeMapping],
    formatter: Callable[[ResumeMapping, int], str],
    ignore_keys: set[str] | None = None,
) -> None:
    min_len = min(len(original_items), len(improved_items))

    for idx in range(min_len):
        original_entry = original_items[idx]
        improved_entry = improved_items[idx]
        if _normalize_entry(original_entry, ignore_keys) != _normalize_entry(
            improved_entry, ignore_keys
        ):
            changes.append(
                Diff(
                    field_path=f"{field_key}[{idx}]",
                    field_type=field_type,
                    change_type="modified",
                    original_value=formatter(original_entry, idx),
                    new_value=formatter(improved_entry, idx),
                    confidence="medium",
                )
            )

    for idx in range(min_len, len(improved_items)):
        changes.append(
            Diff(
                field_path=f"{field_key}[{idx}]",
                field_type=field_type,
                change_type="added",
                new_value=formatter(improved_items[idx], idx),
                confidence="high",
            )
        )

    for idx in range(min_len, len(original_items)):
        changes.append(
            Diff(
                field_path=f"{field_key}[{idx}]",
                field_type=field_type,
                change_type="removed",
                original_value=formatter(original_items[idx], idx),
                confidence="medium",
            )
        )


def _normalize_string_list(value: object) -> list[str]:
    """Normalize string lists, accepting dicts with name/label/value keys."""

    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                normalized.append(stripped)
            continue
        if isinstance(item, Mapping):
            candidate = item.get("name") or item.get("label") or item.get("value")
            if isinstance(candidate, str):
                stripped = candidate.strip()
                if stripped:
                    normalized.append(stripped)
    return normalized


def _build_string_index(value: object) -> dict[str, str]:
    """Build a case-insensitive first-seen index for string list comparisons."""

    index: dict[str, str] = {}
    for item in _normalize_string_list(value):
        key = item.casefold()
        if key not in index:
            index[key] = item
    return index


def _extract_description_list(entry: object) -> list[str]:
    if not isinstance(entry, Mapping):
        return []
    return _normalize_string_list(entry.get("description", []))


def _append_list_changes(
    changes: list[Diff],
    field_path: str,
    field_type: FieldType,
    original_items: list[str],
    improved_items: list[str],
    confidences: DiffConfidence,
) -> None:
    matcher = SequenceMatcher(a=original_items, b=improved_items, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            for item in original_items[i1:i2]:
                changes.append(
                    Diff(
                        field_path=field_path,
                        field_type=field_type,
                        change_type="removed",
                        original_value=item,
                        confidence=confidences.removed,
                    )
                )
        elif tag == "insert":
            for item in improved_items[j1:j2]:
                changes.append(
                    Diff(
                        field_path=field_path,
                        field_type=field_type,
                        change_type="added",
                        new_value=item,
                        confidence=confidences.added,
                    )
                )
        elif tag == "replace":
            original_segment = original_items[i1:i2]
            improved_segment = improved_items[j1:j2]
            segment_len = max(len(original_segment), len(improved_segment))
            for offset in range(segment_len):
                original_value = (
                    original_segment[offset] if offset < len(original_segment) else None
                )
                new_value = improved_segment[offset] if offset < len(improved_segment) else None
                if original_value is not None and new_value is not None:
                    changes.append(
                        Diff(
                            field_path=field_path,
                            field_type=field_type,
                            change_type="modified",
                            original_value=original_value,
                            new_value=new_value,
                            confidence=confidences.modified,
                        )
                    )
                elif new_value is not None:
                    changes.append(
                        Diff(
                            field_path=field_path,
                            field_type=field_type,
                            change_type="added",
                            new_value=new_value,
                            confidence=confidences.added,
                        )
                    )
                elif original_value is not None:
                    changes.append(
                        Diff(
                            field_path=field_path,
                            field_type=field_type,
                            change_type="removed",
                            original_value=original_value,
                            confidence=confidences.removed,
                        )
                    )


def _append_index_added_removed(
    changes: list[Diff],
    *,
    original_index: Mapping[str, str],
    improved_index: Mapping[str, str],
    field_path: str,
    field_type: FieldType,
    added_confidence: Confidence,
    removed_confidence: Confidence,
) -> None:
    for key, value in improved_index.items():
        if key not in original_index:
            changes.append(
                Diff(
                    field_path=field_path,
                    field_type=field_type,
                    change_type="added",
                    new_value=value,
                    confidence=added_confidence,
                )
            )

    for key, value in original_index.items():
        if key not in improved_index:
            changes.append(
                Diff(
                    field_path=field_path,
                    field_type=field_type,
                    change_type="removed",
                    original_value=value,
                    confidence=removed_confidence,
                )
            )


def _append_scalar_description_change(
    changes: list[Diff],
    *,
    field_path: str,
    field_type: FieldType,
    original_value: str,
    improved_value: str,
) -> None:
    if original_value == improved_value:
        return
    if original_value and not improved_value:
        change_type: ChangeType = "removed"
    elif improved_value and not original_value:
        change_type = "added"
    else:
        change_type = "modified"
    changes.append(
        Diff(
            field_path=field_path,
            field_type=field_type,
            change_type=change_type,
            original_value=original_value or None,
            new_value=improved_value or None,
            confidence="medium",
        )
    )


def calculate_resume_diff(
    original: ResumeMapping,
    improved: ResumeMapping,
) -> tuple[ResumeDiffSummary, list[Diff]]:
    """Compute a deterministic field-level diff between two resume dictionaries."""

    changes: list[Diff] = []

    original_summary = str(original.get("summary") or "").strip()
    improved_summary = str(improved.get("summary") or "").strip()
    _append_scalar_description_change(
        changes,
        field_path="summary",
        field_type="summary",
        original_value=original_summary,
        improved_value=improved_summary,
    )

    original_additional = _child_mapping(original, "additional")
    improved_additional = _child_mapping(improved, "additional")

    orig_skills = _build_string_index(original_additional.get("technicalSkills", []))
    new_skills = _build_string_index(improved_additional.get("technicalSkills", []))
    _append_index_added_removed(
        changes,
        original_index=orig_skills,
        improved_index=new_skills,
        field_path="additional.technicalSkills",
        field_type="skill",
        added_confidence="high",
        removed_confidence="medium",
    )

    original_experiences = _mapping_list(original, "workExperience")
    improved_experiences = _mapping_list(improved, "workExperience")
    max_experience_len = max(len(original_experiences), len(improved_experiences))
    confidences = DiffConfidence(added="medium", removed="low", modified="medium")
    for idx in range(max_experience_len):
        original_entry = original_experiences[idx] if idx < len(original_experiences) else None
        improved_entry = improved_experiences[idx] if idx < len(improved_experiences) else None
        if not original_entry and not improved_entry:
            continue
        _append_list_changes(
            changes,
            field_path=f"workExperience[{idx}].description",
            field_type="description",
            original_items=_extract_description_list(original_entry),
            improved_items=_extract_description_list(improved_entry),
            confidences=confidences,
        )

    orig_certs = _build_string_index(original_additional.get("certificationsTraining", []))
    new_certs = _build_string_index(improved_additional.get("certificationsTraining", []))
    _append_index_added_removed(
        changes,
        original_index=orig_certs,
        improved_index=new_certs,
        field_path="additional.certificationsTraining",
        field_type="certification",
        added_confidence="high",
        removed_confidence="medium",
    )

    original_education = _mapping_list(original, "education")
    improved_education = _mapping_list(improved, "education")
    for idx in range(max(len(original_education), len(improved_education))):
        original_entry = original_education[idx] if idx < len(original_education) else None
        improved_entry = improved_education[idx] if idx < len(improved_education) else None
        original_description = (
            str(original_entry.get("description") or "").strip()
            if original_entry is not None
            else ""
        )
        improved_description = (
            str(improved_entry.get("description") or "").strip()
            if improved_entry is not None
            else ""
        )
        _append_scalar_description_change(
            changes,
            field_path=f"education[{idx}].description",
            field_type="education",
            original_value=original_description,
            improved_value=improved_description,
        )

    orig_langs = _build_string_index(original_additional.get("languages", []))
    new_langs = _build_string_index(improved_additional.get("languages", []))
    _append_index_added_removed(
        changes,
        original_index=orig_langs,
        improved_index=new_langs,
        field_path="additional.languages",
        field_type="language",
        added_confidence="high",
        removed_confidence="medium",
    )

    orig_awards = _build_string_index(original_additional.get("awards", []))
    new_awards = _build_string_index(improved_additional.get("awards", []))
    _append_index_added_removed(
        changes,
        original_index=orig_awards,
        improved_index=new_awards,
        field_path="additional.awards",
        field_type="award",
        added_confidence="high",
        removed_confidence="medium",
    )

    _append_entry_changes(
        changes,
        "workExperience",
        "experience",
        original_experiences,
        improved_experiences,
        _format_experience_entry,
        {"description"},
    )
    _append_entry_changes(
        changes,
        "education",
        "education",
        original_education,
        improved_education,
        _format_education_entry,
        {"description"},
    )
    _append_entry_changes(
        changes,
        "personalProjects",
        "project",
        _mapping_list(original, "personalProjects"),
        _mapping_list(improved, "personalProjects"),
        _format_project_entry,
    )

    summary = ResumeDiffSummary(
        total_changes=len(changes),
        skills_added=len(
            [c for c in changes if c.field_type == "skill" and c.change_type == "added"]
        ),
        skills_removed=len(
            [c for c in changes if c.field_type == "skill" and c.change_type == "removed"]
        ),
        descriptions_modified=len(
            [
                c
                for c in changes
                if c.field_type == "description" and c.change_type == "modified"
            ]
        ),
        certifications_added=len(
            [
                c
                for c in changes
                if c.field_type == "certification" and c.change_type == "added"
            ]
        ),
        high_risk_changes=len([c for c in changes if c.confidence == "high"]),
    )

    return summary, changes
