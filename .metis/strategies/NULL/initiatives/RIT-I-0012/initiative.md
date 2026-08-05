---
id: second-agent-review-step-dev-debug
level: initiative
title: "Second-agent review step + dev debug/refine loop"
short_code: "RIT-I-0012"
created_at: 2026-08-05T01:57:19.595757+00:00
updated_at: 2026-08-05T02:36:41.421071+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: second-agent-review-step-dev-debug
---

# Second-agent review step + dev debug/refine loop Initiative

## Context **[REQUIRED]**

We now have a single-responsibility, self-gating skill flow (RIT-I-0011) that produces a tailored resume
from a real resume + job description with no LLM required. What we lack is a feedback signal on OUTPUT
QUALITY: did the tailoring actually help, truthfully? did the deterministic checks miss something a human
(or a second model) would catch? Right now the only judge is the deterministic scorers and the truth gate.

Owner decision (Daniel): add a reusable "second-agent review" step — dispatch ANOTHER agent to critique
the (new resume, original resume, job description) triple and return findings — and expose it as an
OPTIONAL step in the real workflow. On top of that reusable step, build a lightweight DEV debug/refine
loop: run trial pairs (real resume + JD) through the pipeline, have the second agent critique the output,
review the findings, and turn them into improvements to the TOOLKIT (skills/engine) — not the candidate's
resume.

Two forks resolved up front:
- **Reviewer = any subagent by default; codex optional.** The user-facing review step dispatches a Task
  subagent so it works anywhere Claude Code runs (no hard dependency on codex). The dev debug/refine loop
  MAY force a fully independent `codex exec` reviewer for a second-model perspective.
- **Refine target = the toolkit.** The dev loop turns the critique into fixes/additions to resume-kit's
  skills/engine (filed as Metis backlog tasks / changes). The user-facing optional step is ADVICE-ONLY —
  it critiques the tailored resume and writes findings; it never auto-edits the resume (edits stay with
  the truth-gated `inject-keywords` / `update-terminology` skills the user chooses to run).

Relevant substrate: the `resume-workflow` guide + `_shared/prerequisites.md` gate convention (RIT-I-0011);
the `resume-kit/` working-dir convention (`config.json` `active_resume`/`active_job`, `working/<session>/`,
`review/`); the SessionStart hook `bin/check-resume-kit.sh`; the existing subagent convention used by
`resume-to-json`/`job-to-json`/`manage-synonyms`.

**Relationship to RIT-I-0013 (independent).** RIT-I-0013 is a separate initiative for deterministic,
no-LLM preference learning from per-EDIT outcomes (accept/modify/reject/undo) → preference memory +
Preference-RAG + heuristic ranking. This initiative (RIT-I-0012) is distinct: a second AGENT's qualitative
CRITIQUE of a finished tailored resume (new+original+JD) → findings for dev toolkit improvement + optional
user advice. **RIT-I-0012 stands on its own and does not depend on RIT-I-0013.** If both land, RIT-I-0013
MAY optionally ingest signals from RIT-I-0012's review findings, but that is an enhancement only — nothing
in RIT-I-0012's scope, delivery, or exit criteria requires RIT-I-0013.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- A reusable, single-responsibility `review-tailored-resume` skill (shipped in the plugin): given the new
  (tailored) resume + the original resume + the job description, dispatch a SUBAGENT to evaluate and
  critique — strengths, weaknesses, truthfulness concerns, missed JD requirements, over/under-claims,
  terminology-mirroring opportunities — and write STRUCTURED findings to `resume-kit/review/<session>.md`.
  Advice-only; it never mutates the resume. Self-gates on the prerequisites (new resume JSON + original
  resume JSON + job JSON).
- Wire it as an OPTIONAL step in the `resume-workflow` guide (after tailoring / before export), clearly
  marked optional and advice-only.
- A once-per-session OFFER: when a session begins in an initialized `resume-kit/` working dir, the agent
  offers the optional review exactly once (not on every skill invocation). Mechanism: a session marker
  under the working dir so the offer is not repeated; the SessionStart hook may surface the availability.
