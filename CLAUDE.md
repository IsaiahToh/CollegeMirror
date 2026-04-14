# CollegeMirror

CollegeMirror automates creation of multi-page pharmaceutical company documents (reports, brochures, product guides) in Adobe InDesign IDML format. Users upload example IDML files paired with the Word docs that sourced their content. The app learns the design patterns and content-to-layout mappings from those examples. When a new Word doc is uploaded, the app generates a new IDML file that follows the same design spirit — with new content, slightly varied styling — ready for the designer to review and finalize in InDesign.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend runtime | Python 3.12+, FastAPI |
| IDML manipulation | `SimpleIDML` + `zipfile` + `lxml` |
| Word parsing | `python-docx` + `mammoth` |
| LLM | Anthropic Claude API (`claude-sonnet-4-6`) |
| Task queue | FastAPI `BackgroundTasks` (→ Celery + Redis later) |
| Frontend | React + Vite + Tailwind CSS |
| Storage | Local filesystem (`./storage/`) — S3 later |
| Config | `pydantic-settings` + `.env` |
| Testing | `pytest` + `pytest-asyncio` |
| Linting / formatting | `ruff` |
| Dependency management | `uv` |

---

## Architecture: Two Phases

**Ingestion phase** (one-time, per example set): IDML files + Word docs → Claude content mapper → `DesignSchema` JSON persisted to disk.

**Generation phase** (per request): New Word doc + `DesignSchema` → Claude layout planner → IDML Writer (clone + substitute) → output IDML.

Rule: Claude handles *reasoning* (which content goes where). The IDML Writer is pure deterministic code — no LLM inside the XML assembly loop.

---

## Folder Structure

```
CollegeMirror/
├── CLAUDE.md
├── pyproject.toml
├── .env / .env.example
├── .gitignore
├── docker-compose.yml
│
├── backend/
│   └── app/
│       ├── main.py                    # FastAPI app entry point
│       ├── api/
│       │   ├── deps.py
│       │   └── routes/
│       │       ├── examples.py        # POST /examples — upload pairs, trigger ingestion
│       │       ├── generate.py        # POST /generate — upload Word doc, return job ID
│       │       └── jobs.py            # GET /jobs/{id} — poll; GET /jobs/{id}/download
│       ├── core/
│       │   ├── config.py              # pydantic-settings
│       │   └── storage.py             # File I/O abstraction
│       ├── idml/
│       │   ├── models.py              # DesignLayout, Spread, TextFrame, ImageFrame, …
│       │   ├── reader.py              # IDML → DesignLayout
│       │   └── writer.py              # LayoutPlan + example IDML → new IDML ZIP
│       ├── word/
│       │   ├── models.py              # WordDocument, Section, Paragraph, Table, Figure
│       │   └── reader.py              # .docx → WordDocument
│       ├── ai/
│       │   ├── client.py              # Single Claude API wrapper (all LLM calls here)
│       │   ├── prompts/
│       │   │   ├── map_content.md     # System prompt: Word → IDML content mapping
│       │   │   └── plan_layout.md     # System prompt: spread-by-spread layout planning
│       │   ├── mapper.py              # Produce ContentMapping from an example pair
│       │   └── planner.py             # Produce LayoutPlan from WordDoc + DesignSchema
│       ├── pipeline/
│       │   ├── ingest.py              # Example ingestion orchestrator
│       │   └── generate.py            # Document generation orchestrator
│       └── models/
│           ├── design_schema.py       # DesignSchema, SemanticRole, FrameTemplate
│           ├── layout_plan.py         # LayoutPlan, SpreadPlan, ContentAssignment
│           └── job.py                 # Job (id, status, output_path, error)
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
│   ├── fixtures/                      # Small stripped IDML + docx files
│   ├── test_idml/
│   ├── test_word/
│   └── test_pipeline/
│
├── storage/                           # Runtime file storage (gitignored)
│   ├── examples/
│   └── jobs/
│
└── examples/                          # Real example pairs (gitignored)
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

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=backend/app --cov-report=term-missing

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run pyright backend/
```

---

## Coding Conventions

### General
- Python 3.12+. Use `match`, `TypeAlias`, and `type` keyword where appropriate.
- All public functions and classes must have type annotations. No `Any` unless unavoidable.
- Use `pydantic` `BaseModel` for all data-carrying structures. No bare dicts between modules.
- Pass dependencies explicitly. No global mutable state.

### IDML / XML
- IDML files are ZIP archives. Open with `zipfile.ZipFile` in read mode; never mutate in-place.
- Use `lxml.etree` for all XML — not `xml.etree.ElementTree`.
- Namespace-qualify all IDML element lookups. Define namespace maps as module-level constants.
- When building output XML, clone source trees and mutate — do not construct documents from scratch.
- Only mutate `<Content>` elements in Stories XML. Never restructure style reference attributes.

### Claude API
- All Claude calls go through `ai/client.py`. Never call `anthropic.Anthropic()` directly in business logic.
- Always enable prompt caching (`cache_control: {"type": "ephemeral"}`) for system prompts and large context blocks (design schemas, example XML).
- Keep prompts in `ai/prompts/*.md` — not inline strings.
- Never log raw LLM responses at INFO — they can contain confidential document content.
- Claude handles reasoning only. No LLM calls inside the IDML XML assembly loop.

### Testing
- Unit tests mock the Claude API. No real API calls in tests.
- Fixture files in `tests/fixtures/` — small, stripped, no real content.
- Test file names mirror source: `idml/reader.py` → `test_idml/test_reader.py`.

### Error Handling
- Raise domain-specific exceptions (`CollegeMirrorError` subclasses) from all public APIs.
- Validate inputs at module boundaries with pydantic. No re-validation internally.
- Never swallow exceptions silently.

---

## Agent Delegation Rules

| Agent | Scope | Must NOT touch |
|---|---|---|
| **IDML agent** | `idml/`, `models/design_schema.py` | Word, AI, pipeline |
| **Word agent** | `word/` | IDML internals, AI |
| **AI/prompt agent** | `ai/`, prompt `.md` files | IDML XML assembly, Word parsing |
| **Pipeline agent** | `pipeline/`, `api/routes/` | Business logic below orchestration |
| **Frontend agent** | `frontend/` | Backend source |
| **Test agent** | `tests/` only | Source files (read-only reference) |

- Agents must read relevant files before editing. Never modify based on assumptions.
- Agents working on IDML output must validate by unzipping and parsing the XML before returning.
- When uncertain about design intent, surface the question rather than guess.
- No agent hardcodes file paths. Use `core/config.py` settings threaded via `core/storage.py`.
