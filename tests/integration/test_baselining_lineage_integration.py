"""End-to-end integration for the RIT-I-0016 baselining lineage.

Proves the full ``original -> base -> standard`` lineage over a single fixture
resume, driven through the real CLI transport (the same boundary users hit),
and asserts the three artifacts, the gates, the best-practices classification,
and the config resolution that makes ``standard`` the tailoring default.

The lineage exercised:

    init -> extract-text -> (faithful ResumeDocument) -> validate-faithfulness
         -> set-active -> build-base (auto) -> analyze-best-practices
         -> build-standard (walkthrough answers) -> resolved default = standard

Every step is deterministic and offline. The baselining write paths
(``build-base`` / ``build-standard`` / ``analyze-best-practices``) never
construct a provider and ignore ``--no-llm`` by design, so no live LLM or
network is touched — TC-002 proves this by blocking all sockets and re-running
the lineage.

Note on the "faithfulness gate relative to original" for ``base``: an *edited*
base intentionally strips PII and normalizes presentation, so a source-file
faithfulness check would wrongly reject it. The correct gate — enforced by
``build_base`` and asserted here explicitly — is the **claim-preservation
gate** (``claims_preserved``): no employer/title/degree/skill claim is added,
dropped, or altered. We assert that plus a clean structural check on ``base``.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from resume_kit_ats.engine import check_ats_structure
from resume_kit_cli.app import app
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.best_practices import BestPracticesReport, ResolutionKind
from resume_kit_scoring import claims_preserved, finding_key
from typer.testing import CliRunner

runner = CliRunner()


# Raw source text whose content tokens are a superset of the faithful original
# ResumeDocument's, with every high-signal field value (title / company /
# date-range, institution / degree / years) appearing as a contiguous run and
# exactly one bullet-prefixed line (matching the single JSON description bullet).
_SOURCE_TEXT = (
    "Jordan Rivera\n"
    "Staff Software Engineer\n"
    "jordan@example.com 555-0100\n"
    "Results-driven engineer. SSN 123-45-6789.\n"
    "Staff Software Engineer, Acme Corp, Jan 2020 - Present\n"
    "- Responsible for maintaining the billing platform\n"
    "Python, Go\n"
    "BS Computer Science, MIT, 2016\n"
)


def _original_resume() -> ResumeDocument:
    """A faithful original carrying PII + an inconsistent date (base auto-fixes)
    and a buzzword + weak opener + missing quantification (best-practices)."""
    return ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jordan Rivera",
                "title": "Staff Software Engineer",
                "email": "jordan@example.com",
                "phone": "555-0100",
            },
            "summary": "Results-driven engineer. SSN 123-45-6789.",
            "workExperience": [
                {
                    "id": 1,
                    "title": "Staff Software Engineer",
                    "company": "Acme Corp",
                    "years": "Jan 2020 - Present",
                    "description": ["Responsible for maintaining the billing platform"],
                }
            ],
            "education": [
                {
                    "id": 1,
                    "institution": "MIT",
                    "degree": "BS Computer Science",
                    "years": "2016",
                }
            ],
            "additional": {"technicalSkills": ["Python", "Go"]},
        }
    )


def _init_project(root: Path) -> None:
    result = runner.invoke(app, ["init", "--root", str(root)])
    assert result.exit_code == 0, result.stdout
    assert (root / "resume-kit" / "config.json").is_file()


def _read(root: Path, rel: str) -> ResumeDocument:
    return ResumeDocument.model_validate(
        json.loads((root / "resume-kit" / rel).read_text(encoding="utf-8"))
    )


def test_full_lineage_original_to_base_to_standard(tmp_path: Path) -> None:
    """TC-001: the full lineage over the fixture, end to end through the CLI."""
    _init_project(tmp_path)
    rk = tmp_path / "resume-kit"

    # --- 1) ingest -> original (faithful) ---
    src = tmp_path / "resume.txt"
    src.write_text(_SOURCE_TEXT, encoding="utf-8")
    original_json = rk / "resumes" / "jordan-original.json"
    original_json.write_text(_original_resume().model_dump_json(), encoding="utf-8")

    gate = runner.invoke(
        app, ["validate-faithfulness", "--source", str(src), "--json", str(original_json)]
    )
    assert gate.exit_code == 0, gate.stdout
    report = json.loads(gate.stdout)["data"]
    assert report["passed"] is True
    assert [f for f in report["findings"] if f["severity"] == "error"] == []

    activate = runner.invoke(
        app,
        ["set-active", "--root", str(tmp_path), "--resume",
         "resumes/jordan-original.json", "--source", str(src)],
    )
    assert activate.exit_code == 0, activate.stdout

    # --- 2) build-base (auto): passes the structural check + claim-preservation gate ---
    base = runner.invoke(app, ["build-base", "--root", str(tmp_path)])
    assert base.exit_code == 0, base.stdout
    base_data = json.loads(base.stdout)["data"]
    assert base_data["base_path"] == "resumes/jordan-base.json"
    # auto-safe fixes were applied: PII stripped
    assert "PII_SSN" in base_data["applied"]

    original_doc = _read(tmp_path, "resumes/jordan-original.json")
    base_doc = _read(tmp_path, "resumes/jordan-base.json")
    # claim-preservation gate (the correct "faithfulness" gate for an edited base)
    assert claims_preserved(original_doc, base_doc)
    # base passes the structural check: no error/hard-gate structural findings remain
    base_structure = check_ats_structure(base_doc)
    assert [
        f for f in base_structure.findings if f.severity in ("error", "hard-gate")
    ] == []
    # PII really is gone from base
    assert "123-45-6789" not in (base_doc.summary or "")

    # --- 3) best-practices report: classified auto_suggestible vs needs_user_input ---
    analyze = runner.invoke(
        app, ["analyze-best-practices", "--resume", str(rk / "resumes" / "jordan-base.json")]
    )
    assert analyze.exit_code == 0, analyze.stdout
    bp_report = BestPracticesReport.model_validate(json.loads(analyze.stdout)["data"])
    auto = [f for f in bp_report.findings if f.resolution_kind == ResolutionKind.AUTO_SUGGESTIBLE]
    needs = [f for f in bp_report.findings if f.resolution_kind == ResolutionKind.NEEDS_USER_INPUT]
    # at least one of each class appears for the fixture
    assert auto, "expected >= 1 auto_suggestible finding"
    assert needs, "expected >= 1 needs_user_input finding"

    # --- 4) simulated walkthrough: accept auto items; resolve needs-input with facts ---
    mq = next(f for f in needs if f.rule_code == "MISSING_QUANTIFICATION")
    answers = {finding_key(mq): "Cut billing incidents 40% over two quarters."}
    answers_path = tmp_path / "answers.json"
    answers_path.write_text(json.dumps(answers), encoding="utf-8")

    std = runner.invoke(
        app, ["build-standard", "--root", str(tmp_path), "--answers", str(answers_path)]
    )
    assert std.exit_code == 0, std.stdout
    std_data = json.loads(std.stdout)["data"]
    assert std_data["standard_path"] == "resumes/jordan-standard.json"

    std_doc = _read(tmp_path, "resumes/jordan-standard.json")
    # auto rewrites landed (buzzword + weak opener), user fact applied, claims preserved
    assert "results-driven" not in (std_doc.summary or "").lower()
    assert not std_doc.workExperience[0].description[0].lower().startswith("responsible for")
    assert any("40%" in b for b in std_doc.workExperience[0].description)
    assert claims_preserved(base_doc, std_doc)

    # --- 5) three artifacts exist; config resolves standard as the tailoring default ---
    for rel in (
        "resumes/jordan-original.json",
        "resumes/jordan-base.json",
        "resumes/jordan-standard.json",
    ):
        assert (rk / rel).is_file(), rel

    config = json.loads((rk / "config.json").read_text(encoding="utf-8"))
    assert config["standard_resume"] == "resumes/jordan-standard.json"
    # resolution prefers standard ?? base ?? original
    from resume_kit_facade.project_config import load_config, resolve_active_resume

    assert resolve_active_resume(load_config(tmp_path)) == "resumes/jordan-standard.json"


def test_lineage_is_offline_no_network_no_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-002: the deterministic lineage completes with all sockets blocked.

    The baselining commands never construct a provider; blocking all outbound
    network (DNS resolution + socket connect) proves no live LLM is reached on
    the path. If a step secretly called out, the command would exit non-zero.
    (We block egress rather than socket construction so the asyncio event loop's
    internal self-pipe still works — only real network access fails.)
    """

    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access attempted on the deterministic path")

    _init_project(tmp_path)
    rk = tmp_path / "resume-kit"
    (rk / "resumes" / "jordan-original.json").write_text(
        _original_resume().model_dump_json(), encoding="utf-8"
    )
    runner.invoke(
        app,
        ["set-active", "--root", str(tmp_path), "--resume", "resumes/jordan-original.json"],
    )

    # From here on, any outbound network access is a hard failure.
    monkeypatch.setattr(socket, "getaddrinfo", _no_network)
    monkeypatch.setattr(socket.socket, "connect", _no_network)

    base = runner.invoke(app, ["build-base", "--root", str(tmp_path)])
    assert base.exit_code == 0, base.stdout

    analyze = runner.invoke(
        app, ["analyze-best-practices", "--resume", str(rk / "resumes" / "jordan-base.json")]
    )
    assert analyze.exit_code == 0, analyze.stdout

    std = runner.invoke(app, ["build-standard", "--root", str(tmp_path)])
    assert std.exit_code == 0, std.stdout
    assert (rk / "resumes" / "jordan-standard.json").is_file()
