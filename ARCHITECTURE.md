# CollegeMirror — Architecture

> **Living document.** Update this file whenever a module's responsibility, data contract, or connection to other modules changes. The goal is that a new contributor can read this and understand how the whole system fits together without needing to ask.

---

## Overview

CollegeMirror turns the pain of re-creating pharmaceutical company InDesign documents into a two-step upload flow. Users provide example IDML files alongside the Word docs that produced them — the app learns the design vocabulary from those examples, then applies it to any new Word doc, generating a ready-to-review IDML file.

The key property of the system: **Claude reasons about layout, deterministic code builds it.** No LLM call sits inside the XML assembly loop.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend runtime | Python 3.12+ / FastAPI | Best library ecosystem for IDML + ML; async I/O for file uploads |
| IDML manipulation | `SimpleIDML` + `zipfile` + `lxml` | Only mature Python IDML library; lxml for namespace-aware XML |
| Word parsing | `python-docx` | Structural heading/para/table/image extraction from .docx |
| LLM | `anthropic` SDK — `claude-sonnet-4-6` | 200k context fits multiple IDML + Word docs; best reasoning for layout intent |
| Async jobs | FastAPI `BackgroundTasks` | Generation takes 30–120s; avoids HTTP timeout without Celery overhead at MVP |
| Storage | Local filesystem (`./storage/`) | No infra dependency for MVP; paths abstracted behind `Storage` class for later S3 swap |
| Config | `pydantic-settings` | Type-safe; reads from `.env` |
| Frontend | React + Vite + Tailwind CSS | Upload/poll/download flow; proxied to backend via Vite dev server |
| Deps | `uv` | Fast, deterministic |
| Lint/format | `ruff` | Single tool for lint + format |
| Tests | `pytest` + `pytest-asyncio` | In-memory IDML fixture; Claude always mocked |

---

## Two-Phase Pipeline

Every user flow passes through exactly one of two phases. They share no mutable state — the only connection is the `DesignSchema` JSON file on disk.

```
╔══════════════════════════════════════════════════════════════════════╗
║  PHASE 1 — INGESTION  (run once per example set)                     ║
║                                                                      ║
║  Upload:  N × IDML file  +  N × Word doc                            ║
║                │                    │                                ║
║         idml/reader.py        word/reader.py                        ║
║                │                    │                                ║
║         DesignLayout          WordDocument      ← pydantic models   ║
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
║         idml/writer.py  ←──  primary template IDML (cloned)         ║
║         (pure Python, no LLM)                                        ║
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
│   ├── config.py            Settings (pydantic-settings); single source of truth for
│   │                        env vars: ANTHROPIC_API_KEY, CLAUDE_MODEL, STORAGE_PATH
│   └── storage.py           All file I/O. Constructs paths for example sets and jobs.
│                            Must be the only place that touches the filesystem.
│
├── idml/
│   ├── models.py            Pydantic types for a parsed IDML file (see Data Models)
│   ├── reader.py            read_idml(path|bytes) → DesignLayout
│   │                        Unzips IDML; parses designmap.xml, Spreads/, Stories/,
│   │                        Resources/Styles.xml, Resources/Graphic.xml
│   └── writer.py            IDMLWriter(template_path).apply_plan(plan, output_path)
│                            Clone-and-modify: only mutates <Content> elements and
│                            spread list; preserves all style references
│
├── word/
│   ├── models.py            Pydantic types for a parsed Word document (see Data Models)
│   └── reader.py            read_docx(path|bytes) → WordDocument
│                            Uses python-docx; sections delineated by Heading 1
│
├── ai/
│   ├── client.py            ClaudeClient — the ONLY place anthropic.Anthropic() is called.
│   │                        call_structured() → always uses tool_use for JSON output;
│   │                        always caches system prompts with cache_control: ephemeral
│   ├── prompts/
│   │   ├── map_content.md   System prompt for content mapping (Phase 1)
│   │   └── plan_layout.md   System prompt for layout planning (Phase 2)
│   ├── mapper.py            map_content(word_doc, idml_layout) → ExampleAnalysis
│   │                        Summarises both docs as compact JSON, calls Claude,
│   │                        returns ContentMapping list
│   └── planner.py           plan_layout(word_doc, schema) → LayoutPlan
│                            Serialises DesignSchema as cached context block,
│                            asks Claude to produce spread-by-spread assignments
│
├── models/
│   ├── design_schema.py     DesignSchema — persisted output of ingestion (see Data Models)
│   ├── layout_plan.py       LayoutPlan — Claude's plan consumed by the writer
│   └── job.py               Job — async job state machine
│
├── pipeline/
│   ├── ingest.py            run_ingestion(example_set_id, pairs, storage)
│   │                        pairs: list[tuple[Path, list[Path]]] — one IDML, N Word docs each
│   │                        Orchestrates reader → mapper → schema derivation → save
│   └── generate.py          run_generation(job_id, storage)
│                            Orchestrates reader → planner → writer → job update
│                            Called as a BackgroundTask; updates Job status on disk
│
└── api/
    ├── deps.py              FastAPI dependency: get_storage() → Storage
    └── routes/
        ├── examples.py      POST /examples   — upload files + optional `grouping` JSON, start ingestion (202)
        │                                      grouping: [{"idml": "x.idml", "words": ["a.docx","b.docx"]}]
        │                    GET  /examples   — list example sets
        │                    GET  /examples/{id}/schema — return DesignSchema JSON
        ├── generate.py      POST /generate   — upload Word doc, start generation (202)
        └── jobs.py          GET  /jobs/{id}          — poll job status
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
│       │       ├── self_id, story_id   (story_id links to Stories/Story_<id>.xml)
│       │       ├── x, y, width, height (geometric bounds in points)
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
        └── has_overflow: bool
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
│               ├── style_name: str | None     (original Word style, e.g. "Heading 2")
│               ├── bold: bool
│               └── italic: bool
└── figures: list[WordFigure]     (all images found in the document, in order)
```

