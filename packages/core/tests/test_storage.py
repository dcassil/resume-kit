"""Tests for storage Protocol and FakeArtifactStore."""

from __future__ import annotations

import pytest
from resume_kit_core.errors import ErrorCode, ResumeKitError
from resume_kit_core.storage import ArtifactRef, ArtifactStore
from resume_kit_core.testing import FakeArtifactStore


class TestArtifactRef:
    def test_construction(self) -> None:
        ref = ArtifactRef(artifact_id="abc123", artifact_type="resume")
        assert ref.artifact_id == "abc123"
        assert ref.content_type == "application/json"
        assert ref.metadata == {}

    def test_round_trip(self) -> None:
        ref = ArtifactRef(
            artifact_id="x",
            artifact_type="report",
            content_type="text/plain",
            metadata={"version": 1},
        )
        restored = ArtifactRef.model_validate(ref.model_dump())
        assert restored == ref


class TestFakeArtifactStoreProtocol:
    def test_satisfies_runtime_checkable_protocol(self) -> None:
        store = FakeArtifactStore()
        assert isinstance(store, ArtifactStore)

    @pytest.mark.asyncio
    async def test_put_returns_artifact_ref(self) -> None:
        store = FakeArtifactStore()
        ref = await store.put("id1", "resume", {"name": "Alice"})
        assert isinstance(ref, ArtifactRef)
        assert ref.artifact_id == "id1"
        assert ref.artifact_type == "resume"

    @pytest.mark.asyncio
    async def test_get_returns_stored_data(self) -> None:
        store = FakeArtifactStore()
        payload = {"score": 0.9}
        await store.put("a1", "report", payload)
        result = await store.get("a1")
        assert result == payload

    @pytest.mark.asyncio
    async def test_get_raises_for_missing_artifact(self) -> None:
        store = FakeArtifactStore()
        with pytest.raises(ResumeKitError) as exc_info:
            await store.get("nonexistent")
        assert exc_info.value.error.code == ErrorCode.ARTIFACT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_exists_true(self) -> None:
        store = FakeArtifactStore()
        await store.put("x", "resume", {})
        assert await store.exists("x") is True

    @pytest.mark.asyncio
    async def test_exists_false(self) -> None:
        store = FakeArtifactStore()
        assert await store.exists("missing") is False

    @pytest.mark.asyncio
    async def test_stored_ids_helper(self) -> None:
        store = FakeArtifactStore()
        await store.put("a", "resume", {})
        await store.put("b", "report", {})
        assert set(store.stored_ids()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_metadata_stored_on_ref(self) -> None:
        store = FakeArtifactStore()
        ref = await store.put(
            "m1", "resume", {}, metadata={"source": "upload"}
        )
        assert ref.metadata["source"] == "upload"
