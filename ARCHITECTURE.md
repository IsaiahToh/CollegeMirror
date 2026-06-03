# CollegeMirror — Architecture

> **Living document.** Update this file whenever a module's responsibility, data contract, or connection to other modules changes. The goal is that a new contributor can read this and understand how the whole system fits together without needing to ask.

---

## Overview

CollegeMirror turns the pain of re-creating pharmaceutical company InDesign documents into a two-step upload flow. Users provide example IDML files alongside the Word docs that produced them — the app learns the design vocabulary from those examples, then applies it to any new Word doc, generating a ready-to-review IDML file.

The key property of the system: **Claude reasons about layout, InDesign (or deterministic code) builds it.** No LLM call sits inside the document production loop.

**macOS only** — the InDesign MCP server uses AppleScript to drive InDesign.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend runtime | Python 3.12+ / FastAPI | Async I/O for file uploads and MCP communication |
| IDML reading (primary) | `idml/reader_indesign.py` via InDesign MCP | InDesign resolves transforms, style inheritance, threading natively — authoritative |
| IDML reading (fallback) | `idml/reader.py` — `zipfile` + `lxml` | No InDesign required; used in CI and tests |
| IDML writing (primary) | `idml/writer_indesign.py` via InDesign MCP | InDesign handles reflow, overflow detection, font validation |
| IDML writing (fallback) | `idml/writer.py` — `lxml` XML clone | No InDesign required; used in CI and tests |
| InDesign automation | `mcp` Python SDK + `indesign-mcp-server` (Node.js) | MCP server spawned per-job via stdio; drives InDesign via AppleScript + ExtendScript |
| Word parsing | `python-docx` | Structural heading/para/table/image extraction from .docx |
| LLM | `anthropic` SDK (`claude-sonnet-4-6`) or `google-generativeai` (Gemini) | Switchable via `LLM_PROVIDER`; both produce structured JSON via tool use / response schema |
| Async jobs | FastAPI `BackgroundTasks` | Generation takes 30–120s; avoids HTTP timeout without Celery overhead at MVP |
| Storage | Local filesystem (`./storage/`) | No infra dependency for MVP; paths abstracted behind `Storage` class for later S3 swap |
| Config | `pydantic-settings` | Type-safe; reads from `.env` |
| Frontend | React + Vite + Tailwind CSS | Upload/poll/download flow |
| Deps | `uv` | Fast, deterministic |
| Lint/format | `ruff` | Single tool for lint + format |
| Tests | `pytest` + `pytest-asyncio` | Claude always mocked; InDesign never used (`INDESIGN_MCP_ENABLED=false`) |

---

## Two-Phase Pipeline

Every user flow passes through exactly one of two phases. They share no mutable state — the only connection is the `DesignSchema` JSON file on disk.

Both pipeline functions (`run_ingestion`, `run_generation`) are **async**. They select the reader/writer at runtime based on `INDESIGN_MCP_ENABLED`.