### Design Schema (`models/design_schema.py`)

The output of Phase 1. Saved as `storage/examples/{id}/design_schema.json`. Human-editable.

```
DesignSchema
├── example_set_id: str
├── primary_template_idml: str | None   (filename of the IDML to clone for generation)
├── document_context_notes: str          (Claude's observations about this doc family)
├── frame_templates: list[FrameTemplate]
│   └── FrameTemplate
│       ├── role: SemanticRole           (see full list below)
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
                ├── word_element_type   (e.g. "heading_1")
                ├── word_text_preview   (first 80 chars)
                ├── idml_frame_id
                ├── idml_spread_index
                ├── role: SemanticRole
                └── paragraph_style: str
```

**SemanticRole values** (the vocabulary Claude uses to label content):

| Role | Meaning |
|---|---|
| `cover_title` | Main document title on the cover page |
| `cover_subtitle` | Subtitle or tagline on the cover |
| `product_name` | Pharmaceutical product name (may repeat throughout) |
| `document_type` | e.g. "Clinical Study Report", "Product Monograph" |
| `section_header` | Top-level section heading (typically H1) |
| `subsection_header` | Second- or third-level heading |
| `body` | Regular body text paragraphs |
| `body_lead` | First (often larger/bolder) paragraph of a section |
| `bullet_list` | Bulleted or numbered list |
| `table_title` | Heading above a data table |
| `table_body` | The table itself |
| `figure_caption` | Caption beneath an image or chart |
| `footnote` | Footnotes, references, source citations |
| `header_running` | Running header text (lives on master pages) |
| `footer_running` | Running footer text (lives on master pages) |
| `page_number` | Page number placeholder |
| `callout` | Highlighted sidebar, pull-quote, or warning box |
| `legal_disclaimer` | Regulatory/legal disclaimer text |
| `unknown` | Could not be determined |

### Layout Plan (`models/layout_plan.py`)

Produced by `ai/planner.py`, consumed by `idml/writer.py`. Never persisted to disk.

```
LayoutPlan
├── document_title: str
├── total_spreads: int
├── global_notes: str          (Claude's notes for the designer)
└── spreads: list[SpreadPlan]
    └── SpreadPlan
        ├── spread_index: int
        ├── spread_purpose: str              (e.g. "cover page", "section 3 body")
        ├── template_spread_source: str      (e.g. "Spreads/Spread_0001.xml" — to clone)
        ├── image_frame_notes: list[str]     (designer instructions for image frames)
        └── assignments: list[ContentAssignment]
            └── ContentAssignment
                ├── role: SemanticRole
                ├── paragraph_style: str
                ├── text: str                (exact text to place in the frame)
                └── frame_index: int         (0-based; for multiple frames of the same role)
```

### Job (`models/job.py`)

```
Job
├── id: str                     (hex UUID)
├── status: JobStatus           (pending | running | completed | failed)
├── example_set_id: str
├── created_at: datetime
├── completed_at: datetime | None
├── output_filename: str | None  (original .docx name; used to name the download)
├── error: str | None
└── warnings: list[str]         (e.g. overset text frame names)
```

Persisted as `storage/jobs/{id}/meta.json`. Updated in-place by `pipeline/generate.py`.

---

## API Surface

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/examples` | Upload IDML + Word pairs; start ingestion (returns 202 + `example_set_id`) |
| `GET` | `/examples` | List all example sets with schema-ready flag |
| `GET` | `/examples/{id}/schema` | Return raw `DesignSchema` JSON |
| `POST` | `/generate?example_set_id=…` | Upload new Word doc; start generation (returns 202 + `job_id`) |
| `GET` | `/jobs/{id}` | Poll job status + warnings + error |
| `GET` | `/jobs/{id}/download` | Stream the generated `.idml` file |

All file uploads are `multipart/form-data`. The frontend Vite dev server proxies all API routes to `http://localhost:8000`.

