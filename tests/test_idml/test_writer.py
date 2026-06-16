"""Unit tests for the IDML writer."""

import io
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from backend.app.idml.writer import IDMLWriteError, IDMLWriter
from backend.app.models.design_schema import SemanticRole
from backend.app.models.layout_plan import ContentAssignment, LayoutPlan, SpreadPlan


def _make_plan(spread_source: str = "Spreads/Spread_0001.xml") -> LayoutPlan:
    return LayoutPlan(
        document_title="Test Document",
        total_spreads=1,
        spreads=[
            SpreadPlan(
                spread_index=0,
                spread_purpose="body page",
                template_spread_source=spread_source,
                assignments=[
                    ContentAssignment(
                        role=SemanticRole.BODY,
                        paragraph_style="ParagraphStyle/Body Text",
                        text="This is the generated body text.",
                        frame_index=0,
                    )
                ],
                image_frame_notes=[],
            )
        ],
    )


def test_writer_produces_valid_zip(minimal_idml_file: Path, tmp_path: Path) -> None:
    writer = IDMLWriter(minimal_idml_file)
    output = tmp_path / "output.idml"
    writer.apply_plan(_make_plan(), output)

    assert output.exists()
    assert output.stat().st_size > 0
    assert zipfile.is_zipfile(output)


def test_writer_output_contains_designmap(minimal_idml_file: Path, tmp_path: Path) -> None:
    writer = IDMLWriter(minimal_idml_file)
    output = tmp_path / "output.idml"
    writer.apply_plan(_make_plan(), output)

    with zipfile.ZipFile(output, "r") as zf:
        assert "designmap.xml" in zf.namelist()


def test_writer_output_contains_spread(minimal_idml_file: Path, tmp_path: Path) -> None:
    writer = IDMLWriter(minimal_idml_file)
    output = tmp_path / "output.idml"
    writer.apply_plan(_make_plan(), output)

    with zipfile.ZipFile(output, "r") as zf:
        spread_files = [n for n in zf.namelist() if n.startswith("Spreads/")]
        assert len(spread_files) == 1


def test_writer_substitutes_text_content(minimal_idml_file: Path, tmp_path: Path) -> None:
    writer = IDMLWriter(minimal_idml_file)
    output = tmp_path / "output.idml"
    writer.apply_plan(_make_plan(), output)

    with zipfile.ZipFile(output, "r") as zf:
        story_files = [n for n in zf.namelist() if n.startswith("Stories/")]
        assert story_files
        story_xml = zf.read(story_files[0])
        root = etree.fromstring(story_xml)
        contents = [c.text or "" for c in root.findall(".//Content")]
        all_text = " ".join(contents)
        assert "generated body text" in all_text


def test_writer_missing_template_raises(tmp_path: Path) -> None:
    missing = tmp_path / "ghost.idml"
    with pytest.raises(IDMLWriteError):
        IDMLWriter(missing)


def test_writer_returns_warnings_list(minimal_idml_file: Path, tmp_path: Path) -> None:
    writer = IDMLWriter(minimal_idml_file)
    output = tmp_path / "output.idml"
    warnings = writer.apply_plan(_make_plan(), output)
    assert isinstance(warnings, list)


# ── Leakage scenarios: unassigned text frames + source images ──────────────────
#
# A richer fixture with two text frames (only one gets an assignment) and three
# graphic frames: a full-bleed background image (keep), a small placed content
# image (remove), and a decorative shape with no placed image (keep).


def _leaky_idml_bytes() -> bytes:
    designmap = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
          DOMVersion="18.0">
  <idPkg:Spread src="Spreads/Spread_0001.xml"/>
  <idPkg:Story src="Stories/Story_s_assigned.xml"/>
  <idPkg:Story src="Stories/Story_s_unassigned.xml"/>
