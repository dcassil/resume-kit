"""Resume Kit Feedback — deterministic, offline preference-learning substrate.

No-LLM preference learning over the edit-feedback log
(``resume-kit/learning/edit-feedback.jsonl``). Exposes:

- append-only log I/O + a deterministic whole-term diff (``log``);
- preference-memory derivation with confidence tiers + time decay
  (``preferences``);
- deterministic Preference-RAG retrieval (``retrieval``);
- candidate feature extraction reusing the ats/matching/evidence scorers
  (``features``);
- a pluggable, explainable ranker with an unsupported-claim hard block
  (``ranker``).

Pure and offline: timestamps and any "now" are DATA passed in by callers — this
package never reads the clock, the network, or an LLM.
"""

from .features import Candidate, CandidateSection, FeatureContext, extract_features
from .log import (
    append_edit_feedback,
    append_preference_pair,
    diff_terms,
    read_edit_feedback,
    read_preference_pairs,
)
from .preferences import derive_preferences
from .ranker import (
    DEFAULT_WEIGHTS,
    TRUTH_BLOCK_THRESHOLD,
    HeuristicRanker,
    RankedCandidate,
    Ranker,
)
from .retrieval import EditContext, PreferenceContext, RetrievedEdit, retrieve_preference_context

__version__ = "0.0.0"

__all__ = [
    # log I/O
    "append_edit_feedback",
    "append_preference_pair",
    "diff_terms",
    "read_edit_feedback",
    "read_preference_pairs",
    # preference memory
    "derive_preferences",
    # preference-RAG retrieval
    "EditContext",
    "PreferenceContext",
    "RetrievedEdit",
    "retrieve_preference_context",
    # candidate features
    "Candidate",
    "CandidateSection",
    "FeatureContext",
    "extract_features",
    # ranking
    "Ranker",
    "HeuristicRanker",
    "RankedCandidate",
    "DEFAULT_WEIGHTS",
    "TRUTH_BLOCK_THRESHOLD",
]
