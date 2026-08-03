"""Core package for resume evaluation, matching, and validation.

Public surface — everything re-exported here is stable API.
"""

__version__ = "0.0.0"

# Errors & warnings
from resume_kit_core.errors import (
    CoreError,
    CoreWarning,
    ErrorCode,
    ResumeKitError,
    WarningCode,
)

# Provider contracts
from resume_kit_core.providers import (
    CompletionProvider,
    CompletionRequest,
    MessageParam,
    StructuredCompletionProvider,
    StructuredCompletionRequest,
)

# Response envelope & supporting value types
from resume_kit_core.response import (
    InterfaceResponse,
    ProvenanceRef,
    Question,
)

# Storage contracts
from resume_kit_core.storage import (
    ArtifactRef,
    ArtifactStore,
)

__all__ = [
    # errors
    "CoreError",
    "CoreWarning",
    "ErrorCode",
    "ResumeKitError",
    "WarningCode",
    # providers
    "CompletionProvider",
    "CompletionRequest",
    "MessageParam",
    "StructuredCompletionProvider",
    "StructuredCompletionRequest",
    # storage
    "ArtifactRef",
    "ArtifactStore",
    # response
    "InterfaceResponse",
    "ProvenanceRef",
    "Question",
]
