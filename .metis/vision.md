---
id: resume-kit
level: vision
title: "Resume Intelligence Toolkit Product Vision"
short_code: "RIT-V-0001"
created_at: 2026-08-03T21:11:07.335788+00:00
updated_at: 2026-08-03T21:11:07.335788+00:00
archived: false

tags:
  - "#vision"
  - "#phase/draft"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Resume Intelligence Toolkit Vision

## Purpose **[REQUIRED]**

Resume Intelligence Toolkit exists to provide a reusable, trustworthy system for evaluating, comparing, aligning, generating, and validating resume materials against specific jobs. The project should help users and calling systems answer five core questions:

- Can an ATS reliably parse this resume?
- How closely does this resume match a specific job?
- Which relevant qualifications are missing or poorly represented?
- What truthful changes would improve alignment?
- Did the revised resume actually improve?

The toolkit should serve both as a standalone local resume analysis product and as the lower-level resume intelligence capability for the `job-hunter` plugin.

## Product/Solution Overview **[CONDITIONAL: Product/Solution Vision]**

Resume Intelligence Toolkit is a standalone agent plugin, MCP server, CLI, API, and shared engine for evaluating, matching, aligning, validating, and generating resume and application materials. It provides deterministic parsing, ATS checks, keyword and qualification matching, semantic analysis, controlled resume modification, human-in-the-loop editing, truth validation, score explanations, provenance, and artifact export.

The product should not be built as a ground-up rewrite of every resume-analysis capability, and it should not become a permanent fork of Resume Matcher. Development will begin with a subsystem-level audit of `https://github.com/srbhr/Resume-Matcher`, an Apache 2.0 licensed donor codebase and upstream reference implementation. Useful code should be selectively ported into a clean modular architecture. Existing algorithms and services should be reused when solid, adapted when close to our needs, and replaced only when they are too coupled, unsafe, low quality, or harder to maintain than rebuilding.

The engineering principle is: use Resume Matcher as a donor codebase, not as the permanent architecture of the new product.

The primary audience is an individual job seeker using `job-hunter` or standalone tooling. Secondary audiences include agent plugins, coding agents, desktop agents, hosted applications, automation systems, and future products that need structured resume analysis without duplicating resume-specific logic.

The product should be built as a resume intelligence and controlled-transformation system, not as an unconstrained LLM rewriting tool. Its value comes from canonical models, deterministic analysis, explainable scoring, structured evidence, configurable editorial freedom, verified diffs, claim provenance, truth validation, human approval, optional LLM reasoning, and reusable programmatic interfaces. Resume Matcher accelerates implementation; it does not define the final product architecture.

## Current State **[REQUIRED]**

The project is at product-definition stage. The desired behavior, interfaces, data models, safety boundaries, scoring dimensions, CLI surface, API shape, MCP tool names, plugin structure, package architecture, privacy posture, MVP phases, and success criteria have been specified, but the toolkit itself is not yet implemented.

Resume analysis and tailoring workflows currently risk being scattered across agent prompts, manual review, ad hoc scripts, and future `job-hunter` orchestration. Without a dedicated toolkit, resume parsing, scoring, evidence validation, claim safety, and artifact generation would be duplicated and less reliable.

Resume Matcher provides a meaningful upstream reference with useful backend work, especially its newer diff-based resume improvement pipeline. The project should avoid rebuilding proven resume matching and tailoring behavior from scratch, but also avoid inheriting Resume Matcher's web application architecture, frontend, persistence model, application tracker, migrations, configuration system, and unrelated product scope.

## Future State **[REQUIRED]**

Resume Intelligence Toolkit becomes the canonical resume analysis and transformation layer for local and agent-driven job search workflows. Users can parse resumes, check ATS compatibility, compare variants, evaluate job fit, identify gaps, produce controlled revisions, validate truthfulness, and export revised artifacts through the same underlying models and policies.

`job-hunter` consumes the toolkit through MCP tools, CLI commands, library calls, or API calls while remaining responsible for job discovery, job records, application state, submission flow, and user handoffs. The toolkit never modifies `job-hunter` state directly; it returns structured results, reports, questions, provenance, and generated artifact references to the caller.

