# resume-kit — Orchestration Handoff

Copy-paste this into a fresh session to resume the autonomous build.

## The directive (from Daniel)
> Orchestrate the build. Use **codex** agents to decompose ONE Metis initiative at a time, then
> use **claude/codex** subagents (teamwork-orchestration skill) to implement the tasks. The main
> session is the ORCHESTRATOR: it owns ALL git (commits/merges/pushes), checks on background agents
> ~every 5 min for hangs, works ONE initiative at a time until all are done. Repo is a new PUBLIC
> git repo (done). Publish to npm **only if a good fit** (it is NOT — see below; target PyPI).
> When context hits ~90%, write a copy-paste handoff doc and stop.

## Where things live
- **Repo:** https://github.com/dcassil/resume-kit  (gh acct `dcassil`; npm acct `dpcassil01`)
- **Local:** /Users/danielcassil/Code/resume-kit  · integration branch `main` (orchestrator pushes directly; greenfield, not a protected legacy branch)
- **Planning:** Metis in `.metis/` (vision `RIT-V-0001`). Use the `mcp__plugin_metis_metis__*` tools.
- **Orchestration state:** `.agents/work-log.md` (wave/claim log), `.agents/decomp-RIT-I-*.json` (codex decompositions).
- **Donor:** Resume-Matcher cloned at gitignored `./upstream/`, pinned SHA `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc`. Never distribute it.

## Key decisions already made
- **Python 3.12 + uv workspace**, NOT JavaScript. Distribution → **PyPI, not npm** (donor is Python; a JS rewrite throws away the reuse strategy). Recorded in `references/architectural-decisions/ADR-0001-*`. If Daniel wants an npm artifact, add a thin JS client over MCP/CLI in a later phase — core stays Python.
- Toolchain: `uv` 0.12.x (installed via brew), dev deps ruff+mypy(strict)+pytest+pytest-asyncio. Verify with `uv run ruff check packages`, `uv run mypy packages`, `uv run pytest`.
- Roadmap = vision Phases 0–6, each becomes ONE initiative, created + fully specified only when reached (conserves orchestrator context). Metis task `.md` files are populated by writing them directly from the codex decomposition JSON (frontmatter preserved).

## Orchestration procedure (repeat per initiative)
1. Create initiative (`create_document` type=initiative, parent RIT-V-0001), fully populate the template (all sections — Metis rule), transition discovery→design→ready→decompose.
2. Dispatch **codex** to decompose: `codex exec --skip-git-repo-check -s read-only --output-schema <scratch>/decomp-schema.json --color never "<prompt>"`. Schema is at the scratchpad path (recreate: tasks[] with title, context, acceptance_criteria[], implementation_notes, verification_steps[], recommended_agent, files_touched[], depends_on[]). Give codex the initiative path + relevant `references/*.md` for grounding.
3. Save decomp to `.agents/decomp-<code>.json`. Create Metis task docs, populate their `.md` files directly from the JSON (see the python snippet pattern in git history / prior tasks).
4. Transition initiative → active. Commit planning.
5. Execute in WAVES by file-disjointness (see each task's `files_touched` + `depends_on`):
   - Parallel agents for disjoint files (dispatch in one message, `run_in_background: true`).
   - Serialize tasks sharing a file.
   - Agent model = task's `recommended_agent` (opus/sonnet/haiku). Prompt = fully self-contained, "WRITE FILES ONLY, no git, package-local verification only".
6. On each wave completion: orchestrator runs `uv run ruff check packages && uv run mypy packages && uv run pytest`, fixes/re-dispatches if red, updates `.agents/work-log.md`, commits with the repo's trailer, pushes `main`.
7. When all waves green → transition tasks todo→active→completed and the initiative → completed. Commit.
8. Next initiative.

Commit trailer (every commit):
```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WpLT8iXnxtXkgRQeHFbhNj
```

## Status ledger
- **Phase 0 — Upstream Audit (RIT-I-0001): COMPLETE & pushed.** Deliverables: `references/upstream-audit.md`, `reuse-inventory.md` (Reuse/Extract/Adapt/Replace/New matrix), `attribution.md` (Apache-2.0). 530 upstream tests pass. Tasks RIT-T-0001..0004 completed.
- **Phase 1 — Clean Core & Schemas (RIT-I-0002): IN PROGRESS.**
  - RIT-T-0005 scaffold (packages/core, packages/schemas, uv workspace, toolchain): DONE & committed.
  - RIT-T-0006 canonical + ported schemas (packages/schemas + attribution): running (Wave 2).
  - RIT-T-0007 core contracts (Protocols, InterfaceResponse, fakes; packages/core): running (Wave 2).
  - RIT-T-0008 boundary/integration quality gates (tests/): NOT STARTED — Wave 3, depends on 0006+0007.
- **Phases 2–6: NOT STARTED.** Next initiatives to create from vision roadmap:
  - Phase 2 — Document extraction & parsing (MarkItDown, date-restoration, LLM parse behind provider iface, no-LLM text mode).
  - Phase 3 — Matching & deterministic analysis (keyword/match, ATS engine — note `services/ats.py` is already deterministic+no-LLM, a strong seed — scoring dims; check-ats, check-job-match, select-best, compare-versions).
  - Phase 4 — Controlled alignment (diff apply/verify engine, allowed-path policy, freedom 0-10, evidence+provenance, human-in-loop, validate-truth).
  - Phase 5 — Interfaces (CLI `resume-tool`, MCP server, agent plugin, REST API, job-hunter bridge).
  - Phase 6 — Export & package workflows (PDF/DOCX export WITHOUT the upstream Next.js frontend — `pdf.py` hard-deps Playwright+Chromium+frontend, so Replace→New; app-package audit; cover-letter match/align). Then configure PyPI publishing.

## Known landmines
- Root `pyproject.toml` `[tool.hatch.build.targets.wheel] packages = ["src/resume_kit"]` points at a dir that doesn't exist (root is a meta-package). `uv sync` tolerates it in editable mode; fix before any root `uv build` (Phase 6 packaging).
- Structured resume parsing is LLM-only upstream — no-LLM structured extraction is a known gap to design around (Phase 2).
- `improver.py` upstream is a ~1500-line mega-module; decompose during Phase 4 extraction.
- Export `pdf.py` depends on the upstream frontend/print-route — must be replaced, not ported (Phase 6).
