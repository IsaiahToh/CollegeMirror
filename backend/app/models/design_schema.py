"""DesignSchema — the learned vocabulary extracted from example IDML + Word pairs."""

from enum import StrEnum

from pydantic import BaseModel, Field


class SemanticRole(StrEnum):
    """Semantic roles that content can play in a pharmaceutical document."""

    COVER_TITLE = "cover_title"
    COVER_SUBTITLE = "cover_subtitle"
    PRODUCT_NAME = "product_name"
    DOCUMENT_TYPE = "document_type"           # e.g. "Clinical Study Report"
    SECTION_HEADER = "section_header"
    SUBSECTION_HEADER = "subsection_header"
    BODY = "body"
    BODY_LEAD = "body_lead"                   # first paragraph of a section, often larger
    BULLET_LIST = "bullet_list"
    TABLE_TITLE = "table_title"
    TABLE_BODY = "table_body"
    FIGURE_CAPTION = "figure_caption"
    FOOTNOTE = "footnote"
    HEADER_RUNNING = "header_running"         # running header (master page)
    FOOTER_RUNNING = "footer_running"         # running footer (master page)
    PAGE_NUMBER = "page_number"
    CALLOUT = "callout"                       # highlighted sidebar / pull-quote
    LEGAL_DISCLAIMER = "legal_disclaimer"
    UNKNOWN = "unknown"


class FrameTemplate(BaseModel):
    """Describes a type of text frame and its typical characteristics."""

    role: SemanticRole
    # Positions and sizes are stored as fractions of page width/height (0.0–1.0)
    # so they remain meaningful across different page sizes.
    typical_x: float
    typical_y: float
    typical_width: float
    typical_height: float
    applied_paragraph_style: str
    applied_character_style: str | None = None
    master_page: str | None = None
    layer: str = "Default"
    is_threaded: bool = False       # part of a linked text frame chain


class ColorSwatch(BaseModel):
    name: str
    model: str          # "CMYK" | "RGB" | "Lab" | "Spot"
    values: list[float] # CMYK: [C, M, Y, K] each 0–100; RGB: [R, G, B] each 0–255


class TypefaceUsage(BaseModel):
    paragraph_style_name: str
    font_family: str
    font_style: str     # "Regular" | "Bold" | "Italic" | "Bold Italic"
    point_size: float
    leading: float | None = None


class ContentMapping(BaseModel):
    """How one Word doc element mapped to one IDML frame in a specific example."""

    word_element_type: str          # "heading_1" | "paragraph" | "table" | "figure" etc.
    word_text_preview: str          # first 80 chars of the element
    idml_frame_id: str
    idml_spread_index: int
    role: SemanticRole
    paragraph_style: str


class ExampleAnalysis(BaseModel):
    """Result of analysing one IDML + one or more Word docs."""

    idml_filename: str
    word_filenames: list[str]          # one IDML can draw from multiple Word docs
    mappings: list[ContentMapping]
    spread_count: int
    page_count: int

    # Per-example design observations returned by Claude during content mapping.
    document_context_notes: str = ""


class DesignSchema(BaseModel):
    """
    The learned design vocabulary. Persisted as design_schema.json inside each
    example-set directory. Designers can inspect and hand-edit this file.
    """

    example_set_id: str
    frame_templates: list[FrameTemplate] = Field(default_factory=list)
    color_palette: list[ColorSwatch] = Field(default_factory=list)
    typefaces: list[TypefaceUsage] = Field(default_factory=list)
    example_analyses: list[ExampleAnalysis] = Field(default_factory=list)

    # Representative IDML filename to use as cloning base for new documents.
    # Defaults to the first uploaded example; can be overridden by the designer.
    primary_template_idml: str | None = None

    # Pharmaceutical document context notes, populated by Claude during ingestion.
    document_context_notes: str = ""
