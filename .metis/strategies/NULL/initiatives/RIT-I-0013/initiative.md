---
id: deterministic-preference-learning
level: initiative
title: "Deterministic preference learning: feedback log + preference memory + Preference-RAG + heuristic ranker"
short_code: "RIT-I-0013"
created_at: 2026-08-05T02:19:39.936363+00:00
updated_at: 2026-08-05T02:19:39.936363+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: deterministic-preference-learning
---

# Deterministic preference learning: feedback log + preference memory + Preference-RAG + heuristic ranker Initiative

## Context **[REQUIRED]**

resume-kit already separates generation from decision-making: the deterministic engine scores/matches/
validates, edits go through truth + policy gates, and DATA (the alias index, RIT-I-0009) is grown in the
`resume-kit/learning/` working dir. What is missing is a way to LEARN which truthful edit to prefer for a
given user + job + resume, from the user's own behavior — without retraining anything and without an LLM.

This initiative captures the **non-LLM first pass** of the feedback-driven refinement idea: treat every
suggested edit as structured feedback, remember what the user accepts/modifies/rejects/undoes, retrieve
similar past outcomes to inform the next suggestion (Preference-RAG), and RANK candidate edits with an
explainable heuristic — all deterministic, offline, and DATA-driven, consistent with the toolkit's
posture. The interesting rewrites here are produced by the EXISTING no-LLM improve skills
(`inject-keywords`, `update-terminology`) enumerating a few truthful strategies; the ranker/feedback/
preference layers decide among them and improve over time.

The LLM candidate-generator path and any learned ML ranker are deliberately OUT of this initiative (see
Non-Goals) — this is the deterministic substrate they could later plug into.

Substrate reused: `resume-kit/learning/` DATA convention (RIT-I-0009); match provenance + terminology
(RIT-I-0008/0010); the truth gate `validate_resume_truth` + policy (unsupported-claim hard blocker);
the improve skills `inject-keywords`/`update-terminology` (candidate sources); the deterministic scorers
in `matching`/`ats` (feature signals). Complements RIT-I-0012 (second-agent review) but does not depend
on it — see "Relationship to RIT-I-0012".

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- **Feedback log** (`EditFeedback`): record every suggested edit as structured data — section, edit_type,
  original/proposed/final text, target terms, matched JD requirements, predicted ATS gain, confidence,
  outcome (`accepted` | `accepted_modified` | `rejected` | `undone`), optional rejection reason, and the
  term-level diff (preserved/removed/added). Persisted append-only as DATA under
  `resume-kit/learning/edit-feedback.jsonl`.
- **Preference memory** (`UserPreferenceProfile`): derive a persistent, per-project user profile from the
  log deterministically — preferred tone/length/edit-strength, accepted/rejected phrases, disliked
  patterns, max length growth — with CONFIDENCE thresholds (≈1 = weak, ≈3 = moderate, ≈7+ = strong) and
  time DECAY of older signals. Persisted to `resume-kit/learning/preferences.json`; never updated from a
  single click; human-readable + prunable.
- **Preference-RAG**: before proposing edits, retrieve the most relevant past outcomes + preferences
  (similar accepted/rejected edits, same section, similar target terms, similar aggressiveness) using
  DETERMINISTIC similarity (term overlap, section/edit-type/aggressiveness match) — no embeddings, no
  model — and surface a compact "preference context" the improve skills inject.
- **Deterministic candidate enumeration**: for an edit site, enumerate a small set of TRUTHFUL candidate
  strategies from the existing no-LLM improve skills (e.g. minimal keyword substitution, terminology
  mirror, preserve-original, injectable-keyword surfacing) — no LLM generation.
- **Explainable heuristic ranker**: score candidates over deterministic `CandidateFeatures` (ATS gain,
  keyword gain, unsupported-claim risk, voice/preference match, length delta, specificity, repetition,
  section fit, historical success) with a transparent weighted formula, and emit WHY each candidate
  scored as it did. Unsupported claims are a HARD BLOCKER (reuse the truth gate) regardless of score.
- **Multi-objective + preference-learning-as-ranking**: store preference PAIRS (preferred vs rejected
  candidate + strength) so the ranking is trained-by-comparison conceptually, and the final choice
  balances predicted acceptance, ATS, fact support, readability, and voice — never acceptance alone.
- **Wire into the flow**: the improve step generates candidates → extracts features → retrieves
  preferences (RAG) → ranks → presents the top with an explanation; a feedback-logging step records the
  user's outcome; preference memory updates. Surface via the plugin (skills) + working-dir DATA; keep the
  ranker a pluggable deterministic component.

**Non-Goals:**
- **No LLM path.** No LLM candidate generation and no LLM ranking are recorded or built here. (The
  existing provider-gated generation stays as-is/disabled; this initiative does not touch or depend on it.)
