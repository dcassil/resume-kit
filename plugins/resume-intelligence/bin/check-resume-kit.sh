#!/usr/bin/env bash
# SessionStart hook for the resume-intelligence plugin.
#
# The plugin's MCP server (resume-kit-mcp) and CLI-backed skills (resume-tool)
# come from the `resume-kit` PyPI package. If that package is not installed the
# commands are missing, so warn the user (never block, never auto-install).
set -euo pipefail

# Installed already? Then only speak up inside an initialized resume-kit/ working
# dir, to offer the optional advice-only second-agent review ONCE this session.
if command -v resume-kit-mcp >/dev/null 2>&1; then
  # Initialized working dir? config.json under resume-kit/ marks it.
  if [ -f resume-kit/config.json ]; then
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"resume-kit working dir detected. An OPTIONAL, advice-only second-agent review is available via the review-resume skill: it dispatches a subagent to critique the tailored resume against the original resume and the job, and writes ADVICE-ONLY findings to resume-kit/review/<session>.md (it never edits the resume and never auto-runs). Its gate is that a NEW tailored resume, the ORIGINAL resume, and the JOB JSON all exist. OFFER this review to the user AT MOST ONCE this session, and only after a tailored resume exists. Guard the offer with the presence marker resume-kit/.cache/review-offered: if that file exists, do NOT offer again; after you offer (whether the user accepts or declines), create that marker. Always opt-in; never auto-run."}}'
  fi
  exit 0
fi

# Not installed: emit a non-blocking SessionStart warning as valid JSON (no jq).
printf '%s' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"The resume-intelligence plugin needs the resume-kit package, but the resume-kit-mcp / resume-tool commands are not on PATH. Install it with: uv tool install \"resume-kit[all]\"  (or: pip install \"resume-kit[all]\"), then run /reload-plugins. Or run the /resume-intelligence:setup command to install it now.","systemMessage":"resume-kit not installed — run /resume-intelligence:setup or: uv tool install \"resume-kit[all]\""}}'
exit 0