The system supports deterministic no-LLM operation where practical for extraction, ATS checks, keyword matching, scoring inputs, diffs, validation, and reporting. LLM usage is optional and limited to semantic interpretation, structured parsing where needed, rewriting, explanations, prioritization, and interactive user workflows under strict factual constraints.

The final runtime and package graph should contain only the code and dependencies the new toolkit actually requires. Resume Matcher may be cloned beside the new repository, added as a development-only remote, temporarily added as a subtree during extraction, or referenced by pinned commit SHA in a reuse inventory, but it should not be distributed as the product architecture.

## Major Features **[CONDITIONAL: Product Vision]**

- Canonical data models for `ResumeDocument`, `JobDescription`, `CandidateEvidence`, `AnalysisReport`, `ChangeProposal`, diffs, provenance, warnings, artifacts, and interface responses shared across plugin, MCP, CLI, API, and packages.
- Deterministic resume and job parsing for PDF, DOCX, Markdown, plain text, JSON resume schema, internal resume models, raw job descriptions, normalized job records, and structured job requirements.
- ATS compatibility checks covering text extraction, reading order, section recognition, contact detection, dates, tables, columns, headers, footers, text boxes, images, glyph extraction, hyperlinks, metadata, hidden text, Unicode risks, formatting, keyword placement, and skills readability.
- Job-match analysis with explainable scoring for required qualifications, preferred qualifications, responsibilities, seniority, leadership, architecture, product ownership, domain, scale, stack, education, certifications, experience, keyword coverage, evidence strength, recency, and placement prominence.
- Controlled resume alignment with freedom levels 0 through 10, preserving factual boundaries while allowing progressively broader editorial changes when supported by evidence.
- Human-in-the-loop workflows that review changes section by section, show current and proposed content, explain changes, list evidence, estimate score impact, and require approval, rejection, edit, retry, freedom adjustment, or skip decisions before continuing.
- Truth validation and claim provenance that classify claims as verified, supported, partially supported, user-confirmed, ambiguous, unsupported, or contradicted. `align-resume` may not emit unsupported claims.
- Resume comparison, best-variant selection, gap identification, consistency checks, bullet scoring, section improvement, job-specific resume orchestration, cover-letter analysis, cover-letter alignment, candidate evidence building, approved-claim storage, unsupported-claim detection, and application-package auditing.
- MCP tools with structured JSON input/output, stable error codes, warnings separate from errors, `requiresHumanInput`, questions, artifacts, and provenance.
- CLI command suite under `resume-tool` with JSON, text, and Markdown output; no-LLM mode; strict mode; human-in-loop and non-interactive modes; evidence/config inputs; and automation-friendly exit codes.
- REST API endpoints for resume extraction, job extraction, ATS checks, match checks, selection, gap analysis, alignment, validation, consistency, comparison, job-specific creation, cover-letter workflows, asynchronous jobs, and application-package audits.
- Package architecture separating core contracts, schemas, document parsing, job parsing, matching, alignment, evidence, policy, ATS analysis, LLM adapters, export, CLI, MCP, API, plugin skills, and `job-hunter` integration.

## Core Skill and Interface Surface

The toolkit should preserve the intended skill and tool surface while implementing each capability as a thin adapter over the shared core engine:

- `extract-resume`
- `extract-job-description`
- `check-resume-ats`
- `check-resume-job-match`
- `align-resume`
- `validate-facts`
- `check-resume-consistency`
- `compare-versions`
- `select-resume`
- `check-gaps`
- `score-resume-bullet`
- `improve-resume-section`
- `create-job-specific-resume`
- `check-cover-letter-job-match`
- `align-cover-letter`
- `extract-evidence`
- `audit-application-package`

MCP tools should use stable names such as `resume_extract`, `job_description_extract`, `resume_check_ats`, `resume_check_job_match`, `resume_select_best`, `resume_identify_gaps`, `resume_align`, `resume_validate_truth`, `resume_check_consistency`, `resume_compare_versions`, `resume_score_bullet`, `resume_improve_section`, `resume_create_for_job`, `cover_letter_check_job_match`, `cover_letter_align`, `application_package_audit`, and `candidate_evidence_build`.

