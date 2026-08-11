from __future__ import annotations

import base64
from pathlib import Path

import pytest
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_facade.project_config import init_project, set_active, working_dir
from resume_kit_feedback import Candidate, FeatureContext
from resume_kit_mcp.server import TOOLS
from resume_kit_mcp.tools import HANDLERS, TOOL_NAMES
from resume_kit_schemas import (
    CandidateEvidence,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    JobDescription,
    ResumeDocument,
)


def _resume(
    summary: str = "Python engineer with Docker experience.",
) -> dict[str, object]:
    return {
        "personalInfo": {
            "name": "Jane Dev",
            "email": "jane@example.com",
            "phone": "555-1000",
        },
        "summary": summary,
        "workExperience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "years": "2020-2024",
                "description": ["Built Python APIs with Docker."],
            }
        ],
        "additional": {"technicalSkills": ["Python", "Docker"]},
    }


def _job() -> dict[str, object]:
    return {
        "title": "Backend Engineer",
        "company": "Acme",
        "requirements": [
            {
                "text": "Python experience",
                "kind": "required",
                "keywords": ["Python"],
            }
        ],
        "keywords": ["Python", "Docker"],
    }


def _assert_envelope(payload: dict[str, object]) -> None:
    assert set(payload) == {
        "data",
        "warnings",
        "errors",
        "requires_human_input",
        "questions",
        "artifacts",
        "provenance",
    }
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["requires_human_input"], bool)
    assert isinstance(payload["questions"], list)
    assert isinstance(payload["artifacts"], list)
    assert isinstance(payload["provenance"], list)


def _assert_export_envelope(payload: dict[str, object]) -> None:
    assert set(payload) == {
        "data",
        "warnings",
        "errors",
        "requires_human_input",
        "questions",
        "artifacts",
        "provenance",
        "artifact_bytes_base64",
    }
    assert isinstance(payload["artifact_bytes_base64"], str)
    canonical = {key: payload[key] for key in payload if key != "artifact_bytes_base64"}
    _assert_envelope(canonical)


def test_registers_exactly_the_stable_tools() -> None:
    expected = {
        "resume_extract",
        "resume_extract_text",
        "job_description_extract",
        "resume_check_ats",
        "resume_check_ats_structure",
        "resume_check_job_match",
        "resume_select_best",
        "resume_compare_versions",
        "resume_identify_gaps",
        "resume_align",
        "resume_validate_truth",
        "resume_validate_faithfulness",
        "candidate_evidence_build",
        "candidate_evidence_add",
        "edit_feedback_record",
        "requirement_answer_record",
        "edit_candidates_rank",
        "preferences_refresh",
        "edit_session_open",
        "edit_session_prompt",
        "edit_session_decide",
        "edit_session_commit",
        "edit_session_status",
        "edit_session_reconcile",
        "resume_export",
        "resume_suggest_terminology",
        "resume_suggest_terminology_candidates",
        "resume_align_terminology",
        "project_init",
        "project_set_active",
        "resume_build_base",
        "resume_analyze_shape",
        "resume_build_structure",
        "resume_build_standard",
        "resume_build_refine",
        "resume_build_perfect",
        "resume_analyze_best_practices",
        "resume_ats_view",
    }
    assert set(TOOL_NAMES) == expected
    assert set(HANDLERS) == expected
    assert {tool.name for tool in TOOLS} == expected


def _baseline_project(root: Path) -> Path:
    init_project(root)
    base = working_dir(root)
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jordan Lee",
                "title": "Senior Backend Engineer",
                "email": "jordan@example.com",
                "phone": "555-0100",
                "location": "Austin, TX",
            },
            "summary": (
                "Responsible for building Python APIs, Docker services, and "
                "PostgreSQL analytics."
            ),
            "workExperience": [
                {
                    "id": 1,
                    "title": "Senior Software Engineer",
                    "company": "Acme Labs",
                    "years": "2021-2025",
                    "description": [
                        "Responsible for Python APIs with FastAPI and PostgreSQL.",
                        "Containerized services with Docker and automated CI pipelines.",
                    ],
                }
            ],
            "additional": {"technicalSkills": ["Python", "FastAPI", "PostgreSQL", "Docker"]},
        }
    )
    (base / "resumes" / "jordan-original.json").write_text(
        resume.model_dump_json(), encoding="utf-8"
    )
    set_active(root, resume="resumes/jordan-original.json")
    return root


