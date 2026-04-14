"""LayoutPlan — Claude's spread-by-spread content assignment for a new document."""

from pydantic import BaseModel, Field

from backend.app.models.design_schema import SemanticRole


class ContentAssignment(BaseModel):
    """Assigns one piece of content to one frame on a spread."""

    role: SemanticRole
    paragraph_style: str
    text: str                           # the actual text content to place
    frame_index: int = 0               # which frame of that role on the spread (0-based)


class SpreadPlan(BaseModel):
    """Plan for a single spread (one or two pages)."""

    spread_index: int
    spread_purpose: str                 # e.g. "cover", "executive summary", "section 2 body"
    template_spread_source: str        # which example IDML spread to clone (spread XML filename)
    assignments: list[ContentAssignment] = Field(default_factory=list)
    image_frame_notes: list[str] = Field(default_factory=list)  # notes for designer on images


class LayoutPlan(BaseModel):
    """
    Claude's complete layout plan for a new document. Produced by ai/planner.py
    and consumed by idml/writer.py.
    """

    document_title: str
    total_spreads: int
    spreads: list[SpreadPlan] = Field(default_factory=list)
    global_notes: str = ""              # any overarching observations for the designer
