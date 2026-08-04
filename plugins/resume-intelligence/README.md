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
├── config.json                          # active_resume / active_job pointers + preferences
├── resumes/<name>-original.json         # immutable faithful resume conversions
├── jobs/<name>-original.json            # immutable job conversions
├── working/<session-id>/resume.json     # the resume currently being changed/reviewed (mutable)
└── learning/<skill>.md                  # accumulated hints; skills read these first, append new ones
```

`-original.json` files are the untouched conversions (the name maps back to the
source file). To modify a resume, copy it into `working/<session-id>/` and edit
the copy; leave the original pristine.

These skills describe how an agent drives the `resume-tool` CLI or the MCP
server to invoke each of the 10 built capabilities.  Skills are thin
invocation guides — they do not implement resume intelligence logic and must
not invent facts, bypass evidence, or create business rules in prompt text.

## Capability Map

| Skill directory | CLI command | MCP tool name | LLM required? |
|---|---|---|---|
| `extract-resume` | `resume-tool extract` | `resume_extract` | Optional (no-LLM path available) |
| `extract-job-description` | `resume-tool extract-job` | `job_description_extract` | Optional (no-LLM path available) |
| `check-resume-ats` | `resume-tool check-ats` | `resume_check_ats` | No (deterministic) |
| `check-resume-job-match` | `resume-tool match` | `resume_check_job_match` | No (deterministic) |
| `select-best-resume` | `resume-tool select` | `resume_select_best` | No (deterministic) |
| `compare-resume-versions` | `resume-tool compare` | `resume_compare_versions` | No (deterministic) |
| `identify-resume-gaps` | `resume-tool identify-gaps` | `resume_identify_gaps` | No (deterministic) |
| `align-resume` | `resume-tool align` | `resume_align` | Yes (provider required) |
| `validate-resume-truth` | `resume-tool validate-truth` | `resume_validate_truth` | No (deterministic) |
| `build-candidate-evidence` | `resume-tool build-evidence` | `candidate_evidence_build` | No (deterministic) |

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
