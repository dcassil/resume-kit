# Upstream Audit — Resume-Matcher

> Phase 0 deliverable. This file records reproducible audit evidence; it is not a design document.

---

## Repository Identity

| Field | Value |
|-------|-------|
| Upstream URL | https://github.com/srbhr/Resume-Matcher |
| Pinned full commit SHA | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` |
| License | Apache-2.0 |
| Audit date | 2026-08-03 |

### Clone commands

```sh
# Clone into ./upstream/ (already gitignored via /upstream/ in .gitignore line 30)
git clone https://github.com/srbhr/Resume-Matcher upstream

# Confirm pinned SHA
git -C upstream rev-parse HEAD
# → 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
```

The clone was performed on 2026-08-03. The SHA above is the HEAD of the default branch at that moment. Future clones should pin to this SHA explicitly if exact reproducibility is required:

```sh
git -C upstream checkout 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
```

---

## Backend Test Run

### Setup

| Item | Value |
|------|-------|
| Working directory | `upstream/apps/backend` |
| Python version | 3.13.7 (CPython, darwin) |
| Package manager | pip into an isolated venv (upstream also supports `uv`) |
| Install command | `pip install -e ".[dev]"` |
| Test framework | pytest 9.1.1, pytest-asyncio 1.4.0, respx 0.23.1 |

```sh
# Create isolated venv
python3.13 -m venv /tmp/rm-venv

# Install backend + dev extras
/tmp/rm-venv/bin/pip install -e "/path/to/upstream/apps/backend[dev]"

