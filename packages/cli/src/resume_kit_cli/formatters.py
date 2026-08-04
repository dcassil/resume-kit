"""Rendering helpers for the Resume Kit CLI.

Turns an :class:`~resume_kit_core.response.InterfaceResponse` into one of three
serialisations — ``json``, ``text``, or ``md`` — without redefining the
response, warning, error, provenance, artifact, or question shapes.  The
canonical JSON form is simply ``InterfaceResponse.model_dump(mode="json")``;
the human-readable forms are derived views over the same envelope.
"""

from __future__ import annotations

import json
from enum import StrEnum

from resume_kit_core.response import InterfaceResponse


class OutputFormat(StrEnum):
    """Supported CLI output serialisations."""

    JSON = "json"
    TEXT = "text"
    MD = "md"


def _dump(response: InterfaceResponse[object]) -> dict[str, object]:
    """Return the canonical JSON-mode dump of the response envelope."""
    return response.model_dump(mode="json")


def _render_json(response: InterfaceResponse[object]) -> str:
    """Render the full envelope as indented JSON."""
    return json.dumps(_dump(response), indent=2, sort_keys=True)


def _status_line(response: InterfaceResponse[object]) -> str:
    """Describe the top-level outcome of the response."""
    if response.errors:
        return "status: error"
    if response.requires_human_input:
        return "status: needs-input"
    if response.warnings:
        return "status: ok (with warnings)"
    return "status: ok"


def _render_text(response: InterfaceResponse[object]) -> str:
    """Render a plain-text human-readable view of the envelope."""
    lines: list[str] = [_status_line(response)]
    for error in response.errors:
        lines.append(f"error [{error.code}]: {error.message}")
    for warning in response.warnings:
        lines.append(f"warning [{warning.code}]: {warning.message}")
    for question in response.questions:
        lines.append(f"question [{question.question_id}]: {question.text}")
    for ref in response.provenance:
        lines.append(f"provenance: {ref.source_type}:{ref.source_id}")
    for artifact in response.artifacts:
        lines.append(f"artifact: {artifact.artifact_id}")
    dump = _dump(response)
    lines.append("data:")
    lines.append(json.dumps(dump.get("data"), indent=2, sort_keys=True))
    return "\n".join(lines)


def _md_section(title: str, items: list[str]) -> list[str]:
    """Build a Markdown bullet section, omitting it when there are no items."""
    if not items:
        return []
    out = [f"## {title}", ""]
    out.extend(f"- {item}" for item in items)
    out.append("")
    return out


def _render_md(response: InterfaceResponse[object]) -> str:
    """Render a Markdown human-readable view of the envelope."""
    dump = _dump(response)
    lines: list[str] = [f"# Result — {_status_line(response)}", ""]
    lines.extend(
        _md_section(
            "Errors",
            [f"`{e.code}` {e.message}" for e in response.errors],
        )
    )
    lines.extend(
        _md_section(
            "Warnings",
            [f"`{w.code}` {w.message}" for w in response.warnings],
        )
    )
    lines.extend(
        _md_section(
            "Questions",
            [f"`{q.question_id}` {q.text}" for q in response.questions],
        )
    )
    lines.extend(
        _md_section(
            "Provenance",
            [f"{r.source_type}:{r.source_id}" for r in response.provenance],
        )
    )
    lines.extend(
        _md_section(
            "Artifacts",
            [a.artifact_id for a in response.artifacts],
        )
    )
    lines.append("## Data")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(dump.get("data"), indent=2, sort_keys=True))
    lines.append("```")
    return "\n".join(lines)


def render(response: InterfaceResponse[object], output: OutputFormat) -> str:
    """Render ``response`` in the requested ``output`` format."""
    if output is OutputFormat.JSON:
        return _render_json(response)
    if output is OutputFormat.TEXT:
        return _render_text(response)
    return _render_md(response)
