"""Storage boundary contracts for artifact persistence.

No concrete backend (filesystem, S3, database, etc.) is imported here.
Phase 2+ injects implementations via the :class:`ArtifactStore` Protocol.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Artifact reference / metadata value types
# ---------------------------------------------------------------------------


class ArtifactRef(BaseModel):
    """Lightweight reference to a stored artifact.

    Carries enough information to retrieve the artifact later without exposing
    backend-specific paths or URLs in the core interface.
    """

    artifact_id: str = Field(description="Unique identifier for the artifact.")
    artifact_type: str = Field(
        description="Logical type tag, e.g. 'resume', 'job_description', 'report'."
    )
    content_type: str = Field(
        default="application/json",
        description="MIME content type of the stored payload.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key/value metadata associated with the artifact.",
    )


# ---------------------------------------------------------------------------
# ArtifactStore Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ArtifactStore(Protocol):
    """Async boundary for writing and reading generated artifacts.

    Concrete implementations (in-memory, filesystem, object-storage) must
    satisfy this structural Protocol.
    """

    async def put(
        self,
        artifact_id: str,
        artifact_type: str,
        data: Any,
        *,
        content_type: str = "application/json",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        """Persist ``data`` and return a reference to it.

        Args:
            artifact_id:  Caller-supplied unique identifier.
            artifact_type: Logical type tag.
            data:          Serialisable artifact payload.
            content_type:  MIME type of the payload.
            metadata:      Optional key/value annotations.

        Returns:
            :class:`ArtifactRef` describing the persisted artifact.
        """
        ...

    async def get(self, artifact_id: str) -> Any:
        """Retrieve the payload previously stored under ``artifact_id``.

        Returns:
            The original payload.

        Raises:
            :class:`resume_kit_core.errors.ResumeKitError` with
            ``ErrorCode.ARTIFACT_NOT_FOUND`` if the id is unknown.
        """
        ...

    async def exists(self, artifact_id: str) -> bool:
        """Return ``True`` if an artifact with ``artifact_id`` is stored."""
        ...
