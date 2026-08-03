"""Generic InterfaceResponse envelope shared by CLI, MCP, and API layers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from resume_kit_core.errors import CoreError, CoreWarning
from resume_kit_core.storage import ArtifactRef

# ---------------------------------------------------------------------------
# Supporting value types
# ---------------------------------------------------------------------------


class Question(BaseModel):
    """A clarifying question the interface would like a human to answer."""

    question_id: str = Field(description="Stable identifier for this question.")
    text: str = Field(description="Human-readable question text.")
    hint: str | None = Field(
        default=None,
        description="Optional hint or expected answer format.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvenanceRef(BaseModel):
    """A reference to the source / lineage of a piece of generated data."""

    source_id: str = Field(description="Identifier of the originating resource.")
    source_type: str = Field(
        description="Category of source, e.g. 'resume', 'job_description', 'llm_response'."
    )
    field_path: str | None = Field(
        default=None,
        description="Dot-notation path within the source document, if applicable.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# InterfaceResponse envelope
# ---------------------------------------------------------------------------


class InterfaceResponse[T](BaseModel):
    """Generic envelope returned by all resume-kit interface operations.

    Every CLI command, MCP tool, and API endpoint wraps its result in this
    type so callers get a uniform structure regardless of the layer they use.

    Type parameter ``T`` is the type of the :attr:`data` payload.  Use
    ``InterfaceResponse[None]`` for operations with no meaningful output.

    Example::

        from resume_kit_core.response import InterfaceResponse
        from resume_kit_core.errors import CoreWarning, WarningCode

        resp: InterfaceResponse[dict[str, str]] = InterfaceResponse(
            data={"score": "0.92"},
            warnings=[
                CoreWarning(
                    code=WarningCode.HUMAN_REVIEW_SUGGESTED,
                    message="Confidence below threshold",
                )
            ],
        )
        print(resp.model_dump_json())
    """

    data: T | None = Field(
        default=None,
        description="Primary result payload.  ``None`` on failure.",
    )
    warnings: list[CoreWarning] = Field(
        default_factory=list,
        description="Non-fatal advisory notices.  May be non-empty even on success.",
    )
    errors: list[CoreError] = Field(
        default_factory=list,
        description=(
            "Structured errors.  Non-empty implies the operation failed or partially "
            "failed.  ``data`` may still be present for partial success."
        ),
    )
    requires_human_input: bool = Field(
        default=False,
        description=(
            "True when the operation cannot proceed without human answers to "
            ":attr:`questions`."
        ),
    )
    questions: list[Question] = Field(
        default_factory=list,
        description=(
            "Clarifying questions for the human when ``requires_human_input`` is True."
        ),
    )
    artifacts: list[ArtifactRef] = Field(
        default_factory=list,
        description="References to artifacts produced during this operation.",
    )
    provenance: list[ProvenanceRef] = Field(
        default_factory=list,
        description="Lineage references explaining how ``data`` was derived.",
    )

    # -----------------------------------------------------------------------
    # Convenience constructors
    # -----------------------------------------------------------------------

    @classmethod
    def success(
        cls,
        data: T,
        *,
        warnings: list[CoreWarning] | None = None,
        artifacts: list[ArtifactRef] | None = None,
        provenance: list[ProvenanceRef] | None = None,
    ) -> InterfaceResponse[T]:
        """Return a successful response wrapping ``data``."""
        return cls(
            data=data,
            warnings=warnings or [],
            artifacts=artifacts or [],
            provenance=provenance or [],
        )

    @classmethod
    def failure(
        cls,
        errors: list[CoreError],
        *,
        warnings: list[CoreWarning] | None = None,
    ) -> InterfaceResponse[None]:
        """Return a failed response with no data payload."""
        return InterfaceResponse[None](
            data=None,
            errors=errors,
            warnings=warnings or [],
        )

    @classmethod
    def needs_input(
        cls,
        questions: list[Question],
        *,
        warnings: list[CoreWarning] | None = None,
    ) -> InterfaceResponse[None]:
        """Return a response that pauses execution pending human input."""
        return InterfaceResponse[None](
            data=None,
            requires_human_input=True,
            questions=questions,
            warnings=warnings or [],
        )

    # -----------------------------------------------------------------------
    # Derived properties
    # -----------------------------------------------------------------------

    @property
    def ok(self) -> bool:
        """True when there are no errors and no human input is required."""
        return not self.errors and not self.requires_human_input

    model_config = {"arbitrary_types_allowed": True}
