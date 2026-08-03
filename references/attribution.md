# Apache-2.0 Attribution Ledger

> Engineering compliance record for selective reuse of Resume-Matcher code, tests, prompts,
> and schemas. This file is a Phase 0 deliverable. Update it before porting any subsystem.
> Not legal advice.

---

## Upstream Repository Identity

| Field | Value |
|-------|-------|
| Repository URL | https://github.com/srbhr/Resume-Matcher |
| Pinned full commit SHA | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` |
| License | Apache-2.0 |
| Local clone path | `./upstream/` (gitignored) |
| NOTICE file | None present at pinned SHA |
| Audit date | 2026-08-03 |

The upstream LICENSE file is a standard Apache-2.0 text. No NOTICE file is present at the
pinned SHA, so there are no embedded third-party attribution notices to propagate from that
file. If a NOTICE file appears in a future upstream commit, re-audit before updating the pin.

---

## Concrete Engineering Compliance Obligations

These obligations apply whenever resume-kit ports, extracts, or adapts any material from
Resume-Matcher. They are derived directly from the Apache-2.0 license text.

### 1. Retain copyright and attribution notices

Every source file copied from upstream must preserve the original copyright header, if one is
present. Do not strip, reword, or relocate upstream copyright notices when porting code.
If an upstream file has no copyright header, note that in the modification note column of the
provenance table below.

### 2. Include the Apache-2.0 license text

The Apache-2.0 license text must be present in this repository when resume-kit distributes
any covered work (source or binary). The license is already present at `./LICENSE`. Verify
that file is not removed or replaced during repackaging.

### 3. Mark modified files prominently

Any upstream file that is modified — even lightly — must carry a prominent notice that
the file has been changed. Place this notice at the top of the file in a comment block:

```python
# Derived from Resume-Matcher (Apache-2.0)
# Upstream: apps/backend/app/<path>
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: <brief description of changes>
```

Files ported without any modification still need an origin comment, but do not need a
"Modified" line. Files that are substantially rewritten beyond recognition should be
marked as "Adapted from" rather than "Derived from" and should still record the upstream
path and SHA.

### 4. Track upstream path and SHA per ported subsystem

The provenance table below is the canonical record. Every ported file, schema, prompt, or
test must have a row. Update the table before committing any ported material. Future agents
extracting subsystems must add their rows before their extraction PR is merged.

### 5. Avoid using Resume-Matcher trademarks as product identity

Do not use "Resume Matcher", "Resume-Matcher", or the upstream project's branding, logos, or
product names as the identity of resume-kit or any package it ships. Attribution in comments,
this ledger, and documentation is required and permitted. Product naming and promotion must
use resume-kit's own identity.

### 6. No additional restrictions on downstream use

Apache-2.0 does not permit imposing additional restrictions on recipients. If resume-kit adds
its own license, that license must not restrict rights already granted by Apache-2.0 for the
upstream-derived portions.

---

## Provenance Table

> **STATUS: PROVISIONAL** — references/reuse-inventory.md exists but contains no rows at the
> time this ledger was written (2026-08-03). Subsystem names, classifications, and upstream
> paths below are drawn from the vision document (`.metis/vision.md`, "Reuse Classification
> Plan") and corroborated against the upstream directory listing. This table must be reconciled
> with the final reuse-inventory.md classifications during task RIT-T-0004.
>
> Replace/Leave-behind subsystems are listed in a separate section below to confirm they were
> reviewed and intentionally excluded from reuse attribution.

| Subsystem | Classification | Upstream path(s) | Pinned SHA | Material type | Attribution requirement | Modification note | Target package |
|-----------|---------------|-----------------|------------|--------------|------------------------|-------------------|----------------|
| Resume Pydantic schemas | Extract | `apps/backend/app/schemas/models.py`, `apps/backend/app/schemas/enrichment.py`, `apps/backend/app/schemas/refinement.py`, `apps/backend/app/schemas/resume_wizard.py`, `apps/backend/app/schemas/applications.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code/schemas | Retain copyright header; mark modified files; include LICENSE | Will be re-namespaced; application tracker schemas will be excluded | `packages/schemas` |
| LLM prompts and templates | Extract | `apps/backend/app/prompts/templates.py`, `apps/backend/app/prompts/enrichment.py`, `apps/backend/app/prompts/refinement.py`, `apps/backend/app/prompts/resume_wizard.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | prompts/code | Retain copyright header; mark modified files; include LICENSE | Prompts will be reviewed and adapted; original strings are attributed here | `packages/llm` |
| Document parser — text extraction | Extract | `apps/backend/app/services/parser.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | LLM-calling path will be extracted behind a provider interface; pure markitdown path reused largely unchanged | `packages/document-parser` |
| Date-restoration helpers | Extract | `apps/backend/app/services/parser.py` (internal helpers within `parse_resume_to_json`) | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header in containing file; include LICENSE | Will be extracted into standalone helpers; logic preserved | `packages/document-parser` |
| Diff path parsing and resolution | Extract | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Will be extracted from service class into standalone module | `packages/alignment` |
| Allowed-path and blocked-path gates | Extract | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Policy constants will be separated from service logic | `packages/policy` |
| Original-value verification | Extract | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Will be extracted as a pure function; no behavioral change | `packages/alignment` |
| Verified skill-addition logic | Extract | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Skill gate logic extracted; freedom-level integration is new | `packages/policy` |
| Diff application and rejection reporting | Extract | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Core apply/reject logic extracted; reporting interface adapted | `packages/alignment` |
| Structural resume evaluators | Extract | `apps/backend/app/services/ats.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Structural checks extracted; ATS engine will be extended deterministically | `packages/matching` |
| Unit and service test fixtures | Extract | `apps/backend/tests/unit/`, `apps/backend/tests/service/` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | tests | Retain copyright headers in test files; include LICENSE | Fixtures ported without behavioral change; test layout adapted | `packages/schemas`, `packages/document-parser`, `packages/alignment` |
| JSON extraction and retry helpers | Extract | `apps/backend/app/llm.py` (internal helpers) | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Extracted from LiteLLM-coupled wrapper into standalone helpers; provider coupling removed | `packages/llm` |
| LiteLLM provider integration | Adapt | `apps/backend/app/llm.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified file; include LICENSE | Router, retry, and timeout behavior preserved; global app-level config replaced with explicit dependency injection | `packages/llm` |
| LLM configuration | Adapt | `apps/backend/app/config.py`, `apps/backend/app/config_cache.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Config structure adapted; web-app and database settings removed; pydantic-settings interface retained | `packages/llm` |
| Resume-to-JSON parsing | Adapt | `apps/backend/app/services/parser.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code/prompts | Retain copyright header; mark modified file; include LICENSE | LLM provider injected as a protocol; direct `app.llm` import removed | `packages/document-parser` |
| Job-keyword extraction | Adapt | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified file; include LICENSE | Keyword extraction logic adapted into a standalone function with explicit LLM provider; no persistence dependency | `packages/matching` |
| Resume improvement prompts | Adapt | `apps/backend/app/prompts/templates.py`, `apps/backend/app/prompts/refinement.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | prompts | Retain copyright header; mark modified file; include LICENSE | Prompts adapted for freedom-level parameters and truth constraints | `packages/llm` |
| Truthfulness and guardrail prompts | Adapt | `apps/backend/app/prompts/templates.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | prompts | Retain copyright header; mark modified file; include LICENSE | Adapted for claim-provenance and truth-validation workflows | `packages/policy` |
| Skill-target planning | Adapt | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified file; include LICENSE | Adapted to separate planning from execution; freedom level drives gate logic | `packages/alignment` |
| Resume diff generation | Adapt | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified file; include LICENSE | Diff generation adapted behind provider interface; output enriched with provenance fields | `packages/alignment` |
| Diff verification | Adapt | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified file; include LICENSE | Verification logic preserved; adapted to return structured provenance records | `packages/alignment` |
| Match scoring | Adapt | `apps/backend/app/services/ats.py`, `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified files; include LICENSE | Scoring dimensions preserved; explainability fields and weighting model added | `packages/matching` |
| Cover-letter generation | Adapt | `apps/backend/app/services/cover_letter.py`, related prompts | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code/prompts | Retain copyright header; mark modified files; include LICENSE | Generation logic preserved; injected LLM provider; adapted for provenance output | `packages/export` |
| PDF/DOCX export | Adapt | `apps/backend/app/pdf.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified file; include LICENSE | Frontend-and-Playwright dependency replaced; pure Python export path implemented instead | `packages/export` |
| Before-and-after comparison | Adapt | `apps/backend/app/services/improver.py` | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` | code | Retain copyright header; mark modified file; include LICENSE | Comparison logic preserved; adapted to return structured diff with score delta | `packages/matching` |

---

## Intentionally Excluded Subsystems (Replace / Leave Behind)

The following Resume-Matcher subsystems were reviewed during Phase 0 and intentionally
excluded from reuse. No attribution is required for these areas because no upstream material
will be ported.

| Subsystem | Upstream path(s) | Reason for exclusion |
|-----------|-----------------|----------------------|
| Application tracker / Kanban | `apps/backend/app/routers/applications.py`, `apps/backend/app/schemas/applications.py` (tracker portion), `apps/frontend/app/tracker/`, `apps/frontend/components/tracker/` | Product scope not carried forward; resume-kit has no application-tracking responsibility |
| SQLite persistence layer | `apps/backend/app/database.py`, `apps/backend/app/db_engine.py`, `apps/backend/app/models.py` | Architecture replaced; resume-kit does not use a persistent database layer |
| TinyDB migration logic | `apps/backend/app/scripts/` | One-time migration artefact; not relevant to a clean implementation |
| Existing API routers | `apps/backend/app/routers/` | HTTP layer tightly coupled to the web application; replaced by thin adapter pattern over core engine |
| Web frontend | `apps/frontend/` | Entire Next.js application excluded; resume-kit has no frontend |
| API-key persistence and settings UI | `apps/backend/app/crypto.py` (persistence path), `apps/backend/app/routers/` (settings endpoints) | Settings and credential management model not carried forward |
| Web-specific configuration system | `apps/backend/app/config.py` (web-app portions) | Replaced by explicit dependency injection; web-app config fields dropped |
| Application-specific job storage | `apps/backend/app/models.py` (Job, Application models) | resume-kit does not own job records; job-hunter integration handled at boundary |
| Full Resume-Matcher deployment model | `apps/backend/app/main.py`, `apps/frontend/`, Docker config | Not applicable; resume-kit is a library/tool package, not a standalone web application |
| Interview-preparation UI and service | `apps/backend/app/services/interview_prep.py`, related routers | Feature not in resume-kit scope |

---

## Per-File Attribution Comment Template

When porting any upstream file into a package under `packages/`, add the following comment
block at the top of the file (after the module docstring if one exists):

```python
# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/<relative-path>
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: <one-line description of modifications, or "None — ported unchanged">
# ---------------------------------------------------------------------------
```

For adapted files with significant structural changes, use "Adapted from" instead of
"Derived from". For test files, add the comment after the module docstring and before any
imports.

---

## Reconciliation Notes

This table is PROVISIONAL pending completion of task RIT-T-0004. When references/reuse-inventory.md
is fully populated, the implementer of RIT-T-0004 must:

1. Cross-check every Reuse/Extract/Adapt row in reuse-inventory.md against this table.
2. Add any subsystems present in the inventory but missing here.
3. Correct any upstream paths that differ from what was actually ported.
4. Remove the PROVISIONAL notice from this file once reconciliation is complete.
5. Confirm the pinned SHA matches `git -C upstream rev-parse HEAD` at the time of reconciliation.