The CLI should expose equivalent commands through `resume-tool`, including `extract`, `check-ats`, `match`, `select`, `align`, `validate-truth`, `compare`, and `create-for-job`. API endpoints should expose equivalent REST operations as thin adapters. No business rule should exist only inside a CLI command, MCP handler, agent skill, or API route.

## Freedom Model and Human Review

The `freedom` scale remains central to controlled alignment:

- Freedom 0: skills-only correction, normalization, and verified skill insertion.
- Freedom 1: skills and ordering changes without sentence rewriting.
- Freedom 2: terminology and acronym alignment where meaning is identical.
- Freedom 3: light phrase editing for clarity without changing scope.
- Freedom 4: bullet-level rewriting while preserving all facts.
- Freedom 5: section-level optimization using known evidence.
- Freedom 6: summary and positioning changes.
- Freedom 7: cross-section restructuring and job-specific grouping.
- Freedom 8: full resume reconstruction from candidate evidence.
- Freedom 9: aggressive evidence-backed alignment from approved projects and experience.
- Freedom 10: maximum truthful alignment within factual constraints.

Freedom 10 means maximum editorial freedom, not freedom from factual constraints. The system must never fabricate employers, titles, dates, responsibilities, accomplishments, metrics, certifications, education, security clearances, technical experience, management experience, or industry experience.

When `humanInLoop: true`, alignment must proceed section by section. For each section, the system shows current content, proposed content, change explanation, evidence for meaningful claims, expected score impact, and asks the user to approve, reject, edit, request another version, reduce freedom, increase freedom, or skip. It must not continue until the current section is resolved.

When `humanInLoop: false`, the system may produce a complete proposal in one pass, but it must still return a full diff, claim provenance, warnings, unresolved questions, before/after match score, ATS report, and final truth-validation report. It must not silently add uncertain claims.

## Resume Matcher Audit Findings

Phase 0 must confirm these findings against a pinned upstream commit. Until then, all reuse claims in this document are preliminary.

Strong and reusable areas include:

- PDF and DOCX text extraction through MarkItDown.
- Structured resume schemas using Pydantic.
- LLM-based resume-to-JSON parsing.
- Date-restoration logic when an LLM drops month information.
- Job-keyword extraction.
- Resume-tailoring prompts.
- A diff-based modification model.
- Whitelisted paths that an LLM is allowed to edit.
- Blocked fields such as names, employers, titles, dates, institutions, and locations.
- Verification that the original value in a proposed change matches the actual resume.
- Skill-addition gates.
- Rejection of malformed or unsupported changes.
- Preservation of omitted original content.
- LiteLLM support for local and hosted providers.
- Structural resume evaluators.
- Unit, service, integration, transport, database, and PDF-rendering tests.

Areas that should not define the new architecture include:

- Web frontend.
- Application tracker and Kanban system.
- Job and resume persistence.
- SQLite database facade.
- TinyDB migration compatibility.
- API-key persistence and settings UI.
- Frontend-specific PDF rendering.
- Web application routing.
- Application management.
- Interview-preparation UI.
- Full local application deployment.
- Existing navigation and state management.

Architectural concerns to address during extraction:

- Useful backend code imports heavily from the application-level `app` package.
- The resume improver contains several responsibilities in one large service.
- Parsing structured resume data currently requires an LLM after deterministic text extraction.
- Some orchestration and business logic remains inside large API router or service files.
- The existing persistence and configuration architecture is designed for its web application, not for an MCP/CLI library.
- The codebase has been significantly hardened recently, but upstream documentation acknowledges earlier gaps in automated testing and integration coverage.

Resume Matcher is useful and generally respectable, but it requires selective extraction, dependency inversion, test protection, modularization, and attribution.

## Reuse Classification Plan

Every relevant Resume Matcher subsystem must receive one of these classifications:

- Reuse: use mostly unchanged.
- Extract: move existing behavior into an independent package with minimal behavioral changes.
- Adapt: preserve the underlying implementation but change its API, boundaries, or behavior.
- Replace: existing implementation is unsuitable and should not be carried forward.
- New: no meaningful equivalent exists in Resume Matcher.

Implementation must follow this order:

