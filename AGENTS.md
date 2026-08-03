# AGENTS.md — Orchestration conventions for resume-kit

This repo is built via **teamwork orchestration**. The main Claude session is the
**orchestrator**; it decomposes Metis initiatives into tasks, dispatches implementing agents
(codex / claude subagents), and owns all git.

## Branches
- `main` — integration + release branch. The **orchestrator** may commit and push `main`
  directly for this greenfield project (there is no separate `develop` yet, and `main` is not
  a protected legacy branch here). Feature work happens on `feat/<slug>` branches or in
  `../.worktrees/<slug>` and is merged with `--no-ff`.
- Worker/implementing agents **never** run git. They only write files.

## Git ownership
- Only the orchestrator stages, verifies, commits, merges, and pushes.
- Verification (ruff, mypy, pytest) is run by the orchestrator once per wave, never inside a
  racing worker agent.

## Work claims
- `.agents/work-log.md` holds one exclusive file claim per in-flight agent. Never let two
  in-flight agents claim the same file. Disjoint files → parallel; shared files → serial.

## Task decomposition
- Initiatives and tasks live in Metis (`.metis/`). Each task carries a `Recommended Agent`
  execution profile. Decomposition of an initiative is done by a codex agent, reviewed by the
  orchestrator, then recorded as Metis task documents.

## Tech stack
- Python 3.12+, `uv` workspace, `ruff` (lint/format), `mypy` (types), `pytest` (tests).
- Pydantic v2 for models. LiteLLM behind a provider `Protocol`. MarkItDown for extraction.

## Upstream donor
- Resume-Matcher is cloned to `./upstream/` (gitignored, never distributed) at a pinned commit
  for reference/extraction only. Every ported subsystem records its upstream SHA in
  `references/reuse-inventory.md` and attribution in `references/attribution.md`.
