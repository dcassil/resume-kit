# resume-kit-facade

The single in-process **capability facade** for Resume Kit Phase 5. Every
transport (CLI, MCP, API, bridge) calls the capabilities in this package instead
of touching engine functions directly, so all surfaces stay in parity and every
result flows through the `resume_kit_core` interface substrate as an
`InterfaceResponse`.

Import package: `resume_kit_facade`.

## Why a separate package

`resume_kit_core` sits *below* the engine packages (document-parser, job-parser,
ats, matching, alignment, evidence) in the dependency graph. A facade that wraps
those engines must sit *above* them, so it cannot live in core without creating
a cycle. This dedicated package depends inward on core, schemas, and the engine
packages only — never on a transport dependency (Typer, MCP SDK, FastAPI,
uvicorn, httpx) and never on a concrete LLM provider.

## Capabilities

Each capability is an `async` callable `(request, options) -> InterfaceResponse`.
They are also registered in `capabilities.REGISTRY` (name → callable) so
transports can enumerate and dispatch uniformly.

| Capability | Engine API wrapped | LLM? |
|---|---|---|
| `extract-resume` | `parse_resume_structured` / `extract_resume_text_only` | yes / no_llm |
| `extract-job-description` | `parse_job_description` / `parse_job_description_text_only` | yes / no_llm |
| `check-resume-ats` | `analyze_keyword_gaps` + `compute_ats_score` | no |
| `check-resume-job-match` | `check_job_match` | no |
| `select-best-resume` | `select_best` | no |
| `compare-resume-versions` | `compare_versions` | no |
| `identify-resume-gaps` | `analyze_keyword_gaps` | no |
| `align-resume` | `align_resume` (async) | yes / no_llm no-change |
| `validate-resume-truth` | `validate_resume_truth` | no |
| `build-candidate-evidence` | `build_candidate_evidence` | no |

## Options

`CapabilityOptions` carries the shared execution flags:

- `no_llm` — force the deterministic, provider-free path.
- `strict` — escalate advisory warnings to failures.
- `human_in_loop` — request human-in-the-loop behaviour (`align-resume`).
- `provider` — an already-constructed `StructuredCompletionProvider`, or `None`.
  Provider construction stays out of the facade; callers inject it.

LLM-requiring capabilities invoked with `provider=None` (and `no_llm` False)
return the stable provider-not-configured failure instead of calling the engine
or crashing.
