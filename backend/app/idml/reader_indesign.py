"""
InDesign-backed IDML reader.

Opens an IDML file in the running InDesign instance via MCP and runs a single
ExtendScript that extracts the complete document structure. InDesign resolves
ItemTransform matrices, style inheritance chains, master page overrides, text
threading, and font properties natively — none of which our XML parser handles
reliably.

Returns the same DesignLayout pydantic model as reader.py so the rest of the
pipeline is unaffected.
"""

import logging
from pathlib import Path
from typing import Any

from backend.app.idml.indesign_client import InDesignClient
from backend.app.idml.models import (
    CharacterStyle,
    ColorSwatch,
    DesignLayout,
    ImageFrame,
    MasterPage,
    ParagraphStyle,
    ParagraphStyleProperties,
    Spread,
    StoryContent,
    StyleCatalog,
    TextFrame,
)

logger = logging.getLogger(__name__)

# ── ExtendScript ──────────────────────────────────────────────────────────────
#
# Executed inside InDesign after the document is open. Returns a JSON string
# representing the full DesignLayout. All values use the same field names as the
# pydantic models so _data_to_layout() can map them directly.
#
# Design choices:
# - geometricBounds returns [top, left, bottom, right] in spread coordinates
#   (InDesign has already applied ItemTransform — no matrix math needed).
# - story.overflows is the authoritative overflow flag.
# - allPageItems walks the full item tree including groups.
# - Every block is wrapped in try/catch so a single bad item never aborts the
#   whole extraction.

