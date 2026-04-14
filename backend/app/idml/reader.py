"""
IDML Reader — parses an IDML file (ZIP archive) into a DesignLayout pydantic model.

IDML structure:
  designmap.xml          — root manifest, page dimensions, spread/story references
  Spreads/Spread_*.xml   — page layout: frames, positions, geometry
  MasterSpreads/MasterSpread_*.xml — master page templates
  Stories/Story_*.xml    — text content with style references
  Resources/Styles.xml   — paragraph, character, object style definitions
  Resources/Graphic.xml  — color swatches
"""

import contextlib
import zipfile
from io import BytesIO
from pathlib import Path

from lxml import etree

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

# IDML XML namespaces
NS: dict[str, str] = {
    "idPkg": "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging",
}

# Geometric bounds attribute order in IDML: [y1, x1, y2, x2] (top, left, bottom, right)
_BOUNDS_ATTR = "GeometricBounds"


class IDMLReadError(Exception):
    pass


def _parse_bounds(element: etree._Element) -> tuple[float, float, float, float]:
    """Return (x, y, width, height) from a GeometricBounds attribute."""
    raw = element.get(_BOUNDS_ATTR, "")
    if not raw:
        return 0.0, 0.0, 0.0, 0.0
    try:
        top, left, bottom, right = (float(v) for v in raw.split())
        return left, top, right - left, bottom - top
    except ValueError:
        return 0.0, 0.0, 0.0, 0.0


def _attr(element: etree._Element, name: str, default: str = "") -> str:
    return element.get(name, default)


def _float_attr(element: etree._Element, name: str, default: float = 0.0) -> float:
    try:
        return float(element.get(name, default))
    except (ValueError, TypeError):
        return default


def _parse_text_frame(elem: etree._Element, master_page: str | None = None) -> TextFrame:
    x, y, w, h = _parse_bounds(elem)
    return TextFrame(
        self_id=_attr(elem, "Self"),
        story_id=_attr(elem, "ParentStory"),
        x=x,
        y=y,
        width=w,
        height=h,
        applied_paragraph_style=_attr(elem, "AppliedParagraphStyle", "ParagraphStyle/$ID/NormalParagraphStyle"),
        applied_object_style=elem.get("AppliedObjectStyle"),
        master_page=master_page,
        layer=_attr(elem, "ItemLayer", "Default"),
        threading_next_id=elem.get("NextTextFrame") or None,
        threading_prev_id=elem.get("PreviousTextFrame") or None,
    )


def _parse_image_frame(elem: etree._Element, master_page: str | None = None) -> ImageFrame:
    x, y, w, h = _parse_bounds(elem)
    # Check if a graphic is linked inside this frame
    linked_path: str | None = None
    for link in elem.iter("Link"):
        linked_path = link.get("LinkResourceURI") or None
        break
    return ImageFrame(
        self_id=_attr(elem, "Self"),
        x=x,
        y=y,
        width=w,
        height=h,
        applied_object_style=elem.get("AppliedObjectStyle"),
        master_page=master_page,
        layer=_attr(elem, "ItemLayer", "Default"),
        linked_image_path=linked_path,
    )


def _parse_spread_xml(
    xml_bytes: bytes, filename: str, master_page_name: str | None = None
) -> tuple[list[TextFrame], list[ImageFrame], str, int]:
    """Parse a Spread or MasterSpread XML. Returns (text_frames, image_frames, spread_id, page_count)."""
    root = etree.fromstring(xml_bytes)
    spread_elem = root.find(".//Spread")
    if spread_elem is None:
        spread_elem = root.find(".//MasterSpread")
    if spread_elem is None:
        raise IDMLReadError(f"No Spread/MasterSpread element found in {filename}")

    spread_id = _attr(spread_elem, "Self")
    pages = spread_elem.findall("Page")
    page_count = len(pages) if pages else 1

    text_frames: list[TextFrame] = []
    image_frames: list[ImageFrame] = []

    for elem in spread_elem.iter():
        tag = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""
        if tag == "TextFrame":
            text_frames.append(_parse_text_frame(elem, master_page=master_page_name))
        elif tag in ("Rectangle", "Oval", "Polygon") and elem.get("ParentStory") is None:
            # Frames without a ParentStory are potential image frames
            image_frames.append(_parse_image_frame(elem, master_page=master_page_name))

    return text_frames, image_frames, spread_id, page_count


def _parse_styles(xml_bytes: bytes) -> StyleCatalog:
    root = etree.fromstring(xml_bytes)
    para_styles: list[ParagraphStyle] = []
    char_styles: list[CharacterStyle] = []

    for ps in root.iter("ParagraphStyle"):
        props = ParagraphStyleProperties(
            font_family=ps.get("AppliedFont"),
            font_style=ps.get("FontStyle"),
            point_size=float(ps.get("PointSize", 0)) or None,
            leading=float(ps.get("Leading", 0)) or None,
            alignment=ps.get("Justification"),
            space_before=float(ps.get("SpaceBefore", 0)) or None,
            space_after=float(ps.get("SpaceAfter", 0)) or None,
        )
        para_styles.append(
            ParagraphStyle(
                self_id=_attr(ps, "Self"),
                name=_attr(ps, "Name"),
                based_on=ps.get("BasedOn") or None,
                properties=props,
            )
        )

    for cs in root.iter("CharacterStyle"):
        char_styles.append(
            CharacterStyle(
                self_id=_attr(cs, "Self"),
                name=_attr(cs, "Name"),
                font_family=cs.get("AppliedFont"),
                font_style=cs.get("FontStyle"),
                point_size=float(cs.get("PointSize", 0)) or None,
            )
        )

    return StyleCatalog(paragraph_styles=para_styles, character_styles=char_styles)