# Run backend tests (from apps/backend working directory)
cd upstream/apps/backend
/tmp/rm-venv/bin/pytest --tb=short -q
```

The `pyproject.toml` `[tool.pytest.ini_options]` already excludes `eval`-marked tests (those that call a real LLM provider) by default via `addopts = ["-m", "not eval"]`. No extra flags are needed to skip LLM-dependent evals.

### Results

```
531 collected, 1 deselected (eval marker), 530 selected
530 passed, 1 deselected, 7 warnings in 22.73s
```

All 530 selected tests passed. Zero failures, zero errors, zero skips.

### Warnings

Seven warnings were emitted. All originate from `litellm`'s internal logging worker:

```
RuntimeWarning: coroutine 'Logging.async_success_handler' was never awaited
```

These warnings appear in `tests/integration/test_llm_contract.py` tests that exercise the LiteLLM transport layer with `respx` HTTP mocks. They are benign teardown artefacts inside the `litellm` library (a background logging coroutine that is not awaited when the event loop closes at test teardown). They do not indicate test failures and are not caused by resume-kit code.

A post-exit `ValueError: I/O operation on closed file` was also printed by `litellm`'s `logging_worker.py` flush path (same root cause). This is a known upstream litellm issue and is not actionable.

### Environment requirements for tests

The test suite ran to completion **without** any of the following:

- A real LLM API key (all LLM calls are mocked by `respx` or `respx`-backed fixtures)
- A running database server (SQLite on `aiosqlite` is used; tests create in-memory or temp databases via fixtures)
- A running frontend build
- A Playwright/Chromium browser install (PDF render tests mock the Playwright layer)
- Any `.env` file or environment variables

The only external requirement was Python 3.13+ and the packages from `pyproject.toml`.

---

## Runtime and Dependency Requirements

These requirements are relevant to later extraction decisions.

### Database

The backend uses **SQLite via SQLAlchemy async + aiosqlite**. There is no Postgres, MySQL, or Redis dependency. The SQLite file lives at `apps/backend/data/resume_matcher.db` and is created automatically on startup. Tests use in-memory SQLite. **No database server is required.**

### Frontend build

The backend's PDF generation feature (`app/pdf.py`) renders HTML by calling the **frontend** at a `/print/*` URL using a headless Chromium browser (Playwright). This means PDF export requires:
1. The Next.js frontend to be running.
2. Playwright with Chromium installed.

All other backend features (resume parsing, improvement pipeline, job matching, cover letter generation, config, tracker) do **not** require the frontend. The integration test suite mocks the Playwright/Chromium layer (`test_pdf_render.py` patches `app.pdf`), so tests pass without a live frontend or Chromium.

### API keys / LLM provider

LLM calls go through **LiteLLM** (`app/llm.py`). Any OpenAI-compatible provider can be configured. API keys are stored encrypted in the SQLite `api_keys` table (Fernet, key at `data/.secret_key`). No key is needed to run tests; all LLM calls are mocked. In production, at least one LLM provider API key is required.

### Browser

Playwright/Chromium is listed as a runtime dependency for PDF export only. The `playwright` Python package is installed, but `playwright install chromium` must also be run to download the browser binary for production use. Tests mock it away entirely.

### PDF renderer

PDF export uses Playwright to render the frontend print page in headless Chromium — it is not a standalone PDF library. `pdfminer.six` is also present for PDF-to-text extraction (uploaded resume parsing). Both are only relevant for PDF upload/export flows, not for the core improvement pipeline.

### Document parsing

`markitdown[docx]` converts DOCX and PDF files to Markdown. `pdfminer.six` handles PDF text extraction. These are pure Python libraries with no service dependency.

---

## Backend Modules Runnable Without DB or Frontend

The following modules contain pure or near-pure logic with no mandatory DB or frontend coupling. They are good extraction candidates:

| Module | What it does | External deps |
|--------|-------------|---------------|
| `app/prompts/templates.py` | All LLM prompt string constants | None |
| `app/prompts/enrichment.py` | Enrichment-specific prompts | None |
| `app/prompts/resume_wizard.py` | Wizard prompts | None |
| `app/schemas/` (all) | Pydantic request/response models and `ResumeData` | Pydantic only |
| `app/services/parser.py` | `parse_document` (markitdown bytes→Markdown); `parse_resume_to_json` calls LLM but can be injected | markitdown, pdfminer, LiteLLM (for LLM path) |
| `app/services/refiner.py` | Multi-pass polish: keyword injection, AI-phrase removal, alignment check | LiteLLM (mocked in tests) |
| `app/services/improver.py` | Diff-based resume improvement, keyword extraction, skill-target planning | LiteLLM (mocked in tests) |
| `app/services/cover_letter.py` | Cover letter, outreach message, title generation | LiteLLM (mocked in tests) |
| `app/services/ats.py` | ATS scoring logic | Likely LiteLLM |
| `app/services/interview_prep.py` | Interview prep service | Likely LiteLLM |
| `app/llm.py` | LiteLLM wrapper: Router, retries, JSON extraction, timeouts | LiteLLM + a configured provider at runtime |
| `app/crypto.py` | Fernet encrypt/decrypt | `cryptography` package only |
| `app/config.py` / `app/config_cache.py` | Settings singleton; TTL-cached config reads | pydantic-settings, reads `data/config.json` |

Modules that are **tightly coupled** to the DB or frontend and require more work to extract:
- `app/database.py`, `app/db_engine.py`, `app/models.py` — SQLite persistence layer (could be replaced by an interface but contains the schema)
- `app/pdf.py` — requires Playwright + running frontend
- `app/routers/` — HTTP layer; depends on DB and services together
- `app/main.py` — wires everything; requires DB init on startup

---

## Test Coverage by Category

| Directory | Files | Tests collected |
|-----------|-------|----------------|
| `tests/unit/` | 23 files | ~370 |
| `tests/integration/` | 13 files | ~140 |
| `tests/service/` | 1 file | ~18 |
| `tests/evals/` | 1 file | 31 (deselected by default via `-m not eval`) |

Unit tests cover: `apply_diffs`, `crypto`, `database`, `description_styles`, `e2e_monitor_*`, `improve_confirm_hash`, `interview_prep_service`, `llm`, `llm_providers`, `parser`, `prompt_guardrails`, `refiner`, `resume_diff`, `resume_wizard_service`, `settings_timeout`, `verify_diffs`.

Integration tests cover: `applications_api`, `config_api`, `health_api`, `jobs_api`, `llm_contract`, `pdf_render`, `pipeline_e2e`, `regenerate_endpoints`, `resume_api`, `resume_wizard_api`, `tracker_autocreate`, `upload_api`.
