"""Pure text-extraction and JSON-fence parsing helpers for LLM responses.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/llm.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# License: Apache-2.0
# Modified: Extracted pure response-text helpers (_extract_text_parts,
#   _join_text_parts, _extract_message_text, _safe_get, _extract_choice_text,
#   _to_code_block, _strip_thinking_tags, _extract_json) into a standalone
#   module with no app.*, LiteLLM, or network coupling. Safety constants and
#   public parse_response_json() entry-point added.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

# Safety limits (mirrored from upstream)
_MAX_JSON_EXTRACTION_RECURSION = 10
_MAX_JSON_CONTENT_SIZE = 1024 * 1024  # 1 MB


# ---------------------------------------------------------------------------
# Internal text-extraction helpers
# ---------------------------------------------------------------------------


def _extract_text_parts(value: Any, depth: int = 0, max_depth: int = 10) -> list[str]:
    """Recursively extract text segments from nested response structures.

    Handles strings, lists, dicts with 'text'/'content'/'value' keys, and
    objects with text/content attributes. Limits recursion depth to avoid
    cycles.

    Args:
        value: Input value that may contain text in strings, lists, dicts,
            or objects.
        depth: Current recursion depth.
        max_depth: Maximum recursion depth before returning no content.

    Returns:
        A list of extracted text segments.
    """
    if depth >= max_depth:
        return []

    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        parts: list[str] = []
        next_depth = depth + 1
        for item in value:
            parts.extend(_extract_text_parts(item, next_depth, max_depth))
        return parts

    if isinstance(value, dict):
        next_depth = depth + 1
        if "text" in value:
            return _extract_text_parts(value.get("text"), next_depth, max_depth)
        if "content" in value:
            return _extract_text_parts(value.get("content"), next_depth, max_depth)
        if "value" in value:
            return _extract_text_parts(value.get("value"), next_depth, max_depth)
        return []

    next_depth = depth + 1
    if hasattr(value, "text"):
        return _extract_text_parts(value.text, next_depth, max_depth)
    if hasattr(value, "content"):
        return _extract_text_parts(value.content, next_depth, max_depth)

    return []


def _join_text_parts(parts: list[str]) -> str | None:
    """Join text parts with newlines, filtering empty strings.

    Args:
        parts: Candidate text segments.

    Returns:
        Joined string or None if the result is empty.
    """
    joined = "\n".join(part for part in parts if part).strip()
    return joined or None


def _safe_get(obj: Any, key: str) -> Any:
    """Get attribute or dict key from an object."""
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key)
    return None


def _extract_message_text(message: Any) -> str | None:
    """Extract plain text from a message object across providers.

    Fallback order:
      1. message.content (standard OpenAI-compatible path)
      2. message.reasoning_content (DeepSeek R1, OpenAI o1/o3 via LiteLLM
         standardized field)
      3. message.thinking (Anthropic extended thinking)

    Reasoning-only responses are treated as valid content so thinking models
    can be used without special-casing them in every call site.
    """
    content: Any = None

    if hasattr(message, "content"):
        content = message.content
    elif isinstance(message, dict):
        content = message.get("content")

    text = _join_text_parts(_extract_text_parts(content))
    if text:
        return text

    # Fallback: reasoning_content (DeepSeek R1, OpenAI o1/o3).
    reasoning = _safe_get(message, "reasoning_content")
    text = _join_text_parts(_extract_text_parts(reasoning))
    if text:
        return text

    # Fallback: thinking (Anthropic extended thinking).
    thinking = _safe_get(message, "thinking")
    return _join_text_parts(_extract_text_parts(thinking))


def _extract_choice_text(choice: Any) -> str | None:
    """Extract plain text from a choice object.

    Tries message.content first, then choice.text, then choice.delta. Handles
    both object attributes and dict keys.
    """
    content = _extract_message_text(_safe_get(choice, "message"))
    if content:
        return content

    for field in ("text", "delta"):
        value = _safe_get(choice, field)
        if value is not None:
            extracted = _join_text_parts(_extract_text_parts(value))
            if extracted:
                return extracted

    return None


def _to_code_block(content: str | None, language: str = "text") -> str:
    """Wrap content in a markdown code block for display."""
    text = (content or "").strip()
    if not text:
        text = "<empty>"
    return f"```{language}\n{text}\n```"


# ---------------------------------------------------------------------------
# Thinking-tag stripping
# ---------------------------------------------------------------------------


def _strip_thinking_tags(content: str) -> str:
    """Strip thinking/reasoning tags from model output.

    Ollama thinking models (deepseek-r1, qwq, etc.) wrap their reasoning in
    <think>...</think> tags. The actual answer follows after the closing tag.
    Strip these so JSON extraction finds the real output.
    """
    # Remove <think>...</think> blocks (including multiline).
    stripped = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    # Also handle unclosed <think> tag (model may still be "thinking" at end).
    stripped = re.sub(r"<think>.*", "", stripped, flags=re.DOTALL)
    return stripped.strip()


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------


def _extract_json_str(content: str, _depth: int = 0) -> str:
    """Extract a raw JSON string from an LLM response.

    Handles fenced ```json blocks, generic code fences, unfenced JSON embedded
    in surrounding prose, and thinking-tag stripping. Raises ``ValueError`` if
    no JSON object is found or safety limits are exceeded.

    Args:
        content: Raw text from the model response.
        _depth: Internal recursion counter; callers should not set this.

    Returns:
        The extracted JSON string (not yet parsed).

    Raises:
        ValueError: When no JSON object can be located or limits are breached.
    """
    if _depth > _MAX_JSON_EXTRACTION_RECURSION:
        raise ValueError(
            f"JSON extraction exceeded max recursion depth: {_depth}"
        )
    if len(content) > _MAX_JSON_CONTENT_SIZE:
        raise ValueError(
            f"Content too large for JSON extraction: {len(content)} bytes"
        )

    original = content

    # Strip thinking model tags (deepseek-r1, qwq, etc.)
    if "<think>" in content:
        content = _strip_thinking_tags(content)

    # Remove markdown code blocks.
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
            # Remove language identifier if present (e.g., "json\n{...").
            if content.startswith(("json", "JSON")):
                content = content[4:]

    content = content.strip()

    # If content starts with {, find the matching }.
    if content.startswith("{"):
        depth = 0
        end_idx = -1
        in_string = False
        escape_next = False

        for i, char in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break

        if end_idx == -1 and depth != 0:
            logging.warning(
                "JSON extraction found unbalanced braces (depth=%d), possible truncation",
                depth,
            )

        if end_idx != -1:
            return content[: end_idx + 1]

    # Try to find JSON object in the content (only if not already at start).
    start_idx = content.find("{")
    if start_idx > 0:
        return _extract_json_str(content[start_idx:], _depth + 1)

    logging.error(
        "Could not extract JSON from response format. Content preview: %s",
        content[:200] if content else "<empty>",
    )
    raise ValueError(f"No JSON found in response: {original[:200]}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_response_text(response: Any) -> str | None:
    """Extract plain text from a raw model response object.

    Accepts a plain string, a message object/dict, a choice object/dict, or a
    completion object/dict that contains a ``choices`` list. Returns the first
    non-empty text found, or ``None``.

    Args:
        response: The raw object returned by any provider adapter.

    Returns:
        Extracted text string, or ``None`` if nothing could be found.
    """
    if response is None:
        return None

    if isinstance(response, str):
        return response or None

    # Full completion object: try choices list first.
    choices = _safe_get(response, "choices")
    if choices and isinstance(choices, list) and len(choices) > 0:
        text = _extract_choice_text(choices[0])
        if text:
            return text

    # Maybe it IS a choice directly.
    text = _extract_choice_text(response)
    if text:
        return text

    # Maybe it IS a message directly.
    return _extract_message_text(response)


def parse_response_json(response: Any) -> dict[str, Any]:
    """Extract and parse the first JSON object from a model response.

    Accepts anything that ``extract_response_text`` accepts, plus a plain
    string. Strips ``<think>`` tags, handles fenced and unfenced JSON, and
    returns a parsed dict.

    Args:
        response: Raw model response (string, message, choice, or completion).

    Returns:
        Parsed JSON as ``dict[str, Any]``.

    Raises:
        ValueError: When no JSON object can be located in the response text.
        json.JSONDecodeError: When the extracted text is not valid JSON.
    """
    raw_text = response if isinstance(response, str) else extract_response_text(response)

    if not raw_text:
        raise ValueError("Response contains no extractable text")

    json_str = _extract_json_str(raw_text)
    result: dict[str, Any] = json.loads(json_str)
    return result
