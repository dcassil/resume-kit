---
name: update-terminology
description: >
  Section-by-section, human-in-loop terminology update. When a deterministic
  ATS/match/gap run finds a JD keyword the resume already satisfies under a
  DIFFERENT surface form (an ALIAS hit — e.g. resume "k8s", JD "Kubernetes"),
  this workflow proposes mirroring the employer's EXACT wording, presents the
  suggestions grouped by resume section, asks the user to accept/skip each one,
  and applies ONLY the accepted ones — then reports the before/after
  keyword-match delta and exactly what changed. This is truthful mirroring of a
  skill the candidate genuinely has, NOT fabrication: a JD keyword with NO match
  is a GAP and is never rewritten in. Acceptance is truth-gated by the engine
  (validate_resume_truth) regardless. Best run in a subagent.
---

# update-terminology — analyze → present per section → accept/skip → apply → report delta

## Purpose

`check-keyword-match` and `identify-resume-gaps` score a
resume against a job **deterministically** — no LLM at scoring time. When the
resume already demonstrates a job's required skill but under a *different surface
form* (an **alias hit**), the employer's exact wording is missing even though the
underlying skill is present. Mirroring the employer's exact term is a legitimate,
truthful edit that improves ATS keyword match without inventing anything.

This skill is the **agent-side review loop** for those mirrors: it runs the
deterministic terminology-alignment analysis, presents the resulting suggestions
**grouped by resume section**, asks the user to **accept or skip each one**,
applies only the accepted mirrors, and reports the before/after keyword-match
delta plus a per-change log (path, old→new wording). **Scoring stays
deterministic; the agent only presents suggestions and applies accepted ones.**

This is the single-purpose WORDING skill: it only **swaps the surface wording of
a keyword the resume already satisfies**. To add a keyword the resume was
*missing* (present in the master resume but absent from this one), use
**inject-keywords** instead — the two never overlap.

## Prerequisites gate — run this FIRST

Before doing anything, run the shared prerequisites gate defined in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md). This skill's
required inputs are:

- A `ResumeDocument` JSON — the active resume (`config.json` → `active_resume`,
  under `resume-kit/resumes/`), or an explicit path the caller passed.
- A `JobDescription` JSON — the active job (`config.json` → `active_job`, under
  `resume-kit/jobs/`), or an explicit path.
- The project `alias_file` (`config.json` → `alias_file`, default
  `resume-kit/learning/synonyms.json`) — honored so grown synonyms produce
  suggestions (see below). The file may be absent; that is not a blocker.

**If the resume JSON or job JSON is missing, wrong type, or absent: STOP.** Do
not guess, do not run on partial inputs. Name the specific upstream skill:

- Need a `ResumeDocument` JSON but only have a resume file → run **resume-to-json**.
- Need a `JobDescription` JSON but only have posting text/URL/file → run **job-to-json**.

Only when both resume and job resolve to valid JSON do you proceed to the steps
below.

## Run me in a subagent

This is a self-contained, file-mutating task. The main agent should **dispatch it
to a subagent** (e.g. the Task tool / a general-purpose agent), consistent with
`resume-to-json`, `job-to-json`, and `manage-synonyms`. Hand the subagent: the
paths to the resume JSON and job JSON (under `resume-kit/resumes/` and
`resume-kit/jobs/`), the path to `resume-kit/config.json`, and this skill. The
subagent runs the analysis, gets per-suggestion user confirmation, applies the
accepted mirrors, and returns only **what it changed** (path, old→new, delta)
plus what it skipped. Do NOT stream the full resume/job text back into the main
context.

## resume-kit working directory (file convention)

All state lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json          # pointers + preferences; holds alias_file, active_resume
├── resumes/<orig-basename>-original.json
├── jobs/<orig-basename>-original.json
├── working/<session-id>/resume.json   # a revised resume is written here
└── learning/
    └── synonyms.json    # the grown alias index (RIT-T-0068 format)
