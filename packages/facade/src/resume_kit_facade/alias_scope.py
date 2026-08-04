"""Shared, leak-free scoping of the project alias file for the engines.

The deterministic engines (:mod:`resume_kit_matching`, :mod:`resume_kit_ats`)
resolve a project alias index from the ``RESUME_KIT_ALIAS_FILE`` environment
variable when no explicit path is threaded (precedence contract established by
RIT-T-0068: explicit arg > env var > seed-only).  Their public signatures do
not accept a path, so a surface that wants project-alias-aware scoring points
that env var at a project alias JSON for the duration of one call.

This module provides ONE helper — :func:`use_alias_file` — so every surface
scopes the env var identically and always restores the prior value (including
"was unset") in a ``finally``.  Reusing a single helper prevents cross-surface
divergence and, critically, cross-call env leakage: leaving the variable set
would make a later seed-only call non-deterministic.

Packages remain config-file-agnostic.  A surface receives an already-resolved
``alias_file`` path (the ``resume-kit/config.json`` ``alias_file`` pointer is a
plugin/agent working-dir convention that the skill reads and passes through as
the parameter); nothing here opens ``config.json``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from resume_kit_terms.aliases import PROJECT_ALIAS_ENV_VAR

__all__ = ["use_alias_file"]


@contextmanager
def use_alias_file(path: str | Path | None) -> Iterator[None]:
    """Scope ``RESUME_KIT_ALIAS_FILE`` to *path* for the ``with`` body.

    When *path* is ``None`` this is a no-op that leaves the environment
    untouched — identical seed-only behaviour to before RIT-I-0009.  When a
    path is given the env var is set for the body and restored to its prior
    state (its previous value, or unset if it was unset) in a ``finally``,
    guaranteeing no leakage into any later call.
    """
    if path is None:
        yield
        return

    previous = os.environ.get(PROJECT_ALIAS_ENV_VAR)
    os.environ[PROJECT_ALIAS_ENV_VAR] = str(path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(PROJECT_ALIAS_ENV_VAR, None)
        else:
            os.environ[PROJECT_ALIAS_ENV_VAR] = previous
