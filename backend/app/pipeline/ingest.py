"""
Ingestion pipeline — orchestrates IDML + Word parsing and Claude content mapping
to produce and persist a DesignSchema for an example set.
"""

import logging
from pathlib import Path

from backend.app.ai.mapper import map_content
from backend.app.core.storage import Storage
from backend.app.idml.models import DesignLayout, TextFrame
from backend.app.idml.reader import read_idml
from backend.app.models.design_schema import (
    ColorSwatch,
    DesignSchema,
    ExampleAnalysis,
    FrameTemplate,
    SemanticRole,
    TypefaceUsage,
)
from backend.app.word.reader import read_docx

logger = logging.getLogger(__name__)


def _derive_frame_templates(
    layouts: list[DesignLayout],
    analyses: list[ExampleAnalysis],
) -> list[FrameTemplate]:
    """
    Aggregate ContentMappings from all analyses to derive canonical FrameTemplates.

    For each (role, paragraph_style) pair seen across examples, compute the
    median normalised position and size as the 'typical' position.
    """
    from collections import defaultdict

    role_frames: dict[tuple[str, str], list[tuple[float, float, float, float]]] = defaultdict(list)
    role_style: dict[tuple[str, str], str] = {}

    # Build a lookup: frame_id → TextFrame across all layouts
    frame_lookup: dict[str, tuple[TextFrame, DesignLayout]] = {}
    for layout in layouts:
        for spread in layout.spreads:
            for tf in spread.text_frames:
                frame_lookup[tf.self_id] = (tf, layout)

    for analysis in analyses:
        for mapping in analysis.mappings:
            key = (mapping.role, mapping.paragraph_style)
            role_style[key] = mapping.paragraph_style
            if mapping.idml_frame_id in frame_lookup:
                tf, layout = frame_lookup[mapping.idml_frame_id]
                pw = layout.page_width or 595.0
                ph = layout.page_height or 842.0
                role_frames[key].append(
                    (tf.x / pw, tf.y / ph, tf.width / pw, tf.height / ph)
                )

    templates: list[FrameTemplate] = []
    for (role_str, style), positions in role_frames.items():
        n = len(positions)
        avg_x = sum(p[0] for p in positions) / n
        avg_y = sum(p[1] for p in positions) / n
        avg_w = sum(p[2] for p in positions) / n
        avg_h = sum(p[3] for p in positions) / n
        try:
            role = SemanticRole(role_str)
        except ValueError:
            role = SemanticRole.UNKNOWN
        templates.append(
            FrameTemplate(
                role=role,
                typical_x=avg_x,
                typical_y=avg_y,
                typical_width=avg_w,
                typical_height=avg_h,
                applied_paragraph_style=style,
            )
        )

    return templates


def _derive_typefaces(layouts: list[DesignLayout]) -> list[TypefaceUsage]:
    seen: set[str] = set()
    typefaces: list[TypefaceUsage] = []
    for layout in layouts:
        for ps in layout.style_catalog.paragraph_styles:
            key = ps.name
            if key in seen:
                continue
            seen.add(key)
            p = ps.properties
            if p.font_family:
                typefaces.append(
                    TypefaceUsage(
                        paragraph_style_name=ps.name,
                        font_family=p.font_family,
                        font_style=p.font_style or "Regular",
                        point_size=p.point_size or 10.0,
                        leading=p.leading,
                    )
                )
    return typefaces


def _derive_color_palette(layouts: list[DesignLayout]) -> list[ColorSwatch]:
    seen: set[str] = set()
    palette: list[ColorSwatch] = []
    for layout in layouts:
        for swatch in layout.color_swatches:
            if swatch.name not in seen:
                seen.add(swatch.name)
                palette.append(
                    ColorSwatch(name=swatch.name, model=swatch.model, values=swatch.values)
                )
    return palette


def run_ingestion(
    example_set_id: str,
    pairs: list[tuple[Path, list[Path]]],
    storage: Storage,
) -> DesignSchema:
    """
    Ingest a set of (IDML, [Word docs]) example pairs and produce a DesignSchema.

    Each IDML may be paired with one or more Word documents — the content of all
    paired Word docs is sent to Claude together so it can attribute each frame to
    the correct source file.

    Args:
        example_set_id: Unique ID for this example set.
        pairs: List of (idml_path, [word_paths]) tuples.
        storage: Storage instance for persisting the schema.

    Returns:
        The produced DesignSchema (also saved to disk).
    """
    logger.info(
        "Starting ingestion for example_set_id=%s with %d pairs",
        example_set_id,
        len(pairs),
    )

    layouts: list[DesignLayout] = []
    analyses: list[ExampleAnalysis] = []
    context_notes_parts: list[str] = []

    for idml_path, word_paths in pairs:
        logger.info("Parsing IDML: %s", idml_path.name)
        layout = read_idml(idml_path)
        layouts.append(layout)

        word_docs = []
        for word_path in word_paths:
            logger.info("Parsing Word doc: %s", word_path.name)
            word_docs.append(read_docx(word_path))

        word_names = [p.name for p in word_paths]
        logger.info(
            "Running content mapper for pair: %s + %s",
            idml_path.name,
            word_names,
        )
        analysis = map_content(word_docs, layout)
        analyses.append(analysis)

    # Aggregate learned design vocabulary
    frame_templates = _derive_frame_templates(layouts, analyses)
    typefaces = _derive_typefaces(layouts)
    color_palette = _derive_color_palette(layouts)

    # Use the first IDML as the primary template
    primary_template = pairs[0][0].name if pairs else None

    schema = DesignSchema(
        example_set_id=example_set_id,
        frame_templates=frame_templates,
        color_palette=color_palette,
        typefaces=typefaces,
        example_analyses=analyses,
        primary_template_idml=primary_template,
        document_context_notes="\n\n".join(context_notes_parts),
    )

    storage.save_schema(example_set_id, schema.model_dump(mode="json"))

    logger.info(
        "Ingestion complete. Schema saved. frame_templates=%d typefaces=%d",
        len(schema.frame_templates),
        len(schema.typefaces),
    )

    return schema
