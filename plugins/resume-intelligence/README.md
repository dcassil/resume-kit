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

## Skill renames in v1.0.0 (RIT-A-0005)

v1.0.0 renames 14 skills to a uniform `verb-noun` lexicon so behavior class is
inferable from the name (`check-*` = safe read-only report, `validate-*` = a
hard gate, `update-*` = gated mutation, `learn-*` = future-run learning). This is
a **breaking change** (hence the major bump). If you referenced an old skill
name, update it:

| Old skill | New skill |
|-----------|-----------|
| `resume-to-json` | `parse-resume` |
| `job-to-json` | `parse-job` |
| `build-candidate-evidence` | `extract-evidence` |
| `check-ats-structure` | `check-structure` |
| `check-keyword-match` | `check-keywords` |
| `identify-resume-gaps` | `check-gaps` |
| `compare-resume-versions` | `compare-versions` |
| `select-best-resume` | `select-resume` |
| `validate-resume-truth` | `validate-facts` |
| `inject-keywords` | `update-keywords` |
| `rank-edits` | `rank-changes` |
| `review-tailored-resume` | `review-resume` |
| `log-edit-feedback` | `learn-change` |
| `manage-synonyms` | `learn-terminology` |

Six of these names were also the string identifier of a `resume-tool` CLI
command / facade capability, so those code identifiers were renamed to match in
the same release: the CLI command `check-ats-structure` → `check-structure`, and
the capability keys `check-ats-structure` → `check-structure`,
`identify-resume-gaps` → `check-gaps`, `compare-resume-versions` →
`compare-versions`, `select-best-resume` → `select-resume`,
`validate-resume-truth` → `validate-facts`, `build-candidate-evidence` →
`extract-evidence` (each carries a `Renamed to … from …` comment at its
definition). The MCP tool names (`resume_check_ats_structure`, …) are unchanged.

## Turning documents into JSON (agent-driven, no LLM provider)

The analysis/alignment capabilities operate on canonical JSON, not raw files.
Two conversion skills let the agent produce that JSON directly (best run as
**subagents** — they are confined, high-token tasks):

- **`parse-resume`** — a PDF/DOCX/MD/text resume → faithful `ResumeDocument`
  JSON, under strict no-alteration gates. Saved to
  `resume-kit/resumes/<name>-original.json`.
- **`parse-job`** — a job posting → structured `JobDescription` JSON with
  `requirements` + `keywords`, so deterministic **skills-coverage** scoring works
  without an LLM provider. Saved to `resume-kit/jobs/<name>-original.json`.

### Working directory convention

All state lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json                          # active_resume / active_job / alias_file pointers + preferences
├── resumes/<name>-original.json         # immutable faithful resume conversions
├── resumes/<name>-base.json             # baselining: original + auto-safe structural fixes
├── resumes/<name>-structure.json        # baselining: canonical shape after base
├── resumes/<name>-refine.json           # baselining: wording pass (default tailoring input)
├── jobs/<name>-original.json            # immutable job conversions
├── working/edit-session.json            # code-owned active edit-session state
├── working/<name>.tailored.json         # commit-session output for a tailored resume
├── learning/candidate-evidence.json     # durable full-resume evidence seed
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

`config.json` is code-owned by `resume-tool init` / `resume-tool set-active`;
skills must not hand-edit it. Keyword-scoring surfaces also accept an explicit
`alias_file` override — `resume-tool match --alias-file <path>` /
`identify-gaps --alias-file <path>` on the CLI, an `alias_file` field on the
`resume_check_job_match` / `resume_identify_gaps` MCP tools, and an `alias_file`
body field on the corresponding API routes. Keyword matching uses the alias
index; `check-structure` is structure-only and takes no alias file. When the
pointer is absent the surfaces run seed-only, identical to prior behaviour.

These skills describe how an agent drives the `resume-tool` CLI or the MCP
server. Each skill does ONE thing and self-gates on its prerequisites (it stops
and names the upstream skill to run first when a required input - a resume/job
JSON - is missing, rather than producing empty output). Start with the
`complete-resume-flow` guide for the composable end-to-end order. The legacy
`resume-workflow` guide is retained as a thin compatibility pointer. Skills are
thin invocation guides - they do not implement resume intelligence logic and
must not invent facts, bypass evidence, or create business rules in prompt text.

## Workflow (start here)

`complete-resume-flow` is the entry-point guide. It sequences the four reusable
flows without duplicating their stage gates:

1. **`prepare-base-resume` (Flow 1)** - run once per source resume. It prepares
   the reusable `original -> base -> structure -> refine` lineage, seeds
   full-resume learning/evidence, and leaves `refine` as the default downstream
   tailoring input.
2. **`ingest-job` (Flow 2)** - run once per job after Flow 1. It parses and
   activates the job, then grows/dedupes the project alias file through the
   truth-gated terminology learning path before the first job score.
