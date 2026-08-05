# resume-intelligence Plugin

Agent skills for the resume-kit Phase 5 interface surface.

## Install

In Claude Code:

```
/plugin marketplace add dcassil/resume-kit
/plugin install resume-intelligence@resume-kit
```

**Prerequisite** — the skills and the bundled MCP server (`resume-kit-mcp`) call
the `resume-kit` package, so install it too so those commands exist on PATH:

```
uv tool install "resume-kit[all]"      # or: pip install "resume-kit[all]"
```

Without it the skill *docs* still load, but the `resume-tool` CLI and the
`resume-kit` MCP tools won't launch.

## Turning documents into JSON (agent-driven, no LLM provider)

The analysis/alignment capabilities operate on canonical JSON, not raw files.
Two conversion skills let the agent produce that JSON directly (best run as
**subagents** — they are confined, high-token tasks):

- **`resume-to-json`** — a PDF/DOCX/MD/text resume → faithful `ResumeDocument`
  JSON, under strict no-alteration gates. Saved to
  `resume-kit/resumes/<name>-original.json`.
- **`job-to-json`** — a job posting → structured `JobDescription` JSON with
  `requirements` + `keywords`, so deterministic **skills-coverage** scoring works
  without an LLM provider. Saved to `resume-kit/jobs/<name>-original.json`.

### Working directory convention

