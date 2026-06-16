"""
IDML Writer — clones an example IDML, applies a LayoutPlan, and produces a new IDML file.

Strategy (clone-and-modify):
  1. Unzip the example IDML into memory
  2. For each spread in the LayoutPlan, clone the appropriate template spread XML
  3. Substitute <Content> elements in the linked Story XMLs
  4. Rezip everything into a new IDML file

Invariant: We only mutate <Content> elements and spread order.
           All style references, font embeds, master page links, and color swatches
           are preserved from the source IDML.
"""

import copy
import io
import logging
import zipfile
from pathlib import Path

from lxml import etree

from backend.app.models.layout_plan import ContentAssignment, LayoutPlan

logger = logging.getLogger(__name__)

# Only Content elements inside ParagraphStyleRange/CharacterStyleRange are mutated
_CONTENT_TAG = "Content"

# Graphic-frame tags that may hold a placed image, and the placed-image child
# tags that mark a frame as carrying real artwork (vs a decorative shape).
_IMAGE_FRAME_TAGS = {"Rectangle", "Oval", "Polygon", "GraphicLine"}
_PLACED_IMAGE_TAGS = {"Image", "EPS", "PDF", "WMF"}

# A placed image covering at least this fraction of the page is treated as a
# background / design element and kept; anything smaller is treated as a
# source-document figure and removed.
_BACKGROUND_AREA_FRACTION = 0.8


class IDMLWriteError(Exception):
    pass


def _read_xml(zf: zipfile.ZipFile, filename: str) -> etree._Element:
    """Parse an XML file from the ZIP into an lxml Element."""
    try:
        return etree.fromstring(zf.read(filename))
    except KeyError:
        raise IDMLWriteError(f"File not found in IDML archive: {filename}") from None
    except etree.XMLSyntaxError as e:
        raise IDMLWriteError(f"Malformed XML in {filename}: {e}") from e


def _serialise_xml(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=False)


def _find_text_frames_in_spread(spread_root: etree._Element) -> list[etree._Element]:
    """Return all TextFrame elements in a spread XML tree."""
    return spread_root.findall(".//TextFrame")


def _get_story_id(text_frame: etree._Element) -> str | None:
    return text_frame.get("ParentStory")


def _get_story_element(story_root: etree._Element) -> etree._Element:
    """
    Return the inner <Story> element from an idPkg:Story wrapper root.
    Story XML files have a <idPkg:Story> root wrapping the actual <Story> child.
    """
    inner = story_root.find("Story")
    return inner if inner is not None else story_root


def _rebuild_story_content(
    story_root: etree._Element, text: str, paragraph_style: str
) -> None:
    """
    Reconstruct a story's content with correct IDML nesting:
    ParagraphStyleRange > CharacterStyleRange > Content.

    Clones the first existing ParagraphStyleRange as a structural template so
    character styles and local overrides are preserved. One PSR is emitted per
    newline-delimited paragraph in `text`.
    """
    inner = _get_story_element(story_root)

    template_psr = inner.find("ParagraphStyleRange")
    if template_psr is None:
        # No existing structure — fall back to direct Content mutation
        for c in story_root.findall(".//" + _CONTENT_TAG):
            c.text = text
        return

    template_clone = copy.deepcopy(template_psr)

    # Remove all existing ParagraphStyleRange direct children
    for psr in list(inner.findall("ParagraphStyleRange")):
        inner.remove(psr)

    paragraphs = [p for p in text.split("\n") if p.strip()] or [text]
    for para_text in paragraphs:
        new_psr = copy.deepcopy(template_clone)
        new_psr.set("AppliedParagraphStyle", paragraph_style)

        # Set text on the first Content element; blank out any extras
        content_elems = new_psr.findall(".//" + _CONTENT_TAG)
        for i, content in enumerate(content_elems):
            content.text = para_text if i == 0 else ""

        inner.append(new_psr)


def _clear_story_content(story_root: etree._Element) -> None:
    """Blank every Content element in a story, preserving its style structure.

    Used for text frames the layout plan never assigned content to, so the
    example's original words don't leak into the generated document.
    """
    for content in story_root.findall(".//" + _CONTENT_TAG):
        content.text = ""