1. Locate equivalent behavior in Resume Matcher.
2. Review the code and tests.
3. Classify it as Reuse, Extract, Adapt, Replace, or New.
4. Port existing tests when behavior is reused.
5. Add characterization tests before changing behavior.
6. Extract dependencies behind interfaces.
7. Modify behavior only after the extracted version is protected by tests.
8. Record original file, upstream commit, license, and modifications for attribution.

Preliminary Reuse or Extract candidates:

- Resume schemas and related Pydantic models.
- MarkItDown PDF/DOCX extraction.
- Date-restoration helpers.
- Diff path parsing and resolution.
- Allowed-path and blocked-path gates.
- Original-value verification.
- Verified skill-addition logic.
- Diff application and rejection reporting.
- Structural resume evaluators.
- Relevant deterministic test fixtures.
- JSON extraction and retry helpers, after isolation.

Preliminary Adapt candidates:

- LiteLLM provider integration.
- LLM configuration.
- Resume-to-JSON parsing.
- Job-keyword extraction.
- Resume improvement prompts.
- Truthfulness prompts.
- Skill-target planning.
- Resume diff generation.
- Diff verification.
- Match scoring.
- Cover-letter generation.
- PDF/DOCX export.
- Before-and-after comparison.

Preliminary Replace or Leave Behind candidates:

- Application tracker.
- Kanban functionality.
- Existing SQLite persistence.
- TinyDB migration logic.
- Existing API routers.
- Existing web frontend.
- Existing navigation and application state.
- API-key persistence.
- Web-specific configuration system.
- Application-specific job storage.
- Full Resume Matcher deployment model.

Preliminary New areas:

- Agent plugin package.
- MCP server.
- Purpose-built CLI.
- Stable public API contracts.
- `freedom: 0-10` alignment policy.
- Human-in-the-loop review controller.
- Candidate evidence model.
- Claim provenance system.
- Approved-claim bank.
- Truth-validation engine.
- Multiple resume selection.
- `job-hunter` bridge.
- Deterministic ATS-analysis engine.
- Standalone non-LLM analysis mode.

## Architecture and Engine Boundary

The central product should be a reusable engine, not four separate implementations:

```text
Agent skills --\
MCP server ------> Resume Intelligence Core
CLI ------------/
API -----------/
```

The core owns:

- Canonical resume and job models.
- Parsing contracts.
- ATS analysis.
- Matching.
- Scoring.
- Alignment policies.
- Freedom-level enforcement.
- Evidence validation.
- Claim provenance.
- Diffs.
- Truth validation.
- Export contracts.

The interfaces only adapt input/output and orchestrate user interaction. Core matching and alignment services must receive dependencies explicitly so the same service is callable from agent plugin, MCP tool, CLI command, API endpoint, tests, local LLM provider, and hosted LLM provider.

Extracted behavior must be removed from application globals and hidden runtime state. Existing code that directly imports application-level helpers, such as `from app.llm import complete_json`, should be adapted behind interfaces such as:

```python
class StructuredCompletionProvider(Protocol):
    async def complete_json(
        self,
        request: StructuredCompletionRequest,
    ) -> dict[str, Any]:
        ...
```

No business rule should exist only inside a route, handler, command, prompt wrapper, or skill file.

## Repository Strategy

The actual product should live in a clean new repository. Resume Matcher may be cloned separately during development as an upstream reference or donor source, but the upstream repository should not be part of the distributed product.

Recommended product structure:

```text
resume-intelligence/
├── packages/
│   ├── core/
│   ├── schemas/
│   ├── document-parser/
│   ├── job-parser/
│   ├── matching/
│   ├── alignment/
│   ├── evidence/
│   ├── policy/
│   ├── ats/
│   ├── llm/
│   ├── export/
│   ├── cli/
│   ├── mcp/
│   └── api/
├── plugins/
│   └── resume-intelligence/
├── integrations/
│   └── job-hunter/
├── references/
│   ├── upstream-audit.md
│   ├── reuse-inventory.md
│   ├── attribution.md
│   └── architectural-decisions/
└── tests/
    ├── fixtures/
    ├── characterization/
    ├── unit/
    ├── integration/
    └── evals/
```

Resume Matcher may be cloned beside the new repository, added as a development-only Git remote, added temporarily as a subtree during extraction, or referenced by commit SHA in `references/reuse-inventory.md`. The final runtime and package graph should contain only code and dependencies the toolkit actually requires.

