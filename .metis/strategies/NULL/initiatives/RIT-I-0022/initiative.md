---
id: score-gated-missing-requirement
level: initiative
title: "Score-gated missing-requirement interview: elicit-and-prove loop with durable answer memory"
short_code: "RIT-I-0022"
created_at: 2026-08-10T22:59:56.969370+00:00
updated_at: 2026-08-11T02:33:10.677733+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: S
strategy_id: NULL
initiative_id: score-gated-missing-requirement
---

# Score-gated missing-requirement interview: elicit-and-prove loop with durable answer memory Initiative

## Context **[REQUIRED]**

Today the tailoring flow ends after we apply truthful edits and re-score against the job (the
`check-job-match` / second-scoring step). If the score is still below par, the user is left with a low
number and no guided path forward. Many of those gaps are not "the resume is bad" — they are
requirements the resume simply never mentioned but the candidate genuinely has. We never asked.

This initiative adds ONE optional, opt-in step at the end of tailoring: if the score is still low (or a
required must-have is uncovered), offer to walk the user through the job's missing requirements,
truthfully elicit which they actually have, and — for confirmed ones — capture grounding evidence and
route it through the EXISTING truth-gated keyword-update path, then re-score. Every answer is persisted
so future jobs never re-ask the same question.

The governing principle, reinforced by a Codex review of the spec, is **elicit-and-prove, not
raise-the-score**. A "yes" is not a license to insert a keyword; it is a prompt to capture a grounding
fact, persist it as evidence, and let the existing gates decide. This keeps the feature squarely on the
truth posture the tool already enforces.

**This is deliberately a thin, composition-first initiative.** Almost everything it needs already exists
and MUST be reused rather than rebuilt:
- **JD required/nice-to-have split** — `resume_kit_schemas/job.py` already models `RequirementKind.REQUIRED/PREFERRED`, `requirements: list[Requirement]` (each `text`, `kind`, `terms`), and a separate `preferred` list. No new parsing.
- **Gap list** — `analyze_keyword_gaps` → `KeywordGapAnalysis` (missing / injectable / non_injectable) in `resume_kit_matching`.
- **Truth-gated injection** — the `update-keywords` skill (`ChangeProposal` + edit-session) already applies missing-but-TRUE keywords; the interview feeds it, it does not replace it.
- **Evidence** — `resume_kit_evidence` / `CandidateEvidence` is the existing proof record.
- **Answer memory substrate** — RIT-I-0013 is built: `resume_kit_feedback` with `learning/*.jsonl` and the `append_edit_feedback` / `append_preference_pair` pattern. We extend it with one more record type; we do NOT stand up a new store.
- **Re-scoring** — `resume_check_job_match`.

The only genuinely new code is a small answer-memory rail plus one integration decision (how confirmed
answers become proof for `update-keywords`). Everything else is a new skill (prose orchestration) and a
few flow edits.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- **Opt-in, score-gated trigger.** After the existing second scoring, if `overall < threshold` OR a
  required requirement is uncovered, ASK the user whether they want to review additional requirements.
  Decline → proceed to final refinement exactly as today. No behavior change unless the user opts in.
- **Truth-gated interview skill.** A new `interview-missing-job-description` skill drives a question loop
  over *missing* items in priority order — required first, then preferred/nice-to-have, then remaining
  unmatched keywords — read directly from the existing JD + gap analysis (no new ranking, no new parsing).
- **Four response semantics, correctly typed:**
  - **No** — durable "candidate does not have this." Persisted; suppresses future asks globally.
  - **Yes** — MUST immediately capture a grounding fact (where / when / what you did / scale or outcome
    if known), persist it as `CandidateEvidence` + a `RequirementAnswer`, and ONLY THEN let
    `update-keywords` generate proposals from that evidence. A bare boolean "yes" is not accepted.
  - **Need more info** — an EXPLANATION state, not an answer. The agent explains the requirement and
    guides the user to a confident yes/no/not-in-context; it loops back to the same question, is never
    persisted as durable truth, and never suppresses future asks (may be logged as interaction telemetry only).
  - **Not in this context** — a "no" SCOPED to this job's context. Suppresses re-asking only on an exact
    normalized-requirement match AND a coarse context-tag match (e.g. role/industry); a materially
    different future context is eligible to ask again.
- **Cadence controls.** Every 4 questions, pause and offer: re-check the score, or keep going. Whenever
  the score is shown, offer: continue questioning, or move on to final refinement.
- **Durable, reusable answer memory** (extends RIT-I-0013). Persist every durable answer so the next job
  pre-filters already-answered items and honors context-scoped negatives. Deterministic normalized-key
  matching — NO embeddings, consistent with 0013's stance.
- **Configurable threshold + required-coverage trigger.** Threshold is config-driven (default ≈70), and
  the gate fires on BOTH overall score and required-coverage, because a decent overall score can hide a
  missing must-have.