- **No learned ML ranker** (LightGBM / pairwise / XGBoost / contextual-bandit exploration). Deferred to a
  future initiative once there is edit volume; the heuristic ranker is designed behind a pluggable
  interface so a learned ranker can replace it later WITHOUT re-architecting.
- **No cross-user Global/Role/Industry tier.** That requires a hosted, multi-user backend + identity +
  privacy/consent and is a product/service expansion — out of scope. This initiative is LOCAL, per-project,
  single-user (the "This User" tier only).
- **No embedding-based retrieval** in this pass (deterministic feature/term similarity only; embeddings are
  a possible later enhancement).
- No change to engine scoring math; features REUSE existing deterministic scorers. No auto-apply that
  bypasses the truth/policy gates or human-in-loop acceptance.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-1301: An `EditFeedback` record (schema) captures the fields above; a deterministic logger appends
    records to `resume-kit/learning/edit-feedback.jsonl` (create-if-absent; never rewrites history).
  - REQ-1302: A deterministic derivation builds `UserPreferenceProfile` from the log with documented
    confidence thresholds + time decay; persisted to `resume-kit/learning/preferences.json`; reproducible
    for a fixed log.
  - REQ-1303: Preference-RAG retrieves the top-K relevant past edits + preferences for a given edit
    context via deterministic similarity (no model), returning a compact injectable preference context.
  - REQ-1304: A candidate enumerator produces a small set of TRUTHFUL candidate edits from the existing
    no-LLM improve skills; each candidate carries `CandidateFeatures` computed from existing scorers +
    the truth report.
  - REQ-1305: An explainable heuristic ranker scores + orders candidates with a transparent weighted
    formula and emits a per-candidate reason; candidates that fail the truth gate (unsupported claim) are
    hard-blocked regardless of score.
  - REQ-1306: `PreferencePair` records (preferred vs rejected + strength) are stored from outcomes so
    future ranking can learn by comparison; `undone` counts as stronger negative than immediate `reject`.
  - REQ-1307: The flow is wired end-to-end (enumerate → features → RAG → rank → present-with-explanation →
    log outcome → update preferences) via plugin skills + working-dir DATA, human-in-loop (no silent
    apply), reusing the truth/policy gates.
- **Non-Functional:**
  - NFR-1301: Fully deterministic + offline + no LLM/model/network at any point in this initiative; a
    fixed log + fixed inputs yield identical preferences, retrieval, features, ranking, and explanations.
  - NFR-1302: The ranker is a pluggable interface (heuristic implementation now) so a learned ranker can
    be added later without changing callers.
  - NFR-1303: Unsupported-claim hard-block is enforced via the existing truth gate — the ranker cannot
    surface a truth-failing candidate. Identity/employer/date fields never edited (policy gate).
  - NFR-1304: `ruff` + `mypy --strict` clean; full `uv run pytest` green; `claude plugin validate` passes;
    all learning DATA is human-readable + prunable.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
```
edit site + JD context
   │
   ▼
Candidate enumeration (no-LLM: inject-keywords / update-terminology strategies)
   │            ▲
   │            │ Preference-RAG (deterministic retrieval over learning/edit-feedback.jsonl
   │            │                  + learning/preferences.json): similar accepted/rejected,
   │            │                  same section/terms/aggressiveness -> preference context
   ▼
Feature extraction (CandidateFeatures via matching/ats scorers + validate_resume_truth)
   │
   ▼
Heuristic ranker (transparent weighted score; truth = hard block) -> ranked + WHY
   │
   ▼
Present top candidate(s) + explanation  ->  user: accept / accepted_modified / reject / undo
   │
   ▼
Feedback logger -> learning/edit-feedback.jsonl  (+ PreferencePair)
   │
   ▼
Preference memory (confidence thresholds + decay) -> learning/preferences.json
   (feeds the next Preference-RAG round)
```
Deterministic throughout. Candidates come from existing no-LLM improve skills; every layer produces DATA
and explanations. The ranker is pluggable so a learned model could later replace the heuristic without
touching the surrounding flow.

### Component boundaries
- **schemas**: `EditFeedback`, `UserPreferenceProfile`, `CandidateFeatures`, `PreferencePair` (frozen).
- **feedback package (new, e.g. `resume_kit_feedback`)**: append-only log I/O, preference derivation
  (thresholds + decay), Preference-RAG retrieval, `CandidateFeatures` extraction (delegating to existing
  scorers + truth), and the pluggable `Ranker` protocol + heuristic implementation. Pure/deterministic.
- **plugin skills**: a rank/suggest skill (enumerate → RAG → rank → present-with-explanation, gated) and a
  feedback-logging skill (record the outcome → update preferences); both operate on working-dir DATA and
  are human-in-loop. Reuse the RIT-I-0011 prerequisite-gate convention.

## Detailed Design **[REQUIRED]**

1. **Schemas** for `EditFeedback` / `UserPreferenceProfile` / `CandidateFeatures` / `PreferencePair` in
   `resume_kit_schemas`, exported.
