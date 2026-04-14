"""
Layout Planner — uses Claude to produce a spread-by-spread LayoutPlan
from a new WordDocument and a DesignSchema.
"""

import json
import logging

from backend.app.ai.client import get_llm_client
from backend.app.models.design_schema import DesignSchema, SemanticRole
from backend.app.models.layout_plan import ContentAssignment, LayoutPlan, SpreadPlan
from backend.app.word.models import WordDocument

logger = logging.getLogger(__name__)

# JSON Schema for the create_layout_plan tool
_PLAN_SCHEMA: dict = {
    "type": "object",
    "required": ["document_title", "total_spreads", "spreads", "global_notes"],
    "properties": {
        "document_title": {"type": "string"},
        "total_spreads": {"type": "integer"},
        "global_notes": {"type": "string"},
        "spreads": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "spread_index",
                    "spread_purpose",
                    "template_spread_source",
                    "assignments",
                    "image_frame_notes",
                ],
                "properties": {
                    "spread_index": {"type": "integer"},
                    "spread_purpose": {"type": "string"},
                    "template_spread_source": {"type": "string"},
                    "image_frame_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "assignments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["role", "paragraph_style", "text", "frame_index"],
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "enum": [r.value for r in SemanticRole],
                                },
                                "paragraph_style": {"type": "string"},
                                "text": {"type": "string"},
                                "frame_index": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def _schema_to_context(schema: DesignSchema) -> str:
    """Serialise the DesignSchema into a compact JSON block for Claude's context."""
    # Include only what Claude needs for planning — avoid massive payloads
    data = {
        "example_set_id": schema.example_set_id,
        "document_context_notes": schema.document_context_notes,
        "primary_template_idml": schema.primary_template_idml,
        "available_spreads": [
            {
                "filename": a.idml_filename,
                "spread_count": a.spread_count,
                "page_count": a.page_count,
            }
            for a in schema.example_analyses
        ],
        "frame_templates": [
            {
                "role": ft.role,
                "para_style": ft.applied_paragraph_style,
                "typical_position": [round(ft.typical_x, 3), round(ft.typical_y, 3)],
                "typical_size": [round(ft.typical_width, 3), round(ft.typical_height, 3)],
                "master_page": ft.master_page,
            }
            for ft in schema.frame_templates
        ],
        "paragraph_styles": [t.paragraph_style_name for t in schema.typefaces],
    }
    return f"## DesignSchema\n\n```json\n{json.dumps(data, indent=2)}\n```"


def _word_doc_to_context(doc: WordDocument) -> str:
    """Serialise the new WordDocument for Claude."""
    sections_data = []
    for sec in doc.sections:
        elements = []
        for el in sec.elements:
            entry: dict = {"type": el.element_type, "text": el.text[:500] if el.text else ""}
            if el.list_items:
                entry["items"] = el.list_items
            if el.table:
                entry["table"] = el.table.to_markdown()
            if el.figure:
                entry["caption"] = el.figure.caption
            elements.append(entry)
        sections_data.append({"heading": sec.title, "elements": elements})

    preamble = [{"type": el.element_type, "text": el.text[:300]} for el in doc.preamble]

    data = {
        "filename": doc.source_filename,
        "title": doc.title,
        "subject": doc.subject,
        "preamble": preamble,
        "sections": sections_data,
        "total_word_count": doc.total_word_count,
        "figure_count": len(doc.figures),
    }
    return f"## New Word Document\n\n```json\n{json.dumps(data, indent=2)}\n```"


def plan_layout(word_doc: WordDocument, schema: DesignSchema) -> LayoutPlan:
    """
    Use Claude to plan a spread-by-spread layout for a new document.

    Args:
        word_doc: The new document whose content needs to be laid out.
        schema: The DesignSchema learned from example pairs.

    Returns:
        A LayoutPlan ready to be consumed by the IDML Writer.
    """
    client = get_llm_client()

    schema_context = _schema_to_context(schema)
    word_context = _word_doc_to_context(word_doc)

    user_message = (
        f"{word_context}\n\n"
        "Please create a complete spread-by-spread layout plan for this document, "
        "using the DesignSchema as your guide for frame templates and styles."
    )

    result = client.call_structured(
        system_prompt_file="plan_layout.md",
        user_message=user_message,
        output_schema=_PLAN_SCHEMA,
        tool_name="create_layout_plan",
        tool_description="Create a complete spread-by-spread layout plan for the new InDesign document.",
        extra_system_context=schema_context,
    )

    spreads = [
        SpreadPlan(
            spread_index=sp["spread_index"],
            spread_purpose=sp["spread_purpose"],
            template_spread_source=sp["template_spread_source"],
            image_frame_notes=sp.get("image_frame_notes", []),
            assignments=[
                ContentAssignment(
                    role=SemanticRole(a["role"]),
                    paragraph_style=a["paragraph_style"],
                    text=a["text"],
                    frame_index=a.get("frame_index", 0),
                )
                for a in sp.get("assignments", [])
            ],
        )
        for sp in result.get("spreads", [])
    ]

    plan = LayoutPlan(
        document_title=result.get("document_title", word_doc.title or "Untitled"),
        total_spreads=result.get("total_spreads", len(spreads)),
        spreads=spreads,
        global_notes=result.get("global_notes", ""),
    )

    logger.info(
        "Layout plan created: %d spreads for '%s'",
        len(plan.spreads),
        plan.document_title,
    )

    return plan
