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

## Optional: PDF support for the deterministic extractor

The recommended way to turn a PDF/DOCX/Markdown resume into JSON is the
**resume-to-json** skill (the agent reads the file directly — nothing extra to
install). Only the *deterministic* `resume-tool extract` needs the optional
`markitdown[pdf]` extra to read PDFs. Do **not** install it unless the user
wants it — ask first, then run:

```bash
uv tool install "resume-kit[all]" --with "markitdown[pdf]"
```
