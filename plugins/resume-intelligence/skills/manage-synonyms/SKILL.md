---
name: manage-synonyms
description: >
  The shared truth-gated growth loop for the project synonym index. When a
  deterministic ATS/match/gap run reports a job keyword as "missing" that the
  resume plausibly satisfies under a DIFFERENT surface term, this workflow
  proposes an alias, runs the truthfulness gate, asks the user to confirm, and
  ONLY THEN appends a justified entry to `resume-kit/learning/synonyms.json` so
  future deterministic runs match it automatically. The agent writes DATA;
  scoring stays deterministic and provider-free. Referenced by
  check-keyword-match and identify-resume-gaps. Best run in a subagent.
---

# manage-synonyms — propose → truth-gate → confirm → append aliases

## Purpose

`check-keyword-match` and `identify-resume-gaps` score a
resume against a job **deterministically** — no LLM at scoring time. Matching
uses a packaged seed lexicon UNIONed with an optional **project alias file**
(`resume-kit/learning/synonyms.json`, RIT-T-0068 format). When a scoring run
marks a job keyword as "missing" but the resume already demonstrates that exact
skill under a different name, the deterministic engine simply doesn't know the
two terms are the same thing yet.

This skill is the **agent-side growth loop** that teaches it: the agent PROPOSES
a synonym, the user CONFIRMS it, and the agent APPENDS a justified alias to the
project file. From then on the deterministic run matches it — no LLM required at
scoring time, ever. **The agent only writes data; it never makes scoring smarter
at runtime.**

Define the workflow ONCE (here) so the three scoring skills link to it rather
than copy-pasting divergent copies.

## Run me in a subagent

This is a self-contained, file-mutating task. The main agent should **dispatch it
to a subagent** (e.g. the Task tool / a general-purpose agent), consistent with
`resume-to-json` and `job-to-json`. Hand the subagent: the list of candidate
`(missing job keyword, resume term it may equal)` pairs, the path to
`resume-kit/config.json`, and this skill. The subagent runs the gate, gets user
confirmation, appends → and returns only **what it added** (canonical, alias,
why) plus what it rejected/deferred. Do NOT stream the full resume/job text back
into the main context.

## Before you start: read prior learnings

Read `resume-kit/learning/manage-synonyms.md` (if it exists) first — it
accumulates gotchas from earlier runs (terms you previously rejected, house
rules the user set). When you learn something new (a pair the user rejected, a
recurring false candidate), append it there so the next run does not re-propose
it.

## The alias file (target) — `resume-kit/learning/synonyms.json`

- **Where:** the path is `config.json`'s `alias_file` key. **Read
  `resume-kit/config.json` and use its `alias_file` value; default to
  `resume-kit/learning/synonyms.json` if the key is absent.** This is the SAME
  file the scoring skills pass to the engine (see "Honoring the grown index"
  below), so growth and scoring stay in lock-step.
- **Format (RIT-T-0068):**

  ```jsonc
  {
    "version": 1,
    "aliases": {
      "<canonical>": ["<alias>", "..."]      // canonical -> list of surface forms that mean the same skill
    },
    "justifications": {
      "<canonical>": "one-line why these are the same underlying skill/fact"
    }
  }
  ```

- `justifications` is OPTIONAL metadata (canonical → one-line why). It NEVER
  affects matching; it exists so a human can audit and prune the file. Every
  entry this workflow records MUST carry one anyway (see append rule).
- **Project aliases UNION with the seed** — you only ever ADD; you never need to
  restate seed pairs. Keep the file small, human-readable, and prunable.
- **Create the file if absent** with a valid empty shell:
  `{"version": 1, "aliases": {}, "justifications": {}}` — then append into it.

## Steps

1. **Collect candidates.** From the calling scoring run, take each job keyword
   reported as *missing* AND for which the resume plausibly demonstrates the same
   skill under a different surface term. (If nothing plausibly matches, stop —
   there is nothing to propose.)
2. **Run the truthfulness gate** (below) on each candidate. Reject or defer
   anything that does not clearly pass.
3. **Propose to the user** the surviving `{canonical, alias, why}` triples and
   ask for **explicit confirmation** — one at a time or as a reviewable list.
   Never append without a "yes".
4. **Append** each confirmed triple idempotently to the alias file (append rule
   below), creating the file if needed.
5. **Report exactly what you added** (canonical, alias, why for each), plus what
   you rejected/deferred and why. Never grow the file silently.
6. **Append any new learning** to `resume-kit/learning/manage-synonyms.md`.

## Truthfulness gate — LOAD-BEARING PRODUCT POLICY (do not weaken)

The entire point of the project alias file is to match **genuine synonyms of the
SAME underlying skill or fact** that the deterministic seed happened to miss. It
is NOT a lever to inflate a score. A bad alias makes the resume claim a skill the
candidate does not have — that is dishonest and defeats the tool. When in doubt,
**do NOT add** — surface the ambiguity to the user instead.

