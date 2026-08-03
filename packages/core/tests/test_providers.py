"""Tests for provider Protocol and request models."""

from __future__ import annotations

import pytest
from resume_kit_core.providers import (
    CompletionRequest,
    MessageParam,
    StructuredCompletionProvider,
    StructuredCompletionRequest,
)
from resume_kit_core.testing import FakeCompletionProvider, FakeStructuredCompletionProvider


class TestStructuredCompletionRequest:
    def test_prompt_only(self) -> None:
        req = StructuredCompletionRequest(prompt="hello")
        assert req.prompt == "hello"
        assert req.messages is None

    def test_messages(self) -> None:
        req = StructuredCompletionRequest(
            messages=[
                MessageParam(role="system", content="You are helpful."),
                MessageParam(role="user", content="Parse this."),
            ]
        )
        assert len(req.messages) == 2  # type: ignore[arg-type]

    def test_optional_fields(self) -> None:
        req = StructuredCompletionRequest(
            prompt="x",
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1024,
            timeout_seconds=60.0,
            max_retries=3,
            output_schema={"type": "object"},
            extra={"response_format": "json_object"},
        )
        assert req.model == "gpt-4o"
        assert req.temperature == 0.0
        assert req.extra["response_format"] == "json_object"

    def test_forbids_extra_fields(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StructuredCompletionRequest(prompt="x", nonexistent_field=True)  # type: ignore[call-arg]

    def test_round_trip(self) -> None:
        req = StructuredCompletionRequest(prompt="test", model="gpt-4o-mini")
        restored = StructuredCompletionRequest.model_validate(req.model_dump())
        assert restored == req


class TestStructuredCompletionProviderProtocol:
    def test_fake_satisfies_runtime_checkable_protocol(self) -> None:
        provider = FakeStructuredCompletionProvider()
        assert isinstance(provider, StructuredCompletionProvider)

    @pytest.mark.asyncio
    async def test_fake_returns_queued_response(self) -> None:
        expected = {"name": "Alice", "score": 0.95}
        provider = FakeStructuredCompletionProvider(responses=[expected])
        result = await provider.complete_json(StructuredCompletionRequest(prompt="go"))
        assert result == expected

    @pytest.mark.asyncio
    async def test_fake_uses_default_when_queue_empty(self) -> None:
        default = {"fallback": True}
        provider = FakeStructuredCompletionProvider(default_response=default)
        result = await provider.complete_json(StructuredCompletionRequest(prompt="go"))
        assert result == default

    @pytest.mark.asyncio
    async def test_fake_raises_when_exhausted_no_default(self) -> None:
        from resume_kit_core.errors import ResumeKitError

        provider = FakeStructuredCompletionProvider()
        with pytest.raises(ResumeKitError):
            await provider.complete_json(StructuredCompletionRequest(prompt="go"))

    @pytest.mark.asyncio
    async def test_fake_records_calls(self) -> None:
        provider = FakeStructuredCompletionProvider(default_response={})
        req = StructuredCompletionRequest(prompt="abc", model="gpt-4o")
        await provider.complete_json(req)
        await provider.complete_json(req)
        assert len(provider.calls) == 2
        assert provider.calls[0].model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_fake_dequeues_in_order(self) -> None:
        provider = FakeStructuredCompletionProvider(
            responses=[{"n": 1}, {"n": 2}, {"n": 3}]
        )
        req = StructuredCompletionRequest(prompt="x")
        assert (await provider.complete_json(req))["n"] == 1
        assert (await provider.complete_json(req))["n"] == 2
        assert (await provider.complete_json(req))["n"] == 3


class TestCompletionProviderFake:
    @pytest.mark.asyncio
    async def test_fake_returns_queued_text(self) -> None:
        provider = FakeCompletionProvider(responses=["hello world"])
        result = await provider.complete(CompletionRequest(prompt="hi"))
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_fake_uses_default(self) -> None:
        provider = FakeCompletionProvider(default_response="default text")
        result = await provider.complete(CompletionRequest(prompt="?"))
        assert result == "default text"
