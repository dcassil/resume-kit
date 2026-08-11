---
name: ingest-job
description: >
  Parse a job and grow terminology learning against an existing prepared-resume
  learning base. Safe to run repeatedly for multiple jobs, and assumes Flow 1
  has run. Best run in a subagent.
---

# ingest-job - reusable Flow 2 job ingest

Flow 2 ingests one job after **prepare-base-resume** has produced a prepared
resume and seeded the durable learning base. It parses the posting into a
canonical `JobDescription`, then grows project terminology learning before any
tailoring checks run. This is the correctly spelled skill for the originally
requested "injest-job" concept.

## Prerequisites

Run the shared **Prerequisites gate** -
[`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** one job posting as pasted text, URL content, or a
  PDF/DOCX/MD/text file.
- **Required prepared resume:** an active prepared resume, normally the
  `refine`/canonical artifact from **prepare-base-resume**, or a recorded
  override that explicitly permits using another canonical resume artifact.
- **Required learning state:** Flow 1 learning must exist from
  `seed-full-resume-evidence`, normally
  `resume-kit/learning/candidate-evidence.json`, so terminology proposals can be
  checked against the prepared resume's evidence base.
- **If either the prepared resume or Flow 1 learning is missing:** STOP and run
  **prepare-base-resume** first. Do not run Flow 2 against an original-only
  resume, and do not require rerunning Flow 1 for each job once the resume is
  prepared.

## The walkthrough

1. **Parse the job.** Run **parse-job** on the provided posting. For file inputs,
   it uses `resume-tool extract-text <file>` before the confined interpretation
   subagent maps the posting to `JobDescription` JSON. For pasted text or URL
   content, it uses that text directly. The output is saved under
   `resume-kit/jobs/<name>-original.json` and recorded as `active_job` through
   `resume-tool set-active --job ... [--job-source ...]`.

   Do not add a new job faithfulness validator. `validate-faithfulness` is for
   `ResumeDocument`; job accuracy remains governed by **parse-job**'s extraction
   gates and schema validation.

2. **Seed or grow terminology before scoring.** Run **seed-terminology** against
   the active prepared resume, the new active job, and the existing Flow 1
   learning base. It calls the deterministic
   `suggest-terminology-candidates` pre-filter to propose JD-keyword/resume-term
   pairs the resume may already satisfy under different wording.

3. **Confirm through learn-terminology.** Every proposed pair must pass
   **learn-terminology**'s truth gate and explicit human confirmation before it
   is written. Never auto-accept candidates, never alias distinct skills, and
   never use terminology learning to make an absent skill score as present.

4. **Append and dedupe the alias index.** Create or grow
   `resume-kit/learning/synonyms.json` using the append rule from
   **learn-terminology**:
   - create the empty RIT-T-0068 shell only when no alias file exists;
   - append only confirmed `{canonical=jd_keyword, alias=resume_phrase, why}`
     pairs;
   - de-duplicate case-insensitively within each canonical group;
   - preserve every prior alias, justification, and provenance entry.

   The operation is a union. It must never drop prior aliases, overwrite the
   file with only this job's pairs, or hand-edit `resume-kit/config.json`.

5. **Register the alias file through code.** If this is the first alias file for
   the project, or if the pointer needs to be refreshed, register it with:

   ```bash
   resume-tool set-active --alias-file learning/synonyms.json
   ```

   The MCP equivalent is `project_set_active` with
   `{"alias_file": "learning/synonyms.json"}`. The file must exist before this
   call; `set-active` validates the pointer and preserves unrelated config keys.

6. **Stop before tailoring.** Do not run **check-keywords**, **check-gaps**,
   **update-keywords**, **update-terminology**, or any Flow 3 tailoring step from
   this skill. Flow 2 ends with the job active and the alias index grown.

## Why this makes the first tailoring score alias-aware

`check-keywords`, `check-gaps`, and `suggest-terminology` all read the active
project `alias_file` when present. Because Flow 2 writes confirmed aliases and
registers `learning/synonyms.json` before the first Flow 3 score, the very first
deterministic tailoring check unions the project synonyms with the built-in seed
lexicon. Genuine wording variants count immediately, without editing the resume
and without adding runtime LLM scoring.

## How to invoke

**Parse the job**

```bash
resume-tool init
resume-tool extract-text <file>                         # file inputs only
resume-tool set-active --job resume-kit/jobs/<name>-original.json [--job-source <file>]
```

For pasted text or URL content, skip extraction and let **parse-job** save the
validated `JobDescription` candidate before calling `set-active`.

**Seed/grow terminology**

```bash
resume-tool suggest-terminology-candidates --resume <refine.json> --job <job.json> [--alias-file <path>]
resume-tool set-active --alias-file learning/synonyms.json
```

**MCP tools:** `resume_suggest_terminology_candidates` for candidate proposal
and `project_set_active` for registering `alias_file`. **learn-terminology** is
agent-driven: it performs the truth gate, human confirmation, append, and dedupe
loop around the proposed pairs.

## Output

The active job points at a valid `JobDescription` JSON, and the project alias
file is created or grown only with user-confirmed, truthful synonyms from the
prepared resume's evidence base. The same prepared resume can run this skill
again for later jobs; each run appends/dedupes terminology learning and leaves
Flow 1 intact.
