from __future__ import annotations

import json
from pathlib import Path

import pytest
from resume_kit_facade import capabilities as caps
from resume_kit_facade.models import (
    CapabilityOptions,
    CommitSessionRequest,
    DecideChangeRequest,
    OpenEditSessionRequest,
    SessionStatusRequest,
)
from resume_kit_facade.project_config import init_project, set_active, working_dir
from resume_kit_schemas import (
    ChangeProposal,
    ClaimProvenance,
    JobDescription,
    ProvenanceStatus,
    ResumeDocument,
    ReviewAction,
)


def _resume(summary: str = "Built Python services.") -> ResumeDocument:
    return ResumeDocument(summary=summary)


def _change(
    value: str = "Built Python and FastAPI services.",
    *,
    path: str = "summary",
) -> ChangeProposal:
    return ChangeProposal(
        path=path,
        action="replace",
        original="Built Python services.",
        value=value,
        reason="Mirror job terminology.",
    )


def _setup_project(root: Path) -> None:
    init_project(root)
    base = working_dir(root)
    (base / "resumes" / "daniel-original.json").write_text(
        _resume().model_dump_json(),
        encoding="utf-8",
    )
    (base / "jobs" / "job.json").write_text(
        JobDescription(
            title="Engineer",
            keywords=["Python", "FastAPI"],
            raw_text="Python FastAPI",
        ).model_dump_json(),
        encoding="utf-8",
    )
    set_active(root, resume="resumes/daniel-original.json", job="jobs/job.json")


async def _open(
    root: Path,
    *,
    mode: str = "interactive",
    changes: list[ChangeProposal] | None = None,
    provenance: list[ClaimProvenance] | None = None,
) -> None:
    response = await caps.REGISTRY["open-edit-session"](
        OpenEditSessionRequest(
            root=root,
            mode=mode,
            changes=changes or [_change()],
            claim_provenance=provenance or [],
        ),
        CapabilityOptions(),
    )
    assert not response.errors


@pytest.mark.asyncio
async def test_gate_refuses_unlogged_write(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    await _open(tmp_path)

    response = await caps.REGISTRY["commit-session"](
        CommitSessionRequest(root=tmp_path),
        CapabilityOptions(),
    )

    assert response.errors
    assert response.errors[0].details["gate_code"] == "unlogged_decision"
    assert "summary" in response.errors[0].details["paths"]
    assert not (working_dir(tmp_path) / "working" / "daniel.tailored.json").exists()


@pytest.mark.asyncio
async def test_gate_refuses_truth_failing_accepted_change(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    change = _change("Built fictional quantum services.")
    await _open(
        tmp_path,
        changes=[change],
        provenance=[
            ClaimProvenance(
                claim="Built fictional quantum services.",
                field_path="summary",
                status=ProvenanceStatus.CONTRADICTED,
            )
        ],
    )
    decided = await caps.REGISTRY["decide-change"](
        DecideChangeRequest(
            root=tmp_path,
            path="summary",
            action=ReviewAction.APPROVE,
        ),
        CapabilityOptions(),
    )
    assert not decided.errors

    response = await caps.REGISTRY["commit-session"](
        CommitSessionRequest(root=tmp_path),
        CapabilityOptions(),
    )

    assert response.errors
    assert response.errors[0].details["gate_code"] == "truth_contradicted"
    assert response.errors[0].details["paths"] == ["summary"]


@pytest.mark.asyncio
async def test_auto_mode_defers_judgment_changes(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    supported = _change("Built Python and FastAPI services.", path="summary")
    judgment = ChangeProposal(
        path="additional.technicalSkills",
        action="append",
        original=None,
        value="Kubernetes",
        reason="Add missing skill.",
    )
    await _open(
        tmp_path,
        mode="auto",
        changes=[supported, judgment],
        provenance=[
            ClaimProvenance(
                claim="Built Python and FastAPI services.",
                field_path="summary",
                status=ProvenanceStatus.SUPPORTED,
            )
        ],
    )

    status_response = await caps.REGISTRY["session-status"](
        SessionStatusRequest(root=tmp_path),
        CapabilityOptions(),
    )
    assert not status_response.errors
    assert status_response.data is not None
    assert status_response.data.decided == ["summary"]
    assert status_response.data.deferred == ["additional.technicalSkills"]

    commit_response = await caps.REGISTRY["commit-session"](
        CommitSessionRequest(root=tmp_path),
        CapabilityOptions(),
    )
    assert not commit_response.errors
    written = json.loads(
        (working_dir(tmp_path) / "working" / "daniel.tailored.json").read_text(
            encoding="utf-8"
        )
    )
    assert written["summary"] == "Built Python and FastAPI services."
    assert "Kubernetes" not in written["additional"]["technicalSkills"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["interactive", "review_at_end"])
async def test_reviewed_modes_happy_path(tmp_path: Path, mode: str) -> None:
    _setup_project(tmp_path)
    await _open(tmp_path, mode=mode)
    decided = await caps.REGISTRY["decide-change"](
        DecideChangeRequest(
            root=tmp_path,
            path="summary",
            action=ReviewAction.APPROVE,
        ),
        CapabilityOptions(),
    )
    assert not decided.errors

    committed = await caps.REGISTRY["commit-session"](
        CommitSessionRequest(root=tmp_path),
        CapabilityOptions(),
    )

    assert not committed.errors
    assert committed.data is not None
    assert committed.data.applied[0].path == "summary"


@pytest.mark.asyncio
async def test_auto_mode_happy_path(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    await _open(
        tmp_path,
        mode="auto",
        provenance=[
            ClaimProvenance(
                claim="Built Python and FastAPI services.",
                field_path="summary",
                status=ProvenanceStatus.VERIFIED,
            )
        ],
    )

    committed = await caps.REGISTRY["commit-session"](
        CommitSessionRequest(root=tmp_path),
        CapabilityOptions(),
    )

    assert not committed.errors
    assert committed.data is not None
    assert committed.data.state.committed_hash is not None
