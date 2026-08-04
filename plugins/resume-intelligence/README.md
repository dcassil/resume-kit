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
