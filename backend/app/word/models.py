"""Pydantic models representing the parsed structure of a Word (.docx) document."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ElementType(StrEnum):
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    HEADING_4 = "heading_4"
    PARAGRAPH = "paragraph"
    BULLET_LIST = "bullet_list"
    NUMBERED_LIST = "numbered_list"
    TABLE = "table"
    FIGURE = "figure"
    PAGE_BREAK = "page_break"


class TableCell(BaseModel):
    row: int
    col: int
    text: str
    is_header: bool = False


class WordTable(BaseModel):
    rows: int
    cols: int
    cells: list[TableCell] = Field(default_factory=list)
    caption: str | None = None

    def to_markdown(self) -> str:
        """Render the table as a markdown string for LLM consumption."""
        if not self.cells:
            return ""
        grid: dict[tuple[int, int], str] = {(c.row, c.col): c.text for c in self.cells}
        lines: list[str] = []
        for r in range(self.rows):
            row_cells = [grid.get((r, c), "") for c in range(self.cols)]
            lines.append("| " + " | ".join(row_cells) + " |")
            if r == 0:
                lines.append("|" + "|".join(["---"] * self.cols) + "|")
        return "\n".join(lines)


class WordFigure(BaseModel):
    index: int          # order of appearance in the document
    caption: str | None = None
    image_bytes: bytes | None = None    # raw image data extracted from docx
    content_type: str | None = None     # e.g. "image/png"


class WordElement(BaseModel):
    """One content element extracted from the Word document."""

    element_type: ElementType
    text: str = ""              # plain text (empty for figures/tables)
    heading_level: int | None = None    # 1–4 for headings
    list_items: list[str] = Field(default_factory=list)
    table: WordTable | None = None
    figure: WordFigure | None = None
    style_name: str | None = None       # original Word style name, e.g. "Heading 1"
    bold: bool = False
    italic: bool = False


class WordSection(BaseModel):
    """A top-level section of the document, anchored by a Heading 1."""

    title: str
    elements: list[WordElement] = Field(default_factory=list)


class WordDocument(BaseModel):
    """Complete parsed structure of a .docx file."""

    source_filename: str
    title: str | None = None            # from core properties
    subject: str | None = None
    sections: list[WordSection] = Field(default_factory=list)
    # Elements that appear before any H1 (e.g., cover page text)
    preamble: list[WordElement] = Field(default_factory=list)
    figures: list[WordFigure] = Field(default_factory=list)
    total_word_count: int = 0
