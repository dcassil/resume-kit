---
name: seed-terminology
description: >
  Seed and grow the project synonym index (`alias_file`) automatically during the
  normal tailoring flow, so match / check-keywords / check-gaps / suggest-terminology
  are alias-aware from the very FIRST score instead of `alias_file` being None on a
  fresh project. Runs after a resume + job are both active: proposes TRUTHFUL synonym
  pairs between resume wording and JD keywords the resume ALREADY satisfies, using a
  conservative fuzzy/stemmed PRE-FILTER (`suggest-terminology-candidates`) to PROPOSE
  candidates the closed lexicon cannot. Every proposal passes human confirmation + the
  existing truth gate before it is written; the proposer never auto-accepts. On first
  run it CREATES the alias file and registers it via `set-active --alias-file`; on
  each later job it APPENDS + DEDUPES new pairs without dropping prior ones. Reuses
  learn-terminology's append rule and truth gate — it adds no scoring logic. Best run
  in a subagent.
---

# seed-terminology — auto-seed & grow the alias index (truth-gated)

## Purpose

On a fresh project `config.alias_file` is `None`, so the deterministic matchers
(`match` / `check-keywords` / `check-gaps` / `suggest-terminology`) mirror only
the built-in seed lexicon. A resume that says **responsive UI** scores as missing
the JD's **responsive design**; **monitoring** misses **observability**; and
coverage is silently understated for pure phrasing differences the candidate
genuinely satisfies — with no flow step ever creating or growing the file.

This skill closes that gap. Run once a **resume + job are both active** and BEFORE
the first keyword/gap check, it:

1. **Proposes** conservative candidate pairs with the deterministic fuzzy
   pre-filter (`suggest-terminology-candidates`) — the one new capability. It only
   surfaces `(jd_keyword, resume_phrase)` pairs for *missing* JD keywords the
   resume plausibly satisfies under a near-miss surface form (shared stem + one
   differing token, or a small single-token edit distance). It **proposes only**;
   `confirmed` is always false.
2. **Truth-gates + confirms** each proposal through the **learn-terminology**
   loop (below). Nothing is written without an explicit user "yes".
3. **Seeds or grows** the `alias_file`: create + register on first run, append +
   dedupe on every later job — never overwrite, never drop prior entries.

**It writes DATA only. Scoring stays deterministic and provider-free.** Unconfirmed
proposals never affect any score — the conservative-lexicon guarantee is preserved.

## Run me in a subagent

Self-contained and file-mutating, like `parse-resume` / `learn-terminology`. The
main agent dispatches it a subagent with: the active resume + job JSON paths, the
path to `resume-kit/config.json`, and this skill. The subagent returns only **what
it seeded/grew** (canonical, alias, why) plus what it rejected/deferred — not the
full resume/job text.

## Where the alias file lives

The path is `config.json`'s `alias_file`. Read it; **default to
`resume-kit/learning/synonyms.json`** if the key is absent (the fresh-project
case). This is the SAME file the scoring skills pass to the engine, so growth and
scoring stay in lock-step. Format is the RIT-T-0068 shape documented in
**learn-terminology** (`{version, aliases, justifications, provenance}`).

## Steps

1. **Gate.** Confirm a resume and a job are both active
   (`config.active_resume` + `config.active_job`, resolving the resume version per
   the normal lineage). If either is missing, STOP — there is nothing to seed yet.
2. **Propose candidates (deterministic).** Run the fuzzy pre-filter against the
   active resume + job, passing the current `alias_file` when it exists so
   already-known pairs are not re-proposed:
   - **CLI:** `resume-tool suggest-terminology-candidates --resume <resume.json>
     --job <job.json> [--alias-file <path>]`
   - **MCP:** `resume_suggest_terminology_candidates` with `resume`, `job`, and
     optional `alias_file`.
   The result is a list of `TerminologyCandidate` `{jd_keyword, resume_phrase,
   locations, reason, confirmed:false}`. If empty, STOP — nothing to seed.
3. **Truth-gate + confirm (learn-terminology).** Hand each candidate to the
   **learn-terminology** truth gate and human-confirmation loop: for each pair,
   verify the two terms name the SAME underlying skill/fact the resume already
   demonstrates (never alias distinct skills, never make an absent skill present,
   never broaden scope; ambiguous → do NOT add, ask the user). Only pairs the user
   explicitly confirms survive. The fuzzy proposer NEVER auto-accepts — it only
   feeds this gate.
4. **Seed or grow (append rule).** For every confirmed `{canonical=jd_keyword,
   alias=resume_phrase, why}`, apply learn-terminology's **append rule**
   idempotently:
   - **Seed (first run — no `alias_file` yet):** create the file with the empty
     shell `{"version":1,"aliases":{},"justifications":{}}`, append the confirmed
     pairs, then **register it** so future runs use it —
     `resume-tool set-active --alias-file learning/synonyms.json`
     (MCP: `project_set_active(alias_file="learning/synonyms.json")`). Never
     hand-edit `config.json`; `set-active` persists and validates the pointer.
   - **Grow (later jobs — `alias_file` already set):** load the existing file,
     append ONLY the new confirmed pairs, **de-dup** case-insensitively within each
     canonical group, and **preserve every prior entry** (union, never overwrite).
     Re-registering via `set-active` is idempotent and optional once the pointer is
     already set.
5. **Report.** List exactly what you seeded/grew (`canonical, alias, why`) and what
   you rejected/deferred and why. Never grow the file silently. Append recurring
   false candidates or house rules to `resume-kit/learning/learn-terminology.md`.

## Truth gate — do not weaken

This skill inherits learn-terminology's **load-bearing truth gate verbatim**. A
looser fuzzy proposer must never let an unsubstantiated pair into `alias_file`:
the proposer only suggests pairs where the resume already satisfies the term under
a near-miss surface form, and human confirmation + the truth gate are mandatory
before any write. A bad alias makes the resume claim a skill the candidate does
not have — that is dishonest and defeats the tool. When in doubt, do NOT add.

## Effect on the next score

Once a confirmed pair is written and the `alias_file` is registered, the very next
deterministic run of `match` / `check-keywords` / `check-gaps` UNIONs the file over
the seed and honors the new synonym — raising coverage with NO change to resume
text and no LLM. Because the pointer is set during this step (between job ingest
and the first check), the first score is already alias-aware.

## Output

The set of aliases actually seeded/grown — each `{canonical, alias, why}` — plus
anything rejected/deferred and why, and the registered `alias_file` pointer. The
updated `resume-kit/learning/synonyms.json` (valid RIT-T-0068 JSON), grown ONLY
with user-confirmed, truthful synonyms, ready for the next deterministic score.