_EXTRACT_LAYOUT_SCRIPT = r"""
(function() {
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;

    var doc = app.activeDocument;

    var result = {
        source_filename: doc.name,
        page_width:  doc.documentPreferences.pageWidth,
        page_height: doc.documentPreferences.pageHeight,
        spreads:      [],
        master_pages: [],
        style_catalog: { paragraph_styles: [], character_styles: [] },
        color_swatches: [],
        stories: []
    };

    // ── helpers ──────────────────────────────────────────────────────────────

    function bounds(item) {
        var b = item.geometricBounds; // [top, left, bottom, right]
        return { x: b[1], y: b[0], width: b[3] - b[1], height: b[2] - b[0] };
    }

    function safeStyleName(obj) {
        try { return obj ? obj.name : null; } catch(e) { return null; }
    }

    function safeFontName(obj) {
        try { return (obj && obj.isValid) ? obj.name : null; } catch(e) { return null; }
    }

    // Styles that don't override an attribute return a "nothing" object from
    // the DOM rather than a primitive — coerce those to null.
    function prim(v) {
        var t = typeof v;
        return (t === "string" || t === "number" || t === "boolean") ? v : null;
    }

    function collectFrames(container, masterName) {
        var textFrames = [], imageFrames = [];
        var items;
        try { items = container.allPageItems; } catch(e) { return { text_frames: [], image_frames: [] }; }

        for (var j = 0; j < items.length; j++) {
            var item = items[j];
            try {
                var tag = item.constructor.name;
                var b = bounds(item);

                if (tag === "TextFrame") {
                    textFrames.push({
                        self_id:   item.id.toString(),
                        story_id:  item.parentStory.id.toString(),
                        x: b.x, y: b.y, width: b.width, height: b.height,
                        applied_paragraph_style: safeStyleName(item.appliedParagraphStyle) || "",
                        applied_object_style:    safeStyleName(item.appliedObjectStyle),
                        master_page: masterName || null,
                        layer:       item.itemLayer ? item.itemLayer.name : "Default",
                        threading_next_id: item.nextTextFrame
                            ? item.nextTextFrame.id.toString() : null,
                        threading_prev_id: item.previousTextFrame
                            ? item.previousTextFrame.id.toString() : null
                    });
                } else if (tag === "Rectangle" || tag === "Oval" ||
                           tag === "Polygon"   || tag === "GraphicFrame") {
                    var linkedPath = null;
                    try {
                        if (item.graphics.length > 0 && item.graphics[0].itemLink) {
                            linkedPath = item.graphics[0].itemLink.filePath;
                        }
                    } catch(e) {}
                    imageFrames.push({
                        self_id: item.id.toString(),
                        x: b.x, y: b.y, width: b.width, height: b.height,
                        applied_object_style: safeStyleName(item.appliedObjectStyle),
                        master_page: masterName || null,
                        layer: item.itemLayer ? item.itemLayer.name : "Default",
                        linked_image_path: linkedPath
                    });
                }
            } catch(e) {}
        }
        return { text_frames: textFrames, image_frames: imageFrames };
    }

    // ── spreads ───────────────────────────────────────────────────────────────

    for (var i = 0; i < doc.spreads.length; i++) {
        var spread = doc.spreads[i];
        var frames = collectFrames(spread, null);
        result.spreads.push({
            filename:   "Spreads/Spread_" + i + ".xml",
            spread_id:  spread.name || i.toString(),
            page_count: spread.pages.length,
            text_frames:  frames.text_frames,
            image_frames: frames.image_frames
        });
    }

    // ── master spreads ────────────────────────────────────────────────────────

    for (var i = 0; i < doc.masterSpreads.length; i++) {
        var master = doc.masterSpreads[i];
        var frames = collectFrames(master, master.name);
        result.master_pages.push({
            filename:  "MasterSpreads/MasterSpread_" + i + ".xml",
            spread_id: master.id.toString(),
            name:      master.name,
            text_frames:  frames.text_frames,
            image_frames: frames.image_frames
        });
    }

    // ── paragraph styles ──────────────────────────────────────────────────────

    for (var i = 0; i < doc.paragraphStyles.length; i++) {
        var ps = doc.paragraphStyles[i];
        try {
            var leading = null;
            try {
                leading = (ps.leading === Leading.AUTO) ? null : Number(ps.leading);
            } catch(e) {}

            var basedOn = null;
            try {
                if (ps.basedOn && ps.basedOn.name !== "[No paragraph style]") {
                    basedOn = ps.basedOn.name;
                }
            } catch(e) {}

            result.style_catalog.paragraph_styles.push({
                self_id:  ps.id.toString(),
                name:     ps.name,
                based_on: basedOn,
                properties: {
                    font_family:  safeFontName(ps.appliedFont),
                    font_style:   prim(ps.fontStyle),
                    point_size:   prim(ps.pointSize),
                    leading:      leading,
                    alignment:    ps.justification ? ps.justification.toString() : null,
                    space_before: prim(ps.spaceBefore),
                    space_after:  prim(ps.spaceAfter)
                }
            });
        } catch(e) {}
    }

    // ── character styles ──────────────────────────────────────────────────────

    for (var i = 0; i < doc.characterStyles.length; i++) {
        var cs = doc.characterStyles[i];
        try {
            result.style_catalog.character_styles.push({
                self_id:     cs.id.toString(),
                name:        cs.name,
                font_family: safeFontName(cs.appliedFont),
                font_style:  prim(cs.fontStyle),
                point_size:  prim(cs.pointSize)
            });
        } catch(e) {}
    }

    // ── color swatches ────────────────────────────────────────────────────────

    var skipColors = { "None": 1, "Paper": 1, "Black": 1, "Registration": 1 };
    for (var i = 0; i < doc.colors.length; i++) {
        var color = doc.colors[i];
        try {
            if (skipColors[color.name]) continue;
            var vals = [];
            try { vals = color.colorValue; } catch(e) {}
            result.color_swatches.push({
                name:   color.name,
                model:  color.model.toString(),
                values: vals
            });
        } catch(e) {}
    }

    // ── stories ───────────────────────────────────────────────────────────────

    for (var i = 0; i < doc.stories.length; i++) {
        var story = doc.stories[i];
        try {
            var paras = [];
            for (var j = 0; j < story.paragraphs.length; j++) {
                var text = story.paragraphs[j].contents;
                if (text && text.replace(/[\s\r\n]/g, "").length > 0) {
                    paras.push(text.substring(0, 500));
                }
            }
            if (paras.length === 0) continue;
            var overflows = false;
            try { overflows = !!story.overflows; } catch(e) {}
            result.stories.push({
                story_id:    story.id.toString(),
                paragraphs:  paras,
                has_overflow: overflows
            });
        } catch(e) {}
    }

    return JSON.stringify(result);
})();
"""