```
╔══════════════════════════════════════════════════════════════════════╗
║  PHASE 1 — INGESTION  (run once per example set)                     ║
║                                                                      ║
║  Upload:  N × IDML file  +  N × Word doc                            ║
║                │                    │                                ║
║   reader_indesign.py          word/reader.py                        ║
║   (InDesign opens IDML,                                             ║
║    ExtendScript extracts              │                             ║
║    layout authoritatively)     WordDocument                         ║
║                │                    │                                ║
║          DesignLayout               │          ← pydantic models    ║
║                │                    │                                ║
║                └────────┬───────────┘                               ║
║                         │                                            ║
║                  ai/mapper.py  ←──────  ai/prompts/map_content.md   ║
║                  (Claude call)                                       ║
║                         │                                            ║
║                  ExampleAnalysis  (per pair)                         ║
║                         │                                            ║
║              pipeline/ingest.py  (aggregates all pairs)             ║
║                         │                                            ║
║                   DesignSchema  ──── saved as design_schema.json    ║
╚══════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════╗
║  PHASE 2 — GENERATION  (run per new document request)                ║
║                                                                      ║
║  Upload:  new Word doc  +  example_set_id                           ║
║                │                                                     ║
║         word/reader.py                                              ║
║                │                                                     ║
║          WordDocument                                                ║
║                │                                                     ║
║         ai/planner.py  ←──  design_schema.json                      ║
║         (Claude call)  ←──  ai/prompts/plan_layout.md               ║
║                │                                                     ║
║           LayoutPlan  (spread-by-spread content assignment)          ║
║                │                                                     ║
║   writer_indesign.py  ←──  primary template IDML                    ║
║   (InDesign opens template,                                         ║
║    ExtendScript applies plan,                                        ║
║    InDesign exports IDML)                                           ║
║                │                                                     ║
║           output.idml  ──── served for download                     ║
║                                                                      ║
║  Job status: pending → running → completed | failed                  ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## Module Map

```
backend/app/
│
├── main.py                  FastAPI app; mounts routers; sets up CORS
│
├── core/
│   ├── config.py            Settings (pydantic-settings); env vars:
│   │                        ANTHROPIC_API_KEY, CLAUDE_MODEL, LLM_PROVIDER,
│   │                        GEMINI_API_KEY, GEMINI_MODEL,
│   │                        INDESIGN_MCP_ENABLED, INDESIGN_MCP_SERVER_PATH,
│   │                        STORAGE_PATH, FRONTEND_URL, LOG_LEVEL
│   └── storage.py           All file I/O. Constructs paths for example sets and jobs.
│                            Must be the only place that touches the filesystem.
│
├── idml/
│   ├── models.py            Pydantic types for a parsed IDML file (see Data Models)
│   ├── indesign_client.py   InDesignClient — async context manager.
│   │                        Spawns the Node.js MCP server via stdio_client per job.
│   │                        Exposes call(), execute_script(), execute_script_json(),
│   │                        open_document(), close_document(), export_as_idml().
│   ├── reader_indesign.py   read_idml_indesign(path) → DesignLayout  [PRIMARY]
│   │                        Opens IDML in InDesign; runs _EXTRACT_LAYOUT_SCRIPT
│   │                        (ExtendScript) to extract spreads, frames, styles,
│   │                        colors, stories authoritatively. Closes doc when done.
│   ├── reader.py            read_idml(path|bytes) → DesignLayout  [FALLBACK]
│   │                        XML parser: designmap.xml, Spreads/, Stories/,
│   │                        Resources/Styles.xml, Resources/Graphic.xml.
│   │                        Reads Properties children for font attrs; applies
│   │                        ItemTransform translation to frame bounds.
│   ├── writer_indesign.py   InDesignWriter(template_path).apply_plan(plan, out)  [PRIMARY]
│   │                        Opens template in InDesign; embeds LayoutPlan as JSON
│   │                        literal in _APPLY_PLAN_SCRIPT (ExtendScript); adjusts
│   │                        page count; matches frames by style name; sets
│   │                        story.contents; applies paragraph styles; exports IDML.
│   └── writer.py            IDMLWriter(template_path).apply_plan(plan, out)  [FALLBACK]
│                            Clone-and-modify: rebuilds ParagraphStyleRange >
│                            CharacterStyleRange > Content structure per assignment.
│
├── word/
│   ├── models.py            Pydantic types for a parsed Word document (see Data Models)
│   └── reader.py            read_docx(path|bytes) → WordDocument
│                            Uses python-docx; sections delineated by Heading 1.
│                            Captures: headings H1–H4, paragraphs, bullet/numbered
│                            lists, tables, inline images, page breaks, bold/italic.
│                            Does NOT capture: text boxes, footnotes, headers/footers.
│
├── ai/
│   ├── client.py            LLMClient protocol + AnthropicClient + GeminiClient.
│   │                        get_llm_client() → singleton; selected by LLM_PROVIDER.
│   │                        call_structured() → always uses tool_use / JSON mode;
│   │                        Anthropic: prompt caching on system + context blocks.
│   ├── prompts/
│   │   ├── map_content.md   System prompt for content mapping (Phase 1)
│   │   └── plan_layout.md   System prompt for layout planning (Phase 2)
│   ├── mapper.py            map_content(word_docs, idml_layout) → ExampleAnalysis
│   │                        Summarises both as compact JSON, calls Claude,
│   │                        returns ContentMapping list.
│   └── planner.py           plan_layout(word_doc, schema) → LayoutPlan
│                            Serialises DesignSchema as cached context block,
│                            asks Claude to produce spread-by-spread assignments.
│
├── models/
│   ├── design_schema.py     DesignSchema — persisted output of ingestion (see Data Models)
│   ├── layout_plan.py       LayoutPlan — Claude's plan consumed by the writer
│   └── job.py               Job — async job state machine
│
├── pipeline/
│   ├── ingest.py            async run_ingestion(example_set_id, pairs, storage)
│   │                        _read_idml() routes to reader_indesign or reader based
│   │                        on INDESIGN_MCP_ENABLED. Orchestrates read → map →
│   │                        schema derivation → save.
│   └── generate.py          async run_generation(job_id, storage)
│                            _write_idml() routes to InDesignWriter or IDMLWriter.
│                            Orchestrates read_docx → plan_layout → write → job update.
│                            Called as a BackgroundTask; updates Job status on disk.
│
└── api/
    ├── deps.py              FastAPI dependency: get_storage() → Storage
    └── routes/
        ├── examples.py      POST /examples   — upload files + optional grouping JSON,
        │                                       start ingestion (202).
        │                    GET  /examples   — list example sets
        │                    GET  /examples/{id}/status — poll ingestion status
        │                    GET  /examples/{id}/schema — return DesignSchema JSON
        ├── generate.py      POST /generate   — upload Word doc, start generation (202)
        └── jobs.py          GET  /jobs/{id}          — poll job status + warnings
                             GET  /jobs/{id}/download — stream output IDML
