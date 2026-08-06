---
description: Install the resume-kit package that powers this plugin's MCP tools and CLI-backed skills.
---

Install the `resume-kit` package so this plugin's MCP server (`resume-kit-mcp`)
and the `resume-tool` CLI are available.

Prefer `uv` when it is present; otherwise fall back to `pip`. Run:

```bash
uv tool install "resume-kit[all]"
```

If `uv` is not installed, use pip instead:

```bash
pip install "resume-kit[all]"
```

Then confirm the command now exists:

```bash
resume-kit-mcp --help >/dev/null 2>&1 && echo "resume-kit installed OK"
```

On success, tell the user to run `/reload-plugins` (or restart Claude Code) so
the `resume-kit` MCP server starts and its tools become available.

If installation fails, show the error output and suggest checking that Python
and `uv`/`pip` are available and that PyPI is reachable.

## Deterministic extraction is included in the base install

The base `resume-kit[all]` install already bundles `markitdown`, `pdfminer.six`,
and `python-docx`. The `resume-tool extract --no-llm <file>` CLI can extract
text from PDF, DOCX, Markdown, and plain-text files without any optional extras.
Use this as the primary extraction path in the **parse-resume** and
**parse-job** skills.

The `markitdown[pdf]` optional extra is not required for extraction and does not
need to be installed as part of normal setup.
