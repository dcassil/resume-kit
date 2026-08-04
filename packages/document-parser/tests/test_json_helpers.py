"""Characterization tests for json_helpers — pure text extraction and JSON parsing.

Covers: fenced JSON, unfenced JSON in surrounding text, generic code fence,
thinking-tag stripping, empty content / empty code block, and nested
message-content extraction. Each test asserts exact results so that any
regression in the extraction logic causes a failure.
"""

from __future__ import annotations

import json
import types

import pytest
from resume_kit_document_parser.json_helpers import (
    _extract_json_str,
    _extract_message_text,
    _strip_thinking_tags,
    extract_response_text,
    parse_response_json,
)

# ---------------------------------------------------------------------------
# _strip_thinking_tags
# ---------------------------------------------------------------------------


def test_strip_thinking_tags_removes_closed_block() -> None:
    content = "<think>internal reasoning</think>The real answer."
    assert _strip_thinking_tags(content) == "The real answer."


def test_strip_thinking_tags_removes_multiline_block() -> None:
    content = "<think>\nline one\nline two\n</think>\nFinal output."
    assert _strip_thinking_tags(content) == "Final output."


def test_strip_thinking_tags_removes_unclosed_tag() -> None:
    content = "Preamble <think>still thinking..."
    assert _strip_thinking_tags(content) == "Preamble"


def test_strip_thinking_tags_no_tags_unchanged() -> None:
    content = "No thinking tags here."
    assert _strip_thinking_tags(content) == content


# ---------------------------------------------------------------------------
# _extract_json_str — raw extraction (returns string)
# ---------------------------------------------------------------------------


def test_extract_json_str_fenced_json_block() -> None:
    content = '```json\n{"key": "value"}\n```'
    result = _extract_json_str(content)
    assert json.loads(result) == {"key": "value"}


def test_extract_json_str_generic_code_fence() -> None:
    content = '```\n{"key": "value"}\n```'
    result = _extract_json_str(content)
    assert json.loads(result) == {"key": "value"}


def test_extract_json_str_unfenced_json_in_prose() -> None:
    content = 'Here is the result: {"name": "Alice", "age": 30} — end.'
    result = _extract_json_str(content)
    assert json.loads(result) == {"name": "Alice", "age": 30}


def test_extract_json_str_plain_json() -> None:
    content = '{"status": "ok"}'
    result = _extract_json_str(content)
    assert json.loads(result) == {"status": "ok"}


def test_extract_json_str_strips_thinking_tags_first() -> None:
    content = '<think>ignore me</think>\n```json\n{"answer": 42}\n```'
    result = _extract_json_str(content)
    assert json.loads(result) == {"answer": 42}


def test_extract_json_str_empty_code_block_raises() -> None:
    content = "```json\n```"
    with pytest.raises((ValueError, json.JSONDecodeError)):
        raw = _extract_json_str(content)
        # If extraction silently returns empty, parsing it should fail.
        json.loads(raw)


def test_extract_json_str_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        _extract_json_str("")


def test_extract_json_str_no_json_raises() -> None:
    with pytest.raises(ValueError, match="No JSON found"):
        _extract_json_str("There is no JSON here at all.")


def test_extract_json_str_nested_object() -> None:
    content = '{"outer": {"inner": [1, 2, 3]}}'
    result = _extract_json_str(content)
    assert json.loads(result) == {"outer": {"inner": [1, 2, 3]}}


# Prove-it-catches-regressions: if brace balancing breaks, this must fail.
def test_extract_json_str_brace_balance_regression() -> None:
    """Only the first complete JSON object should be extracted."""
    content = '{"a": 1} trailing garbage {"b": 2}'
    raw = _extract_json_str(content)
    parsed = json.loads(raw)
    assert parsed == {"a": 1}, (
        "Brace balancer must stop at the first closing brace, not consume trailing objects"
    )


# ---------------------------------------------------------------------------
# parse_response_json — high-level entry point
# ---------------------------------------------------------------------------


def test_parse_response_json_plain_string() -> None:
    result = parse_response_json('{"x": 1}')
    assert result == {"x": 1}


def test_parse_response_json_fenced_string() -> None:
    result = parse_response_json('```json\n{"x": 2}\n```')
    assert result == {"x": 2}


def test_parse_response_json_with_thinking_tags() -> None:
    result = parse_response_json('<think>reasoning</think>\n{"x": 3}')
    assert result == {"x": 3}


def test_parse_response_json_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        parse_response_json("")


def test_parse_response_json_no_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_response_json("No JSON here.")


# ---------------------------------------------------------------------------
# extract_response_text — message / choice / completion structures
# ---------------------------------------------------------------------------


def test_extract_response_text_plain_string() -> None:
    assert extract_response_text("hello") == "hello"


def test_extract_response_text_none_returns_none() -> None:
    assert extract_response_text(None) is None


def test_extract_response_text_dict_message() -> None:
    msg = {"content": "text from dict"}
    assert extract_response_text(msg) == "text from dict"


def test_extract_response_text_object_message() -> None:
    msg = types.SimpleNamespace(content="text from object")
    assert extract_response_text(msg) == "text from object"


def test_extract_response_text_nested_content_list() -> None:
    # Anthropic-style: content is a list of dicts with "text" keys.
    msg = types.SimpleNamespace(content=[{"text": "part one"}, {"text": "part two"}])
    result = extract_response_text(msg)
    assert result == "part one\npart two"


def test_extract_response_text_choice_object() -> None:
    message = types.SimpleNamespace(content="choice content")
    choice = types.SimpleNamespace(message=message)
    assert extract_response_text(choice) == "choice content"


def test_extract_response_text_completion_with_choices() -> None:
    message = types.SimpleNamespace(content="completion text")
    choice = types.SimpleNamespace(message=message, text=None, delta=None)
    completion = types.SimpleNamespace(choices=[choice])
    assert extract_response_text(completion) == "completion text"


def test_extract_response_text_reasoning_content_fallback() -> None:
    # When content is empty, fall back to reasoning_content.
    msg = types.SimpleNamespace(content="", reasoning_content="thought")
    result = extract_response_text(msg)
    assert result == "thought"


# ---------------------------------------------------------------------------
# _extract_message_text — direct unit tests
# ---------------------------------------------------------------------------


def test_extract_message_text_dict_content() -> None:
    msg = {"content": "dict content"}
    assert _extract_message_text(msg) == "dict content"


def test_extract_message_text_thinking_fallback() -> None:
    msg = types.SimpleNamespace(content=None, reasoning_content=None, thinking="deep thought")
    assert _extract_message_text(msg) == "deep thought"


def test_extract_message_text_all_empty_returns_none() -> None:
    msg = types.SimpleNamespace(content=None, reasoning_content=None, thinking=None)
    assert _extract_message_text(msg) is None
