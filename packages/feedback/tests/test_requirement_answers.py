"""Tests for the RequirementAnswer learning rail (RIT-T-0157)."""

from __future__ import annotations

from pathlib import Path

from resume_kit_feedback import (
    append_requirement_answer,
    is_already_answered,
    load_and_check,
    load_requirement_answers,
    normalize_requirement_key,
)
from resume_kit_schemas import RequirementAnswer
from resume_kit_terms import surface_form


def _answer(
    key: str,
    ans: str,
    *,
    context_tag: str | None = None,
    evidence_ref: str | None = None,
    ts: str = "2026-08-10T00:00:00+00:00",
) -> RequirementAnswer:
    return RequirementAnswer(
        requirement_key=key,
        answer=ans,  # type: ignore[arg-type]
        context_tag=context_tag,
        evidence_ref=evidence_ref,
        ts=ts,
    )


def test_append_and_load_round_trip(tmp_path: Path) -> None:
    r1 = _answer("kubernetes", "yes", evidence_ref="ev-1")
    r2 = _answer("fedramp", "no")
    append_requirement_answer(r1, base_path=tmp_path)
    append_requirement_answer(r2, base_path=tmp_path)

    loaded = load_requirement_answers(base_path=tmp_path)

    assert loaded == [r1, r2]
    log = tmp_path / "learning" / "requirement-answers.jsonl"
    assert log.exists()
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_empty_log_load_returns_empty(tmp_path: Path) -> None:
    assert load_requirement_answers(base_path=tmp_path) == []


def test_normalize_reuses_shared_normalizer() -> None:
    assert normalize_requirement_key("Kubernetes") == surface_form("Kubernetes")
    assert normalize_requirement_key("  K8s!  ") == surface_form("  K8s!  ")


def test_global_yes_suppresses() -> None:
    answers = [_answer("kubernetes", "yes")]
    assert is_already_answered("kubernetes", None, answers) == "yes"
    # context is irrelevant for a global answer
    assert is_already_answered("kubernetes", "ic", answers) == "yes"


def test_global_no_suppresses() -> None:
    answers = [_answer("fedramp", "no")]
    assert is_already_answered("fedramp", None, answers) == "no"
    assert is_already_answered("fedramp", "manager", answers) == "no"


def test_unanswered_key_returns_none() -> None:
    answers = [_answer("kubernetes", "yes")]
    assert is_already_answered("terraform", None, answers) is None


def test_not_in_context_suppresses_on_matching_context() -> None:
    answers = [_answer("management", "not_in_context", context_tag="ic")]
    assert is_already_answered("management", "ic", answers) == "not_in_context"


def test_not_in_context_eligible_on_differing_context() -> None:
    answers = [_answer("management", "not_in_context", context_tag="ic")]
    assert is_already_answered("management", "manager", answers) is None


def test_not_in_context_eligible_on_absent_context() -> None:
    answers = [_answer("management", "not_in_context", context_tag="ic")]
    assert is_already_answered("management", None, answers) is None


def test_last_write_wins_global() -> None:
    answers = [
        _answer("kubernetes", "no", ts="2026-01-01T00:00:00+00:00"),
        _answer("kubernetes", "yes", ts="2026-02-01T00:00:00+00:00"),
    ]
    assert is_already_answered("kubernetes", None, answers) == "yes"


def test_last_write_wins_context_reverses_suppression() -> None:
    # A later not_in_context for a differing context makes the key eligible again,
    # overriding an earlier matching-context suppression.
    answers = [
        _answer("management", "not_in_context", context_tag="ic"),
        _answer("management", "not_in_context", context_tag="manager"),
    ]
    assert is_already_answered("management", "ic", answers) is None
    assert is_already_answered("management", "manager", answers) == "not_in_context"


def test_load_and_check_wrapper(tmp_path: Path) -> None:
    append_requirement_answer(_answer("kubernetes", "yes"), base_path=tmp_path)
    assert load_and_check("kubernetes", None, base_path=tmp_path) == "yes"
    assert load_and_check("terraform", None, base_path=tmp_path) is None