# ── Public API ────────────────────────────────────────────────────────────────

async def read_idml_indesign(path: Path) -> DesignLayout:
    """
    Open an IDML file in InDesign and extract its layout authoritatively.
    InDesign must be running and INDESIGN_MCP_SERVER_PATH must be configured.
    """
    logger.info("Reading IDML via InDesign: %s", path.name)

    async with InDesignClient() as client:
        await client.open_document(path)
        try:
            data = await client.execute_script_json(_EXTRACT_LAYOUT_SCRIPT)
        finally:
            await client.close_document(save=False)

    layout = _data_to_layout(data)
    logger.info(
        "InDesign reader: %d spreads, %d styles, %d stories from '%s'",
        len(layout.spreads),
        len(layout.style_catalog.paragraph_styles),
        len(layout.stories),
        path.name,
    )
    return layout


# ── Data → pydantic ───────────────────────────────────────────────────────────

def _text_frame(d: dict[str, Any]) -> TextFrame:
    return TextFrame(
        self_id=d["self_id"],
        story_id=d["story_id"],
        x=d["x"],
        y=d["y"],
        width=d["width"],
        height=d["height"],
        applied_paragraph_style=d.get("applied_paragraph_style", ""),
        applied_object_style=d.get("applied_object_style"),
        master_page=d.get("master_page"),
        layer=d.get("layer", "Default"),
        threading_next_id=d.get("threading_next_id"),
        threading_prev_id=d.get("threading_prev_id"),
    )


def _image_frame(d: dict[str, Any]) -> ImageFrame:
    return ImageFrame(
        self_id=d["self_id"],
        x=d["x"],
        y=d["y"],
        width=d["width"],
        height=d["height"],
        applied_object_style=d.get("applied_object_style"),
        master_page=d.get("master_page"),
        layer=d.get("layer", "Default"),
        linked_image_path=d.get("linked_image_path"),
    )


def _data_to_layout(data: dict[str, Any]) -> DesignLayout:
    spreads = [
        Spread(
            filename=s["filename"],
            spread_id=s["spread_id"],
            page_count=s["page_count"],
            text_frames=[_text_frame(tf) for tf in s.get("text_frames", [])],
            image_frames=[_image_frame(img) for img in s.get("image_frames", [])],
        )
        for s in data.get("spreads", [])
    ]

    master_pages = [
        MasterPage(
            filename=m["filename"],
            spread_id=m["spread_id"],
            name=m["name"],
            text_frames=[_text_frame(tf) for tf in m.get("text_frames", [])],
            image_frames=[_image_frame(img) for img in m.get("image_frames", [])],
        )
        for m in data.get("master_pages", [])
    ]

    sc = data.get("style_catalog", {})
    style_catalog = StyleCatalog(
        paragraph_styles=[
            ParagraphStyle(
                self_id=ps["self_id"],
                name=ps["name"],
                based_on=ps.get("based_on"),
                properties=ParagraphStyleProperties(
                    **{k: v for k, v in ps.get("properties", {}).items() if v is not None}
                ),
            )
            for ps in sc.get("paragraph_styles", [])
        ],
        character_styles=[
            CharacterStyle(
                self_id=cs["self_id"],
                name=cs["name"],
                font_family=cs.get("font_family"),
                font_style=cs.get("font_style"),
                point_size=cs.get("point_size"),
            )
            for cs in sc.get("character_styles", [])
        ],
    )

    return DesignLayout(
        source_filename=data.get("source_filename", ""),
        spreads=spreads,
        master_pages=master_pages,
        style_catalog=style_catalog,
        color_swatches=[ColorSwatch(**sw) for sw in data.get("color_swatches", [])],
        stories=[StoryContent(**s) for s in data.get("stories", [])],
        page_width=float(data.get("page_width", 0.0)),
        page_height=float(data.get("page_height", 0.0)),
    )
