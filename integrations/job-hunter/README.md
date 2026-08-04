# resume-kit-job-hunter-bridge

A **pure library** bridge (Phase 5, REQ-506) that the `job-hunter` tool imports
to reach resume-kit's capabilities. It is **not** a server and has **no**
transport: it exposes a small, stable set of typed Python callables that
delegate to the resume-kit **capability facade** and return canonical
`resume_kit_core.InterfaceResponse` payloads carrying `resume_kit_schemas`
data (never a bridge-local DTO).

## Guarantees

- **No job-hunter state mutation.** The bridge never reads or writes job-hunter
  application state, storage, queues, HTTP clients, CLIs, MCP, FastAPI, or
  Typer. It imports only `resume_kit_facade`, `resume_kit_core`,
  `resume_kit_schemas`, and the standard library.
- **No input mutation.** Callables never modify the `ResumeDocument`,
  `JobDescription`, or `CandidateEvidence` values passed in. Facade request
  models are frozen and the engines treat schema values as read-only, returning
  new result objects.
- **Canonical responses.** Every callable returns an `InterfaceResponse` with
  its `data`, `warnings`, `errors`, `questions`, `artifacts`, and `provenance`
  fields preserved as the facade produced them.
- **Stable provider policy.** The only LLM-requiring callable is
  `align_resume_for_job`. Called without a provider (and without `no_llm`) it
  returns the standard `PROVIDER_NOT_CONFIGURED` structured error — identical to
  every other resume-kit surface.

## Callables

All async callables accept an optional
`resume_kit_facade.models.CapabilityOptions` (`no_llm`, `strict`,
`human_in_loop`, `provider`). Each has a `*_sync` convenience wrapper that runs
the coroutine via `asyncio.run`.

### `analyze_resume_for_job(resume, job, *, master=None, options=None) -> ResumeJobAnalysis`

Runs the three deterministic analysis capabilities and returns a
`ResumeJobAnalysis` bundling their canonical responses:

- `.ats` — `check-resume-ats` (`ATSScore`)
- `.job_match` — `check-resume-job-match` (`JobMatchReport`)
- `.gaps` — `identify-resume-gaps` (`KeywordGapAnalysis`)

`master` supplies the gap-analysis baseline and defaults to `resume`.

### `align_resume_for_job(resume, job, *, evidence=None, options=None) -> InterfaceResponse`

Delegates to `align-resume`. Requires a provider (or `no_llm=True`); otherwise
returns the provider-not-configured error.

### `validate_truth(resume, evidence=None, *, options=None) -> InterfaceResponse`

Delegates to `validate-resume-truth` (deterministic). Data is a `TruthReport`.

### `build_evidence(resume, *, approved_claims=None, options=None) -> InterfaceResponse`

Delegates to `build-candidate-evidence` (deterministic). Data is a
`list[CandidateEvidence]`.

## Example

```python
import asyncio
from resume_kit_job_hunter_bridge import analyze_resume_for_job
from resume_kit_schemas import JobDescription, ResumeDocument

async def main() -> None:
    analysis = await analyze_resume_for_job(ResumeDocument(), JobDescription())
    print(analysis.ats.ok, analysis.job_match.ok, analysis.gaps.ok)

asyncio.run(main())
```