```

If this skill writes a revised resume, save it under
`resume-kit/working/<session-id>/resume.json` and **update `config.json`'s
`active_resume`** to point at it — mirroring the `resume-to-json` convention so
downstream skills pick up the latest version.

## Honor the project alias index

Alias hits are exactly what makes a suggestion appear, so the grown, user-
confirmed synonym index MUST be honored. Read `resume-kit/config.json`'s
`alias_file` (default `resume-kit/learning/synonyms.json`) and pass it to the
analysis:

- **CLI:** add `--alias-file <path>` to the analyze invocation.
- **MCP:** set the `alias_file` field on the analyze request.

The engine UNIONs the project file over the seed lexicon, so a synonym grown via
`manage-synonyms` produces a mirror suggestion here on the very next run —
deterministically, with no LLM. (Note: stemming is OFF, so only true alias hits
— not stem collisions — produce suggestions.)

## The surfaces this skill drives (RIT-T-0074)

The deterministic terminology-alignment capability is exposed as an
**analyze** surface (list suggestions) and an **apply** surface (apply one
accepted suggestion, returning the before/after delta). Keep the split: analyze
first, then apply only the accepted suggestions one at a time — never auto-apply
the whole set.

- **The terminology-alignment ANALYZE tool** — CLI `suggest-terminology`, MCP
  `resume_suggest_terminology`. Inputs mirror the scoring skills: `resume`, `job`,
  and `alias_file` (see above). Returns the list of mirror suggestions, each
  carrying the resume **section** + path, the current (resume) surface form, and
  the employer's exact target wording.
- **The terminology-alignment APPLY tool** — CLI `align-terminology`, MCP
  `resume_align_terminology`. Takes one accepted suggestion (+ its location) and
  returns the revised resume plus the before/after keyword-match delta for that
  change.

> `resume-tool` is the CLI entrypoint for both commands (e.g.
> `resume-tool suggest-terminology ...`, `resume-tool align-terminology ...`).

## Steps

1. **Honor the alias index.** Read `config.json`'s `alias_file` (default
   `resume-kit/learning/synonyms.json`); you will pass it to the analyze tool.
2. **Analyze.** Run the terminology-alignment analyze tool with the resume, the
   job, and the `alias_file`. It returns the mirror suggestions — one per JD
   keyword the resume satisfies under a different surface form.
3. **Present grouped by resume section.** Organize the suggestions **by the
   resume section they touch** (e.g. Summary, Experience → <role>, Skills). For
   each suggestion show: the section + path, the current wording, the employer's
   exact target wording, and (if available) the per-suggestion match delta.
4. **Accept/skip per suggestion.** For each suggestion, ask the user to
   **accept or skip** it — one at a time or as a reviewable per-section list.
   **Never apply anything without an explicit "accept".** Default is skip.
5. **Apply accepted ones.** For each accepted suggestion, call the
   terminology-alignment apply tool. Acceptance is **truth-gated by the engine
   (`validate_resume_truth`) regardless** — if the engine rejects a change,
   report it and move on; never override the gate.
6. **Persist & report.** If a revised resume was produced, save it under
   `resume-kit/working/<session-id>/resume.json` and update `config.json`'s
   `active_resume`. Then report the **before/after keyword-match delta** and a
   per-change log: for each applied change, the **path** and the **old→new
   wording**; and list every suggestion the user skipped.

## Truth posture — LOAD-BEARING PRODUCT POLICY (do not weaken)

The only thing this skill does is **mirror the employer's exact surface wording
for a skill the candidate GENUINELY has** (the resume already shows it under a
different name). That is truthful. It is NOT a lever to claim skills the
candidate lacks.

### DO — mirror surface wording of a genuine skill

- The resume already demonstrates the skill; the JD just uses a different surface
  form of the same thing. Mirror the employer's exact term.
- **resume "k8s" → JD "Kubernetes"**, `Node` → `Node.js`, `Postgres` →
  `PostgreSQL`, `GHA` → `GitHub Actions`, `CI/CD` → `continuous integration` —
  the identical underlying skill, restated in the employer's words.

### DON'T — these are forbidden

- **Never turn an ABSENT skill into a claimed one.** A JD keyword with **NO
  match** is a **GAP**, not a mirror candidate. Surface it and route the user to
  **`identify-resume-gaps`** — never rewrite an absent skill into the resume to
  close the gap.
- **Never edit identity, employer, or date fields.** Terminology updates only
  restate a skill's surface wording; they never touch names, companies,
  titles-of-record, or dates.
- **Never apply without explicit per-suggestion acceptance**, and never
  auto-apply the whole set. Report every change you make.
- **When in doubt, skip.** If you are not confident the resume's term and the
  JD's term are the same underlying skill for THIS candidate, do not apply —
  leave it for the user and, if it warrants a durable alias, route it through
  `manage-synonyms`.

Acceptance is additionally **truth-gated by the engine (`validate_resume_truth`)
regardless** of user acceptance: the engine is the backstop, not your only line
of defense. Honor the gate; never work around it.

## Gaps vs. terminology updates vs. keyword injection

Do not confuse these:

- **Terminology update** (this skill) — the resume ALREADY satisfies the JD
  keyword under a different surface form (alias hit). Mirroring the employer's
  exact wording is truthful. WORDING only.
- **Keyword injection** (`inject-keywords`) — the JD keyword is absent from THIS
  resume, but the **master resume proves the candidate genuinely has it**
  (injectable). Surfacing it into the skills list / summary is truthful.
- **Gap** (`identify-resume-gaps`) — the JD keyword is absent from the resume
  entirely (no match) AND the master resume does not prove it either. It must be
  **surfaced, never rewritten in** — a real, non-injectable gap.

## Output

The set of mirrors actually applied — each reported as `{section, path, old,
new}` — plus the **before/after keyword-match delta**, and every suggestion the
user skipped. If a revised resume was written, its path under
`resume-kit/working/<session-id>/` and the updated `active_resume` pointer.
Nothing is applied without explicit per-suggestion acceptance; nothing is grown
silently.