```

---

## Data Models

All models are pydantic `BaseModel`. No bare dicts cross module boundaries.

### IDML-side (`idml/models.py`)

```
DesignLayout
├── source_filename: str
├── page_width: float          (points; 595.0 = A4)
├── page_height: float
├── spreads: list[Spread]
│   └── Spread
│       ├── filename: str      e.g. "Spreads/Spread_0001.xml"
│       ├── spread_id: str
│       ├── page_count: int
│       ├── text_frames: list[TextFrame]
│       │   └── TextFrame
│       │       ├── self_id, story_id
│       │       ├── x, y, width, height  (spread coordinates, in points)
│       │       ├── applied_paragraph_style
│       │       ├── master_page: str | None
│       │       ├── layer: str
│       │       └── threading_next_id, threading_prev_id
│       └── image_frames: list[ImageFrame]
│           └── ImageFrame
│               ├── self_id
│               ├── x, y, width, height
│               └── linked_image_path: str | None
├── master_pages: list[MasterPage]  (same structure as Spread but named)
├── style_catalog: StyleCatalog
│   ├── paragraph_styles: list[ParagraphStyle]
│   │   └── ParagraphStyle
│   │       ├── self_id, name, based_on
│   │       └── properties: ParagraphStyleProperties
│   │           └── font_family, font_style, point_size, leading, alignment, …
│   └── character_styles: list[CharacterStyle]
├── color_swatches: list[ColorSwatch]   (name, model, values)
└── stories: list[StoryContent]
    └── StoryContent
        ├── story_id: str
        ├── paragraphs: list[str]   (plain text, for analysis)
        └── has_overflow: bool      (InDesign's authoritative overflow flag)
```

### Word-side (`word/models.py`)

```
WordDocument
├── source_filename: str
├── title, subject: str | None    (from .docx core properties)
├── total_word_count: int
├── preamble: list[WordElement]   (content before the first Heading 1)
├── sections: list[WordSection]   (one per Heading 1)
│   └── WordSection
│       ├── title: str            (the H1 text)
│       └── elements: list[WordElement]
│           └── WordElement
│               ├── element_type: ElementType  (heading_1–4 | paragraph | bullet_list |
│               │                               numbered_list | table | figure | page_break)
│               ├── text: str
│               ├── heading_level: int | None
│               ├── list_items: list[str]
│               ├── table: WordTable | None
│               │   └── WordTable (rows, cols, cells: list[TableCell])
│               │       WordTable.to_markdown() → str  (used in LLM prompts)
│               ├── figure: WordFigure | None
│               │   └── WordFigure (index, caption, image_bytes, content_type)
│               ├── style_name: str | None
│               ├── bold: bool
│               └── italic: bool
└── figures: list[WordFigure]     (all images in the document, in order)
```

### Design Schema (`models/design_schema.py`)

The output of Phase 1. Saved as `storage/examples/{id}/design_schema.json`. Human-editable.

```
DesignSchema
├── example_set_id: str
├── primary_template_idml: str | None   (filename of the IDML to open for generation)
├── document_context_notes: str          (Claude's observations about this doc family)
├── frame_templates: list[FrameTemplate]
│   └── FrameTemplate
│       ├── role: SemanticRole
│       ├── typical_x, typical_y         (normalised 0–1, averaged across examples)
│       ├── typical_width, typical_height
│       ├── applied_paragraph_style: str
│       ├── applied_character_style: str | None
│       ├── master_page: str | None
│       └── is_threaded: bool
├── color_palette: list[ColorSwatch]
├── typefaces: list[TypefaceUsage]
│   └── TypefaceUsage (paragraph_style_name, font_family, font_style, point_size, leading)
└── example_analyses: list[ExampleAnalysis]
    └── ExampleAnalysis
        ├── idml_filename, word_filenames: list[str]
        ├── spread_count, page_count
        └── mappings: list[ContentMapping]
            └── ContentMapping
                ├── word_element_type, word_text_preview
                ├── idml_frame_id, idml_spread_index
                ├── role: SemanticRole
                └── paragraph_style: str
```

**SemanticRole values:**

| Role | Meaning |
|---|---|
| `cover_title` | Main document title on the cover page |
| `cover_subtitle` | Subtitle or tagline on the cover |
| `product_name` | Pharmaceutical product name |
| `document_type` | e.g. "Clinical Study Report" |
| `section_header` | Top-level section heading (H1) |
| `subsection_header` | Second- or third-level heading |
| `body` | Regular body text paragraphs |
| `body_lead` | First (often larger/bolder) paragraph of a section |
| `bullet_list` | Bulleted or numbered list |
| `table_title` | Heading above a data table |
| `table_body` | The table itself |
| `figure_caption` | Caption beneath an image or chart |
| `footnote` | Footnotes, references, source citations |
| `header_running` | Running header (master pages) |
| `footer_running` | Running footer (master pages) |
| `page_number` | Page number placeholder |
| `callout` | Highlighted sidebar, pull-quote, or warning box |
| `legal_disclaimer` | Regulatory/legal disclaimer text |
| `unknown` | Could not be determined |

### Layout Plan (`models/layout_plan.py`)

Produced by `ai/planner.py`, consumed by the writer. Never persisted to disk.

```
LayoutPlan
├── document_title: str
├── total_spreads: int
├── global_notes: str
└── spreads: list[SpreadPlan]
    └── SpreadPlan
        ├── spread_index: int
        ├── spread_purpose: str              (e.g. "cover page", "section 3 body")
        ├── template_spread_source: str      (e.g. "Spreads/Spread_0001.xml")
        ├── image_frame_notes: list[str]
        └── assignments: list[ContentAssignment]
            └── ContentAssignment
                ├── role: SemanticRole
                ├── paragraph_style: str
                ├── text: str
                └── frame_index: int
```

### Job (`models/job.py`)

```
Job
├── id: str                     (hex UUID)
├── status: JobStatus           (pending | running | completed | failed)
├── example_set_id: str
├── created_at: datetime
├── completed_at: datetime | None
├── output_filename: str | None
├── error: str | None
└── warnings: list[str]         (overset text, unmatched frames, missing styles)
```

Persisted as `storage/jobs/{id}/meta.json`.

---

## API Surface

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/examples` | Upload IDML + Word pairs; start ingestion (202 + `example_set_id`) |
| `GET` | `/examples` | List all example sets with schema-ready flag |
| `GET` | `/examples/{id}/status` | Poll ingestion status: running / completed / failed |
| `GET` | `/examples/{id}/schema` | Return raw `DesignSchema` JSON |
| `POST` | `/generate?example_set_id=…` | Upload new Word doc; start generation (202 + `job_id`) |
| `GET` | `/jobs/{id}` | Poll job status + warnings + error |
| `GET` | `/jobs/{id}/download` | Stream the generated `.idml` file |

All file uploads are `multipart/form-data`.

---

## Key Design Decisions

### 1. InDesign as the authoritative IDML engine

Both reading and writing go through the running InDesign instance via the `indesign-mcp-server` Node.js process (spawned per-job over stdio). InDesign resolves frame positions (ItemTransform matrices), style inheritance chains, master page overrides, text threading, overflow, and font availability natively. Our XML parser (`reader.py`) and XML writer (`writer.py`) are retained as a fallback for CI environments without InDesign.

### 2. Claude for reasoning, InDesign for construction

Claude's job in Phase 1: "this H1 maps to the `section_header` frame with style `ParagraphStyle/Section Title`." Claude's job in Phase 2: "Spread 3 should be a body spread, with the Section 2 body text placed in the body frame."

No Claude call happens inside `InDesignWriter.apply_plan()` or `IDMLWriter.apply_plan()`. The writer is deterministic: match assignment to frame by style name, set story content, apply style.

### 3. Template-based generation, not from scratch

Generation opens the `primary_template_idml` from the example set in InDesign and mutates it. The template provides all font embeds, kerning, master pages, color profiles, and style definitions. The writer only replaces story content and adjusts page count.

### 4. Prompt caching on every large context block

`ai/client.py` (Anthropic path) always sends system prompts and the `DesignSchema` context block with `cache_control: {"type": "ephemeral"}`. For large example sets, the schema JSON can be 10–50k tokens.

### 5. DesignSchema is human-editable

After ingestion, `storage/examples/{id}/design_schema.json` is a plain JSON file. If Claude misidentified a semantic role, a designer can fix it and re-run generation without re-ingesting.

### 6. Frame positions are normalised (0–1)

`FrameTemplate.typical_x/y/width/height` are stored as fractions of page width/height so they remain meaningful across A4 and US Letter example documents.

---

## Storage Layout

```
storage/                          (gitignored)
├── examples/
│   └── {example_set_id}/
│       ├── design_schema.json    ← output of Phase 1; human-editable
│       ├── ingestion_status.json ← running / completed / failed
│       ├── example_1.idml        ← uploaded IDML files
│       ├── example_1.docx        ← uploaded Word files
│       └── …
└── jobs/
    └── {job_id}/
        ├── meta.json             ← Job model (status, warnings, error)
        ├── input.docx            ← the uploaded new Word document
        └── output.idml           ← generated IDML (only present when completed)
```

---

## Known Limitations (MVP)

| Limitation | Impact | Future fix |
|---|---|---|
| Image placement | Image frames from the template are kept as-is; Word images are not placed | Extract Word images, insert into image frames via InDesign MCP `place_image` |
| Frame matching heuristic | Frames matched to assignments by paragraph style name substring; ambiguous on dense layouts | Use frame_id from DesignSchema mappings for deterministic matching |
| Single template | All spreads use `primary_template_idml`; multi-template layouts not supported | Per-spread template selection from across all example IDMLs |
| BackgroundTasks concurrency | Runs in the same process; concurrent heavy jobs may queue | Migrate to Celery + Redis |
| No auth | Anyone with the API URL can upload and generate | Add API key or session auth before shared/cloud deployment |
| InDesign must be open | If InDesign is closed mid-job, the job fails with `InDesignMCPError` | Detect and restart InDesign via AppleScript before spawning MCP session |

---

## How to Keep This Document Current

When you make a change that affects any of the following, update the relevant section:

- **A new pydantic model or field** → update Data Models
- **A new module or file** → update Module Map
- **A new API endpoint** → update API Surface
- **A changed design decision** → update Key Design Decisions
- **A new limitation discovered or resolved** → update Known Limitations

The test suite is the source of truth for behaviour. This document is the source of truth for intent.
