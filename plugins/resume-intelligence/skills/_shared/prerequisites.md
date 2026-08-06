# Prerequisites gate (shared convention)

Every resume-intelligence skill that consumes inputs runs this gate **first**,
before doing any work. It is the single, reusable definition each skill points
to; each skill then names its own specific inputs and upstream skills.

## The gate

1. **Locate the working dir.** State lives under `resume-kit/` in the current
   project. Read `resume-kit/config.json` for the active pointers:
   - `active_resume` → path to a `ResumeDocument` JSON (under `resume-kit/resumes/`).
   - `active_job` → path to a `JobDescription` JSON (under `resume-kit/jobs/`).
2. **Resolve every required input** the skill declares — the active pointers
   above plus any skill-specific inputs (a second resume JSON, an evidence file,
   a source document, posting text, etc.). Prefer an explicit path the caller
   passed; otherwise fall back to the matching `config.json` pointer.
3. **If any required input is missing** (no pointer, file absent, or wrong type —
   e.g. a raw PDF where a `ResumeDocument` JSON is required): **STOP**. Do not
   guess, do not fabricate, do not run on partial inputs. Tell the caller exactly
   which input is missing and name the **specific upstream skill** to run first:
   - Need a `ResumeDocument` JSON but only have a resume file → run **parse-resume**.
   - Need a `JobDescription` JSON but only have posting text/URL/file → run **parse-job**.
   - Need `CandidateEvidence` → run **extract-evidence**.
   - Need gap analysis → run **check-gaps**.
4. **Only when all required inputs resolve to valid JSON** do you proceed to the
   skill's own steps.

Conversions (parse-resume / parse-job) are best run in **subagents** so the
large intermediate text stays out of the main context; pass the saved JSON paths
back to this skill.