@pytest.mark.parametrize(
    ("name", "arguments", "data_kind"),
    [
        (
            "resume_extract",
            {"content": b"Jane Dev\nPython Engineer", "filename": "cv.txt"},
            type(None),
        ),
        ("job_description_extract", {"raw_text": "Backend Engineer\nPython"}, dict),
        ("resume_check_ats", {"resume": _resume(), "job": _job()}, dict),
        ("resume_check_job_match", {"resume": _resume(), "job": _job()}, dict),
        (
            "resume_select_best",
            {"resumes": [_resume(), _resume("Generalist.")], "job": _job()},
            dict,
        ),
        (
            "resume_compare_versions",
            {"base": _resume(), "candidate": _resume(), "job": _job()},
            dict,
        ),
        (
            "resume_identify_gaps",
            {"job": _job(), "tailored": _resume(), "master": _resume()},
            dict,
        ),
        ("resume_align", {"resume": _resume(), "job": _job()}, dict),
        ("resume_validate_truth", {"resume": _resume(), "evidence": []}, dict),
        ("resume_analyze_shape", {"resume": _resume()}, dict),
        ("candidate_evidence_build", {"resume": _resume()}, list),
    ],
)
async def test_each_deterministic_tool_returns_json_envelope(
    name: str,
    arguments: dict[str, object],
    data_kind: type[object],
) -> None:
    arguments["no_llm"] = True
    payload = await HANDLERS[name](arguments)

    _assert_envelope(payload)
    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    assert isinstance(payload["data"], data_kind)


@pytest.mark.parametrize(
    ("tool_name", "expected_key", "legacy_key"),
    [
        ("resume_build_standard", "standard_path", "refine_path"),
        ("resume_build_refine", "refine_path", "standard_path"),
    ],
)
async def test_build_wording_tools_return_alias_specific_schema(
    tmp_path: Path,
    tool_name: str,
    expected_key: str,
    legacy_key: str,
) -> None:
    root = _baseline_project(tmp_path / tool_name)
    base = await HANDLERS["resume_build_base"]({"root": str(root)})
    _assert_envelope(base)
    assert base["errors"] == []

    payload = await HANDLERS[tool_name]({"root": str(root)})

    _assert_envelope(payload)
    assert payload["errors"] == []
    data = payload["data"]
    assert isinstance(data, dict)
    assert data[expected_key] == "resumes/jordan-refine.json"
    assert legacy_key not in data


async def test_warnings_remain_separate_from_errors() -> None:
    payload = await HANDLERS["resume_extract"](
        {"content": b"Jane Dev\nPython Engineer", "filename": "cv.txt", "no_llm": True}
    )

    _assert_envelope(payload)
    warnings = payload["warnings"]
    assert isinstance(warnings, list)
    assert warnings
    assert payload["errors"] == []


async def test_project_set_active_alias_file_persists(tmp_path: Path) -> None:
    # RIT-T-0167: the advertised alias_file param is real — it persists.
    from resume_kit_facade.project_config import load_config

    init_project(tmp_path)
    alias = tmp_path / "resume-kit" / "learning" / "synonyms.json"
    alias.write_text("{}", encoding="utf-8")
    payload = await HANDLERS["project_set_active"](
        {"alias_file": "learning/synonyms.json", "root": str(tmp_path)}
    )
    _assert_envelope(payload)
    assert payload["errors"] == []
    assert load_config(tmp_path).alias_file == "learning/synonyms.json"


async def test_project_set_active_invalid_alias_file_is_validation(tmp_path: Path) -> None:
    # RIT-T-0167: invalid alias_file → validation error, not internal_error.
    init_project(tmp_path)
    payload = await HANDLERS["project_set_active"](
        {"alias_file": "learning/nope.json", "root": str(tmp_path)}
    )
    errors = payload["errors"]
    assert isinstance(errors, list) and errors
    assert errors[0]["code"] == "validation_failed"


async def test_project_init_does_not_accept_alias_file(tmp_path: Path) -> None:
    # RIT-T-0167 decision: project_init does NOT support alias_file (use
    # project_set_active). Passing it is silently ignored — never persisted.
    from resume_kit_facade.project_config import load_config

    payload = await HANDLERS["project_init"](
        {"alias_file": "learning/synonyms.json", "root": str(tmp_path)}
    )
    _assert_envelope(payload)
    assert payload["errors"] == []
    assert load_config(tmp_path).alias_file is None


async def test_validate_truth_returns_reason_code_fields() -> None:
    payload = await HANDLERS["resume_validate_truth"](
        {"resume": _resume(), "evidence": [], "no_llm": True}
    )

    _assert_envelope(payload)
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["needs_evidence_count"] >= 1
    assert data["claims"][0]["reason_code"] == "missing_evidence"


async def test_resume_align_human_in_loop_surfaces_questions_without_advancing() -> None:
    provider = FakeStructuredCompletionProvider(
        [
            {
                "changes": [
                    {
                        "path": "summary",
                        "action": "replace",
                        "original": "Python engineer with Docker experience.",
                        "value": "Python engineer with Docker experience.",
                        "reason": "No-op review gate test.",
                    }
                ]
            }
        ]
    )

    payload = await HANDLERS["resume_align"](
        {
            "resume": _resume(),
            "job": _job(),
            "provider": provider,
            "human_in_loop": True,
        }
    )

    _assert_envelope(payload)
    assert payload["errors"] == []
    assert payload["requires_human_input"] is True
    assert payload["questions"]
    data = payload["data"]
    assert isinstance(data, dict)
    review_state = data["review_state"]
    assert isinstance(review_state, dict)
    assert review_state["current_section"] == "summary"
    assert review_state["decisions"] == []


