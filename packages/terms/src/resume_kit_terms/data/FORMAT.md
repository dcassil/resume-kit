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

## How RIT-I-0009 (agent-grown index) appends

The agent-grown alias initiative appends new `"<canonical>": [...]` entries — or
extends an existing canonical's alias list — using this exact format. No schema
change is required: the same loader, the same `version: 1`, the same rules. The
ambiguity check (rule 2) is the safety net that catches a bad automated addition
before it can affect scoring.