- A DEV debug/refine loop (repo-level, not a shipped user skill) that: takes a real resume + JD trial
  pair, runs the pipeline, invokes `review-tailored-resume` (optionally forcing a `codex exec` reviewer),
  presents the critique, and converts actionable findings into TOOLKIT improvements (Metis backlog
  tasks / skill or engine changes), with a running trial/findings log.
- Keep everything deterministic where the engine is concerned; the review is an agent judgement layer that
  produces DATA (findings), not a runtime scoring dependency.

**Non-Goals:**
- No auto-editing of the candidate resume from the review (the user-facing step is advice-only; edits stay
  in `inject-keywords`/`update-terminology` under the truth gate).
- No hard dependency on codex for the shipped review step (codex is a dev-only option).
- No engine/scoring math change; the review does not feed back into deterministic scores.
- No new PyPI engine release required unless a task turns a finding into an engine change (the review step
  itself is plugin + working-dir only). Plugin version bump for the new skill.
- Not a general "LLM judge" framework — scoped to the resume/JD critique triple.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-1201: `review-tailored-resume` skill dispatches a subagent to critique (new, original, JD) and
    writes structured findings to `resume-kit/review/<session>.md`. Single responsibility; advice-only
    (no resume mutation). Self-gates on new+original resume JSON + job JSON (STOP + name upstream skill if
    missing).
  - REQ-1202: The review is OPTIONAL in `resume-workflow`, placed after tailoring and before export, and
    labelled advice-only.
  - REQ-1203: Once-per-session offer when a session starts in an initialized `resume-kit/` working dir;
    the offer is not repeated within the session (session marker). Declining is remembered for the
    session.
  - REQ-1204: The findings file has a consistent, parseable structure (e.g. sections for
    strengths / weaknesses / truthfulness-risks / missed-JD-requirements / terminology-suggestions, each
    with concrete, located items) so the dev loop can consume it.
  - REQ-1205: A dev debug/refine loop (repo-level runbook + the reuse of the review step) runs a trial
    pair through the pipeline, invokes the review (optionally `codex exec`), and records findings +
    resulting toolkit actions in a dev log; actionable toolkit findings are filed as Metis backlog tasks.
- **Non-Functional:**
  - NFR-1201: Reviewer defaults to a Task subagent; `codex exec` is an opt-in for the dev loop only. The
    shipped review step must function with no codex present.
  - NFR-1202: `claude plugin validate` passes; the plugin skill-markdown suite + full `uv run pytest`
    stay green.
  - NFR-1203: Advice-only guarantee for the user-facing step: the review path has no code that edits the
    resume JSON.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
```
resume-workflow (optional step, advice-only)
  review-tailored-resume  --dispatch subagent-->  critique(new, original, JD)
     -> resume-kit/review/<session>.md  (structured findings)

once-per-session offer: SessionStart hook detects initialized working dir ->
  agent offers review once -> session marker under resume-kit/ prevents repeat

DEV debug/refine loop (repo-level, not shipped as a user skill):
  trial pair (real resume + JD)
    -> run pipeline (resume-workflow) -> tailored resume
    -> review-tailored-resume (may force `codex exec` reviewer)
    -> read resume-kit/review/<session>.md
    -> dev reviews findings -> file Metis backlog tasks / make skill+engine fixes
    -> append to a trial/findings dev log
```
The review step is a thin agent-judgement layer writing DATA. The dev loop is orchestration over it +
the existing pipeline; its output is toolkit improvements, tracked in Metis.

## Detailed Design **[REQUIRED]**

1. **`review-tailored-resume` skill** (plugin, shipped): frontmatter mirrors siblings; Prerequisites gate
   (new resume JSON in `working/<session>/` + original resume JSON + job JSON). It dispatches a subagent
   with the three artifacts and a critique rubric (truthfulness, JD-requirement coverage, over/under-claim,
   terminology mirroring, structure/ATS readability, overall verdict), and writes the returned findings to
   `resume-kit/review/<session>.md` in the REQ-1204 structure. Explicitly advice-only; points the user to
   `inject-keywords`/`update-terminology`/`validate-resume-truth` to act on findings. Note codex is an
   optional reviewer for power users but the default is a subagent.
