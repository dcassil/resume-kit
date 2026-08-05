"""Tests for append-only log I/O and the deterministic term-diff helper."""

from __future__ import annotations

from pathlib import Path

from resume_kit_feedback import append_edit_feedback, diff_terms, read_edit_feedback
from resume_kit_schemas import EditFeedback


def _record(edit_id: str, timestamp: str, outcome: str = "accepted") -> EditFeedback:
    return EditFeedback(
        edit_id=edit_id,
        resume_id="r1",
        job_id="j1",
        section="experience",
        edit_type="keyword_substitution",
        original_text="Built things",
        proposed_text="Built scalable services",
        final_text="Built scalable services",
        target_terms=["scalable"],
        matched_job_requirements=["REQ-1"],
        predicted_ats_gain=0.1,
        confidence=0.8,
        outcome=outcome,  # type: ignore[arg-type]
        timestamp=timestamp,
    )


def test_read_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_edit_feedback(base_path=tmp_path) == []


def test_append_creates_file_if_absent(tmp_path: Path) -> None:
    log = tmp_path / "learning" / "edit-feedback.jsonl"
    assert not log.exists()
    append_edit_feedback(_record("e1", "2026-08-04T00:00:00Z"), base_path=tmp_path)
    assert log.exists()


def test_append_read_round_trip(tmp_path: Path) -> None:
    original = _record("e1", "2026-08-04T00:00:00Z")
    append_edit_feedback(original, base_path=tmp_path)
    records = read_edit_feedback(base_path=tmp_path)
    assert len(records) == 1
    assert records[0] == original


def test_append_preserves_prior_lines_and_order(tmp_path: Path) -> None:
    first = _record("e1", "2026-08-04T00:00:00Z", outcome="accepted")
    second = _record("e2", "2026-08-04T01:00:00Z", outcome="rejected")
    third = _record("e3", "2026-08-04T02:00:00Z", outcome="undone")
    append_edit_feedback(first, base_path=tmp_path)
    append_edit_feedback(second, base_path=tmp_path)

    log = tmp_path / "learning" / "edit-feedback.jsonl"
    lines_after_two = log.read_text(encoding="utf-8").splitlines()

    append_edit_feedback(third, base_path=tmp_path)
    lines_after_three = log.read_text(encoding="utf-8").splitlines()

    # The first two lines are byte-for-byte unchanged after the third append.
    assert lines_after_three[:2] == lines_after_two
    assert [r.edit_id for r in read_edit_feedback(base_path=tmp_path)] == ["e1", "e2", "e3"]


def test_one_json_object_per_line(tmp_path: Path) -> None:
    append_edit_feedback(_record("e1", "2026-08-04T00:00:00Z"), base_path=tmp_path)
    append_edit_feedback(_record("e2", "2026-08-04T01:00:00Z"), base_path=tmp_path)
    log = tmp_path / "learning" / "edit-feedback.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_append_serialization_is_deterministic(tmp_path: Path) -> None:
    record = _record("e1", "2026-08-04T00:00:00Z")
    append_edit_feedback(record, base_path=tmp_path / "a")
    append_edit_feedback(record, base_path=tmp_path / "b")
    line_a = (tmp_path / "a" / "learning" / "edit-feedback.jsonl").read_text(encoding="utf-8")
    line_b = (tmp_path / "b" / "learning" / "edit-feedback.jsonl").read_text(encoding="utf-8")
    assert line_a == line_b


def test_diff_terms_basic() -> None:
    preserved, removed, added = diff_terms("Built things fast", "Built scalable things")
    assert preserved == ["Built", "things"]
    assert removed == ["fast"]
    assert added == ["scalable"]


def test_diff_terms_sorted_and_unique() -> None:
    preserved, removed, added = diff_terms("b a a c", "a a b d d")
    assert preserved == ["a", "b"]
    assert removed == ["c"]
    assert added == ["d"]


def test_diff_terms_deterministic() -> None:
    args = ("led team of five engineers", "managed team of six engineers")
    assert diff_terms(*args) == diff_terms(*args)


def test_diff_terms_empty() -> None:
    assert diff_terms("", "") == ([], [], [])
