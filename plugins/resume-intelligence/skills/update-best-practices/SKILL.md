---
name: update-best-practices
description: >
  DEPRECATED one-release alias for update-refine. The job-independent wording
  pass was renamed from `standard` to `refine` in RIT-I-0020; use
  update-refine to write <name>-refine.json through the build-refine capability.
---

# update-best-practices — DEPRECATED alias

DEPRECATED: this skill remains as a one-release registered alias only.

Use **update-refine** instead. The job-independent wording pass was renamed from
the `standard` pass to the `refine` pass in RIT-I-0020; **update-refine** writes
`resume-kit/resumes/<name>-refine.json` through `resume-tool build-refine`,
preserves the truth/claim-preservation gates, and points config's `refine`
pointer at the result.

Do not start new workflow guidance from this skill name.
