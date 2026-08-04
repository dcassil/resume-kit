"""Provider-not-configured tests for every LLM-requiring capability.

Each LLM-requiring capability, invoked with ``provider=None`` and ``no_llm``
False, must return the stable provider-not-configured failure from the core
substrate — never call the engine, never crash.
"""

from __future__ import annotations

from resume_kit_core import InterfaceResponse
from resume_kit_core.errors import ErrorCode
from resume_kit_core.interface import ExitCode, exit_code_for
from resume_kit_facade import capabilities as caps
from resume_kit_facade.models import (
    AlignResumeRequest,
    CapabilityOptions,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
)
from resume_kit_schemas import JobDescription, ResumeDocument

# provider=None, no_llm=False -> LLM path required but no provider.
_NO_PROVIDER = CapabilityOptions()


def _assert_provider_not_configured(response: InterfaceResponse[object]) -> None:
    assert not response.ok
    assert len(response.errors) == 1
    assert response.errors[0].code is ErrorCode.PROVIDER_NOT_CONFIGURED
    assert exit_code_for(response) == int(ExitCode.PROVIDER_NOT_CONFIGURED)


async def test_extract_resume_requires_provider() -> None:
    response = await caps.extract_resume(
        ExtractResumeRequest(content=b"Jane Doe", filename="cv.txt"), _NO_PROVIDER
    )
    _assert_provider_not_configured(response)


async def test_extract_job_description_requires_provider() -> None:
    response = await caps.extract_job_description(
        ExtractJobDescriptionRequest(raw_text="Backend Engineer"), _NO_PROVIDER
    )
    _assert_provider_not_configured(response)


async def test_align_resume_requires_provider() -> None:
    response = await caps.align_resume(
        AlignResumeRequest(resume=ResumeDocument(), job=JobDescription()),
        _NO_PROVIDER,
    )
    _assert_provider_not_configured(response)
