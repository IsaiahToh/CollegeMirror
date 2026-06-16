"""
Content Mapper — uses Claude to infer how a Word doc's content was mapped
to an IDML layout, producing a list of ContentMapping objects.
"""

import json
import logging

from pydantic import ValidationError

from backend.app.ai.client import get_llm_client
from backend.app.idml.models import DesignLayout
from backend.app.models.design_schema import ContentMapping, ExampleAnalysis, SemanticRole
from backend.app.word.models import WordDocument

logger = logging.getLogger(__name__)


class ContentMappingError(Exception):
    """Raised when the LLM returns a malformed content mapping."""


# JSON Schema for the extract_content_mapping tool
_MAPPING_SCHEMA: dict = {
    "type": "object",
    "required": ["mappings", "document_context_notes"],
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "word_element_type",
                    "word_text_preview",
                    "idml_frame_id",
                    "idml_spread_index",
                    "role",
                    "paragraph_style",
                ],
                "properties": {
                    "word_element_type": {"type": "string"},
                    "word_text_preview": {"type": "string"},
                    "idml_frame_id": {"type": "string"},
                    "idml_spread_index": {"type": "integer"},
                    "role": {
                        "type": "string",
                        "enum": [r.value for r in SemanticRole],
                    },
                    "paragraph_style": {"type": "string"},
                },
            },
        },
        "document_context_notes": {
            "type": "string",
            "description": "Observations about this document's design patterns, pharmaceutical context, or anything a designer should know.",
        },
    },
}


_MAX_FRAMES_PER_SPREAD = 30  # cap to control token usage on dense layouts


def _summarise_layout(layout: DesignLayout) -> str:
    """Produce a compact JSON summary of the IDML layout for Claude.

    Only frames that reference a story (i.e. have text content) are included,
    capped at _MAX_FRAMES_PER_SPREAD per spread. Story snippets are limited to
    stories actually referenced by the included frames, avoiding token waste on
    empty or purely decorative frames.
    """
    # Build a lookup from story_id → first paragraph snippet
    story_text: dict[str, str] = {
        s.story_id: s.paragraphs[0][:120]
        for s in layout.stories
        if s.paragraphs
    }

    spread_summaries = []
    for i, spread in enumerate(layout.spreads):
        # Only frames with a story reference carry text content
        text_frames = [tf for tf in spread.text_frames if tf.story_id][:_MAX_FRAMES_PER_SPREAD]

        frames = [
            {
                "id": tf.self_id,
                "story_id": tf.story_id,
                "x": round(tf.x, 1),
                "y": round(tf.y, 1),
                "w": round(tf.width, 1),
                "h": round(tf.height, 1),
                "para_style": tf.applied_paragraph_style,
            }
            for tf in text_frames
        ]

        # Only include snippets for stories referenced by the included frames
        referenced_ids = {tf.story_id for tf in text_frames if tf.story_id}
        story_snippets = {sid: story_text[sid] for sid in referenced_ids if sid in story_text}

        spread_summaries.append(
            {"spread_index": i, "filename": spread.filename, "frames": frames, "story_snippets": story_snippets}
        )
    return json.dumps(
        {
            "source_filename": layout.source_filename,
            "page_width_pt": layout.page_width,
            "page_height_pt": layout.page_height,
            "spread_count": len(layout.spreads),
            "spreads": spread_summaries,
            "paragraph_styles": [s.name for s in layout.style_catalog.paragraph_styles],
        },
        indent=2,
    )


def _summarise_word_docs(docs: list[WordDocument]) -> str:
    """
    Produce a compact JSON summary of one or more Word documents for Claude.
    Multiple docs are labelled by filename so Claude knows which content came from where.
    """
    doc_summaries = []
    for doc in docs:
        section_summaries = []
        for sec in doc.sections:
            elements = []
            for el in sec.elements[:20]:
                entry: dict = {"type": el.element_type, "text": el.text[:200] if el.text else ""}
                if el.list_items:
                    entry["items"] = el.list_items[:10]
                if el.table:
                    entry["table_rows"] = el.table.rows
                    entry["table_cols"] = el.table.cols
                if el.figure:
                    entry["caption"] = el.figure.caption
                elements.append(entry)
            section_summaries.append({"title": sec.title, "elements": elements})

        preamble = [
            {"type": el.element_type, "text": el.text[:200]} for el in doc.preamble[:10]
        ]
        doc_summaries.append(
            {
                "source_filename": doc.source_filename,
                "title": doc.title,
                "subject": doc.subject,
                "preamble": preamble,
                "sections": section_summaries,
                "total_word_count": doc.total_word_count,
            }
        )

    return json.dumps(doc_summaries if len(doc_summaries) > 1 else doc_summaries[0], indent=2)


def map_content(
    word_docs: list[WordDocument],
    idml_layout: DesignLayout,
) -> ExampleAnalysis:
    """
    Use Claude to infer how content from one or more Word docs was mapped to an IDML layout.

    Multiple Word docs are sent together so Claude can attribute each frame's content
    to the correct source document.
    """
    client = get_llm_client()

    doc_label = (
        "## Word Documents (multiple source files)\n\n"
        if len(word_docs) > 1
        else "## Word Document\n\n"
    )

    user_message = (
        f"{doc_label}"
        f"```json\n{_summarise_word_docs(word_docs)}\n```\n\n"
        "## InDesign Layout (IDML)\n\n"
        f"```json\n{_summarise_layout(idml_layout)}\n```\n\n"
        "Please analyse how the Word document content was mapped to this InDesign layout "
        "and extract the content mappings."
    )

    result = client.call_structured(
        system_prompt_file="map_content.md",
        user_message=user_message,
        output_schema=_MAPPING_SCHEMA,
        tool_name="extract_content_mapping",
        tool_description="Extract the mapping between Word document elements and InDesign frames.",
    )

    try:
        mappings = [
            ContentMapping(
                word_element_type=m["word_element_type"],
                word_text_preview=m["word_text_preview"],
                idml_frame_id=m["idml_frame_id"],
                idml_spread_index=m["idml_spread_index"],
                role=SemanticRole(m["role"]),
                paragraph_style=m["paragraph_style"],
            )
            for m in result.get("mappings", [])
        ]
        context_notes = str(result.get("document_context_notes", ""))
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        logger.debug("Malformed LLM mapping response: %r", result)
        raise ContentMappingError("LLM returned a malformed content mapping") from exc

    total_pages = sum(s.page_count for s in idml_layout.spreads)
    word_filenames = [d.source_filename for d in word_docs]

    logger.info(
        "Mapped %d content elements from %s → '%s'",
        len(mappings),
        word_filenames,
        idml_layout.source_filename,
    )

    return ExampleAnalysis(
        idml_filename=idml_layout.source_filename,
        word_filenames=word_filenames,
        mappings=mappings,
        spread_count=len(idml_layout.spreads),
        page_count=total_pages,
        document_context_notes=context_notes,
    )