@pytest.mark.parametrize(
    ("format_value", "signature"),
    [
        ("pdf", b"%PDF-"),
        ("docx", b"PK"),
    ],
)
async def test_resume_export_returns_envelope_metadata_and_base64_bytes(
    format_value: str,
    signature: bytes,
) -> None:
    payload = await HANDLERS["resume_export"]({"resume": _resume(), "format": format_value})

    _assert_export_envelope(payload)
    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    data = payload["data"]
    artifacts = payload["artifacts"]
    assert isinstance(data, dict)
    assert isinstance(artifacts, list)
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert isinstance(artifact, dict)
    assert data["artifact_id"] == artifact["artifact_id"]
    assert data["artifact_type"] == "resume"
    assert artifact["metadata"] == {"format": format_value}
    raw = base64.b64decode(str(payload["artifact_bytes_base64"]))
    assert raw.startswith(signature)


async def test_resume_export_rejects_invalid_format() -> None:
    payload = await HANDLERS["resume_export"]({"resume": _resume(), "format": "html"})

    _assert_envelope(payload)
    assert payload["data"] is None
    assert payload["errors"]
    error = payload["errors"][0]
    assert isinstance(error, dict)
    assert error["code"] == "invalid_input"
    assert error["details"] == {"field": "format"}


def _feedback() -> dict[str, object]:
    return EditFeedback(
        edit_id="edit-1",
        resume_id="resume-1",
        job_id="job-1",
        section="summary",
        edit_type="keyword_substitution",
        original_text="Built APIs.",
        proposed_text="Built Python APIs.",
        final_text=None,
        predicted_ats_gain=2.0,
        confidence=0.8,
        outcome="rejected",
        reason_code=EditFeedbackReasonCode.NOT_MY_VOICE,
        timestamp="2026-08-05T00:00:00+00:00",
    ).model_dump(mode="json")


async def test_feedback_and_evidence_tools(tmp_path: Path) -> None:
    base = tmp_path / "resume-kit"
    record = await HANDLERS["edit_feedback_record"](
        {"feedback": _feedback(), "base_path": str(base)}
    )
    _assert_envelope(record)
    assert record["errors"] == []
    assert (base / "learning" / "edit-feedback.jsonl").is_file()

    refresh = await HANDLERS["preferences_refresh"](
        {"now": "2026-08-05T00:00:00+00:00", "base_path": str(base)}
    )
    _assert_envelope(refresh)
    assert refresh["errors"] == []

    context = FeatureContext(
        resume=ResumeDocument(summary="Python engineer."),
        job=JobDescription(raw_text="Docker"),
        evidence=[
            CandidateEvidence(
                id="ev-docker",
                kind=EvidenceKind.SKILL,
                content="Docker",
                user_confirmed=True,
            )
        ],
    )
    ranked = await HANDLERS["edit_candidates_rank"](
        {
            "candidates": [
                Candidate(
                    candidate_id="c1",
                    section="skill",
                    proposed_text="Docker",
                ).model_dump(mode="json")
            ],
            "context": context.model_dump(mode="json"),
        }
    )
    _assert_envelope(ranked)
    assert ranked["errors"] == []

    added = await HANDLERS["candidate_evidence_add"](
        {
            "confirmed": True,
            "root": str(tmp_path),
            "content": "Confirmed Docker work",
            "kind": "user_statement",
            "tags": ["Docker"],
            "update_active": True,
        }
    )
    _assert_envelope(added)
    assert added["errors"] == []


async def test_requirement_answer_record_tool(tmp_path: Path) -> None:
    base = tmp_path / "resume-kit"
    written = await HANDLERS["requirement_answer_record"](
        {
            "answer": {
                "requirement_key": "kubernetes",
                "answer": "yes",
                "evidence_ref": "ev-1",
                "ts": "2026-08-10T00:00:00+00:00",
            },
            "base_path": str(base),
        }
    )
    _assert_envelope(written)
    assert written["errors"] == []
    assert (base / "learning" / "requirement-answers.jsonl").is_file()
    assert written["data"]["already_answered"] == "yes"

    read = await HANDLERS["requirement_answer_record"](
        {"query_key": "kubernetes", "base_path": str(base)}
    )
    _assert_envelope(read)
    assert read["errors"] == []
    assert read["data"]["already_answered"] == "yes"
    assert read["data"]["appended"] is None
    assert len(read["data"]["answers"]) == 1


async def test_build_evidence_approved_claims_and_envelope_truth_input() -> None:
    built = await HANDLERS["candidate_evidence_build"](
        {"resume": _resume(), "approved_claims": ["Confirmed Docker work"]}
    )
    _assert_envelope(built)
    assert isinstance(built["data"], list)

    validated = await HANDLERS["resume_validate_truth"](
        {"resume": _resume(), "evidence": {"data": built["data"]}}
    )
    _assert_envelope(validated)
    assert validated["errors"] == []
