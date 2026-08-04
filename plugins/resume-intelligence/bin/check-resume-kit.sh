#!/usr/bin/env bash
# SessionStart hook for the resume-intelligence plugin.
#
# The plugin's MCP server (resume-kit-mcp) and CLI-backed skills (resume-tool)
# come from the `resume-kit` PyPI package. If that package is not installed the
# commands are missing, so warn the user (never block, never auto-install).
set -euo pipefail

# Installed already? Say nothing and continue.
if command -v resume-kit-mcp >/dev/null 2>&1; then
  exit 0
fi

# Not installed: emit a non-blocking SessionStart warning as valid JSON (no jq).
printf '%s' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"The resume-intelligence plugin needs the resume-kit package, but the resume-kit-mcp / resume-tool commands are not on PATH. Install it with: uv tool install \"resume-kit[all]\"  (or: pip install \"resume-kit[all]\"), then run /reload-plugins. Or run the /resume-intelligence:setup command to install it now.","systemMessage":"resume-kit not installed — run /resume-intelligence:setup or: uv tool install \"resume-kit[all]\""}}'
exit 0
