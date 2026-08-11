# Config Pointer Contract

This is the shared contract for code-owned pointers in
`resume-kit/config.json`. The field names below are grounded in the
`ProjectConfig` model in
`packages/facade/src/resume_kit_facade/project_config.py`.

`ProjectConfig` allows unknown extra keys so older or future skill metadata can
round-trip through config saves, but skills must not treat an extra key as a
code-owned pointer unless it is declared in `ProjectConfig`.

## Resume Pointers

| Field | Meaning |
|---|---|
| `active_resume` | Original active `ResumeDocument` JSON. This is the immutable source resume pointer used as the last baseline fallback. |
| `base_resume` | ATS-cleaned `base` resume JSON derived from `active_resume`. |
| `structure_resume` | Canonical `structure` resume JSON derived from `base_resume`. |
| `refine_resume` | Job-independent `refine` resume JSON derived from `structure_resume` or `base_resume`; this is the default downstream tailoring input once present. |
| `standard_resume` | Legacy pre-rename read alias for the old job-independent standard pass. New writes use `refine_resume`. |
| `final_resume` | Job-specific final resume JSON produced by the perfect-stage budget fit. It exists in `ProjectConfig`; it is not part of the baseline fallback chain. |

## Lineage Fields

| Field | Meaning |
|---|---|
| `base_derived_from` | Resume path that produced `base_resume`, conventionally `active_resume`. |
| `structure_derived_from` | Resume path that produced `structure_resume`, conventionally `base_resume`. |
| `refine_derived_from` | Resume path that produced `refine_resume`, conventionally `structure_resume` or `base_resume`. |
| `standard_derived_from` | Legacy lineage field for `standard_resume`. New writes use `refine_derived_from`. |
| `final_derived_from` | Resume path that produced `final_resume`, conventionally a tailored working resume. |
| `final_job_id` | Stable job identifier associated with `final_resume`. |

Lineage values are written together with their matching pointer by the
code-owned config helpers. Do not invent a lineage value without the matching
resume pointer.

## Evidence And Alias Pointers

| Field | Meaning |
|---|---|
| `evidence_file` | Default confirmed-evidence JSON file, relative to `resume-kit/` by convention. |
| `active_evidence` | Active evidence JSON file, relative to `resume-kit/` by convention. Prefer this when a skill needs the current Flow 1 learning-evidence file. |
| `alias_file` | Project synonym index passed to synonym-aware deterministic scoring and terminology tools. |

## Job Pointer

| Field | Meaning |
|---|---|
| `active_job` | Active `JobDescription` JSON for job-aware scoring, tailoring, review, and finalization. |

## Source Pointers

| Field | Meaning |
|---|---|
| `active_resume_source` | Original source file, such as the `.docx` or `.pdf`, that produced `active_resume`. |
| `active_job_source` | Original source file, URL capture, or posting file that produced `active_job`. |

## Resolution Order

Baseline resume resolution follows the code-owned `resolve_active_resume`
precedence:

```text
refine_resume -> standard_resume (legacy) -> structure_resume -> base_resume -> active_resume
```

When describing the modern baseline chain, use:

```text
refine -> structure -> base -> original
```

`standard_resume` is only a legacy read alias between `refine_resume` and
`structure_resume`.

`final_resume` is tailored/final output from Flow 4. It records its own lineage
through `final_derived_from` and `final_job_id`, but it does not replace the
baseline resolution order used to choose the prepared resume for tailoring.
