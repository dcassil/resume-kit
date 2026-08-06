# resume-kit — Orchestration Handoff

Copy-paste-friendly resume doc. Last updated **2026-08-06**. Supersedes the Phase 0–6 era handoff (that history now lives in Metis / git).

## ⭐ Current state (resume here)

- **Branch:** `feat/rit-i-0016-baselining` (NOT `main`). All recent work is committed + pushed here; `main` has the v1.0.0 skill rename merged in. Last commit `b0dd79a`.
- **Green & clean:** working tree clean (after the final Metis-doc commit below). Full suite **3345 passed / 1 skipped**; **repo-wide mypy clean (98 src files)**; ruff clean except 10 cosmetic E501s in the in-progress `packages/scoring` (left to RIT-I-0017's own reconcile).
- **Shipped:** `resume-kit` on PyPI (0.1.1); Claude plugin `resume-intelligence` at **v1.0.0** (major bump from the skill rename). 21 skills + `_shared/`.
- **Three active initiatives (all `discovery` on the board, but 0016 is largely delivered):**
  - **RIT-I-0016 — Resume baselining (`original → base → standard`)** — engine + surfaces + skills DONE this session; only E2E/docs (0121) and a conditional (0122) remain. **This is the near-complete one.**
  - **RIT-I-0017 — ScoreDoc projection** — 0104–0108 done; the "what the ATS sees" report (0109/0110/0111) is the open slice.
  - **RIT-I-0018 — Industry guidance audit** — `discovery`, not decomposed.

## What shipped this session (2026-08-06)

- **RIT-A-0005 (decided):** verb-noun skill lexicon + the shared change-application runbook. Verbs: `parse` (ingest) · `extract` · `check` (read-only) · `validate` (hard gate) · `review` (LLM) · `suggest` · `update` (gated edit) · `apply` (writes resume) · `learn` (writes future-learning state only) + utility `compare/select/rank/export`.
- **RIT-T-0123 (done):** renamed 14 skills to the lexicon (`inject-keywords`→`update-keywords`, `check-ats-structure`→`check-structure`, `validate-resume-truth`→`validate-facts`, `log-edit-feedback`→`learn-change`, `manage-synonyms`→`learn-terminology`, `resume-to-json`→`parse-resume`, `build-candidate-evidence`→`extract-evidence`, etc.); plugin bumped to **1.0.0**; migration breadcrumbs in each renamed SKILL.md + README table. The rename also touched CLI command names + capability keys.
- **RIT-T-0124 (done):** `plugins/resume-intelligence/skills/_shared/apply-changes.md` — the shared review-edits spine (`create-change → request-change → apply-change → validate-facts → learn-change`). `update-keywords` + `update-terminology` slimmed to their `create-change` bodies + a directive to the runbook.
- **RIT-T-0119 (done, prior):** baselining capabilities surfaced across facade/CLI/MCP/API + parity — `build-base`, `build-standard`, `analyze-best-practices` (+ pre-existing `check-ats-structure`).
- **RIT-T-0120 (done):** three baselining skills + workflow gating:
  - `update-structure` (structural check + auto-safe `base` fix), `check-best-practices` (read-only score), `update-best-practices` (`standard` step: elicit answers → `build-standard`).
  - `resume-workflow` now has a **baselining phase (step 2) before tailoring**, and every tailoring step is **gated on `standard` present (or a recorded override)**.
  - **Three ACs were accepted as deltas** (engine is narrower than the ACs assumed): base fix is auto-only; `build_standard` is a batch gated write not a per-item edit-session walkthrough; AC#6 (reuse the ATS-view report) deferred to RIT-T-0109. Tracked in **RIT-T-0125**.
- **CI pre-clean (commit b0dd79a):** fixed 2 pre-existing boundary-test failures, a real `baseline.py` bug (`CoreError` raised positionally → `ResumeKitError.from_code`), and scoring/edit_session mypy errors. Repo-wide mypy now clean.

## Immediate next steps (pick up here)

1. **RIT-T-0121 — close RIT-I-0016:** author the E2E integration test (`original → base → standard` through the skills/capabilities), reconcile README/docs to the baselining flow, and bump the plugin version. CI is already pre-cleaned green (see the task's status note). Then transition RIT-I-0016 → completed.
2. **RIT-T-0109/0110/0111 — RIT-I-0017 "what the ATS sees" report** (facade+CLI+MCP+API+parity, like RIT-T-0119 — a full cross-surface slice; sizeable). Unblocks RIT-T-0125 slice 3 (and would have been 0120 AC#6).
3. **RIT-T-0125 (P2)** — the accepted 0120 deltas: interactive `base` fixing, edit-session `standard` walkthrough, ATS-view reuse (slice 3 blocked by 0109).
4. **RIT-T-0122 (conditional)** — REQ-011 bounded source-file layout parse-risk detector.

## Gate command (current)

```
uv sync --all-packages && \
uv run ruff check packages tests integrations plugins && \
uv run mypy packages/*/src && \
uv run pytest
```
- mypy: **98 src files clean**. (Hyphenated test dirs have no `tests/__init__.py`, so mypy scans src only — tests are covered by ruff + pytest. By design.)
- The clean-venv install proof (`tests/packaging/test_clean_venv_install.py`) adds ~23s; skips if `uv` absent or `RESUME_KIT_SKIP_INSTALL_TEST=1`.
- Known-remaining: 10 cosmetic E501s in `packages/scoring` (RIT-I-0017 WIP) — not from this work.

## Architecture essentials (still true)

- **One facade REGISTRY, thin transports.** Every surface (CLI/MCP/API/bridge) is a thin adapter over the `resume_kit_facade` capability REGISTRY (async capabilities returning `InterfaceResponse` via `resume_kit_core.interface`). **Adding a capability = engine fn → facade capability + REGISTRY entry → each transport adapter + a cross-surface parity case** (`tests/interface/test_surface_parity.py`). Boundary tests forbid business logic in transports and forbid provider SDKs in the engine.
- **Skill lexicon (RIT-A-0005):** all skills are `verb-noun` from the closed vocabulary above. New skills self-place; `update-*` tailoring skills defer to `_shared/apply-changes.md`; baselining `update-*` skills (`update-structure`, `update-best-practices`) instead drive the `build-base`/`build-standard` **claim-preservation** gated writes (NOT the review-edits runbook).
- **Baselining lineage (RIT-A-0003):** `original` (extraction-faithfulness gate) → `base` (auto structural fix, claim-preservation gate) → `standard` (best-practices pass, claim-preservation gate). `standard` is the default for tailoring.
- **Two learning stores:** `learn-change` (edit feedback → `learning/`, biases ranking) and `learn-terminology` (grown aliases → `synonyms.json`). Both auto-fire inside the review-edits `decide`/`commit`; the skills are the explicit out-of-session entry points.

## Metis + workflow notes

- **Metis MCP tools WORK this session** (the old "project_prefix broken" landmine is gone). Use `mcp__plugin_metis_metis__*` for create/read/edit/transition. ADRs: `RIT-A-0001`/`0002`/`0005` decided; `0003`/`0004` draft. Backlog tech-debt/feature tasks live under `.metis/backlog/`.
- **Human-in-the-loop:** for initiative design/architecture decisions, check in before deciding (per global CLAUDE.md). Task execution against a decided ADR + populated task ACs is fine autonomously.
- **Completed Metis docs are historical** — do not rewrite them during renames/reconciles (the 0123 reconcile correctly skipped completed initiatives/tasks).
- Commit trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01PuESBqLCtXXY7DDG7Xnkos
  ```

## Where things live

- **Repo:** https://github.com/dcassil/resume-kit · **Local:** /Users/danielcassil/Code/resume-kit · branch `feat/rit-i-0016-baselining`.
- **Packages (17 + 1 integration):** `schemas, core, document-parser, matching, ats, job-parser, policy, evidence, alignment, scoring, export` (engine) · `facade` · `cli, mcp, api` (transports) · `terms, feedback` · `integrations/job-hunter`.
- **Plugin:** `plugins/resume-intelligence/` (21 skills + `_shared/{prerequisites,apply-changes}.md`; `.claude-plugin/plugin.json` v1.0.0; marketplace at repo-root `.claude-plugin/marketplace.json`).
- **Planning:** Metis in `.metis/` (vision `RIT-V-0001`).
- **Console scripts:** `resume-tool` (CLI), `resume-kit-mcp` (stdio MCP), `resume-kit-api` (uvicorn).