- **Termination.** The loop ends when the score crosses threshold, the user declines to continue, or
  there are no more unanswered items — then control returns to the existing final-refinement step.

**Non-Goals:**
- **Relevance ranking of gaps** — explicitly dropped for this pass. Ask in the JD's own priority order
  (required → preferred → keyword). No scoring/ranking of which gap is "most worth asking."
- **Embeddings / semantic similarity** — deterministic normalized-key + coarse context tag only.
- **Any new scoring engine or change to the truth/faithfulness gate.** The interview is a new *source* of
  claims; it does not bypass or weaken any existing gate.
- **Auto-answering or coaching the witness.** "Need more info" explains a requirement; it must not lead
  the user into claiming experience they don't have.
- **A parallel MCP/CLI surface** — reuse the existing rails; add at most one thin command for the new record.

## Use Cases **[CONDITIONAL: User-Facing Initiative]**

### Use Case 1: Low score after tailoring, candidate actually has the missing skill
- **Actor**: Job seeker tailoring a resume to a specific posting.
- **Scenario**:
  1. Tailoring + second scoring completes; score is 62 (< 70 threshold), and a required item
     "Kubernetes" is uncovered.
  2. Tool offers: "Score is still below par and 2 required items are uncovered — want to review them?"
     User says yes → `interview-missing-job-description` starts.
  3. First question (required): "The role requires Kubernetes. Do you have experience with it?"
  4. User picks **Yes** → agent asks for grounding: "Where/when, and what did you do with it?" User:
     "At Acme 2022–2023, ran our prod EKS cluster, ~40 services." Agent persists a `CandidateEvidence`
     record + a `RequirementAnswer{answer: yes}`, then hands it to `update-keywords`, which proposes a
     truthful bullet/skill edit through the normal edit-session gate.
  5. After 4 questions the tool asks: re-score or continue? User re-scores → 74. Tool asks: continue or
     finalize? User finalizes → existing perfect/refinement step runs.
- **Expected Outcome**: Score crosses threshold via TRUTHFUL, evidence-backed edits; the Kubernetes
  answer is banked so the next K8s job never re-asks.

### Use Case 2: Candidate genuinely lacks the requirement
- **Actor**: Same.
- **Scenario**: Question "Do you have FedRAMP compliance experience?" → user picks **No**. Persisted as a
  global negative. No edit is made. Next job that lists FedRAMP does not re-ask.
- **Expected Outcome**: No fabrication, no wasted re-ask, score honestly reflects a real gap.

### Use Case 3: Context-scoped negative
- **Actor**: Same.
- **Scenario**: "Do you have management experience?" in a *senior IC* posting → user picks **Not in this
  context** ("not for this IC role"). Persisted scoped to role=IC. A later *manager* posting asks the
  question again (different context); a later IC posting does not.
- **Expected Outcome**: Suppression is context-aware, erring toward re-asking when context differs.

## Detailed Design **[REQUIRED]**

**1. Answer-memory rail (the only substantial new code) — extends RIT-I-0013.**
Add a `RequirementAnswer` record to `resume_kit_feedback`, persisted append-only alongside the existing
learning logs (`learning/requirement-answers.jsonl`), reusing the established `append_*` / load pattern —
do NOT invent a new persistence mechanism. Shape (kept minimal):
- `requirement_key: str` — normalized requirement/term text (reuse existing normalization from matching).
- `answer: Literal["yes", "no", "not_in_context"]`.
- `context_tag: str | None` — coarse role/industry tag, populated only for `not_in_context`.
- `evidence_ref: str | None` — link to the `CandidateEvidence` record for a `yes`.
- `ts: str`.
Helpers: `append_requirement_answer(...)`, `load_requirement_answers(...)`, and a small
`is_already_answered(requirement_key, context_tag) -> answer|None` that encapsulates the dedupe rule
(global yes/no suppress; `not_in_context` suppresses only on exact key + matching context tag). Expose via
ONE thin CLI/MCP command so the skill writes through the deterministic rail, not by hand-editing files —
mirroring how the other learning writes are surfaced.