2. **Feedback log**: append-only JSONL under `resume-kit/learning/edit-feedback.jsonl`; a small deterministic
   read/append API; each record includes the term-level diff (preserved/removed/added) computed
   deterministically from proposed vs final.
3. **Preference memory**: derive `UserPreferenceProfile` from the log — accepted/rejected phrase and
   pattern frequencies with confidence tiers (1 weak / 3 moderate / 7+ strong) and exponential time decay;
   persist to `resume-kit/learning/preferences.json`; document the exact thresholds/decay so it is
   reproducible and prunable.
4. **Preference-RAG**: deterministic retrieval — score past edits by section match + target-term overlap +
   edit-type + aggressiveness bucket similarity; return top-K plus the relevant preference summary as a
   compact context block the improve skills inject before suggesting.
5. **Candidate features + heuristic ranker**: compute `CandidateFeatures` from `matching`/`ats` scorers +
   `validate_resume_truth` (unsupported_claim_risk) + preference match; a transparent weighted score
   (documented default weights) with a per-candidate reason string; truth failure = hard exclude. Behind a
   `Ranker` protocol (NFR-1302).
6. **Flow + skills**: a suggest/rank skill and a feedback-logging skill wire the loop, human-in-loop,
   reusing gates; explanations shown for every suggestion (REQ-1305 / "explain every suggestion").
7. **Registration/tests**: new skills registered in the plugin slug set (+ mapping/exemption as
   appropriate); `claude plugin validate` + full gate green; deterministic unit tests for log/preference/
   RAG/features/ranker; an integration test proving the loop is reproducible for a fixed log.

## Relationship to RIT-I-0012 **[REQUIRED]**

RIT-I-0012 (second-agent review + dev debug/refine loop) and this initiative are complementary but
independent:
- RIT-I-0012 = a second AGENT's qualitative CRITIQUE of a finished tailored resume (new+original+JD) →
  findings, used for dev toolkit improvement + optional user advice.
- RIT-I-0013 = deterministic learning from per-EDIT outcomes (accept/modify/reject/undo) → preference
  memory + RAG + ranking of the next suggestion.

Neither depends on the other. RIT-I-0012 stands alone without this initiative. If both land, RIT-I-0013's
feedback log MAY optionally ingest signals surfaced by RIT-I-0012's review findings, but that is an
enhancement, not a dependency; RIT-I-0012 is being (or will be) delivered on its own terms.

## Alternatives Considered **[REQUIRED]**

- **Fine-tune / train an LLM on edits.** Rejected (the whole premise): opaque, expensive, non-transparent;
  the goal is to CHOOSE the best truthful rewrite per user/job/resume, which a deterministic ranker over
  structured feedback does transparently.
- **Start with a learned ML ranker (LightGBM/bandit).** Deferred: needs edit volume and adds ML deps;
  begin with an explainable heuristic behind a pluggable interface so the learned ranker is a drop-in later.
- **Embedding-based Preference-RAG.** Deferred: embeddings need a model; deterministic feature/term
  similarity is enough for the first pass and keeps it offline/no-LLM.
- **Cross-user global learning now.** Rejected for scope: requires a hosted multi-user backend + privacy
  handling; keep local single-user; a global tier is a separate product decision (possible future vision
  update).
- **Update preferences from a single action.** Rejected: noisy; confidence thresholds + decay required.
- **Rank by acceptance only.** Rejected: multi-objective (acceptance + ATS + fact + readability + voice)
  with unsupported-claim hard block, so the system never learns to sacrifice truth for acceptance.

## Implementation Plan **[REQUIRED]**

Decompose (on approval) into ~4-5 tasks:
1. Schemas (`EditFeedback`, `UserPreferenceProfile`, `CandidateFeatures`, `PreferencePair`) + the new
   `feedback` package skeleton (log I/O) + tests.
2. Preference memory derivation (thresholds + decay) + `preferences.json` + tests.
3. Preference-RAG deterministic retrieval + injectable preference context + tests.
4. `CandidateFeatures` extraction (reusing scorers + truth) + pluggable `Ranker` protocol + heuristic
   ranker with explanations + truth hard-block + tests.
5. Plugin skills wiring the loop (suggest/rank + feedback-logging, gated, human-in-loop) + registration +
   README/version + integration test proving reproducibility.

**Exit criteria:** a deterministic, offline, no-LLM preference-learning first pass — structured
`EditFeedback` logging, decayed/confidence-tiered `UserPreferenceProfile`, deterministic Preference-RAG,
and an explainable pluggable heuristic ranker with an unsupported-claim hard block — wired into the plugin
flow over `resume-kit/learning/` DATA, human-in-loop, reproducible for a fixed log; `ruff` + `mypy
--strict` + full `pytest` green and `claude plugin validate` passing. Learned ML ranker, LLM generation,
embedding retrieval, and cross-user tiers are explicitly deferred/out of scope.