</Document>"""

    preferences = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Preferences xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
                   DOMVersion="18.0">
  <DocumentPreference PageWidth="595" PageHeight="842"/>
</idPkg:Preferences>"""

    # Graphic frames carry geometry as PathGeometry anchor points (real IDML),
    # not a GeometricBounds attribute. rect_bg spans the full page (background,
    # kept); rect_fig is a small placed figure (removed); rect_decor has no
    # placed image (kept).
    spread = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
              DOMVersion="18.0">
  <Spread Self="spread_0001" PageCount="1">
    <Page Self="page_0001" Name="1" GeometricBounds="0 0 842 595"/>
    <TextFrame Self="tf_0001" ParentStory="s_assigned"
               GeometricBounds="50 50 200 500"
               AppliedParagraphStyle="ParagraphStyle/Body Text"/>
    <TextFrame Self="tf_0002" ParentStory="s_unassigned"
               GeometricBounds="210 50 360 500"
               AppliedParagraphStyle="ParagraphStyle/Body Text"/>
    <Rectangle Self="rect_bg">
      <PathGeometry><GeometryPathType PathOpen="false"><PathPointArray>
        <PathPointType Anchor="-297 -421"/>
        <PathPointType Anchor="-297 421"/>
        <PathPointType Anchor="297 421"/>
        <PathPointType Anchor="297 -421"/>
      </PathPointArray></GeometryPathType></PathGeometry>
      <Image Self="img_bg"/>
    </Rectangle>
    <Rectangle Self="rect_fig">
      <PathGeometry><GeometryPathType PathOpen="false"><PathPointArray>
        <PathPointType Anchor="-100 -75"/>
        <PathPointType Anchor="-100 75"/>
        <PathPointType Anchor="100 75"/>
        <PathPointType Anchor="100 -75"/>
      </PathPointArray></GeometryPathType></PathGeometry>
      <Image Self="img_fig"/>
    </Rectangle>
    <Rectangle Self="rect_decor">
      <PathGeometry><GeometryPathType PathOpen="false"><PathPointArray>
        <PathPointType Anchor="0 0"/>
        <PathPointType Anchor="0 50"/>
        <PathPointType Anchor="50 50"/>
        <PathPointType Anchor="50 0"/>
      </PathPointArray></GeometryPathType></PathGeometry>
    </Rectangle>
  </Spread>
</idPkg:Spread>"""

    story_assigned = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
             DOMVersion="18.0">
  <Story Self="s_assigned">
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Body Text">
      <CharacterStyleRange>
        <Content>Original assigned text.</Content>
      </CharacterStyleRange>
    </ParagraphStyleRange>
  </Story>
</idPkg:Story>"""

    story_unassigned = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
             DOMVersion="18.0">
  <Story Self="s_unassigned">
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Body Text">
      <CharacterStyleRange>
        <Content>ORIGINAL LEFTOVER TEXT FROM EXAMPLE.</Content>
      </CharacterStyleRange>
    </ParagraphStyleRange>
  </Story>
</idPkg:Story>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("designmap.xml", designmap)
        zf.writestr("Resources/Preferences.xml", preferences)
        zf.writestr("Spreads/Spread_0001.xml", spread)
        zf.writestr("Stories/Story_s_assigned.xml", story_assigned)
        zf.writestr("Stories/Story_s_unassigned.xml", story_unassigned)
        zf.writestr("META-INF/container.xml", b"<container/>")
    return buf.getvalue()


@pytest.fixture
def leaky_idml_file(tmp_path: Path) -> Path:
    path = tmp_path / "leaky.idml"
    path.write_bytes(_leaky_idml_bytes())
    return path


def _run_leaky(leaky_idml_file: Path, tmp_path: Path) -> tuple[bytes, str, str, list[str]]:
    """Apply a single-assignment plan and return (spread_xml, assigned_story,
    unassigned_story, warnings)."""
    plan = _make_plan(spread_source="Spreads/Spread_0001.xml")
    writer = IDMLWriter(leaky_idml_file)
    output = tmp_path / "output.idml"
    warnings = writer.apply_plan(plan, output)

    with zipfile.ZipFile(output, "r") as zf:
        spread_xml = zf.read("Spreads/Spread_0000.xml")
        assigned = zf.read("Stories/Story_s_assigned.xml").decode("utf-8")
        unassigned = zf.read("Stories/Story_s_unassigned.xml").decode("utf-8")
    return spread_xml, assigned, unassigned, warnings


def test_unassigned_text_frame_is_cleared(leaky_idml_file: Path, tmp_path: Path) -> None:
    _, assigned, unassigned, _ = _run_leaky(leaky_idml_file, tmp_path)
    # Assigned frame got the new content
    assert "generated body text" in assigned
    # Unassigned frame's original example text must NOT leak through
    assert "ORIGINAL LEFTOVER TEXT" not in unassigned


def test_source_image_frame_is_removed(leaky_idml_file: Path, tmp_path: Path) -> None:
    spread_xml, _, _, _ = _run_leaky(leaky_idml_file, tmp_path)
    root = etree.fromstring(spread_xml)
    selfs = {el.get("Self") for el in root.iter()}
    # Small placed content image removed; full-bleed background + decorative shape kept
    assert "rect_fig" not in selfs
    assert "rect_bg" in selfs
    assert "rect_decor" in selfs


def test_leakage_fix_reports_warnings(leaky_idml_file: Path, tmp_path: Path) -> None:
    _, _, _, warnings = _run_leaky(leaky_idml_file, tmp_path)
    joined = " ".join(warnings).lower()
    assert "cleared" in joined
    assert "image" in joined or "removed" in joined