_A4_POINTS = (595.275590551, 841.889763778)


def _bounds_wh(geometric_bounds: str | None) -> tuple[float, float] | None:
    """Width/height from a 'y1 x1 y2 x2' GeometricBounds string, or None."""
    if not geometric_bounds:
        return None
    parts = geometric_bounds.split()
    if len(parts) != 4:
        return None
    try:
        y1, x1, y2, x2 = (float(p) for p in parts)
    except ValueError:
        return None
    return abs(x2 - x1), abs(y2 - y1)


def _doc_page_size(zf: zipfile.ZipFile, names: set[str]) -> tuple[float, float]:
    """Document page size from Resources/Preferences.xml, falling back to A4.

    Real IDML keeps page dimensions in Preferences.xml (not designmap.xml).
    """
    if "Resources/Preferences.xml" in names:
        try:
            root = etree.fromstring(zf.read("Resources/Preferences.xml"))
            pref = root.find(".//DocumentPreference")
            if pref is not None:
                w = float(pref.get("PageWidth", "0"))
                h = float(pref.get("PageHeight", "0"))
                if w > 0 and h > 0:
                    return w, h
        except (etree.XMLSyntaxError, TypeError, ValueError):
            pass
    return _A4_POINTS


def _spread_page_size(
    spread_root: etree._Element, fallback: tuple[float, float]
) -> tuple[float, float]:
    """Page size from the spread's first <Page> GeometricBounds, else fallback."""
    page = spread_root.find(".//Page")
    if page is not None:
        wh = _bounds_wh(page.get("GeometricBounds"))
        if wh:
            return wh
    return fallback


def _frame_area(frame: etree._Element) -> float:
    """Area of a frame in square points.

    Prefers a GeometricBounds attribute (TextFrames), then falls back to the
    bounding box of the frame's <PathGeometry> anchor points (graphic frames
    like Rectangle/Oval, which carry no GeometricBounds attribute in real IDML).
    """
    wh = _bounds_wh(frame.get("GeometricBounds"))
    if wh:
        return wh[0] * wh[1]

    xs: list[float] = []
    ys: list[float] = []
    for pt in frame.findall(".//PathPointType"):
        anchor = (pt.get("Anchor") or "").split()
        if len(anchor) != 2:
            continue
        try:
            xs.append(float(anchor[0]))
            ys.append(float(anchor[1]))
        except ValueError:
            continue
    if len(xs) >= 2 and len(ys) >= 2:
        return abs(max(xs) - min(xs)) * abs(max(ys) - min(ys))
    return 0.0


def _strip_source_images(
    spread_root: etree._Element,
    page_w: float,
    page_h: float,
    warnings: list[str],
) -> None:
    """Remove placed source-document images from a spread, keeping backgrounds.

    A frame is removed only if it (a) actually contains a placed image and
    (b) covers less than `_BACKGROUND_AREA_FRACTION` of the page — i.e. a
    content figure rather than a full-bleed background or design element.
    Decorative shapes with no placed image are always kept.
    """
    page_area = page_w * page_h
    for frame in list(spread_root.iter()):
        if frame.tag not in _IMAGE_FRAME_TAGS:
            continue
        if not any(frame.find(tag) is not None for tag in _PLACED_IMAGE_TAGS):
            continue  # decorative shape, not a placed image — keep
        if page_area > 0 and _frame_area(frame) >= _BACKGROUND_AREA_FRACTION * page_area:
            continue  # full-bleed background / design element — keep
        parent = frame.getparent()
        if parent is not None:
            parent.remove(frame)
            warnings.append(
                f"Removed source image frame {frame.get('Self', '?')} "
                "(content figure — designer to re-place)"
            )


