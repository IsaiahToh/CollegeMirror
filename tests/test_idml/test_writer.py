"""Unit tests for the IDML writer."""

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
