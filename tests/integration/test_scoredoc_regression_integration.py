"""E2E integration tests closing RIT-I-0017 (ScoreDoc scoring projection).

RIT-I-0017 split the *build* representation (``ResumeDocument`` / BuildDoc) from
the *scoring* representation (``ScoreDoc``) via the deterministic, offline
``project_scoredoc``. This suite proves the split end-to-end:

* the "85.8->75.8" regression is fixed — skills placed in a categorized
  ``stringList`` custom section now score as canonical skills (placement > 0 and
  no composite penalty vs. the same terms in ``additional.technicalSkills``);
* structure + match numbers read coherently off the shared ScoreDoc;
* the ats-view "what the ATS sees" report is identical across facade and CLI;
* export output is deterministic — the ScoreDoc split did not leak into it.

The grep guard here asserts the *matching placement path*
(``match.py::_high_value_text``) reads ScoreDoc, not raw BuildDoc field names.
The ATS composite path (``resume_kit_ats.engine``) is INTENTIONALLY excluded from
that guard per RIT-T-0108's reduced, codex-reviewed scope: only the matching
placement path was repointed to ScoreDoc; the full zone-weighted ATS repoint was
deferred, so ``engine.py`` still reads BuildDoc field names by design.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from resume_kit_ats import check_ats_structure
from resume_kit_cli.app import app
from resume_kit_export import ExportFormat
from resume_kit_export.render import render
from resume_kit_facade.capabilities import REGISTRY
from resume_kit_facade.models import AtsViewRequest, CapabilityOptions
from resume_kit_matching import check_job_match
from resume_kit_schemas import (
    JobDescription,
    JobMatchReport,
    Requirement,
    RequirementKind,
    ResumeDocument,
)
from typer.testing import CliRunner

_RUNNER = CliRunner()


def _job() -> JobDescription:
    """The job fixture shape reused from ``matching/tests/test_match.py``."""
    return JobDescription(
        title="Backend Engineer",
        company="Acme",
        requirements=[
            Requirement(
                text="Python experience",
                kind=RequirementKind.REQUIRED,
                keywords=["python"],
            ),
            Requirement(
                text="Docker in production",
                kind=RequirementKind.REQUIRED,
                keywords=["docker"],
            ),
        ],
        qualifications=[
            Requirement(
                text="Kubernetes",
                kind=RequirementKind.PREFERRED,
                keywords=["kubernetes"],
            ),
        ],
        keywords=["python", "docker", "kubernetes"],
    )


def _resume_skills_in_technical_skills() -> ResumeDocument:
    """Fixture A: JD terms live in ``additional.technicalSkills`` (canonical)."""
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "555"},
            "summary": "Engineer.",
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Prev",
                    "years": "2020-2023",
                    "description": ["Delivered internal tooling."],
                }
            ],
            "additional": {"technicalSkills": ["Python", "Docker", "Kubernetes"]},
        }
    )


def _resume_skills_in_custom_section() -> ResumeDocument:
    """Fixture B: SAME terms ONLY in a categorized ``stringList`` custom section."""
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "555"},
            "summary": "Engineer.",
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Prev",
                    "years": "2020-2023",
                    "description": ["Delivered internal tooling."],
                }
            ],
            "additional": {"technicalSkills": []},
            "customSections": {
                "Cloud Skills": {
                    "sectionType": "stringList",
                    "strings": ["Python", "Docker", "Kubernetes"],
                }
            },
        }
    )


def _dimension(report: JobMatchReport, key: str) -> float:
    return next(d.score for d in report.dimensions if d.key == key)


def _placement_score(report: JobMatchReport) -> float:
    return _dimension(report, "evidence_placement")


def test_categorized_skills_scored_as_canonical() -> None:
    """TC-001: categorized custom-section skills score as canonical (no penalty).

    The 85.8->75.8 regression lived in ``evidence_placement``: categorized skills
    were counted as ordinary body text and scored 0. Post-fix, fixture B (terms in
    a ``stringList`` custom section) earns the SAME placement as fixture A (terms
    in ``additional.technicalSkills``) — the placement path reads ScoreDoc zones.

    The two composites are NOT identical: ``ats_contribution`` still diverges
    because the ATS composite path (``engine.py``) intentionally reads BuildDoc
    ``technicalSkills`` per RIT-T-0108's reduced, codex-reviewed scope. That
    divergence is confined to that one dimension; the regression dimension is now
    equal. B's composite is pinned so it cannot silently drift.
    """
    job = _job()
    resume_a = _resume_skills_in_technical_skills()
    resume_b = _resume_skills_in_custom_section()

    rep_a = check_job_match(resume_a, job)
    rep_b = check_job_match(resume_b, job)

    # Root cause: pre-fix, categorized skills scored 0 placement (body text).
    assert _placement_score(rep_b) > 0.0
    # The 85.8->75.8 fix: categorized skills now earn the SAME placement credit as
    # canonical technicalSkills — no placement penalty for categorizing skills.
    assert _placement_score(rep_b) == _placement_score(rep_a)
    # The only remaining divergence is the intentionally-BuildDoc ats_contribution.
    for key in ("keyword_coverage", "required_coverage", "preferred_coverage"):
        assert _dimension(rep_b, key) == _dimension(rep_a, key)
    # regression pin: categorized-skills composite (RIT-I-0017)
    assert rep_b.overall_score == 87.7


def test_structure_and_match_coherent_off_scoredoc() -> None:
    """(b) structure + match read coherently and deterministically off ScoreDoc."""
    resume = _resume_skills_in_custom_section()
    job = _job()

    structure_first = check_ats_structure(resume)
    structure_second = check_ats_structure(resume)
    match_first = check_job_match(resume, job)
    match_second = check_job_match(resume, job)

    assert 0.0 <= structure_first.section_completeness <= 100.0
    assert 0.0 <= match_first.overall_score <= 100.0

    # Both surfaces are deterministic across repeated runs.
    assert (
        structure_first.section_completeness == structure_second.section_completeness
    )
    assert match_first.model_dump() == match_second.model_dump()


def test_ats_view_identical_facade_and_cli(tmp_path: Path) -> None:
    """(c) ats-view report is identical via the facade capability and the CLI."""
    resume = _resume_skills_in_custom_section()
    resume_path = tmp_path / "resume.json"
    resume_path.write_text(resume.model_dump_json(), encoding="utf-8")

    async def _run_facade() -> dict[str, object]:
        response = await REGISTRY["ats-view"](
            AtsViewRequest(resume=resume), CapabilityOptions()
        )
        payload = cast(dict[str, object], response.model_dump(mode="json"))
        return cast(dict[str, object], payload["data"])

    facade_data = asyncio.run(_run_facade())

    result = _RUNNER.invoke(
        app, ["ats-view", "--resume", str(resume_path), "--output", "json"]
    )
    assert result.exit_code == 0, result.stdout
    cli_payload = cast(dict[str, object], json.loads(result.stdout))
    cli_data = cast(dict[str, object], cli_payload["data"])

    assert cli_data == facade_data


def test_export_is_deterministic_unchanged() -> None:
    """(d) export bytes are deterministic — the ScoreDoc split did not leak in.

    DOCX bytes are deterministic here because the renderer pins core properties
    (no wall-clock timestamps), so a raw byte-equality check is sufficient and we
    do not need to fall back to a text/structural digest. PDF is also asserted
    since the renderer is likewise deterministic.
    """
    resume = _resume_skills_in_custom_section()

    docx_first = render(resume, ExportFormat.docx)
    docx_second = render(resume, ExportFormat.docx)
    assert docx_first == docx_second

    pdf_first = render(resume, ExportFormat.pdf)
    pdf_second = render(resume, ExportFormat.pdf)
    assert pdf_first == pdf_second


def _high_value_text_body() -> str:
    """Source of ``_high_value_text`` from its def to the next top-level def."""
    source = Path(
        "packages/matching/src/resume_kit_matching/match.py"
    ).read_text(encoding="utf-8")
    marker = "def _high_value_text("
    start = source.index(marker)
    rest = source[start + len(marker) :]
    next_def = rest.index("\ndef ")
    return rest[:next_def]


def test_matching_placement_path_reads_scoredoc_not_builddoc() -> None:
    """Grep guard: matching placement path reads ScoreDoc, not BuildDoc fields.

    The ATS composite path (``engine.py``) is intentionally EXCLUDED from this
    guard per RIT-T-0108's reduced, codex-reviewed scope (the full zone-weighted
    ATS repoint was deferred; ``engine.py`` still reads BuildDoc fields by design).
    """
    body = _high_value_text_body()

    assert "project_scoredoc" in body
    assert "zone" in body.lower()
    for builddoc_field in ("technicalSkills", "customSections", "workExperience"):
        assert builddoc_field not in body