def _clone_spread(
    template_spread_root: etree._Element,
    new_spread_index: int,
) -> etree._Element:
    """Deep-clone a spread element and assign new IDs to avoid conflicts."""
    cloned = copy.deepcopy(template_spread_root)
    spread_elem = cloned.find(".//Spread")
    if spread_elem is None:
        spread_elem = cloned.find(".//MasterSpread")
    if spread_elem is not None:
        old_id = spread_elem.get("Self", "")
        new_id = f"spread_{new_spread_index:04d}"
        spread_elem.set("Self", new_id)
        # Update child element IDs to be unique
        for child in spread_elem.iter():
            child_id = child.get("Self")
            if child_id and child_id.startswith(old_id):
                child.set("Self", child_id.replace(old_id, new_id, 1))
    return cloned


def _update_designmap(
    designmap_root: etree._Element,
    spread_filenames: list[str],
) -> etree._Element:
    """
    Update designmap.xml to reference the new set of spread filenames.
    Removes old Spread entries and adds new ones.
    """
    ns = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"

    # Remove existing Spread entries
    for spread_ref in designmap_root.findall(f"{{{ns}}}Spread"):
        designmap_root.remove(spread_ref)

    # Insert new Spread entries (before the first Story entry, or at end)
    first_story = designmap_root.find(f"{{{ns}}}Story")
    insert_pos = list(designmap_root).index(first_story) if first_story is not None else len(designmap_root)

    for i, filename in enumerate(spread_filenames):
        elem = etree.SubElement(designmap_root, f"{{{ns}}}Spread")
        elem.set("src", filename)
        # Move to correct position
        designmap_root.remove(elem)
        designmap_root.insert(insert_pos + i, elem)

    return designmap_root