3. **`tailor-resume` (Flow 3)** - run for that active job. It scores,
   truth-gates keyword and terminology improvements through the edit-session
   loop, validates facts, and re-scores for deltas.
4. **`finalize-resume` (Flow 4)** - run after tailoring. It performs the
   job-aware `perfect` fit and then exports the PDF/DOCX artifact; export is the
   rendered page hard gate.

Repeated-use path: run Flow 1 once per resume, then run Flows 2, 3, and 4 many
times for different jobs. Do not rerun Flow 1 per job unless the source resume
changes. `resume-workflow` remains as a compatibility guide that points to
`complete-resume-flow` and the four flow skills.

Supporting: `extract-evidence`, `compare-versions`, `select-resume`,
`learn-terminology`, `review-resume`, and `interview-missing-job-description`
are used from within the four flow skills when their gates call for them.

## Capability Map

| Skill directory | CLI command | MCP tool name | LLM required? |
|---|---|---|---|
| `parse-resume` | (agent-driven) | — | No (agent converts) |
| `parse-job` | (agent-driven) | — | No (agent converts) |
| `prepare-base-resume` | `resume-tool seed-full-resume-evidence` + baseline commands | `resume_seed_full_resume_evidence` + baseline tools | No (deterministic flow) |
| `complete-resume-flow` | (guide) | — | No (orchestration) |
| `ingest-job` | `resume-tool set-active --job` + `resume-tool suggest-terminology-candidates` + `resume-tool set-active --alias-file` | `resume_suggest_terminology_candidates` + `project_set_active` | No (agent-driven flow) |
| `tailor-resume` | `resume-tool match` + `resume-tool identify-gaps` + `resume-tool review-edits ...` + `resume-tool validate-truth` | `resume_check_job_match` + `resume_identify_gaps` + edit-session tools + `resume_validate_truth` | No (agent-driven flow) |
| `finalize-resume` | `resume-tool fit` + `resume-tool export` | `resume_build_perfect` + `resume_export` | No (deterministic flow) |
| `check-structure` | `resume-tool check-structure` | `resume_check_ats_structure` | No (deterministic) |
| `check-keywords` | `resume-tool match` | `resume_check_job_match` | No (deterministic) |
| `check-gaps` | `resume-tool identify-gaps` | `resume_identify_gaps` | No (deterministic) |
| `check-ats-view` | `resume-tool ats-view` | `resume_ats_view` | No (deterministic) |
| `update-keywords` | `resume-tool review-edits open`; `resume-tool review-edits prompt`; `resume-tool review-edits decide`; `resume-tool review-edits commit`; `resume-tool review-edits status`; `resume-tool review-edits reconcile` | `edit_session_open` / `edit_session_prompt` / `edit_session_decide` / `edit_session_commit` / `edit_session_status` / `edit_session_reconcile` | No (deterministic gate) |
| `update-terminology` | `resume-tool suggest-terminology` + `resume-tool review-edits open`; `resume-tool review-edits prompt`; `resume-tool review-edits decide`; `resume-tool review-edits commit`; `resume-tool review-edits status`; `resume-tool review-edits reconcile` | `resume_suggest_terminology` + `edit_session_open` / `edit_session_prompt` / `edit_session_decide` / `edit_session_commit` / `edit_session_status` / `edit_session_reconcile` | No (deterministic gate) |
| `validate-facts` | `resume-tool validate-truth` | `resume_validate_truth` | No (deterministic) |
| `extract-evidence` | `resume-tool build-evidence` | `candidate_evidence_build` | No (deterministic) |
| `compare-versions` | `resume-tool compare` | `resume_compare_versions` | No (deterministic) |
| `select-resume` | `resume-tool select` | `resume_select_best` | No (deterministic) |
| `export-resume` | `resume-tool export` | `resume_export` | No (deterministic) |
| `add-evidence` | `resume-tool add-evidence --confirmed` | `candidate_evidence_add` | No (deterministic) |
| `learn-terminology` | (agent-driven) | — | No (grows alias index) |
| `review-resume` | (agent-driven, advice-only) | — | No (subagent) |
| `rank-changes` | `resume-tool rank-edit-candidates` | `edit_candidates_rank` | No (deterministic ranking) |
| `learn-change` | `resume-tool record-edit-feedback` / `resume-tool refresh-preferences` | `edit_feedback_record` / `preferences_refresh` | No (records outcome) |
| `resume-workflow` | (guide) | — | No (orchestration) |

**Disabled / not surfaced as skills:** LLM auto-rewrite (`align-resume`) is
disabled for now — the no-LLM `update-keywords` + `update-terminology` cover
truthful tailoring. The raw LLM extract tools (`resume_extract`,
`job_description_extract`) remain callable via CLI/MCP but are not surfaced as
skills; prefer the agent-driven `parse-resume` / `parse-job`, which need no
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