---

## Key Design Decisions

### 1. Clone-and-modify, never build from scratch

All IDML output starts by cloning the `primary_template_idml` from the example set. The writer (`idml/writer.py`) only replaces `<Content>` text elements and rewrites the spread list in `designmap.xml`. Everything else — font embeds, kerning, master pages, color profiles, style definitions — is preserved from the original InDesign file.

**Why:** IDML generated from scratch has brittle geometry (text reflow is font-metric-dependent), missing fonts, and broken master page references. Production systems like SimpleIDML and BatchIDMLGenerator both use this approach.

### 2. Claude for reasoning, Python for construction

Claude's job in Phase 1 is to say "this H1 from the Word doc maps to the `section_header` frame with style `ParagraphStyle/Section Title`." Claude's job in Phase 2 is to say "Spread 3 should be a body spread, cloned from `Spreads/Spread_0003.xml`, with the Section 2 body text placed in the body frame."

No Claude call happens inside `IDMLWriter.apply_plan()`. The writer is pure deterministic Python: match assignment to frame by style name, update `<Content>`, rezip.

**Why:** LLMs in tight loops (XML construction) are slow, expensive, and hallucination-prone. They excel at high-level reasoning over structured summaries.

### 3. Prompt caching on every large context block

`ai/client.py` always sends system prompts and the `DesignSchema` context block with `cache_control: {"type": "ephemeral"}`. For large example sets, the schema JSON can be 10–50k tokens — paying to re-encode that on every generation call would be prohibitively expensive.

**Why:** The Anthropic cache TTL is 5 minutes. Within a generation session, the schema is stable — it never changes between the mapper and planner calls.

### 4. DesignSchema is human-editable

After ingestion completes, `storage/examples/{id}/design_schema.json` is a plain JSON file. If Claude misidentified a semantic role (e.g. tagged a callout as `body`), a designer can open the JSON, fix the role, and re-run generation without re-ingesting.

**Why:** Pharmaceutical documents have highly specific terminology and layout conventions. Giving designers a legible override file prevents the system from being a black box they can't correct.

### 5. Frame positions are normalised (0–1)

`FrameTemplate.typical_x/y/width/height` are stored as fractions of page width/height, not absolute points. When `_derive_frame_templates()` aggregates positions across multiple examples, it averages these normalised values so the result remains meaningful even if example documents have different page sizes.

**Why:** A4 (595×842 pt) and US Letter (612×792 pt) are both common in pharma. An absolute position of `x=50` has different visual meaning on each.

### 6. Story files are excluded from static copy, written once

`IDMLWriter.apply_plan()` splits template files into three buckets: static files (copied as-is), story files (parsed, mutated, written once at the end), and spread files (cloned per-plan, written fresh). This prevents the duplicate-filename bug that would arise from copying a story then writing it again.

### 7. Overflow detection is surfaced, not silently dropped

After the writer produces the output IDML, it checks every story XML for `Overflows="true"` attributes (an InDesign flag set when text doesn't fit the frame). Any overflows are returned as `warnings` and stored in the `Job`. The frontend surfaces them to the user after download.

**Why:** Overset text is the most common failure mode in clone-and-modify generation. The designer needs to know so they can reflow manually in InDesign.

---

## Storage Layout

```
storage/                          (gitignored)
├── examples/
│   └── {example_set_id}/
│       ├── design_schema.json    ← output of Phase 1; human-editable
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
| Text reflow | Generated text may overflow frames if new content is longer | Overflow detection surfaced as warning; designer adjusts in InDesign |
| Image placement | MVP: image frames from the template are kept as-is | Phase 2: extract Word images, insert into image frames, scale to fit |
| Loosely-threaded frames | Frame threading (linked text frames) is read but not reconstructed during cloning | Track threading chain and preserve it in cloned spreads |
| Single template clone | All spreads are cloned from `primary_template_idml` only | Support per-spread template selection from across all example IDMLs |
| BackgroundTasks concurrency | FastAPI's `BackgroundTasks` runs in the same process; heavy Claude calls may block | Migrate to Celery + Redis when concurrency becomes an issue |
| No auth | Anyone with the API URL can upload and generate | Add API key or session auth before any shared/cloud deployment |

---

## How to Keep This Document Current

When you make a change that affects any of the following, update the relevant section:

- **A new pydantic model or field** → update Data Models
- **A new module or file** → update Module Map
- **A new API endpoint** → update API Surface
- **A changed design decision** → update Key Design Decisions (and explain *why* it changed)
- **A new limitation discovered or resolved** → update Known Limitations

The test suite (`tests/`) is the source of truth for behaviour. This document is the source of truth for intent.