class IDMLWriter:
    """
    Stateful writer that holds the IDML archive in memory and applies a LayoutPlan.
    """

    def __init__(self, template_idml_path: Path) -> None:
        if not template_idml_path.exists():
            raise IDMLWriteError(f"Template IDML not found: {template_idml_path}")
        self._template_bytes = template_idml_path.read_bytes()
        self._template_names: set[str] = set()
        with zipfile.ZipFile(io.BytesIO(self._template_bytes), "r") as zf:
            self._template_names = set(zf.namelist())

    def _load_template_spread(self, zf: zipfile.ZipFile, filename: str) -> etree._Element:
        """Load and return a spread XML root from the template archive."""
        if filename not in self._template_names:
            # Try to find a similar spread file
            candidates = [n for n in self._template_names if n.startswith("Spreads/")]
            if not candidates:
                raise IDMLWriteError("No spread files found in template IDML")
            filename = candidates[0]
            logger.warning("Requested spread '%s' not found; using '%s' instead", filename, candidates[0])
        return _read_xml(zf, filename)

    def apply_plan(self, plan: LayoutPlan, output_path: Path) -> list[str]:
        """
        Apply a LayoutPlan to the template IDML and write the result to output_path.

        Returns a list of warning messages (e.g. overflow indicators).
        """
        warnings: list[str] = []

        with zipfile.ZipFile(io.BytesIO(self._template_bytes), "r") as template_zf:
            # Build the output archive in memory
            output_buffer = io.BytesIO()

            with zipfile.ZipFile(output_buffer, "w", compression=zipfile.ZIP_DEFLATED) as out_zf:
                # Copy static files from template (master pages, resources, META-INF, etc.)
                # Stories are excluded here — they are written separately after content substitution.
                spread_files_in_template = {
                    n for n in self._template_names if n.startswith("Spreads/")
                }
                story_files_in_template = {
                    n for n in self._template_names if n.startswith("Stories/")
                }
                files_to_copy = (
                    self._template_names
                    - spread_files_in_template
                    - story_files_in_template
                    - {"designmap.xml"}
                )

                for fname in files_to_copy:
                    out_zf.writestr(fname, template_zf.read(fname))

                # Collect all stories so we can update them
                story_roots: dict[str, etree._Element] = {}
                for fname in self._template_names:
                    if fname.startswith("Stories/") and fname.endswith(".xml"):
                        story_roots[fname] = _read_xml(template_zf, fname)

                # Read designmap once for the final spread-list update, and the
                # document page size (for classifying background vs content images).
                designmap_root = _read_xml(template_zf, "designmap.xml")
                doc_page_size = _doc_page_size(template_zf, self._template_names)

                # Process each spread in the layout plan
                new_spread_filenames: list[str] = []

                for spread_plan in plan.spreads:
                    spread_filename = f"Spreads/Spread_{spread_plan.spread_index:04d}.xml"
                    new_spread_filenames.append(spread_filename)

                    # Clone the template spread
                    template_spread_root = self._load_template_spread(
                        template_zf, spread_plan.template_spread_source
                    )
                    cloned_spread = _clone_spread(template_spread_root, spread_plan.spread_index)

                    # Drop source-document images, keeping backgrounds/design elements
                    page_w, page_h = _spread_page_size(cloned_spread, doc_page_size)
                    _strip_source_images(cloned_spread, page_w, page_h, warnings)

                    # Get text frames from the cloned spread
                    text_frames = _find_text_frames_in_spread(cloned_spread)

                    # Group assignments by role for frame matching
                    assignments_by_role: dict[str, list[ContentAssignment]] = {}
                    for assignment in spread_plan.assignments:
                        role_key = assignment.role.value
                        assignments_by_role.setdefault(role_key, []).append(assignment)

                    # Match frames to assignments (best-effort: match by style similarity)
                    frame_assignment_map: dict[str, ContentAssignment] = {}
                    for assignment in spread_plan.assignments:
                        # Find a text frame whose paragraph style matches the assignment's style
                        for tf in text_frames:
                            tf_id = tf.get("Self", "")
                            if tf_id in frame_assignment_map:
                                continue
                            current_style = tf.get("AppliedParagraphStyle", "")
                            if assignment.paragraph_style in current_style or current_style in assignment.paragraph_style:
                                frame_assignment_map[tf_id] = assignment
                                break
                        else:
                            # No style match found — use the next unassigned frame
                            for tf in text_frames:
                                tf_id = tf.get("Self", "")
                                if tf_id not in frame_assignment_map:
                                    frame_assignment_map[tf_id] = assignment
                                    break

                    # Pass 1 — apply assignments to matched frames.
                    assigned_story_fnames: set[str] = set()
                    for tf in text_frames:
                        tf_id = tf.get("Self", "")
                        story_id = _get_story_id(tf)
                        assignment = frame_assignment_map.get(tf_id)

                        if assignment is None or not story_id:
                            continue

                        story_fname = f"Stories/Story_{story_id}.xml"
                        if story_fname not in story_roots:
                            logger.warning("Story file not found: %s", story_fname)
                            continue

                        _rebuild_story_content(
                            story_roots[story_fname], assignment.text, assignment.paragraph_style
                        )
                        assigned_story_fnames.add(story_fname)

                    # Pass 2 — clear any text frame that received no assignment, so
                    # the example's original words don't leak into the output.
                    for tf in text_frames:
                        tf_id = tf.get("Self", "")
                        story_id = _get_story_id(tf)
                        if not story_id or tf_id in frame_assignment_map:
                            continue

                        story_fname = f"Stories/Story_{story_id}.xml"
                        if story_fname not in story_roots or story_fname in assigned_story_fnames:
                            continue

                        _clear_story_content(story_roots[story_fname])
                        warnings.append(
                            f"Cleared unassigned text frame {tf_id} "
                            f"on spread {spread_plan.spread_index}"
                        )

                    # Write the modified spread to output
                    out_zf.writestr(spread_filename, _serialise_xml(cloned_spread))

                # Write all (possibly modified) story files
                for story_fname, story_root in story_roots.items():
                    out_zf.writestr(story_fname, _serialise_xml(story_root))

                # Update designmap.xml with new spread list (root read above)
                updated_designmap = _update_designmap(designmap_root, new_spread_filenames)
                out_zf.writestr("designmap.xml", _serialise_xml(updated_designmap))

        output_path.write_bytes(output_buffer.getvalue())
        logger.info("IDML written to %s (%d bytes)", output_path, output_path.stat().st_size)

        return warnings
