# CollegeMirror — User Guide

CollegeMirror takes your existing InDesign documents and the Word files behind them, learns the design patterns, then generates a new InDesign file from any new Word doc — matching the same layout, styles, and structure.

---

## Before You Start

### One-time setup

Before using the app for the first time, install the InDesign MCP server. You do **not** run it manually — the backend launches and shuts it down automatically per job. You just need it installed and pointed to in your `.env`.

```bash
git clone https://github.com/lucdesign/indesign-mcp-server.git
cd indesign-mcp-server
npm install
```

Then add these two lines to your `.env` file:

```env
INDESIGN_MCP_ENABLED=true
INDESIGN_MCP_SERVER_PATH=/absolute/path/to/indesign-mcp-server/index.js
```

Also make sure **Node.js 18+** is installed (`node --version` to check).

### Every time you use the app

The following must all be in place before submitting any job:

1. **Adobe InDesign 2025** — open on your Mac. No document needs to be open, just the application itself.
2. **Backend server** — `uv run uvicorn backend.app.main:app --reload --port 8000`
3. **Frontend** — `cd frontend && npm run dev`, then open `http://localhost:5173`

The MCP server does **not** need to be started manually. The backend spawns it automatically when a job runs and shuts it down when the job finishes.

If InDesign is not open when you submit a job, the job will fail.

---

## The Two Steps

The app works in two phases. **You must complete Step 1 before Step 2.**

---

## Step 1 — Train (teach the app your design)

Go to the **Train** page (`/`).

You are uploading *example pairs* — an IDML file alongside the Word document(s) that provided its content. The app opens each IDML in InDesign, reads the layout, and uses Claude to understand how the Word content was mapped to the design frames.

### What to prepare

- One or more finished InDesign documents exported as **IDML** (File → Export → InDesign Markup Language in InDesign).
- The Word `.docx` file(s) that the content in those documents originally came from.

> **Important:** The IDML and the Word doc must genuinely correspond. The app learns by comparing them — if the content does not match, the learned design schema will be wrong.

### Uploading

Drag all your files into the dropzone together. If you have multiple IDML+Word pairs, use the **grouping** field to declare which Word docs belong to which IDML:

```json
[
  { "idml": "annual_report.idml",   "words": ["financials.docx", "narrative.docx"] },
  { "idml": "product_brochure.idml", "words": ["product_copy.docx"] }
]
```

Each IDML can be paired with **one or more** Word docs. If a single InDesign document was assembled from content spread across multiple Word files, list all of them — Claude will attribute each frame to the correct source.

If you omit the grouping field, files are paired by order: first IDML with first Word doc, second with second, and so on. The counts must match.

### What happens next

Ingestion runs in the background. The page will poll until it completes. This usually takes 30–90 seconds depending on document size and complexity.

When done, you will see a **schema ID** — keep this. You need it in Step 2.

### Uploading more examples

More examples = better results. The app aggregates design patterns across all pairs you provide. If your document series has multiple layout templates (cover, body, appendix, etc.), include at least one example of each.

---

## Step 2 — Generate (create a new document)

Go to the **Generate** page (`/generate`).

### What to prepare

- A new Word `.docx` file with the content you want laid out.
- The **schema ID** from Step 1.

### Uploading

Enter the schema ID, drag in your new Word doc, and submit. The app will:

1. Parse the Word doc.
2. Ask Claude to plan a spread-by-spread layout using the design schema it learned.
3. Open the template in InDesign, apply the plan, and export a new IDML file.

Generation typically takes 20–60 seconds.

When complete, a **Download** button appears. The file is a `.idml` — open it in InDesign to review, adjust, and finalise.

---

## Word Document Format Guide

The app works with any `.docx` file, but documents structured with Word's built-in heading styles give significantly better results. The better the structure, the better Claude understands what content is a title, a section heading, a body paragraph, a callout, etc.

### Use Word's built-in heading styles

| Content | Use this Word style |
|---|---|
| Major section title | **Heading 1** |
| Subsection title | **Heading 2** |
| Sub-subsection | **Heading 3** |
| Cover page / document title | **Title** |
| Subtitle or tagline | **Subtitle** |
| Body text | **Normal** (default) |
| Bullet points | Any list style, or Word's built-in list bullet |
| Tables | Insert → Table (standard Word tables) |
| Images | Insert → Picture (inline images) |

> **Heading 1 is the section boundary.** Everything between two Heading 1s is treated as one section. Content before the first Heading 1 (cover text, document title, etc.) is treated as a preamble.

### What the parser captures

| ✅ Captured | ❌ Not captured |
|---|---|
| Headings (H1–H4) | Text boxes |
| Body paragraphs | Footnotes and endnotes |
| Bold and italic runs | Headers and footers |
| Bullet and numbered lists | Comments |
| Tables (all cells, header row detection) | SmartArt |
| Inline images | Embedded spreadsheets |

If your documents use text boxes for callouts or pull quotes, move that content into standard paragraphs before uploading. Text box content is invisible to the parser.

### Practical tips

- **Match section count to your template.** If your example IDML has 4 sections, a Word doc with 4 Heading 1s will map most naturally.
- **Keep heading text concise.** Heading 1 text becomes the section title in the layout plan.
- **One image per paragraph.** If you have a caption, put it in the same paragraph as the image or immediately after.
- **Numbered lists are fine.** They are detected and passed to Claude as list items regardless of whether bullets or numbers are used.
- **File must be `.docx`.** Old `.doc` format is not supported. If you have a `.doc`, open it in Word and save as `.docx` first.

---

## Common Issues

**Ingestion failed immediately**
→ Check that InDesign is open. Check that `INDESIGN_MCP_SERVER_PATH` in `.env` points to the correct `index.js` and that `npm install` was run in that folder. Check the backend logs for the specific error.

**"No design schema found" when generating**
→ Ingestion did not complete successfully, or you entered the wrong schema ID. Go back to the Train page and check the status.

**Generated document has wrong text / missing content**
→ The Word doc structure may not match the template well. Try adding Heading 1 markers to delineate sections, or upload additional example pairs that better represent your content type.

**Overset text warnings on download**
→ The new content is longer than the original frames. Open the IDML in InDesign — overset frames are flagged with a red `+` icon. Resize the frame or edit the text.

**Job stays "running" for more than 3 minutes**
→ InDesign may have shown a dialog (missing font, etc.) that blocked the script. Quit and reopen InDesign, then resubmit the job.
