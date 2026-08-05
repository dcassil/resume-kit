"""Code-owned schema and helpers for the ``resume-kit/`` working directory.

Historically the ``resume-kit/`` folder, its ``config.json``, and the
``active_resume`` / ``active_job`` pointers were pure skill conventions: no
package read or wrote them (only ``alias_file`` was threaded as a parameter —
see :mod:`resume_kit_facade.alias_scope`).  That left the agent hand-authoring
``config.json`` — free to drift from the canonical shape — and gave nowhere
machine-readable to record which *source file* a given ``-original.json`` was
converted from.  The faithfulness gate (RIT-T-0092) needs that recorded source
path.

This module gives the working-directory state contract a code owner:

* :class:`ProjectConfig` — a Pydantic v2 model for ``config.json`` covering the
  canonical pointers (``active_resume``, ``active_job``, ``alias_file``) plus
  the per-active-document source paths (``active_resume_source``,
  ``active_job_source``).  It is **backward-compatible**: unknown keys written
  by other skills (e.g. the RIT-I-0013 preference-learning keys) are preserved
  verbatim across a load/save round-trip (``extra="allow"``), and existing
  pointers are never clobbered.
* :func:`init_project` — deterministically and *idempotently* scaffold the
  ``resume-kit/`` tree (``config.json`` + ``resumes/``, ``jobs/``, ``working/``,
  ``learning/``), matching the skill's folder convention.  Re-running never
  overwrites existing pointers or deletes content.
* :func:`set_active` — record an active resume/job pointer plus its originating
  source-file path through the schema.
* :func:`load_config` / :func:`save_config` — the load/atomic-save helpers every
  writer funnels through.  Saves are atomic (temp file + :func:`os.replace`) so
  a crash can never leave a half-written / corrupt ``config.json``.

The layout constants mirror the ``resume-to-json`` skill's documented tree so
existing projects keep working unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict
from resume_kit_schemas import CandidateEvidence

#: The working-directory folder name, relative to a project root.
WORKING_DIR_NAME = "resume-kit"
#: The config file name inside the working directory.
CONFIG_FILE_NAME = "config.json"
#: The content sub-folders scaffolded by :func:`init_project`, in order.
CONTENT_DIRS: tuple[str, ...] = ("resumes", "jobs", "working", "learning")


class ProjectConfig(BaseModel):
    """Machine-owned schema for ``resume-kit/config.json``.

    Only the canonical pointers are declared as fields; every other key a skill
    writes (preference-learning state, future pointers) is tolerated and
    round-tripped verbatim because of ``extra="allow"``.  This guarantees a
    :func:`set_active` (or any other) write never drops keys it does not know
    about and never clobbers an unrelated pointer.

    Attributes:
        active_resume: Path (relative to the working dir, by convention) of the
            resume JSON currently selected as active, or ``None``.
        active_job: Path of the job-description JSON currently active, or ``None``.
        alias_file: Path to the project alias JSON threaded to synonym-aware
            scoring (see :mod:`resume_kit_facade.alias_scope`), or ``None``.
        active_resume_source: The ORIGINAL source file (e.g. the ``.docx`` /
            ``.pdf``) the active resume was converted from, or ``None``.  This
            is the record the faithfulness gate consumes.
        active_job_source: The original source file the active job was converted
            from, or ``None``.
        evidence_file: Path of the default confirmed-evidence JSON file,
            relative to ``resume-kit/`` by convention.
        active_evidence: Path of the active evidence JSON file, relative to
            ``resume-kit/`` by convention.
        base_resume: Path of the ``base`` resume JSON — ``active_resume``
            (original) after ATS structural/format/parse fixes, faithful to the
            original (RIT-I-0016). ``None`` until baselining produces it.
        base_derived_from: The resume path ``base_resume`` was derived from (by
            convention the original ``active_resume``), recording lineage. Only
            written together with ``base_resume``.
        standard_resume: Path of the ``standard`` resume JSON — ``base`` after
            the generic best-practices human-in-the-loop pass (RIT-I-0016). This
            is the default input for all downstream tailoring once present.
            ``None`` until the walkthrough produces it.
        standard_derived_from: The resume path ``standard_resume`` was derived
            from (by convention ``base_resume``), recording lineage. Only written
            together with ``standard_resume``.
    """

    model_config = ConfigDict(extra="allow")

    active_resume: str | None = None
    active_job: str | None = None
    alias_file: str | None = None
    active_resume_source: str | None = None
    active_job_source: str | None = None
    evidence_file: str | None = None
    active_evidence: str | None = None
    base_resume: str | None = None
    base_derived_from: str | None = None
    standard_resume: str | None = None
    standard_derived_from: str | None = None


def working_dir(root: str | Path) -> Path:
    """Return the ``resume-kit/`` working-directory path under *root*."""
    return Path(root) / WORKING_DIR_NAME


def config_path(root: str | Path) -> Path:
    """Return the ``resume-kit/config.json`` path under project *root*."""
    return working_dir(root) / CONFIG_FILE_NAME


def load_config(root: str | Path) -> ProjectConfig:
    """Load ``config.json`` under *root*, or an empty config if absent.

    Unknown keys already present in the file are preserved on the returned
    model (``extra="allow"``), so a later :func:`save_config` round-trips them.
    A missing file yields a default (all-``None``) config — never an error — so
    callers can load-modify-save without a prior :func:`init_project`.
    """
    path = config_path(root)
    if not path.exists():
        return ProjectConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(raw).__name__}.")
    return ProjectConfig.model_validate(raw)


def save_config(root: str | Path, config: ProjectConfig) -> Path:
    """Atomically write *config* to ``config.json`` under *root*.

    The working directory is created if needed.  The write goes to a temp file
    in the same directory and is then :func:`os.replace`-d into place, so a
    crash mid-write cannot corrupt an existing ``config.json`` — a reader always
    sees either the old or the new complete file.  Unknown keys carried on the
    model are serialised back out.  Returns the config file path.
    """
    directory = working_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CONFIG_FILE_NAME
    payload = json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=directory,
        prefix=".config-",
        suffix=".json.tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)
    return path


def atomic_write_json(path: Path, value: object) -> None:
    """Atomically write JSON ``value`` to ``path``.

    Creates the parent directory when needed. The temp file is written beside
    the destination and then moved into place with :func:`os.replace`, matching
    the config save contract.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def load_evidence_file(path: Path) -> list[CandidateEvidence]:
    """Load a JSON evidence file, accepting bare arrays or envelopes."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = raw.get("data") if isinstance(raw, dict) else raw
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain an evidence array or an envelope with data array.")
    return [CandidateEvidence.model_validate(item) for item in payload]


def save_evidence_file(path: Path, evidence: list[CandidateEvidence]) -> None:
    """Atomically write a bare evidence array to ``path``."""
    atomic_write_json(path, [item.model_dump(mode="json") for item in evidence])


def init_project(root: str | Path) -> ProjectConfig:
    """Idempotently scaffold the ``resume-kit/`` tree under *root*.

    Creates ``resume-kit/`` with ``resumes/``, ``jobs/``, ``working/``,
    ``learning/`` and a ``config.json``.  Idempotent: directory creation uses
    ``exist_ok`` and existing content is never deleted; when a ``config.json``
    already exists it is loaded and re-saved unchanged, so existing pointers and
    any unknown (preference) keys survive re-running verbatim.  Returns the
    resulting :class:`ProjectConfig`.
    """
    directory = working_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    for name in CONTENT_DIRS:
        (directory / name).mkdir(parents=True, exist_ok=True)
    config = load_config(root)
    save_config(root, config)
    return config


def set_active(
    root: str | Path,
    *,
    resume: str | None = None,
    resume_source: str | None = None,
    job: str | None = None,
    job_source: str | None = None,
) -> ProjectConfig:
    """Record active resume/job pointers and their source paths through the schema.

    Loads the existing config (preserving unknown keys and any pointer not being
    changed), sets whichever of ``active_resume`` / ``active_job`` (and their
    ``*_source`` companions) were supplied, and saves atomically.  A source is
    only written when its pointer is also supplied — a ``--source`` without the
    matching document is a caller error and raises ``ValueError`` — so the
    recorded source can never drift away from the document it describes.
    Returns the updated :class:`ProjectConfig`.
    """
    if resume is None and job is None:
        raise ValueError("set_active requires at least one of resume or job.")
    if resume_source is not None and resume is None:
        raise ValueError("resume_source given without a resume.")
    if job_source is not None and job is None:
        raise ValueError("job_source given without a job.")
    config = load_config(root)
    if resume is not None:
        config.active_resume = resume
        config.active_resume_source = resume_source
    if job is not None:
        config.active_job = job
        config.active_job_source = job_source
    save_config(root, config)
    return config


def resolve_active_resume(config: ProjectConfig) -> str | None:
    """Resolve the resume path downstream tailoring should consume.

    Implements the version-lineage precedence ``standard -> base -> original``:
    prefer the best-practices-groomed ``standard_resume``, then the ATS-cleaned
    ``base_resume``, then the immutable original ``active_resume``. A project
    that only ever set ``active_resume`` (the pre-RIT-I-0016 world) therefore
    resolves to exactly that original, so this is fully backward-compatible.
    Returns ``None`` only when no resume pointer of any tier is set.
    """
    return config.standard_resume or config.base_resume or config.active_resume


def set_version(
    root: str | Path,
    *,
    base: str | None = None,
    base_derived_from: str | None = None,
    standard: str | None = None,
    standard_derived_from: str | None = None,
) -> ProjectConfig:
    """Record the ``base`` and/or ``standard`` version pointers plus lineage.

    Mirrors :func:`set_active`'s contract: loads the existing config (preserving
    unknown keys and any pointer not being changed), sets whichever of
    ``base_resume`` / ``standard_resume`` (and their ``*_derived_from``
    companions) were supplied, and saves atomically. A ``*_derived_from`` given
    without its matching pointer is a caller error (``ValueError``) so lineage
    can never drift away from the version it describes. Additive: it never
    touches ``active_resume`` (the original). Returns the updated config.
    """
    if base is None and standard is None:
        raise ValueError("set_version requires at least one of base or standard.")
    if base_derived_from is not None and base is None:
        raise ValueError("base_derived_from given without a base.")
    if standard_derived_from is not None and standard is None:
        raise ValueError("standard_derived_from given without a standard.")
    config = load_config(root)
    if base is not None:
        config.base_resume = base
        config.base_derived_from = base_derived_from
    if standard is not None:
        config.standard_resume = standard
        config.standard_derived_from = standard_derived_from
    save_config(root, config)
    return config
