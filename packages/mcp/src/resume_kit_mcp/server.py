"""Official MCP SDK server for Resume Kit facade capabilities."""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.server.context import ServerRequestContext

from mcp import types
from resume_kit_mcp.tools import HANDLERS, TOOL_NAMES, ToolArguments, ToolResult

_INPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "no_llm": {"type": "boolean"},
        "strict": {"type": "boolean"},
        "human_in_loop": {"type": "boolean"},
    },
}


def _tool(name: str) -> types.Tool:
    return types.Tool(
        name=name,
        description=f"Run the resume-kit {name} capability.",
        input_schema=_INPUT_SCHEMA,
    )


TOOLS: tuple[types.Tool, ...] = tuple(_tool(name) for name in TOOL_NAMES)


def _arguments(arguments: dict[str, object] | None) -> ToolArguments:
    if arguments is None:
        return {}
    return dict(arguments)


def _is_error(result: ToolResult) -> bool:
    errors = result.get("errors")
    return isinstance(errors, list) and bool(errors)


def _call_result(result: ToolResult) -> types.CallToolResult:
    return types.CallToolResult(
        content=[
            types.TextContent(
                text=json.dumps(result, sort_keys=True),
            )
        ],
        structured_content=result,
        is_error=_is_error(result),
    )


async def list_tools(
    context: ServerRequestContext[object, object],
    params: types.PaginatedRequestParams | None,
) -> types.ListToolsResult:
    _ = context, params
    return types.ListToolsResult(tools=list(TOOLS))


async def call_tool(
    context: ServerRequestContext[object, object],
    params: types.CallToolRequestParams,
) -> types.CallToolResult:
    _ = context
    handler = HANDLERS.get(params.name)
    if handler is None:
        result: ToolResult = {
            "data": None,
            "warnings": [],
            "errors": [
                {
                    "code": "invalid_input",
                    "message": f"Unknown tool '{params.name}'.",
                    "details": {"tool": params.name},
                }
            ],
            "requires_human_input": False,
            "questions": [],
            "artifacts": [],
            "provenance": [],
        }
        return _call_result(result)
    result = await handler(_arguments(params.arguments))
    return _call_result(result)


server: Server[object] = Server(
    "resume-kit",
    version="0.0.0",
    on_list_tools=list_tools,
    on_call_tool=call_tool,
)
