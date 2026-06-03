# CollegeMirror

CollegeMirror automates creation of multi-page pharmaceutical company documents (reports, brochures, product guides) in Adobe InDesign IDML format. Users upload example IDML files paired with the Word docs that sourced their content. The app learns the design patterns and content-to-layout mappings from those examples. When a new Word doc is uploaded, the app generates a new IDML file that follows the same design spirit — with new content, slightly varied styling — ready for the designer to review and finalize in InDesign.

**macOS only** — the InDesign MCP server uses AppleScript to drive InDesign.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend runtime | Python 3.12+, FastAPI |
| IDML reading | `idml/reader_indesign.py` via InDesign MCP (primary) · `idml/reader.py` XML fallback |
| IDML writing | `idml/writer_indesign.py` via InDesign MCP (primary) · `idml/writer.py` XML fallback |
| InDesign automation | `mcp` Python SDK + `indesign-mcp-server` (Node.js, AppleScript) |
| Word parsing | `python-docx` + `mammoth` |
| LLM | Anthropic Claude API (`claude-sonnet-4-6`) or Google Gemini (switchable via `LLM_PROVIDER`) |
| Task queue | FastAPI `BackgroundTasks` (→ Celery + Redis later) |
| Frontend | React + Vite + Tailwind CSS |
| Storage | Local filesystem (`./storage/`) — S3 later |
| Config | `pydantic-settings` + `.env` |
| Testing | `pytest` + `pytest-asyncio` |
| Linting / formatting | `ruff` |
| Dependency management | `uv` |

---

## Architecture: Two Phases

**Ingestion phase** (one-time, per example set): IDML files + Word docs → InDesign MCP extracts authoritative layout → Claude content mapper → `DesignSchema` JSON persisted to disk.

**Generation phase** (per request): New Word doc + `DesignSchema` → Claude layout planner → InDesign MCP writer applies plan and exports IDML → output file.

### InDesign MCP vs XML fallback

Both pipeline functions (`run_ingestion`, `run_generation`) are **async** and select the reader/writer at runtime:

| `INDESIGN_MCP_ENABLED` | Reading | Writing |
|---|---|---|
| `true` | `reader_indesign.py` — InDesign opens IDML, ExtendScript extracts full layout | `writer_indesign.py` — InDesign applies plan, exports IDML |
| `false` (default) | `reader.py` — XML parser (for CI / environments without InDesign) | `writer.py` — XML clone + substitute |

Rule: Claude handles *reasoning* (which content goes where, what the layout plan is). InDesign or the XML writer handles *assembly* — no LLM calls inside the document production loop.

---

## Folder Structure

```
CollegeMirror/
├── CLAUDE.md
├── ARCHITECTURE.md            # detailed data models, API surface, design decisions
├── INSTRUCTIONS.md            # end-user guide (format requirements, how to run)
├── pyproject.toml
├── .env / .env.example
├── .gitignore
├── docker-compose.yml
│
├── backend/
│   └── app/
│       ├── main.py                        # FastAPI app entry point
│       ├── api/
│       │   ├── deps.py
│       │   └── routes/
│       │       ├── examples.py            # POST /examples — upload pairs, trigger ingestion
│       │       ├── generate.py            # POST /generate — upload Word doc, return job ID
│       │       └── jobs.py                # GET /jobs/{id} — poll; GET /jobs/{id}/download
│       ├── core/
│       │   ├── config.py                  # pydantic-settings (incl. InDesign MCP settings)
│       │   └── storage.py                 # File I/O abstraction
│       ├── idml/
│       │   ├── models.py                  # DesignLayout, Spread, TextFrame, ImageFrame, …
│       │   ├── indesign_client.py         # Async MCP client — spawns Node.js server, calls tools
│       │   ├── reader_indesign.py         # InDesign-backed reader (primary): IDML → DesignLayout
│       │   ├── reader.py                  # XML-based reader (fallback / tests)
│       │   ├── writer_indesign.py         # InDesign-backed writer (primary): LayoutPlan → IDML
│       │   └── writer.py                  # XML-based writer (fallback / tests)
│       ├── word/
│       │   ├── models.py                  # WordDocument, Section, Paragraph, Table, Figure
│       │   └── reader.py                  # .docx → WordDocument
│       ├── ai/
│       │   ├── client.py                  # Single LLM wrapper (Anthropic + Gemini)
│       │   ├── prompts/
│       │   │   ├── map_content.md         # System prompt: Word → IDML content mapping
│       │   │   └── plan_layout.md         # System prompt: spread-by-spread layout planning
│       │   ├── mapper.py                  # Produce ContentMapping from an example pair
│       │   └── planner.py                 # Produce LayoutPlan from WordDoc + DesignSchema
│       ├── pipeline/
│       │   ├── ingest.py                  # Async ingestion orchestrator
│       │   └── generate.py                # Async generation orchestrator
│       └── models/
│           ├── design_schema.py           # DesignSchema, SemanticRole, FrameTemplate
│           ├── layout_plan.py             # LayoutPlan, SpreadPlan, ContentAssignment
│           └── job.py                     # Job (id, status, output_path, error)
│
├── frontend/
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx
│       ├── pages/
│       │   ├── ExamplesPage.tsx
│       │   └── GeneratePage.tsx
│       └── components/
│           ├── FileDropzone.tsx
│           ├── JobStatus.tsx
│           └── DownloadButton.tsx
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/                          # Small stripped IDML + docx files (create if missing)
│   ├── test_idml/
│   ├── test_word/
│   └── test_pipeline/
│
├── storage/                               # Runtime file storage (gitignored)
│   ├── examples/
│   └── jobs/
│
└── examples/                              # Real example pairs (gitignored)
```