2. **Workflow wiring**: add the optional advice-only step to `resume-workflow` (after improve, before
   export) referencing the skill by slug.
3. **Once-per-session offer**: extend `bin/check-resume-kit.sh` (SessionStart) to detect an initialized
   `resume-kit/` working dir and surface that the optional review is available; the agent offers it once
   and writes a per-session marker (e.g. `resume-kit/.cache/review-offered-<session>`) so it is not
   repeated. Decompose to confirm the exact marker/session-id mechanism.
4. **Dev debug/refine loop**: a repo-level runbook (e.g. `docs/dev/debug-refine.md` or an `.agents/`
   process doc) describing: pick a trial pair, run the pipeline, invoke the review (with the `codex exec`
   option shown), read findings, triage into Metis backlog tasks (toolkit fixes) vs noise, and log the
   trial. Keep it "a simple thing that uses" the shipped review step — minimal new machinery.
5. **Register + reconcile**: add `review-tailored-resume` to `EXPECTED_SKILL_SLUGS` (workflow-skill
   exempt from the resume-tool/MCP mapping, like `manage-synonyms`); README capability map + Workflow
   section updated; plugin version bump.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Skill markdown**: `claude plugin validate` passes; slug set includes `review-tailored-resume`;
  frontmatter valid; it references the subagent + working-dir conventions; advice-only wording present.
- **Gate correctness**: the review skill's Prerequisites gate stops when new/original resume or job JSON
  is missing (documented + read-through; consistent with the RIT-I-0011 gate convention).
- **Hook behavior**: the SessionStart hook still exits cleanly and only surfaces the review availability
  when an initialized working dir is present (shell-level check; do not break the existing check).
- **No-mutation guarantee**: read-through/assertion that the review path writes only to
  `resume-kit/review/` and never to the resume JSON.
- Full `uv run pytest packages integrations plugins tests` stays green.

## Alternatives Considered **[REQUIRED]**

- **Bake the critique into an engine capability (deterministic).** Rejected: the value is a second AGENT's
  judgement (qualitative), which is inherently non-deterministic and provider/agent-driven; forcing it
  into the deterministic engine would contradict the "deterministic where practical" posture and add a
  runtime provider dependency. Keep it an agent layer producing DATA.
- **Require codex for the review step.** Rejected for the shipped step (portability); kept as an opt-in for
  the dev loop where a fully independent second model is valuable.
- **Auto-apply the review's suggestions to the resume.** Rejected: violates human-in-control + the truth
  posture; edits must go through the truth-gated improve skills the user explicitly runs.
- **Offer the review on every skill run.** Rejected: noisy; once-per-session offer is the right cadence.
- **Ship the dev debug/refine loop as a user plugin skill.** Rejected: it's dev tooling; keep it
  repo-level so the shipped plugin stays user-focused, while reusing the shipped review step.

## Implementation Plan **[REQUIRED]**

Decompose (on approval) into ~3-4 tasks:
1. `review-tailored-resume` skill (dispatch subagent, critique rubric, structured findings file,
   advice-only, gated) + register in slug test + README + version bump.
2. Workflow wiring (optional advice-only step in `resume-workflow`) + once-per-session offer (SessionStart
   hook + session marker).
3. Dev debug/refine runbook (repo-level) that reuses the review step (with `codex exec` option) and
   triages findings into Metis backlog tasks; a trial/findings log.
4. (If needed) a small fixtures/dev dir + a first real trial run to validate the loop end-to-end.

**Exit criteria:** a shipped, advice-only `review-tailored-resume` skill that dispatches a subagent to
critique new+original+JD and writes structured findings; it is an optional step in `resume-workflow`,
offered once per session in an initialized working dir; a repo-level dev debug/refine loop reuses it
(codex optional) and turns findings into Metis-tracked toolkit improvements; `claude plugin validate`
passes and the full test suite is green; plugin version bumped.