## Business Requirements Overview **[CONDITIONAL: Business Vision]**

- Provide a reusable resume intelligence capability that can power `job-hunter` without coupling to its job-search state or application workflow.
- Preserve user trust by never fabricating claims, never overwriting originals by default, explaining every score, and requiring human authority over truth and final use.
- Support local-first operation, deterministic no-LLM workflows where practical, and explicit privacy boundaries so sensitive resume and job content is not retained, logged, or sent to providers unnecessarily.
- Reuse proven open-source behavior from Resume Matcher when it can be extracted safely, legally, and maintainably.
- Avoid importing unrelated application concerns from Resume Matcher into the new product.
- Make the same core capability available through agent skills, MCP tools, CLI commands, REST API endpoints, and library/package integration.
- Enable incremental delivery through upstream audit, clean core, parsing, matching, controlled alignment, interfaces, export, and package workflows.

## Implementation Roadmap

Phase 0 - Upstream audit:

- Clone Resume Matcher at a pinned commit.
- Run its backend tests.
- Review licenses and attribution requirements.
- Inventory relevant files, dependencies, prompts, schemas, and tests.
- Build the Reuse/Extract/Adapt/Replace/New matrix.
- Identify which modules can operate without the existing database or frontend.
- Record known quality risks and extraction blockers.

Phase 1 - Clean core and schemas:

- Create the clean repository.
- Define canonical resume, job, evidence, analysis, and diff models.
- Port or adapt Resume Matcher schemas.
- Add characterization tests for all ported behavior.
- Create provider and storage interfaces.
- Do not implement a frontend or persistence layer.

Phase 2 - Document extraction and parsing:

- Port deterministic PDF/DOCX-to-text extraction.
- Port date-restoration logic.
- Adapt LLM-based structured parsing behind a provider interface.
- Add parsing confidence, warnings, and provenance.
- Support no-LLM text extraction even when structured parsing is unavailable.

Phase 3 - Matching and deterministic analysis:

- Port or adapt keyword extraction and matching behavior.
- Audit the existing scoring implementation before adopting it.
- Add deterministic ATS checks.
- Add explainable scoring dimensions.
- Implement `check-resume-ats`.
- Implement `check-resume-job-match`.
- Implement `select-resume`.
- Implement `compare-versions`.

Phase 4 - Controlled alignment:

- Extract the diff application and verification engine.
- Generalize the allowed-path policy.
- Implement `freedom: 0-10`.
- Implement verified skill targets.
- Add candidate evidence and claim provenance.
- Implement human-in-the-loop review.
- Implement `validate-facts`.
- Ensure the LLM never directly writes the final document without passing through policy and verification gates.

Phase 5 - Interfaces:

- Add CLI.
- Add MCP server.
- Add agent plugin skills.
- Add API endpoints as thin adapters over the same core.
- Add the `job-hunter` integration.

Phase 6 - Export and package workflows:

- Adapt only the required PDF/DOCX export code.
- Do not require the Resume Matcher frontend to render a resume.
- Implement complete application-package auditing.
- Add cover-letter matching and controlled alignment.

## Testing Strategy

The project should preserve and strengthen useful testing ideas from Resume Matcher.

For every ported subsystem:

- Port relevant existing tests.
- Add characterization tests before refactoring.
- Prove important tests fail when behavior is intentionally broken.
- Keep deterministic tests separate from LLM-quality evals.
- Mock at the LLM transport boundary for normal tests.
- Use optional real-model evals for prompt and semantic quality.
- Maintain golden fixtures for resume/job pairs.
- Add explicit tests for fabrication, dropped sections, changed dates, changed employers, invented metrics, unverified skills, and invalid diff paths.

Required test layers:

- Pure unit tests.
- Service tests with mocked providers.
- Integration tests through the core.
- CLI contract tests.
- MCP contract tests.
- API contract tests.
- Optional LLM evals.
- Export smoke tests.

## Licensing and Attribution

Resume Matcher is Apache 2.0 licensed. Any reused code, tests, prompts, schemas, or derived implementation must comply with Apache 2.0 requirements.

The project must:

