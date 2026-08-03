"""In-memory fakes for testing.

Provides :class:`FakeStructuredCompletionProvider` and
:class:`FakeArtifactStore` that satisfy the core Protocols without any
network calls, filesystem access, or concrete provider SDK dependencies.

Usage::

    from resume_kit_core.testing import FakeStructuredCompletionProvider
    from resume_kit_core.providers import StructuredCompletionRequest

    provider = FakeStructuredCompletionProvider(
        responses=[{"name": "Alice", "score": 0.9}]
    )
    result = await provider.complete_json(
        StructuredCompletionRequest(prompt="Parse this resume")
    )
    assert result == {"name": "Alice", "score": 0.9}
"""

from __future__ import annotations

from collections import deque
from typing import Any

from resume_kit_core.errors import CoreError, ErrorCode, ResumeKitError
from resume_kit_core.providers import CompletionRequest, StructuredCompletionRequest
from resume_kit_core.storage import ArtifactRef


class FakeStructuredCompletionProvider:
    """In-memory fake implementing :class:`~resume_kit_core.providers.StructuredCompletionProvider`.

    Dequeues pre-loaded responses on each :meth:`complete_json` call.  If the
    queue is exhausted and ``default_response`` is provided, it returns that;
    otherwise raises :class:`~resume_kit_core.errors.ResumeKitError`.

    Structurally satisfies ``StructuredCompletionProvider`` (runtime-checkable
    Protocol) without subclassing it.
    """

    def __init__(
        self,
        responses: list[dict[str, Any]] | None = None,
        *,
        default_response: dict[str, Any] | None = None,
    ) -> None:
        self._queue: deque[dict[str, Any]] = deque(responses or [])
        self._default_response = default_response
        self.calls: list[StructuredCompletionRequest] = []

    def enqueue(self, response: dict[str, Any]) -> None:
        """Add a response to the queue."""
        self._queue.append(response)

    async def complete_json(
        self,
        request: StructuredCompletionRequest,
    ) -> dict[str, Any]:
        """Return the next queued response or the default."""
        self.calls.append(request)
        if self._queue:
            return self._queue.popleft()
        if self._default_response is not None:
            return self._default_response
        raise ResumeKitError(
            CoreError(
                code=ErrorCode.PROVIDER_INVALID_RESPONSE,
                message="FakeStructuredCompletionProvider queue exhausted with no default.",
            )
        )


class FakeCompletionProvider:
    """In-memory fake implementing :class:`~resume_kit_core.providers.CompletionProvider`."""

    def __init__(
        self,
        responses: list[str] | None = None,
        *,
        default_response: str | None = None,
    ) -> None:
        self._queue: deque[str] = deque(responses or [])
        self._default_response = default_response
        self.calls: list[CompletionRequest] = []

    def enqueue(self, response: str) -> None:
        """Add a plain-text response to the queue."""
        self._queue.append(response)

    async def complete(self, request: CompletionRequest) -> str:
        """Return the next queued response or the default."""
        self.calls.append(request)
        if self._queue:
            return self._queue.popleft()
        if self._default_response is not None:
            return self._default_response
        raise ResumeKitError(
            CoreError(
                code=ErrorCode.PROVIDER_INVALID_RESPONSE,
                message="FakeCompletionProvider queue exhausted with no default.",
            )
        )


class FakeArtifactStore:
    """In-memory fake implementing :class:`~resume_kit_core.storage.ArtifactStore`.

    Stores artifacts in a plain dict; satisfies the Protocol structurally.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._refs: dict[str, ArtifactRef] = {}

    async def put(
        self,
        artifact_id: str,
        artifact_type: str,
        data: Any,
        *,
        content_type: str = "application/json",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRef:
        """Store ``data`` in memory and return a reference."""
        self._store[artifact_id] = data
        ref = ArtifactRef(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_type=content_type,
            metadata=metadata or {},
        )
        self._refs[artifact_id] = ref
        return ref

    async def get(self, artifact_id: str) -> Any:
        """Return stored data or raise ResumeKitError if not found."""
        if artifact_id not in self._store:
            raise ResumeKitError(
                CoreError(
                    code=ErrorCode.ARTIFACT_NOT_FOUND,
                    message=f"Artifact '{artifact_id}' not found in FakeArtifactStore.",
                )
            )
        return self._store[artifact_id]

    async def exists(self, artifact_id: str) -> bool:
        """Return True if the artifact id is present."""
        return artifact_id in self._store

    def stored_ids(self) -> list[str]:
        """Return all currently stored artifact ids (test introspection helper)."""
        return list(self._store.keys())
