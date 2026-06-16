"""
InDesign-backed IDML writer.

Opens the template IDML in the running InDesign instance, applies the LayoutPlan
via a single ExtendScript call, then exports the result as IDML. InDesign handles
text reflow, overflow detection, style application, and font resolution natively.

The ExtendScript receives the full LayoutPlan as an embedded JSON literal and
applies it by:
  1. Adjusting page/spread count to match plan.total_spreads.
  2. For each SpreadPlan, iterating text frames and matching ContentAssignments
     by paragraph style name (same heuristic as the XML writer, but in JS).
  3. Setting story.contents — InDesign creates one paragraph per \\n.
  4. Applying the named paragraph style to all paragraphs in the story.
  5. Clearing any text frame that received no assignment, so the example's
     original words never leak into the output.
  6. Removing placed source-document images (content figures), while keeping
     full-bleed background / design images.
  7. Shrinking each filled frame to fit short content (shrink-only — overset
     frames are left at template size and flagged, never grown or truncated).

Returns a list of warning strings (overset text, unmatched frames, etc.).
"""

import json
import logging
from pathlib import Path

from backend.app.idml.indesign_client import InDesignClient
from backend.app.models.layout_plan import LayoutPlan

logger = logging.getLogger(__name__)

# ── ExtendScript template ─────────────────────────────────────────────────────
#
# PLAN_JSON_LITERAL is replaced at runtime with a JSON.parse(...) expression
# embedding the serialised LayoutPlan. Using json.dumps(json_string) gives a
# valid JS string literal with all special characters properly escaped.