def _parse_graphic(xml_bytes: bytes) -> list[ColorSwatch]:
    root = etree.fromstring(xml_bytes)
    swatches: list[ColorSwatch] = []
    for color in root.iter("Color"):
        name = _attr(color, "Name")
        model = _attr(color, "Model", "CMYK")
        values_raw = color.get("ColorValue", "")
        try:
            values = [float(v) for v in values_raw.split()]
        except ValueError:
            values = []
        if name and name not in ("None", "Paper", "Black", "Registration"):
            swatches.append(ColorSwatch(name=name, model=model, values=values))
    return swatches


def _parse_story(xml_bytes: bytes, story_id: str) -> StoryContent:
    root = etree.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for para in root.iter("ParagraphStyleRange"):
        texts = [c.text or "" for c in para.iter("Content")]
        combined = "".join(texts).strip()
        if combined:
            paragraphs.append(combined)

    has_overflow = root.find(".//*[@Overflows='true']") is not None

    return StoryContent(
        story_id=story_id,
        paragraphs=paragraphs,
        has_overflow=has_overflow,
    )


def _parse_designmap(xml_bytes: bytes) -> tuple[float, float, list[str], list[str]]:
    """Return (page_width, page_height, spread_filenames, master_spread_filenames)."""
    root = etree.fromstring(xml_bytes)

    # DocumentPreferences holds page dimensions
    doc_prefs = root.find(".//DocumentPreference")
    pw = ph = 0.0
    if doc_prefs is not None:
        pw = _float_attr(doc_prefs, "PageWidth")
        ph = _float_attr(doc_prefs, "PageHeight")

    spreads: list[str] = []
    masters: list[str] = []
    for item in root.findall(".//{http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging}Spread"):
        src = item.get("src", "")
        if src:
            spreads.append(src)
    for item in root.findall(".//{http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging}MasterSpread"):
        src = item.get("src", "")
        if src:
            masters.append(src)

    return pw, ph, spreads, masters


def read_idml(path: Path | str | bytes) -> DesignLayout:
    """
    Parse an IDML file and return a DesignLayout.

    Args:
        path: File path to the .idml file, or raw bytes of the IDML ZIP.
    """
    if isinstance(path, bytes):
        zf = zipfile.ZipFile(BytesIO(path), "r")
        source_filename = "<bytes>"
    else:
        p = Path(path)
        if not p.exists():
            raise IDMLReadError(f"IDML file not found: {p}")
        zf = zipfile.ZipFile(p, "r")
        source_filename = p.name

    names = zf.namelist()

    with zf:
        # 1. Parse designmap.xml for page dimensions and spread order
        if "designmap.xml" not in names:
            raise IDMLReadError("designmap.xml not found — not a valid IDML file")
        pw, ph, spread_files, master_files = _parse_designmap(zf.read("designmap.xml"))

        # Fall back to discovering spread files from the ZIP if designmap missed them
        if not spread_files:
            spread_files = [n for n in names if n.startswith("Spreads/") and n.endswith(".xml")]
        if not master_files:
            master_files = [n for n in names if n.startswith("MasterSpreads/") and n.endswith(".xml")]

        # 2. Parse master pages first (so we know master names)
        master_pages: list[MasterPage] = []
        master_name_by_id: dict[str, str] = {}
        for mf in master_files:
            if mf not in names:
                continue
            xml = zf.read(mf)
            root = etree.fromstring(xml)
            ms_elem = root.find(".//MasterSpread")
            master_name = _attr(ms_elem, "Name", "Master") if ms_elem is not None else "Master"
            tfs, ifs, spread_id, _ = _parse_spread_xml(xml, mf, master_page_name=master_name)
            master_name_by_id[spread_id] = master_name
            master_pages.append(
                MasterPage(
                    filename=mf,
                    spread_id=spread_id,
                    name=master_name,
                    text_frames=tfs,
                    image_frames=ifs,
                )
            )

        # 3. Parse regular spreads
        spreads: list[Spread] = []
        for sf in spread_files:
            if sf not in names:
                continue
            xml = zf.read(sf)
            tfs, ifs, spread_id, page_count = _parse_spread_xml(xml, sf)
            spreads.append(
                Spread(
                    filename=sf,
                    spread_id=spread_id,
                    page_count=page_count,
                    text_frames=tfs,
                    image_frames=ifs,
                )
            )

        # 4. Parse styles
        style_catalog = StyleCatalog()
        for styles_file in ("Resources/Styles.xml", "Resources/styles.xml"):
            if styles_file in names:
                style_catalog = _parse_styles(zf.read(styles_file))
                break

        # 5. Parse color swatches
        color_swatches: list[ColorSwatch] = []
        for graphic_file in ("Resources/Graphic.xml", "Resources/graphic.xml"):
            if graphic_file in names:
                color_swatches = _parse_graphic(zf.read(graphic_file))
                break

        # 6. Parse stories (text content)
        story_files = [n for n in names if n.startswith("Stories/") and n.endswith(".xml")]
        stories: list[StoryContent] = []
        for sf in story_files:
            story_id = sf.removeprefix("Stories/Story_").removesuffix(".xml")
            with contextlib.suppress(etree.XMLSyntaxError):
                stories.append(_parse_story(zf.read(sf), story_id))

    return DesignLayout(
        source_filename=source_filename,
        spreads=spreads,
        master_pages=master_pages,
        style_catalog=style_catalog,
        color_swatches=color_swatches,
        stories=stories,
        page_width=pw,
        page_height=ph,
    )