**2. Evidence integration — the load-bearing decision (call it out, don't bury it).**
Injectable classification currently proves from the MASTER resume (see `resume_kit_matching/keywords.py`:
without a master, `injectable` is always empty — RIT-T-0126). For a confirmed "yes" to become an
injectable, truthful edit, its captured `CandidateEvidence` must be usable as proof by `update-keywords`.
**Decision (locked): option (a) — fold confirmed evidence into a master-equivalent proof source** that the
gap/injectable step already consults, because it touches the fewest seams and reuses the existing
master-as-proof path rather than introducing a second proof mechanism. The captured evidence is projected
into the same proof surface `analyze_keyword_gaps` already reads, so a confirmed "yes" simply becomes
injectable through the existing route — no new proof path in `update-keywords`. (Option (b), a first-class
`CandidateEvidence` proof path, was rejected as more surface area for no thinness gain.) This remains the
one place "thin" is at risk, so it keeps a dedicated task to get the fold-in seam right.

**3. Interview skill (prose orchestration, ~no code).**
`interview-missing-job-description` reads the active JD + `KeywordGapAnalysis`, builds the question queue
in JD priority order (required → preferred → other keywords), pre-filters via `is_already_answered`, then
loops the four-choice interaction with the cadence controls. "Yes" → capture grounding → persist evidence
+ answer → invoke `update-keywords`. "No"/"Not in this context" → persist answer, no edit. "Need more
info" → explain + re-ask (telemetry only). It calls `resume_check_job_match` for re-scores on demand and
at the every-4 checkpoint, and hands back to the existing final-refinement step on termination.

**4. Flow wiring.**
The `resume-workflow` guide gains the branch: after second scoring, if `overall < threshold` OR
required-coverage incomplete, offer the interview; after accepted answers → add evidence → run keyword
update → re-score; on termination → final refinement. Threshold + required-coverage trigger read from
config (default ≈70). No new step is forced on users who decline.

**Truth-safety invariants (cross-cutting):** every persisted answer/evidence still flows through the
existing `validate-truth`/faithfulness gate; the interview adds claims, it never bypasses the gate. "Need
more info" guidance explains, it does not coach a "yes."

## Alternatives Considered **[REQUIRED]**

- **Rank gaps by relevance and auto-ask the "top 4."** Considered and REJECTED for this pass (per the
  user). Ranking adds a scoring/ranking surface and complexity for marginal gain over simply asking in the
  JD's own required→preferred→keyword order. Can be layered later if the flat order proves noisy.
- **A new standalone Q&A/answer store independent of RIT-I-0013.** Rejected: duplicates the learning
  substrate we already built. Extending `resume_kit_feedback` with one record type is thinner and keeps all
  learning in one place. (Chosen per user direction.)
- **Accept a bare "yes" and inject the keyword directly.** Rejected as a truth violation — it turns the
  feature into consented keyword-stuffing. A "yes" must capture grounding evidence and pass the existing
  gates (Codex review's key correction).
- **Trigger only on overall score.** Rejected: an overall score can clear threshold while a required
  must-have is uncovered. Gate on both overall and required-coverage.
- **Semantic/embedding similarity for "similar question" suppression.** Rejected: inconsistent with 0013's
  no-embedding stance and over-engineered. Deterministic normalized-key + coarse context tag; err toward
  re-asking.

## Implementation Plan **[REQUIRED]**

Sequenced thinnest-first. **Decomposition into task documents is NOT yet done — pending human check-in
per the initiative HITL rule.** Proposed task breakdown (with model/effort per the decomposition rubric):

1. **T1 — `RequirementAnswer` learning rail (extends RIT-I-0013).** Add the record type, append/load +
   `is_already_answered` dedupe rule, and one thin CLI/MCP write/read surface in `resume_kit_feedback`.
   Deterministic, offline, append-only; mirror the existing `edit-feedback.jsonl` pattern. Tests for the
   dedupe rule (global vs context-scoped). *Recommended Agent: opus + medium* (small but it is the durable
   data contract other pieces depend on; get the dedupe/context-scope semantics right).

2. **T1a — Evidence-as-proof integration (fold-in).** Implement the LOCKED option (a): project confirmed
   `CandidateEvidence` into the master-equivalent proof source that `analyze_keyword_gaps` already consults,
   so a confirmed "yes" becomes injectable through the existing route with no new proof path in
   `update-keywords`. This is the load-bearing integration; keep it minimal. *Recommended Agent: opus + high*
   (touches the injectable/proof seam that other tailoring relies on; a wrong choice creates compounding
   rework — the one place to reason carefully).

3. **T2 — `interview-missing-job-description` skill.** The interactive driver: JD-priority question queue,
   four-choice semantics (with grounding capture on "yes" and the correct non-durable handling of "need
   more info"), pre-filter via T1, cadence controls (every-4 re-score offer; post-score continue/finalize),
   re-score via existing capability, truth-safety guardrails. Prose orchestration reusing update-keywords /
   evidence / check-job-match. *Recommended Agent: opus + medium* (no core code, but the truth semantics and
   loop control must be exactly right).

4. **T3 — Flow wiring + trigger config.** Add the score-gated / required-coverage branch to the
   `resume-workflow` guide and the "still low → offer interview → finalize" hint at the second-scoring step;
   surface the configurable threshold + required-coverage trigger. Docs/glue + a small config addition.
   *Recommended Agent: sonnet + medium* (follows the stated pattern; single-guide + config edit).

**Dependencies:** RIT-I-0013 (feedback/learning substrate — built), `resume_kit_evidence`,
`update-keywords` skill + edit-session, `analyze_keyword_gaps` (matching), `resume_check_job_match`, JD
schema (`RequirementKind`). **Risks:** the T1a proof-source seam is the main unknown; everything else is
composition. **Sequencing:** T1 → T1a (needs the record) → T2 (needs both) → T3 (wires it in).