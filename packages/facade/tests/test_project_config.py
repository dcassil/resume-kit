"""Tests for the code-owned resume-kit/ working-directory state contract.

Covers the RIT-T-0091 acceptance criteria: idempotent ``init_project``,
``set_active`` recording pointer + source, and a config.json carrying an
unrelated preference key surviving a ``set_active`` round-trip unchanged. Also
exercises the two capabilities end-to-end through the facade REGISTRY.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from resume_kit_facade import capabilities as caps
from resume_kit_facade.models import InitProjectRequest, SetActiveRequest
from resume_kit_facade.project_config import (
    CONTENT_DIRS,
    ProjectConfig,
    config_path,
    init_project,
    load_config,
    load_evidence_file,
    save_config,
    save_evidence_file,
    set_active,
    working_dir,
)
from resume_kit_schemas import CandidateEvidence, EvidenceKind

_OPTIONS = caps.CapabilityOptions()


def test_init_creates_full_tree(tmp_path: Path) -> None:
    init_project(tmp_path)
    root = tmp_path / "resume-kit"
    assert (root / "config.json").is_file()
    for name in CONTENT_DIRS:
        assert (root / name).is_dir()


def test_init_is_idempotent_and_preserves_values_between_runs(tmp_path: Path) -> None:
    # TC-001: run init twice; between runs write a value into config.json.
    init_project(tmp_path)
    config = load_config(tmp_path)
    config.active_resume = "resumes/x-original.json"
    save_config(tmp_path, config)
    # Drop a stray file into a content dir to prove content is not deleted.
    stray = tmp_path / "resume-kit" / "resumes" / "keep.json"
    stray.write_text("{}", encoding="utf-8")

    init_project(tmp_path)

    reloaded = load_config(tmp_path)
    assert reloaded.active_resume == "resumes/x-original.json"
    assert stray.is_file()


def test_set_active_records_pointer_and_source(tmp_path: Path) -> None:
    # TC-002: set-active records active_resume + active_resume_source via schema.
    init_project(tmp_path)
    result = set_active(
        tmp_path,
        resume="resumes/x-original.json",
        resume_source="/path/x.docx",
    )
    assert result.active_resume == "resumes/x-original.json"
    assert result.active_resume_source == "/path/x.docx"
    assert result.active_job is None

    on_disk = json.loads(config_path(tmp_path).read_text(encoding="utf-8"))
    assert on_disk["active_resume"] == "resumes/x-original.json"
    assert on_disk["active_resume_source"] == "/path/x.docx"


def test_preference_key_survives_set_active_round_trip(tmp_path: Path) -> None:
    # A config.json with an unrelated preference key (RIT-I-0013) is preserved.
    directory = tmp_path / "resume-kit"
    directory.mkdir()
    (directory / "config.json").write_text(
        json.dumps(
            {
                "active_job": "jobs/j-original.json",
                "preference_learning": {"weights": {"python": 0.9}},
            }
        ),
        encoding="utf-8",
    )

    set_active(tmp_path, resume="resumes/x-original.json", resume_source="/x.pdf")

    on_disk = json.loads(config_path(tmp_path).read_text(encoding="utf-8"))
    # Unknown key preserved verbatim.
    assert on_disk["preference_learning"] == {"weights": {"python": 0.9}}
    # Existing pointer not clobbered.
    assert on_disk["active_job"] == "jobs/j-original.json"
    # New pointer + source recorded.
    assert on_disk["active_resume"] == "resumes/x-original.json"
    assert on_disk["active_resume_source"] == "/x.pdf"


def test_load_preserves_unknown_keys_on_model(tmp_path: Path) -> None:
    directory = tmp_path / "resume-kit"
    directory.mkdir()
    (directory / "config.json").write_text(json.dumps({"future_key": 42}), encoding="utf-8")
    config = load_config(tmp_path)
    dumped = config.model_dump(mode="json")
    assert dumped["future_key"] == 42


def test_set_active_strips_working_dir_prefix(tmp_path: Path) -> None:
    # RIT-T-0127: cwd-relative input (resume-kit/...) is normalized to the
    # working-dir-relative pointer so build-base does not double the prefix.
    init_project(tmp_path)
    result = set_active(
        tmp_path,
        resume="resume-kit/resumes/x-original.json",
        job="resume-kit/jobs/j.json",
    )
    assert result.active_resume == "resumes/x-original.json"
    assert result.active_job == "jobs/j.json"
    # Round-trip: the stored pointer resolves under the working dir, no doubling.
    resolved = working_dir(tmp_path) / result.active_resume
    assert "resume-kit/resume-kit" not in str(resolved)
    assert resolved == working_dir(tmp_path) / "resumes/x-original.json"


def test_set_active_leaves_wd_relative_and_absolute_unchanged(tmp_path: Path) -> None:
    # RIT-T-0127: already-wd-relative and absolute inputs pass through as-is.
    init_project(tmp_path)
    result = set_active(
        tmp_path,
        resume="resumes/x-original.json",
        resume_source="/abs/path/x.docx",
    )
    assert result.active_resume == "resumes/x-original.json"
    assert result.active_resume_source == "/abs/path/x.docx"


def test_set_active_source_without_document_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        set_active(tmp_path, resume_source="/orphan.docx")


def test_set_active_requires_a_document(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        set_active(tmp_path)


def test_project_config_is_extra_allow() -> None:
    config = ProjectConfig.model_validate({"active_resume": "r.json", "extra": "x"})
    assert config.model_dump(mode="json")["extra"] == "x"


def test_project_config_tracks_evidence_pointers() -> None:
    config = ProjectConfig(
        evidence_file="working/user-confirmed-evidence.json",
        active_evidence="working/user-confirmed-evidence.json",
    )
    assert config.evidence_file == "working/user-confirmed-evidence.json"
    assert config.active_evidence == "working/user-confirmed-evidence.json"


def test_evidence_file_round_trips_atomically(tmp_path: Path) -> None:
    path = tmp_path / "resume-kit" / "working" / "evidence.json"
    record = CandidateEvidence(
        id="ev1",
        kind=EvidenceKind.USER_STATEMENT,
        content="Confirmed Docker work",
        user_confirmed=True,
    )
    save_evidence_file(path, [record])
    assert load_evidence_file(path) == [record]


@pytest.mark.asyncio
async def test_init_capability_returns_config(tmp_path: Path) -> None:
    response = await caps.init_project_capability(InitProjectRequest(root=str(tmp_path)), _OPTIONS)
    assert response.errors == []
    assert isinstance(response.data, ProjectConfig)
    assert (tmp_path / "resume-kit" / "config.json").is_file()


@pytest.mark.asyncio
async def test_set_active_capability_records_source(tmp_path: Path) -> None:
    await caps.init_project_capability(InitProjectRequest(root=str(tmp_path)), _OPTIONS)
    response = await caps.set_active_capability(
        SetActiveRequest(
            resume="resumes/x-original.json",
            resume_source="/path/x.docx",
            root=str(tmp_path),
        ),
        _OPTIONS,
    )
    assert response.errors == []
    assert isinstance(response.data, ProjectConfig)
    assert response.data.active_resume_source == "/path/x.docx"


@pytest.mark.asyncio
async def test_set_active_capability_orphan_source_errors(tmp_path: Path) -> None:
    response = await caps.set_active_capability(
        SetActiveRequest(resume_source="/orphan.docx", root=str(tmp_path)), _OPTIONS
    )
    assert response.errors != []


# --- RIT-T-0113: version lineage (original -> base -> standard) ---------------


def test_resolve_active_resume_precedence_and_fallbacks() -> None:
    from resume_kit_facade.project_config import resolve_active_resume

    # legacy: only the original is set -> resolves to the original
    original_only = ProjectConfig(active_resume="resumes/x-original.json")
    assert resolve_active_resume(original_only) == "resumes/x-original.json"

    # base present -> base wins over original
    with_base = ProjectConfig(
        active_resume="resumes/x-original.json",
        base_resume="resumes/x-base.json",
    )
    assert resolve_active_resume(with_base) == "resumes/x-base.json"

    # structure present -> structure wins over base and original
    with_structure = ProjectConfig(
        active_resume="resumes/x-original.json",
        base_resume="resumes/x-base.json",
        structure_resume="resumes/x-structure.json",
    )
    assert resolve_active_resume(with_structure) == "resumes/x-structure.json"

    # standard present -> standard wins over structure, base, and original
    with_standard = ProjectConfig(
        active_resume="resumes/x-original.json",
        base_resume="resumes/x-base.json",
        structure_resume="resumes/x-structure.json",
        standard_resume="resumes/x-standard.json",
    )
    assert resolve_active_resume(with_standard) == "resumes/x-standard.json"

    with_refine = ProjectConfig(
        active_resume="resumes/x-original.json",
        base_resume="resumes/x-base.json",
        structure_resume="resumes/x-structure.json",
        standard_resume="resumes/x-standard.json",
        refine_resume="resumes/x-refine.json",
    )
    assert resolve_active_resume(with_refine) == "resumes/x-refine.json"

    # nothing set -> None
    assert resolve_active_resume(ProjectConfig()) is None


def test_set_version_records_pointers_and_lineage(tmp_path: Path) -> None:
    from resume_kit_facade.project_config import resolve_active_resume, set_version

    set_active(tmp_path, resume="resumes/x-original.json")
    cfg = set_version(
        tmp_path,
        base="resumes/x-base.json",
        base_derived_from="resumes/x-original.json",
    )
    assert cfg.base_resume == "resumes/x-base.json"
    assert cfg.base_derived_from == "resumes/x-original.json"
    # original pointer untouched (additive)
    assert cfg.active_resume == "resumes/x-original.json"
    assert resolve_active_resume(cfg) == "resumes/x-base.json"

    cfg = set_version(
        tmp_path,
        structure="resumes/x-structure.json",
        structure_derived_from="resumes/x-base.json",
    )
    # base pointer preserved across structure write
    assert cfg.base_resume == "resumes/x-base.json"
    assert cfg.structure_resume == "resumes/x-structure.json"
    assert cfg.structure_derived_from == "resumes/x-base.json"
    assert resolve_active_resume(cfg) == "resumes/x-structure.json"

    cfg = set_version(
        tmp_path,
        standard="resumes/x-standard.json",
        standard_derived_from="resumes/x-structure.json",
    )
    # earlier pointers preserved across a later version write
    assert cfg.base_resume == "resumes/x-base.json"
    assert cfg.structure_resume == "resumes/x-structure.json"
    assert cfg.standard_resume == "resumes/x-standard.json"
    assert cfg.standard_derived_from == "resumes/x-structure.json"
    assert resolve_active_resume(cfg) == "resumes/x-standard.json"

    cfg = set_version(
        tmp_path,
        refine="resumes/x-refine.json",
        refine_derived_from="resumes/x-structure.json",
    )
    # legacy standard pointer preserved; refine wins resolution once present
    assert cfg.standard_resume == "resumes/x-standard.json"
    assert cfg.standard_derived_from == "resumes/x-structure.json"
    assert cfg.refine_resume == "resumes/x-refine.json"
    assert cfg.refine_derived_from == "resumes/x-structure.json"
    assert resolve_active_resume(cfg) == "resumes/x-refine.json"


def test_resolve_active_resume_uses_legacy_standard_when_refine_absent() -> None:
    from resume_kit_facade.project_config import resolve_active_resume

    legacy_only = ProjectConfig(
        active_resume="resumes/x-original.json",
        base_resume="resumes/x-base.json",
        structure_resume="resumes/x-structure.json",
        standard_resume="resumes/x-standard.json",
        refine_resume=None,
    )

    assert resolve_active_resume(legacy_only) == "resumes/x-standard.json"


def test_set_version_requires_a_pointer_and_guards_lineage(tmp_path: Path) -> None:
    from resume_kit_facade.project_config import set_version

    with pytest.raises(ValueError):
        set_version(tmp_path)
    with pytest.raises(ValueError):
        set_version(tmp_path, base_derived_from="resumes/x-original.json")
    with pytest.raises(ValueError):
        set_version(tmp_path, structure_derived_from="resumes/x-base.json")
    with pytest.raises(ValueError):
        set_version(tmp_path, refine_derived_from="resumes/x-structure.json")
    with pytest.raises(ValueError):
        set_version(tmp_path, standard_derived_from="resumes/x-base.json")


def test_version_pointers_round_trip_and_preserve_unknown_keys(tmp_path: Path) -> None:
    # A legacy config with an unknown preference key + only the original.
    cfg = ProjectConfig(active_resume="resumes/x-original.json")
    cfg.__pydantic_extra__["preference_state"] = {"weight": 3}  # type: ignore[index]
    save_config(tmp_path, cfg)

    from resume_kit_facade.project_config import set_version

    set_version(tmp_path, base="resumes/x-base.json", base_derived_from="resumes/x-original.json")
    reloaded = load_config(tmp_path)
    # new lineage fields persisted
    assert reloaded.base_resume == "resumes/x-base.json"
    # unknown key survived the version write untouched
    assert reloaded.model_dump()["preference_state"] == {"weight": 3}
    # backward-compat: a config with no base/standard loads with None defaults
    legacy = ProjectConfig.model_validate({"active_resume": "resumes/y-original.json"})
    assert legacy.base_resume is None
    assert legacy.structure_resume is None
    assert legacy.refine_resume is None
    assert legacy.standard_resume is None
