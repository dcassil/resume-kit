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
    save_config,
    set_active,
)

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
    (directory / "config.json").write_text(
        json.dumps({"future_key": 42}), encoding="utf-8"
    )
    config = load_config(tmp_path)
    dumped = config.model_dump(mode="json")
    assert dumped["future_key"] == 42


def test_set_active_source_without_document_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        set_active(tmp_path, resume_source="/orphan.docx")


def test_set_active_requires_a_document(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        set_active(tmp_path)


def test_project_config_is_extra_allow() -> None:
    config = ProjectConfig.model_validate({"active_resume": "r.json", "extra": "x"})
    assert config.model_dump(mode="json")["extra"] == "x"


@pytest.mark.asyncio
async def test_init_capability_returns_config(tmp_path: Path) -> None:
    response = await caps.init_project_capability(
        InitProjectRequest(root=str(tmp_path)), _OPTIONS
    )
    assert response.errors == []
    assert isinstance(response.data, ProjectConfig)
    assert (tmp_path / "resume-kit" / "config.json").is_file()


@pytest.mark.asyncio
async def test_set_active_capability_records_source(tmp_path: Path) -> None:
    await caps.init_project_capability(
        InitProjectRequest(root=str(tmp_path)), _OPTIONS
    )
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
