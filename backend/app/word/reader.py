"""
Word Document Reader — parses a .docx file into a WordDocument pydantic model.

Strategy:
  - python-docx for structural extraction (headings, paragraphs, tables, images)
  - mammoth for semantic style normalization (maps Word styles → semantic names)
  - Sections are delineated by Heading 1 elements
"""

import re
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph

from backend.app.word.models import (
    ElementType,
    TableCell,
    WordDocument,
    WordElement,
    WordFigure,
    WordSection,
    WordTable,
)


class WordReadError(Exception):
    pass


# Mapping from Word built-in style names to ElementType
_HEADING_STYLES: dict[str, int] = {
    "heading 1": 1,
    "heading 2": 2,
    "heading 3": 3,
    "heading 4": 4,
    "title": 1,
    "subtitle": 2,
}


def _style_name(para: Paragraph) -> str:
    """Return the lowercased style name for a paragraph."""
    if para.style and para.style.name:
        return para.style.name.lower()
    return ""


def _is_heading(para: Paragraph) -> int | None:
    """Return heading level (1–4) or None."""
    sn = _style_name(para)
    for key, level in _HEADING_STYLES.items():
        if sn.startswith(key):
            return level
    # Check outline level in XML as a fallback
    outline = para._p.find(qn("w:pPr"))
    if outline is not None:
        ol = outline.find(qn("w:outlineLvl"))
        if ol is not None:
            lvl = int(ol.get(qn("w:val"), "8"))
            if lvl <= 3:
                return lvl + 1
    return None


def _is_list_item(para: Paragraph) -> bool:
    sn = _style_name(para)
    return "list" in sn or "bullet" in sn or para._p.find(qn("w:numPr")) is not None


def _paragraph_text(para: Paragraph) -> str:
    return para.text.strip()


def _has_page_break(para: Paragraph) -> bool:
    for run in para.runs:
        if run._r.find(qn("w:lastRenderedPageBreak")) is not None:
            return True
    return any(br.get(qn("w:type")) == "page" for br in para._p.iter(qn("w:br")))


def _extract_table(tbl: DocxTable, caption: str | None = None) -> WordTable:
    rows = len(tbl.rows)
    cols = max((len(r.cells) for r in tbl.rows), default=0)
    cells: list[TableCell] = []
    for ri, row in enumerate(tbl.rows):
        for ci, cell in enumerate(row.cells):
            cells.append(
                TableCell(
                    row=ri,
                    col=ci,
                    text=cell.text.strip(),
                    is_header=(ri == 0),
                )
            )
    return WordTable(rows=rows, cols=cols, cells=cells, caption=caption)


def _extract_figures(doc: Document) -> list[WordFigure]:
    """Extract embedded images from the document."""
    figures: list[WordFigure] = []
    idx = 0
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                image_bytes = rel.target_part.blob
                content_type = rel.target_part.content_type
                figures.append(
                    WordFigure(
                        index=idx,
                        image_bytes=image_bytes,
                        content_type=content_type,
                    )
                )
                idx += 1
            except Exception:  # noqa: BLE001
                pass
    return figures


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def read_docx(path: Path | str | bytes) -> WordDocument:
    """
    Parse a .docx file and return a WordDocument.

    Args:
        path: File path to the .docx file, or raw bytes.
    """
    if isinstance(path, bytes):
        raw = path
        source_filename = "<bytes>"
    else:
        p = Path(path)
        if not p.exists():
            raise WordReadError(f"Word document not found: {p}")
        raw = p.read_bytes()
        source_filename = p.name

    doc = Document(BytesIO(raw))

    # Core properties
    title: str | None = None
    subject: str | None = None
    if doc.core_properties:
        title = doc.core_properties.title or None
        subject = doc.core_properties.subject or None

    # Extract figures (images)
    figures = _extract_figures(doc)

    # Walk the document body
    sections: list[WordSection] = []
    preamble: list[WordElement] = []
    current_section: WordSection | None = None
    current_list_items: list[str] = []
    figure_idx = 0
    total_words = 0

    def flush_list() -> None:
        nonlocal current_list_items
        if not current_list_items:
            return
        el = WordElement(
            element_type=ElementType.BULLET_LIST,
            list_items=list(current_list_items),
        )
        target = current_section.elements if current_section else preamble
        target.append(el)
        current_list_items = []

    # Iterate over block-level items (paragraphs and tables)
    for block in doc.element.body:
        tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

        if tag == "tbl":
            flush_list()
            tbl = DocxTable(block, doc)
            word_tbl = _extract_table(tbl)
            el = WordElement(element_type=ElementType.TABLE, table=word_tbl)
            target = current_section.elements if current_section else preamble
            target.append(el)
            continue

        if tag != "p":
            continue

        # Reconstruct paragraph from the element
        para = Paragraph(block, doc)
        text = _paragraph_text(para)

        # Page break — record and continue
        if _has_page_break(para) and not text:
            flush_list()
            el = WordElement(element_type=ElementType.PAGE_BREAK)
            target = current_section.elements if current_section else preamble
            target.append(el)
            continue

        heading_level = _is_heading(para)

        if heading_level == 1:
            flush_list()
            current_section = WordSection(title=text)
            sections.append(current_section)
            total_words += _word_count(text)
            continue

        if heading_level and heading_level > 1:
            flush_list()
            el = WordElement(
                element_type=ElementType(f"heading_{heading_level}"),
                text=text,
                heading_level=heading_level,
                style_name=para.style.name if para.style else None,
            )
            target = current_section.elements if current_section else preamble
            target.append(el)
            total_words += _word_count(text)
            continue

        if not text:
            flush_list()
            continue

        if _is_list_item(para):
            current_list_items.append(text)
            total_words += _word_count(text)
            continue

        flush_list()

        # Check for inline images (drawing elements)
        has_image = para._p.find(".//" + qn("a:blip")) is not None
        if has_image and figure_idx < len(figures):
            fig = figures[figure_idx]
            fig = WordFigure(
                index=fig.index,
                caption=text or None,
                image_bytes=fig.image_bytes,
                content_type=fig.content_type,
            )
            el = WordElement(element_type=ElementType.FIGURE, figure=fig, text=text)
            figure_idx += 1
        else:
            bold = any(run.bold for run in para.runs)
            italic = any(run.italic for run in para.runs)
            el = WordElement(
                element_type=ElementType.PARAGRAPH,
                text=text,
                style_name=para.style.name if para.style else None,
                bold=bold,
                italic=italic,
            )

        target = current_section.elements if current_section else preamble
        target.append(el)
        total_words += _word_count(text)

    flush_list()

    return WordDocument(
        source_filename=source_filename,
        title=title,
        subject=subject,
        sections=sections,
        preamble=preamble,
        figures=figures,
        total_word_count=total_words,
    )