_APPLY_PLAN_SCRIPT = """\
(function() {{
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;

    var doc = app.activeDocument;
    var plan = JSON.parse({plan_json_literal});
    var warnings = [];

    // ── adjust spread count ───────────────────────────────────────────────────

    var targetSpreads = plan.total_spreads;
    // Add pages until we have enough spreads
    while (doc.spreads.length < targetSpreads) {{
        doc.pages.add(LocationOptions.AT_END);
    }}
    // Remove trailing spreads (never remove the last one)
    while (doc.spreads.length > targetSpreads && doc.spreads.length > 1) {{
        var lastSpread = doc.spreads[doc.spreads.length - 1];
        for (var p = lastSpread.pages.length - 1; p >= 0; p--) {{
            if (doc.pages.length > 1) {{
                lastSpread.pages[p].remove();
            }}
        }}
    }}

    // ── apply each spread plan ────────────────────────────────────────────────

    for (var si = 0; si < plan.spreads.length; si++) {{
        var sp = plan.spreads[si];
        if (sp.spread_index >= doc.spreads.length) {{
            warnings.push("spread_index " + sp.spread_index + " out of range (doc has " + doc.spreads.length + " spreads)");
            continue;
        }}

        var spread = doc.spreads[sp.spread_index];
        // Collect text frames ordered top-to-bottom, left-to-right
        var tfList = [];
        try {{
            var raw = spread.textFrames.everyItem().getElements();
            tfList = raw.slice();
            tfList.sort(function(a, b) {{
                var ba = a.geometricBounds, bb = b.geometricBounds;
                var dy = ba[0] - bb[0];
                return (Math.abs(dy) > 10) ? dy : (ba[1] - bb[1]);
            }});
        }} catch(e) {{
            warnings.push("Could not collect text frames for spread " + sp.spread_index + ": " + e.message);
            continue;
        }}

        var usedIds = {{}};

        for (var ai = 0; ai < sp.assignments.length; ai++) {{
            var a = sp.assignments[ai];
            var matched = false;

            // Pass 1: style-name match
            for (var fi = 0; fi < tfList.length; fi++) {{
                var tf = tfList[fi];
                if (usedIds[tf.id]) continue;
                var sn = "";
                try {{ sn = tf.appliedParagraphStyle ? tf.appliedParagraphStyle.name : ""; }} catch(e) {{}}
                if (sn.indexOf(a.paragraph_style) !== -1 || a.paragraph_style.indexOf(sn) !== -1) {{
                    applyAssignment(doc, tf, a, warnings);
                    usedIds[tf.id] = true;
                    matched = true;
                    break;
                }}
            }}

            // Pass 2: first unmatched frame
            if (!matched) {{
                for (var fi = 0; fi < tfList.length; fi++) {{
                    var tf = tfList[fi];
                    if (!usedIds[tf.id]) {{
                        applyAssignment(doc, tf, a, warnings);
                        usedIds[tf.id] = true;
                        matched = true;
                        break;
                    }}
                }}
            }}

            if (!matched) {{
                warnings.push("No frame available for role '" + a.role + "' on spread " + sp.spread_index);
            }}
        }}

        // ── clear text frames that received no assignment ─────────────────────
        // Otherwise the example's original words leak into the output.
        for (var ci = 0; ci < tfList.length; ci++) {{
            var ctf = tfList[ci];
            if (usedIds[ctf.id]) continue;
            try {{ ctf.parentStory.contents = ""; }} catch(e) {{}}
            warnings.push("Cleared unassigned text frame id=" + ctf.id + " on spread " + sp.spread_index);
        }}

        // ── remove source-document images, keep full-bleed backgrounds ────────
        try {{
            var pageW = doc.documentPreferences.pageWidth;
            var pageH = doc.documentPreferences.pageHeight;
            var pageArea = pageW * pageH;
            var graphics = spread.allGraphics;
            for (var gi = graphics.length - 1; gi >= 0; gi--) {{
                try {{
                    var frame = graphics[gi].parent;
                    var fb = frame.geometricBounds; // [y1, x1, y2, x2]
                    var fArea = Math.abs((fb[2] - fb[0]) * (fb[3] - fb[1]));
                    if (pageArea > 0 && fArea >= 0.8 * pageArea) continue; // background — keep
                    frame.remove();
                    warnings.push("Removed source image frame on spread " + sp.spread_index + " (content figure)");
                }} catch(e) {{}}
            }}
        }} catch(e) {{
            warnings.push("Image cleanup failed on spread " + sp.spread_index + ": " + e.message);
        }}
    }}

    return JSON.stringify({{ warnings: warnings }});
}})();

function applyAssignment(doc, tf, assignment, warnings) {{
    try {{
        var story = tf.parentStory;
        // Replace all story content; InDesign creates one paragraph per \\n
        story.contents = assignment.text;

        // Apply paragraph style to every paragraph in the story
        var style = doc.paragraphStyles.itemByName(assignment.paragraph_style);
        if (style.isValid) {{
            for (var p = 0; p < story.paragraphs.length; p++) {{
                try {{ story.paragraphs[p].appliedParagraphStyle = style; }} catch(e) {{}}
            }}
        }} else {{
            warnings.push("Paragraph style not found: '" + assignment.paragraph_style + "'");
        }}

        // Shrink the frame to fit short content, or report overflow for long
        // content. Shrink-only: an overset frame is left at template size (all
        // text is preserved as overset, never cut off) and flagged for the
        // designer; we never grow a frame into its neighbours.
        var overflows = false;
        try {{ overflows = !!story.overflows; }} catch(e) {{}}
        if (overflows) {{
            warnings.push("Overset text in spread " + (assignment.role || "?") +
                          " (frame id=" + tf.id + ")");
        }} else {{
            try {{
                var ob = tf.geometricBounds;        // [top, left, bottom, right]
                tf.fit(FitOptions.FRAME_TO_CONTENT);
                var nb = tf.geometricBounds;
                // Preserve original top/left/right and width; only move the
                // bottom edge up so the frame hugs the text. Never grow.
                tf.geometricBounds = [ob[0], ob[1], Math.min(nb[2], ob[2]), ob[3]];
            }} catch(e) {{
                warnings.push("Could not fit frame id=" + tf.id + ": " + e.message);
            }}
        }}
    }} catch(e) {{
        warnings.push("Error applying assignment role='" + (assignment.role || "?") +
                      "' frame=" + tf.id + ": " + e.message);
    }}
}}
"""


# ── Public API ────────────────────────────────────────────────────────────────

class InDesignWriter:
    """Apply a LayoutPlan to a template IDML using InDesign and export as IDML."""

    def __init__(self, template_idml_path: Path) -> None:
        if not template_idml_path.exists():
            raise FileNotFoundError(f"Template IDML not found: {template_idml_path}")
        self._template_path = template_idml_path

    async def apply_plan(self, plan: LayoutPlan, output_path: Path) -> list[str]:
        """
        Apply a LayoutPlan to the template IDML via InDesign and write the
        result to output_path as IDML.

        Returns a list of warning strings (overflow, missing styles, etc.).
        """
        # Serialise the plan and embed it as a safe JS string literal
        plan_json = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False)
        plan_json_literal = json.dumps(plan_json)  # JSON-encodes the string → valid JS literal

        script = _APPLY_PLAN_SCRIPT.format(plan_json_literal=plan_json_literal)

        logger.info(
            "Applying layout plan via InDesign: %d spreads, template=%s",
            len(plan.spreads),
            self._template_path.name,
        )

        async with InDesignClient() as client:
            await client.open_document(self._template_path)
            try:
                result = await client.execute_script_json(script)
                warnings: list[str] = result.get("warnings", [])
                await client.export_as_idml(output_path)
            finally:
                await client.close_document(save=False)

        if warnings:
            logger.warning(
                "InDesign writer produced %d warning(s) for '%s': %s",
                len(warnings),
                self._template_path.name,
                warnings,
            )

        return warnings
