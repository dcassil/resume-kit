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

# Interface substrate helpers
from resume_kit_core.interface import (
    ExitCode,
    build_needs_input,
    build_provider_not_configured,
    build_success,
    escalate_warnings,
    exit_code_for,
    from_exception,
    from_resume_kit_error,
    from_validation_error,
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
    # interface substrate
    "ExitCode",
    "build_needs_input",
    "build_provider_not_configured",
    "build_success",
    "escalate_warnings",
    "exit_code_for",
    "from_exception",
    "from_resume_kit_error",
    "from_validation_error",
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
