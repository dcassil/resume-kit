"""Provider boundary contracts for LLM completion.

All types here are pure interface definitions — no concrete provider, SDK,
network call, or persistence dependency is allowed in this module.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class MessageParam(BaseModel):
    """A single message in a chat-style completion request."""

    role: Literal["system", "user", "assistant"] = Field(
        description="Role of the message author."
    )
    content: str = Field(description="Text content of the message.")


class StructuredCompletionRequest(BaseModel):
    """LLM-agnostic request for a structured (JSON) completion.

    Decouples callers from concrete provider APIs.  Phase 2+ adapters
    (e.g. LiteLLM) receive this model and translate it to their native API.
    """

    # Either a simple prompt string *or* a list of messages must be supplied.
    prompt: str | None = Field(
        default=None,
        description=(
            "Single-turn prompt text.  Mutually exclusive with ``messages``."
        ),
    )
    messages: list[MessageParam] | None = Field(
        default=None,
        description=(
            "Multi-turn message history.  Mutually exclusive with ``prompt``."
        ),
    )

    # Schema the provider should conform its output to (JSON Schema dict).
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description=(
            "JSON Schema describing the expected output object.  "
            "Providers may use this to guide structured output."
        ),
    )

    # Model / provider hints — treated as advisory by the provider.
    model: str | None = Field(
        default=None,
        description="Provider-specific model identifier, e.g. 'gpt-4o'.",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.  Provider may ignore if unsupported.",
    )
    max_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Maximum tokens to generate.",
    )

    # Timeout / retry metadata — stored as data only; enforcement is caller's.
    timeout_seconds: float | None = Field(
        default=None,
        gt=0.0,
        description="Wall-clock timeout hint (seconds).  Not enforced here.",
    )
    max_retries: int | None = Field(
        default=None,
        ge=0,
        description="Maximum retry attempts hint.  Not enforced here.",
    )

    # Free-form provider-specific extras that don't belong in typed fields.
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary provider-specific parameters passed through as-is.",
    )

    model_config = {"extra": "forbid"}


class CompletionRequest(BaseModel):
    """LLM-agnostic request for a plain-text (non-structured) completion."""

    prompt: str | None = Field(default=None)
    messages: list[MessageParam] | None = Field(default=None)
    model: str | None = Field(default=None)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    timeout_seconds: float | None = Field(default=None, gt=0.0)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Provider Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class StructuredCompletionProvider(Protocol):
    """Async provider that returns a JSON-compatible dict.

    Concrete implementations (LiteLLM adapter, fake, etc.) must satisfy this
    structural Protocol.  No base class inheritance is required.
    """

    async def complete_json(
        self,
        request: StructuredCompletionRequest,
    ) -> dict[str, Any]:
        """Execute a structured completion and return the parsed JSON object.

        Args:
            request: Typed request carrying prompt/messages, schema, and hints.

        Returns:
            A ``dict`` parsed from the provider's JSON response.

        Raises:
            :class:`resume_kit_core.errors.ResumeKitError`: on provider failure.
        """
        ...


@runtime_checkable
class CompletionProvider(Protocol):
    """Async provider that returns plain text."""

    async def complete(
        self,
        request: CompletionRequest,
    ) -> str:
        """Execute a plain-text completion and return the string response."""
        ...