All state lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json                          # active_resume / active_job / alias_file pointers + preferences
├── resumes/<name>-original.json         # immutable faithful resume conversions
├── jobs/<name>-original.json            # immutable job conversions
├── working/edit-session.json            # code-owned active edit-session state
├── working/<name>.tailored.json         # commit-session output for a tailored resume
├── learning/synonyms.json               # grown project alias index (default alias_file target)
└── learning/<skill>.md                  # accumulated hints; skills read these first, append new ones
```

`-original.json` files are the untouched conversions (the name maps back to the
source file). To modify a resume, propose `ChangeProposal` records and run the
`resume-tool review-edits` session loop; `commit-session` writes the tailored copy under
`working/`. Direct hand-editing of the working resume is unsupported unless the
session is reconciled with `resume-tool review-edits reconcile`.

#### `config.json` `alias_file` pointer

Alongside `active_resume` and `active_job`, `config.json` may carry an optional
`alias_file` key pointing at a project alias JSON (the RIT-T-0068 format
`{"version": 1, "aliases": {canonical: [alias, ...]}}`). It defaults to
`learning/synonyms.json` and is resolved against the `resume-kit/` working dir
(not the shell CWD), matching the `active_resume`/`active_job` convention.

This is purely a plugin/agent convention: **no Python package opens
`config.json`.** The skill reads the pointer and passes the resolved path to the
keyword-scoring surfaces through their `alias_file` parameter — `resume-tool
match --alias-file <path>` / `identify-gaps --alias-file <path>` on the CLI, an
`alias_file` field on the `resume_check_job_match` / `resume_identify_gaps` MCP
tools, and an `alias_file` body field on the corresponding API routes. (Keyword
matching uses the alias index; `check-ats-structure` is structure-only and takes
no alias file.) When the pointer is absent the surfaces run seed-only, identical
to prior behaviour.

These skills describe how an agent drives the `resume-tool` CLI or the MCP
server. Each skill does ONE thing and self-gates on its prerequisites (it stops
and names the upstream skill to run first when a required input — a resume/job
JSON — is missing, rather than producing empty output). Start with the
`resume-workflow` guide, which sequences the skills. Skills are thin invocation
guides — they do not implement resume intelligence logic and must not invent
facts, bypass evidence, or create business rules in prompt text.

## Workflow (start here)

`resume-workflow` is the entry-point guide; it runs the skills in order:

1. **Ingest** — `resume-to-json`, `job-to-json` (no LLM; the agent converts the
   files/posting into canonical JSON).
2. **Check** — `check-ats-structure` (structural/parse issues, resume-only),
   `check-keyword-match` (resume↔job keyword coverage), `identify-resume-gaps`
   (missing / injectable keywords).
3. **Improve** (no LLM, truth-gated) — `inject-keywords` and
   `update-terminology` produce truthful `ChangeProposal` records, prompt for
   mode (`interactive`, `review_at_end`, or `auto`), then drive
   `resume-tool review-edits open` → `resume-tool review-edits prompt` →
   `resume-tool review-edits decide` → `resume-tool review-edits commit` →
   `validate-resume-truth`. When several truthful candidates exist,
   `rank-edits` calls `resume-tool rank-edit-candidates` first; after a
   decision, `log-edit-feedback` calls `resume-tool record-edit-feedback` and
   refreshes preferences.
4. **Verify** — `validate-resume-truth`; then re-run the checks to see the delta.
5. **Review** (optional, no LLM provider) — `review-tailored-resume` dispatches a
   subagent to critique the tailored resume against the original + job and writes
   parseable, advice-only findings to `resume-kit/review/<session>.md` (it never
   edits the resume; act on findings via `inject-keywords` /
   `update-terminology` / `validate-resume-truth`).
6. **Export** — `export-resume` (PDF/DOCX).

Supporting: `build-candidate-evidence`, `compare-resume-versions`,
`select-best-resume`, and `manage-synonyms` (grows the project alias index used
by keyword matching + terminology).

## Capability Map

| Skill directory | CLI command | MCP tool name | LLM required? |
|---|---|---|---|
| `resume-to-json` | (agent-driven) | — | No (agent converts) |
| `job-to-json` | (agent-driven) | — | No (agent converts) |
| `check-ats-structure` | `resume-tool check-ats-structure` | `resume_check_ats_structure` | No (deterministic) |
| `check-keyword-match` | `resume-tool match` | `resume_check_job_match` | No (deterministic) |
| `identify-resume-gaps` | `resume-tool identify-gaps` | `resume_identify_gaps` | No (deterministic) |
| `inject-keywords` | `resume-tool review-edits open`; `resume-tool review-edits prompt`; `resume-tool review-edits decide`; `resume-tool review-edits commit`; `resume-tool review-edits status`; `resume-tool review-edits reconcile` | `edit_session_open` / `edit_session_prompt` / `edit_session_decide` / `edit_session_commit` / `edit_session_status` / `edit_session_reconcile` | No (deterministic gate) |
| `update-terminology` | `resume-tool suggest-terminology` + `resume-tool review-edits open`; `resume-tool review-edits prompt`; `resume-tool review-edits decide`; `resume-tool review-edits commit`; `resume-tool review-edits status`; `resume-tool review-edits reconcile` | `resume_suggest_terminology` + `edit_session_open` / `edit_session_prompt` / `edit_session_decide` / `edit_session_commit` / `edit_session_status` / `edit_session_reconcile` | No (deterministic gate) |
| `validate-resume-truth` | `resume-tool validate-truth` | `resume_validate_truth` | No (deterministic) |
| `build-candidate-evidence` | `resume-tool build-evidence` | `candidate_evidence_build` | No (deterministic) |
| `compare-resume-versions` | `resume-tool compare` | `resume_compare_versions` | No (deterministic) |
| `select-best-resume` | `resume-tool select` | `resume_select_best` | No (deterministic) |
| `export-resume` | `resume-tool export` | `resume_export` | No (deterministic) |
| `add-evidence` | `resume-tool add-evidence --confirmed` | `candidate_evidence_add` | No (deterministic) |
| `manage-synonyms` | (agent-driven) | — | No (grows alias index) |
| `review-tailored-resume` | (agent-driven, advice-only) | — | No (subagent) |
| `rank-edits` | `resume-tool rank-edit-candidates` | `edit_candidates_rank` | No (deterministic ranking) |
| `log-edit-feedback` | `resume-tool record-edit-feedback` / `resume-tool refresh-preferences` | `edit_feedback_record` / `preferences_refresh` | No (records outcome) |
| `resume-workflow` | (guide) | — | No (orchestration) |

**Disabled / not surfaced as skills:** LLM auto-rewrite (`align-resume`) is
disabled for now — the no-LLM `inject-keywords` + `update-terminology` cover
truthful tailoring. The raw LLM extract tools (`resume_extract`,
`job_description_extract`) remain callable via CLI/MCP but are not surfaced as
skills; prefer the agent-driven `resume-to-json` / `job-to-json`, which need no
provider.

## Architecture Note

Every interface is a thin adapter over `resume_kit_facade`.  No business rule
lives in an interface.  Agents invoke the CLI or MCP tool and act on the
returned `InterfaceResponse` (data / warnings / errors / requiresHumanInput /
questions / provenance).

## Phase 6 Capabilities (NOT built — do not invoke)

`check-resume-consistency`, `score-resume-bullet`, `improve-resume-section`,
`create-job-specific-resume`, `check-cover-letter-job-match`,
`align-cover-letter`, `audit-application-package`.  These names are reserved
but have no engine implementation and no CLI/MCP tool.