### DO propose an alias when the two terms name the SAME skill/fact

- The candidate genuinely has the skill, and the job's term is just a different
  surface form of what the resume already shows.
- **NetSuite ↔ SuiteCommerce** — where the resume's NetSuite/SuiteCommerce work
  is truly the same platform capability the job's term refers to.
- **"k8s" ↔ "Kubernetes"** — abbreviation / expansion of the identical
  technology.
- Other same-skill forms: `Node` ↔ `Node.js`, `Postgres` ↔ `PostgreSQL`,
  `CI/CD` ↔ `continuous integration`, `GHA` ↔ `GitHub Actions`.

### DON'T — these are forbidden

- **React ≈ Vue → REJECT.** React and Vue are *distinct skills*, not surface
  forms of one skill. Aliasing them would make a React-only resume falsely score
  as satisfying a Vue requirement. Never do this. (Same for Angular ≈ React,
  MySQL ≈ PostgreSQL as *requirements*, AWS ≈ GCP, Java ≈ JavaScript, etc.)
- **Never alias to make an ABSENT skill score as present.** If the job wants
  Kubernetes and the resume shows no container-orchestration experience at all,
  do NOT alias some unrelated term to "Kubernetes" to close the gap. A missing
  skill is a real gap — report it; do not paper over it.
- **Never broaden scope.** Do not alias a narrow term to a broader one (or vice
  versa) so unrelated experience counts — e.g. do not alias "wrote a bash
  script" to "DevOps", or "used Docker once" to "Kubernetes".
- **Ambiguous → do NOT add.** If you are not confident the two terms are the same
  underlying skill/fact for THIS candidate, do not add it. Surface it to the user
  and let them decide; record their decision as a learning.

Every alias you record must have a truthful one-line `why` that a human could
read and agree with. If you cannot write an honest `why`, the alias fails the
gate.

## Append rule — idempotent, justified, prunable

For each **confirmed** `{canonical, alias, why}`:

1. Load the alias file (create the empty shell if absent).
2. Ensure `aliases[canonical]` exists (a list). **Add `alias` to it only if it is
   not already present** (case-insensitive de-dup) — appends are IDEMPOTENT, no
   duplicate alias within a group. If the exact alias is already there, record
   nothing new for it.
3. Set `justifications[canonical] = why` (the one-line justification). If a
   justification already exists for that canonical, keep the clearer of the two
   (do not silently discard a human-authored one).
4. Write the file back as pretty-printed JSON so it stays human-readable and
   prunable.
5. Preserve `"version": 1` and any existing entries untouched.

**Choosing canonical vs alias:** use the **job's keyword** (the term scoring
looks for) as the `canonical` and the **resume's surface term** as the `alias`,
so the engine maps the resume's wording onto what the job asks for. If the file
already has a group for one of the two terms, add into that existing group rather
than creating a parallel one.

Example — the resume says "SuiteCommerce", the job asks for "NetSuite", user
confirms they are the same platform work:

```jsonc
{
  "version": 1,
  "aliases": {
    "NetSuite": ["SuiteCommerce"]
  },
  "justifications": {
    "NetSuite": "SuiteCommerce is NetSuite's commerce platform; the resume's SuiteCommerce work is NetSuite experience"
  }
}
```

## Honoring the grown index in scoring runs

So a recorded alias actually changes the next deterministic score, the scoring
skills must point the engine at this same file. Read `config.json`'s `alias_file`
(default `resume-kit/learning/synonyms.json`) and pass it to the capability:

- **CLI:** add `--alias-file <path>` to the `resume-tool check-ats` / `match` /
  `identify-gaps` invocation.
- **MCP:** set the `alias_file` field on the `resume_check_ats` /
  `resume_check_job_match` / `resume_identify_gaps` request to that path.

The engine UNIONs the file over the seed, so a freshly-recorded synonym is
matched on the very next run — deterministically, with no LLM.

## resume-kit working directory (file convention)

State lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json          # pointers + preferences; holds alias_file (default learning/synonyms.json)
├── resumes/<orig-basename>-original.json
├── jobs/<orig-basename>-original.json
├── working/<session-id>/resume.json
└── learning/
    ├── synonyms.json     # THIS workflow's append target (RIT-T-0068 format)
    └── manage-synonyms.md # accumulated hints (read first, append when you learn)
```

## Output

The set of aliases actually recorded — each reported as `{canonical, alias,
why}` — plus anything rejected or deferred and why. The updated
`resume-kit/learning/synonyms.json` (valid RIT-T-0068 JSON), grown ONLY with
user-confirmed, truthful synonyms, ready for the next deterministic scoring run.
