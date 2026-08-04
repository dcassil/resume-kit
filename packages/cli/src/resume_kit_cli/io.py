"""Input helpers for the Resume Kit CLI.

Reads raw bytes / text / JSON from a file path or standard input and parses
JSON into the ``resume_kit_schemas`` value types the facade request models
carry.  These helpers contain no business rules: they only load and validate
transport inputs before a capability is invoked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from pydantic import BaseModel, ValidationError
from resume_kit_core.storage import ArtifactRef
from resume_kit_schemas import (
    CandidateEvidence,
    JobDescription,
    ResumeDocument,
)

_STDIN = "-"


def _fail(message: str) -> typer.BadParameter:
    """Build a uniform ``BadParameter`` error for input problems."""
    return typer.BadParameter(message)


def read_bytes(source: str) -> bytes:
    """Read raw bytes from ``source`` (a file path, or ``-`` for stdin)."""
    if source == _STDIN:
        return sys.stdin.buffer.read()
    path = Path(source)
    if not path.is_file():
        raise _fail(f"Input file not found: {source}")
    return path.read_bytes()


def read_text(source: str) -> str:
    """Read decoded text from ``source`` (a file path, or ``-`` for stdin)."""
    if source == _STDIN:
        return sys.stdin.read()
    path = Path(source)
    if not path.is_file():
        raise _fail(f"Input file not found: {source}")
    return path.read_text(encoding="utf-8")


def _load_json_text(source: str) -> str:
    """Read the raw JSON text from ``source`` without parsing it."""
    return read_text(source)


def load_model[ModelT: BaseModel](source: str, model: type[ModelT]) -> ModelT:
    """Parse the JSON at ``source`` into ``model``.

    Raises a ``typer.BadParameter`` (never a bare traceback) when the JSON is
    malformed or does not satisfy the model schema.
    """
    raw = _load_json_text(source)
    try:
        return model.model_validate_json(raw)
    except ValidationError as exc:
        raise _fail(f"Invalid {model.__name__} JSON in {source}: {exc}") from exc


def load_resume(source: str) -> ResumeDocument:
    """Load a :class:`ResumeDocument` from JSON at ``source``."""
    return load_model(source, ResumeDocument)


def load_job(source: str) -> JobDescription:
    """Load a :class:`JobDescription` from JSON at ``source``."""
    return load_model(source, JobDescription)


def load_resumes(source: str) -> list[ResumeDocument]:
    """Load a JSON array of :class:`ResumeDocument` objects from ``source``."""
    raw = _load_json_text(source)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _fail(f"Invalid JSON in {source}: {exc}") from exc
    if not isinstance(payload, list):
        raise _fail(f"Expected a JSON array of resumes in {source}.")
    resumes: list[ResumeDocument] = []
    for index, item in enumerate(payload):
        try:
            resumes.append(ResumeDocument.model_validate(item))
        except ValidationError as exc:
            raise _fail(f"Invalid resume at index {index} in {source}: {exc}") from exc
    return resumes


class InMemoryArtifactStore:
    """Minimal in-memory :class:`ArtifactStore` for the CLI transport.

    The CLI injects an instance through ``CapabilityOptions.artifact_store`` so
    it can retrieve rendered bytes after ``export-resume`` returns an
    :class:`ArtifactRef`.  It holds bytes in a plain dict; no test fake is
    imported into app code.
    """

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def put(
        self,
        artifact_id: str,
        artifact_type: str,
        data: object,
        *,
        content_type: str = "application/json",
        metadata: dict[str, object] | None = None,
    ) -> ArtifactRef:
        """Store ``data`` in memory and return a reference to it."""
        self._store[artifact_id] = data
        return ArtifactRef(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_type=content_type,
            metadata=metadata or {},
        )

    async def get(self, artifact_id: str) -> object:
        """Return the payload stored under ``artifact_id``."""
        return self._store[artifact_id]

    async def exists(self, artifact_id: str) -> bool:
        """Return True if ``artifact_id`` is present."""
        return artifact_id in self._store


def load_evidence(source: str) -> list[CandidateEvidence]:
    """Load a JSON array of :class:`CandidateEvidence` objects from ``source``."""
    raw = _load_json_text(source)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _fail(f"Invalid JSON in {source}: {exc}") from exc
    if not isinstance(payload, list):
        raise _fail(f"Expected a JSON array of evidence in {source}.")
    evidence: list[CandidateEvidence] = []
    for index, item in enumerate(payload):
        try:
            evidence.append(CandidateEvidence.model_validate(item))
        except ValidationError as exc:
            raise _fail(f"Invalid evidence at index {index} in {source}: {exc}") from exc
    return evidence