---

## Commands

```bash
# Install Python dependencies
uv sync --extra dev

# Run backend dev server
uv run uvicorn backend.app.main:app --reload --port 8000

# Run frontend dev server
cd frontend && npm run dev

# Run tests (no InDesign required — uses XML fallback)
uv run pytest

# Run tests with coverage
uv run pytest --cov=backend/app --cov-report=term-missing

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run pyright backend/

# Set up InDesign MCP server (one-time, macOS)
git clone https://github.com/lucdesign/indesign-mcp-server.git
cd indesign-mcp-server && npm install
```

---

## Environment Variables

```env
# LLM provider: "anthropic" (default) or "gemini"
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...          # only needed when LLM_PROVIDER=gemini

# InDesign MCP (macOS only, requires InDesign 2025 running)
INDESIGN_MCP_ENABLED=true
INDESIGN_MCP_SERVER_PATH=/absolute/path/to/indesign-mcp-server/index.js

# Storage / server
STORAGE_PATH=./storage
FRONTEND_URL=http://localhost:5173
LOG_LEVEL=INFO
```

---

## Coding Conventions

### General
- Python 3.12+. Use `match`, `TypeAlias`, and `type` keyword where appropriate.
- All public functions and classes must have type annotations. No `Any` unless unavoidable.
- Use `pydantic` `BaseModel` for all data-carrying structures. No bare dicts between modules.
- Pass dependencies explicitly. No global mutable state.
- Pipeline functions (`run_ingestion`, `run_generation`) are async. Background task wrappers in routes must also be async.

### InDesign MCP
- All InDesign automation goes through `idml/indesign_client.py`. Never call the MCP server directly from business logic.
- The MCP server (`node index.js`) is **spawned per job** by the Python `stdio_client` — it is not a persistent background process. No manual startup required.
- Use `InDesignClient` as an async context manager — one context per job. Do not share sessions across jobs.
- ExtendScript passed to `execute_indesign_code` must suppress UI interaction: `app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT`.
- Wrap every item-level operation in the ExtendScript in `try/catch` — a single bad frame must not abort the whole extraction.
- To embed JSON data in ExtendScript, use `json.dumps(json.dumps(data))` to produce a safe JS string literal: `var x = JSON.parse(<literal>)`.
- Never log raw ExtendScript output at INFO — it may contain document content.
- The InDesign MCP reader and writer both close the document after use (`save=False`). Never leave documents open.

### IDML / XML (fallback path)
- IDML files are ZIP archives. Open with `zipfile.ZipFile` in read mode; never mutate in-place.
- Use `lxml.etree` for all XML — not `xml.etree.ElementTree`.
- Namespace-qualify all IDML element lookups. Define namespace maps as module-level constants.
- When building output XML, clone source trees and mutate — do not construct documents from scratch.
- Story content reconstruction must preserve `ParagraphStyleRange > CharacterStyleRange > Content` nesting. Only set `.text` on `Content` elements; never restructure style reference attributes.

### Claude API
- All LLM calls go through `ai/client.py`. Never call provider SDKs directly in business logic.
- Always enable prompt caching (`cache_control: {"type": "ephemeral"}`) for system prompts and large context blocks.
- Keep prompts in `ai/prompts/*.md` — not inline strings.
- Never log raw LLM responses at INFO — they can contain confidential document content.
- Claude handles reasoning only. No LLM calls inside the document production loop.

### Testing
- Unit tests mock the Claude API and never use InDesign (`INDESIGN_MCP_ENABLED` is always false in tests).
- Fixture files in `tests/fixtures/` — small, stripped, no real content.
- Test file names mirror source: `idml/reader.py` → `test_idml/test_reader.py`.

### Error Handling
- Raise domain-specific exceptions (`CollegeMirrorError` subclasses) from all public APIs.
- `InDesignMCPError` (from `idml/indesign_client.py`) for all InDesign automation failures.
- Validate inputs at module boundaries with pydantic. No re-validation internally.
- Never swallow exceptions silently.

---

## Agent Delegation Rules

| Agent | Scope | Must NOT touch |
|---|---|---|
| **IDML agent** | `idml/`, `models/design_schema.py` | Word, AI, pipeline |
| **Word agent** | `word/` | IDML internals, AI |
| **AI/prompt agent** | `ai/`, prompt `.md` files | IDML assembly, Word parsing |
| **Pipeline agent** | `pipeline/`, `api/routes/` | Business logic below orchestration |
| **Frontend agent** | `frontend/` | Backend source |
| **Test agent** | `tests/` only | Source files (read-only reference) |

- Agents must read relevant files before editing. Never modify based on assumptions.
- Agents working on IDML output must validate by opening the result in InDesign (or unzipping and parsing the XML for the fallback path) before returning.
- When uncertain about design intent, surface the question rather than guess.
- No agent hardcodes file paths. Use `core/config.py` settings threaded via `core/storage.py`.
