"""Pydantic models representing the parsed structure of an IDML file."""

from pydantic import BaseModel, Field


class TextFrame(BaseModel):
    """A TextFrame (or TextPath) element within a spread."""

    self_id: str
    story_id: str                   # references Stories/Story_<id>.xml
    x: float                        # geometric bounds, in points
    y: float
    width: float
    height: float
    applied_paragraph_style: str    # e.g. "ParagraphStyle/Body Text"
    applied_object_style: str | None = None
    master_page: str | None = None  # which master page this belongs to (None = regular spread)
    layer: str = "Default"
    threading_next_id: str | None = None  # ID of next linked frame
    threading_prev_id: str | None = None


class ImageFrame(BaseModel):
    """A Rectangle or Oval used as an image placeholder."""

    self_id: str
    x: float
    y: float
    width: float
    height: float
    applied_object_style: str | None = None
    master_page: str | None = None
    layer: str = "Default"
    linked_image_path: str | None = None  # href if an image is already placed


class Spread(BaseModel):
    """One spread (one or two pages) in the document."""

    filename: str                   # e.g. "Spreads/Spread_ub6.xml"
    spread_id: str
    page_count: int = 1
    text_frames: list[TextFrame] = Field(default_factory=list)
    image_frames: list[ImageFrame] = Field(default_factory=list)


class MasterPage(BaseModel):
    """A master spread (master page template)."""

    filename: str
    spread_id: str
    name: str                       # e.g. "A-Master"
    text_frames: list[TextFrame] = Field(default_factory=list)
    image_frames: list[ImageFrame] = Field(default_factory=list)


class ParagraphStyleProperties(BaseModel):
    font_family: str | None = None
    font_style: str | None = None   # "Regular" | "Bold" | "Italic" | "Bold Italic"
    point_size: float | None = None
    leading: float | None = None
    alignment: str | None = None    # "LeftAlign" | "CenterAlign" | "RightAlign" | "Justified"
    space_before: float | None = None
    space_after: float | None = None


class ParagraphStyle(BaseModel):
    self_id: str
    name: str
    based_on: str | None = None
    properties: ParagraphStyleProperties = Field(default_factory=ParagraphStyleProperties)


class CharacterStyle(BaseModel):
    self_id: str
    name: str
    font_family: str | None = None
    font_style: str | None = None
    point_size: float | None = None


class StyleCatalog(BaseModel):
    paragraph_styles: list[ParagraphStyle] = Field(default_factory=list)
    character_styles: list[CharacterStyle] = Field(default_factory=list)


class ColorSwatch(BaseModel):
    name: str
    model: str      # "CMYK" | "RGB" | "Lab" | "Spot"
    values: list[float]


class StoryContent(BaseModel):
    """Simplified representation of a story's text content."""

    story_id: str
    paragraphs: list[str]           # plain text per paragraph (for analysis only)
    has_overflow: bool = False      # True if InDesign flagged this story as overset


class DesignLayout(BaseModel):
    """Complete parsed structure of one IDML file."""

    source_filename: str
    spreads: list[Spread] = Field(default_factory=list)
    master_pages: list[MasterPage] = Field(default_factory=list)
    style_catalog: StyleCatalog = Field(default_factory=StyleCatalog)
    color_swatches: list[ColorSwatch] = Field(default_factory=list)
    stories: list[StoryContent] = Field(default_factory=list)
    page_width: float = 0.0         # in points
    page_height: float = 0.0
