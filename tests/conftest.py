"""Shared fixtures for CollegeMirror tests."""

import io
import zipfile
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _minimal_idml_bytes() -> bytes:
    """
    Build a minimal valid IDML ZIP in memory for testing.
    Contains: designmap.xml, Spreads/Spread_0001.xml, Stories/Story_abc.xml,
              Resources/Styles.xml, Resources/Graphic.xml
    """
    designmap = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
          DOMVersion="18.0">
  <DocumentPreference PageWidth="595" PageHeight="842"/>
  <idPkg:Spread src="Spreads/Spread_0001.xml"/>
  <idPkg:Story src="Stories/Story_abc.xml"/>
</Document>"""

    spread = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
              DOMVersion="18.0">
  <Spread Self="spread_0001" PageCount="1">
    <Page Self="page_0001" Name="1"/>
    <TextFrame Self="tf_0001" ParentStory="abc"
               GeometricBounds="50 50 200 500"
               AppliedParagraphStyle="ParagraphStyle/Body Text">
      <TextFramePreference/>
    </TextFrame>
    <Rectangle Self="img_0001"
               GeometricBounds="210 50 400 250">
    </Rectangle>
  </Spread>
</idPkg:Spread>"""

    story = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
             DOMVersion="18.0">
  <Story Self="abc">
    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/Body Text">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]">
        <Content>Sample body text for testing.</Content>
      </CharacterStyleRange>
    </ParagraphStyleRange>
  </Story>
</idPkg:Story>"""

    styles = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Styles xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
              DOMVersion="18.0">
  <RootParagraphStyleGroup Self="rootParagraphStyleGroup">
    <ParagraphStyle Self="ParagraphStyle/Body Text" Name="Body Text"
                    AppliedFont="Times New Roman" FontStyle="Regular"
                    PointSize="11" Leading="14"/>
    <ParagraphStyle Self="ParagraphStyle/Heading 1" Name="Heading 1"
                    AppliedFont="Helvetica" FontStyle="Bold" PointSize="18"/>
  </RootParagraphStyleGroup>
  <RootCharacterStyleGroup Self="rootCharacterStyleGroup">
    <CharacterStyle Self="CharacterStyle/$ID/[No character style]"
                    Name="[No character style]"/>
  </RootCharacterStyleGroup>
</idPkg:Styles>"""

    graphic = b"""<?xml version="1.0" encoding="UTF-8"?>
<idPkg:Graphic xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
               DOMVersion="18.0">
  <Color Self="color_blue" Name="Brand Blue" Model="CMYK" ColorValue="80 40 0 0"/>
  <Color Self="color_darkgray" Name="Dark Gray" Model="CMYK" ColorValue="0 0 0 80"/>
</idPkg:Graphic>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("designmap.xml", designmap)
        zf.writestr("Spreads/Spread_0001.xml", spread)
        zf.writestr("Stories/Story_abc.xml", story)
        zf.writestr("Resources/Styles.xml", styles)
        zf.writestr("Resources/Graphic.xml", graphic)
        zf.writestr("META-INF/container.xml", b"<container/>")
    return buf.getvalue()


@pytest.fixture
def minimal_idml_bytes() -> bytes:
    """Minimal valid IDML archive as bytes."""
    return _minimal_idml_bytes()


@pytest.fixture
def minimal_idml_file(tmp_path: Path) -> Path:
    """Write a minimal IDML to a temp file and return the path."""
    path = tmp_path / "test_doc.idml"
    path.write_bytes(_minimal_idml_bytes())
    return path
