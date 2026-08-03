# ADR-0001: Implementation language is Python; distribution targets PyPI (not npm)

- Status: Accepted
- Date: 2026-08-03
- Decision maker: Daniel Cassil (via orchestration directive)

## Context

The Resume Intelligence Toolkit vision (RIT-V-0001) mandates building the product by
selectively porting proven behavior from the Resume-Matcher donor codebase, rather than
rewriting resume-analysis capabilities from scratch. Phase 0's entire purpose is a safe,
test-protected extraction of that upstream behavior.

The donor codebase's backend is **Python**, and every concrete technical reference in the
vision is Python-specific:

- Pydantic v2 resume/job schemas
- MarkItDown PDF/DOCX text extraction
- LiteLLM local + hosted provider integration
- `Protocol`-based dependency inversion (`StructuredCompletionProvider`, `async def complete_json`)
- Python service/transport/integration test layers to be ported as characterization tests

The orchestration directive also asked to "publish to npm if it is a good fit."

## Decision

1. Implement the toolkit in **Python 3.12+**, using a `uv` workspace with `packages/*` members,
   `ruff` for lint/format, `mypy --strict` for types, and `pytest` for tests.
2. Distribute via **PyPI**, not npm. npm is not a good fit: the entire reusable surface is a
   Python library, MCP server, and CLI. A JS/TS rewrite would discard the safe-reuse strategy
   that is the vision's core engineering principle.

## Alternatives considered

- **TypeScript/npm rewrite.** Rejected: would require rewriting every extractable subsystem
  (parsing, diff engine, allowed-path gates, scoring) from scratch, directly contradicting the
  "donor codebase, not rewrite" principle and multiplying Phase 0 risk. npm publishability does
  not justify abandoning the proven upstream.
- **Polyglot (Python core + thin TS CLI/MCP).** Rejected for the first release: adds
  cross-language packaging, IPC, and test complexity with no user benefit while the core is
  still being extracted. Can be revisited if a JS-native consumer emerges.

## Consequences

Positive:
- Direct, test-protected reuse of Resume-Matcher subsystems; Phase 0 stays tractable.
- Single-language toolchain; one dependency graph; simpler CI.
- `job-hunter` (the primary consumer) can integrate via MCP/CLI regardless of its own language.

Negative:
- No npm artifact. JS-ecosystem consumers integrate over MCP/CLI/REST rather than a native
  package. Documented in README under "Language & distribution."
- Contributors need a Python toolchain (`uv`).

## Follow-up

- Configure PyPI publishing (trusted publisher / token) when the first `packages/*` distribution
  is release-ready. Tracked as a task under the interfaces/packaging initiative.