- Retain applicable copyright and attribution notices.
- Include the Apache 2.0 license when required.
- Mark modified source files appropriately.
- Maintain an attribution and provenance inventory.
- Avoid use of upstream trademarks as the new product identity.
- Record the upstream commit SHA for every ported subsystem.

The new product may have its own branding and additional licensing terms, subject to Apache 2.0 requirements for reused code.

## Success Criteria **[REQUIRED]**

The MVP is successful when it can:

- Complete the Phase 0 upstream audit and produce a confirmed reuse inventory with commit SHAs, classifications, dependencies, tests, and attribution notes.
- Parse the user's current resume variants with no meaningful content loss.
- Detect common ATS formatting risks and explain remediation steps.
- Compare multiple resumes against a job description.
- Explain why one resume variant is the strongest match.
- Identify missing and underrepresented qualifications.
- Generate a revised resume at a selected freedom level.
- Avoid unsupported claims during alignment and validation.
- Show every material change through structured diff and provenance.
- Produce measurable before/after score differences.
- Allow `job-hunter` to consume the result without duplicating resume-analysis logic.
- Reuse, extract, or adapt valuable Resume Matcher behavior without inheriting its web application architecture, persistence model, application tracker, frontend, or deployment model.

Longer-term success means the toolkit can support hosted API usage, asynchronous alignment jobs, broader schema support, optional web UI, team or multi-user usage, configurable retention, and usage controls without weakening the local-first privacy and truth-safety model.

## Principles **[REQUIRED]**

- Use Resume Matcher as a donor codebase and upstream reference, not as the permanent architecture.
- Never fabricate employers, titles, dates, responsibilities, accomplishments, metrics, certifications, education, clearances, technical experience, management experience, or industry experience.
- Distinguish wording changes from substantive claims, and require evidence or user confirmation before broadening or adding claims.
- Prefer deterministic parsing, extraction, checks, diffs, validation, and scoring inputs before LLM reasoning.
- Explain every score with dimensions, weights, evidence, missing evidence, confidence, and actionable recommendations.
- Preserve original resumes by default and produce new versions, structured diffs, provenance records, validation reports, and optional exports.
- Keep the user as the final authority over claim truth, voice, recommendations, saving, and use.
- Make LLM usage optional, explicit, constrained, and replaceable by hosted, local, or no-LLM modes.
- Keep agent skills thin; put shared contracts, scoring rules, safety policies, schemas, and executable logic in reusable packages and references.
- Keep `job-hunter` orchestration separate from resume intelligence responsibilities.
- Apply dependency inversion to all extracted behavior so core services receive dependencies explicitly.
- Preserve behavior with tests before changing ported code.

## Constraints and Technical Risks **[REQUIRED]**

- The initial product will not guarantee ATS outcomes or reproduce proprietary vendor scores.
- The toolkit will not automatically submit applications, scrape job boards directly, store job-search state, rank candidates for employers, make hiring decisions, replace human review, or become a general resume-design application in the first release.
- Generated claims must be traceable to the source resume, validated user profile, approved experience bank, or direct user answer in the current workflow.
- Remote LLM calls must be opt-in for operations that require them, disclose the provider receiving content, avoid unnecessary contact information exposure, and support local-model-only and deterministic no-LLM modes.
- Hosted API mode must support encryption in transit and at rest, short retention, immediate deletion, tenant separation, access/generation records, zero-retention model providers where configurable, and no customer-data training.
- `align-resume` at freedom 3 or higher must automatically run truth validation.
- `humanInLoop: true` workflows must resolve each section before moving to the next.
- Generated artifacts must be explicit outputs and must not overwrite original resumes by default.
- Scoring must not reward keyword repetition alone; full credit requires presence, meaningful support, appropriate placement, and aligned scope.
- Preliminary reuse assumptions may be invalidated by Phase 0 code review, license review, dependency analysis, or test results.
- Useful Resume Matcher code may be more coupled to application-level `app` modules, persistence, configuration, routing, or frontend assumptions than expected.
- LLM-based structured parsing may limit no-LLM functionality until deterministic structured extraction is improved.
- Ported prompts, scoring logic, and diff behavior may require characterization tests before they can be safely modified.
- Export behavior must not depend on the Resume Matcher frontend or web-specific rendering path unless that dependency is explicitly replaced or isolated.