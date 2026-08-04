# Alias lexicon format (`aliases.json`)

The alias lexicon is the curated **true-synonym** layer of the deterministic
matcher. It bridges synonyms that stemming cannot reach — abbreviations
(`k8s` ↔ `Kubernetes`), spelled-out forms (`RLS` ↔ `row-level security`), and
derivational variants Snowball leaves intact (`mentoring` ↔ `mentorship`, since
`-ship` is a derivational, not inflectional, suffix).

It is **not** for morphological variants: `mentor / mentoring / mentored`,
`test / testing / tested`, `architect / architecting` already collapse via the
stemmer in `normalize()`. Only add an entry when stemming genuinely cannot bridge
the two terms.

## Schema

```json
{
  "version": 1,
  "aliases": {
    "<canonical>": ["<alias>", "<alias>", ...],
    ...
  }
}
```

- `version` — integer schema version. Bump only on a breaking format change.
- `aliases` — object mapping each **canonical** term to a list of its **aliases**.
  Canonical and aliases are stored **human-readable**; the loader
  (`AliasIndex.load`) normalizes every entry through `normalize()` on load, so the
  file stays legible while lookups operate on canonical forms.

Within a group, the canonical and all its aliases are **fully interchangeable** —
`match()` reports `kind="alias"` with `canonical` set to the normalized canonical
for any pair drawn from the same group.

## Rules (enforced at load time — violations raise `LexiconError`)

1. **Append-only, additive.** New entries and new aliases may be added freely;
   existing canonicals/aliases should not be repurposed (that would silently
   change historical match provenance).
2. **No ambiguous aliases.** A given normalized term may belong to **exactly one**
   group. Listing the same alias (e.g. `cd`) under two canonicals is rejected —
   it would make matching non-deterministic. Merge such cases into a single group
   instead (e.g. `"continuous delivery": ["cd", "continuous deployment"]`).
3. **No empty normalizations.** A canonical or alias that normalizes to the empty
   string (pure punctuation) is rejected.
4. **Conservative curation.** Only add synonyms that are genuinely unambiguous and
   safe. When in doubt, leave it out — over-broad entries (e.g. treating `Java` as
   an alias of `JavaScript`) cause false matches and are guarded against by the
   anti-over-match tests.

## Project alias file (engine merge hook — RIT-I-0009)

Beyond the packaged seed, the engine can load a **project alias file** and merge
it on top of the seed, so a user/project vocabulary compounds over time. The
project file uses the **same** JSON shape as the seed, plus an OPTIONAL
justification channel:

```json
{
  "version": 1,
  "aliases": {
    "row-level security": ["rls"],
    "feature flag": ["feature toggle"]
  },
  "justifications": {
    "row-level security": "Our docs abbreviate this everywhere as RLS."
  }
}
```

- `aliases` — identical to the seed: canonical → list of human-readable aliases.
- `justifications` — OPTIONAL top-level object mapping a canonical to a free-text
  reason the entry was added (human review / provenance only). It is validated
  for shape (string → string) but is **metadata**: it is dropped on load and can
  NEVER affect matching. Keys need not correspond one-to-one with `aliases`.

The seed file itself may omit `justifications` entirely (back-compatible).

### Merge / conflict rule

`load_effective_alias_index(project_path)` loads the seed, then UNIONs the
project file onto it, keyed by each entry's **normalized canonical**:

- A project entry whose canonical matches an existing seed canonical has its
  aliases **added** to that seed group.
- A project entry with a new canonical creates a **new** group.
- **Conflict (ambiguous):** if a merged term would belong to two DISTINCT
  canonicals, that is genuinely ambiguous and is **rejected** by the existing
  rule-2 guard (`LexiconError`, "term maps to two canonicals"). This is
  order-independent — the union is built from a set and the members are sorted
  before the index is constructed, so the outcome never depends on file or dict
  iteration order (NFR-902).

### No-op & error semantics

- No project path (arg `None` **and** env var unset/empty/whitespace) → effective
  index == seed.
- Resolved path does not exist → no-op (effective == seed).
- Malformed project file → `LexiconError` (never a silent partial load).

### Path resolution precedence

The project-file path is resolved as: **explicit argument > the
`RESUME_KIT_ALIAS_FILE` environment variable > seed-only**. The env indirection
lets a surface (RIT-T-0069) point the engine at the file without changing
`calculate_keyword_match` / `compute_ats_score` signatures. The `matching` and
`ats` engines cache the effective index **keyed on the resolved path string**, so
a changed path yields a fresh index (invalidatable) while a fixed path stays
deterministic.

## How RIT-I-0009 (agent-grown index) appends

The agent-grown alias initiative appends new `"<canonical>": [...]` entries — or
extends an existing canonical's alias list — using this exact format. No schema
change is required: the same loader, the same `version: 1`, the same rules. The
ambiguity check (rule 2) is the safety net that catches a bad automated addition
before it can affect scoring.
