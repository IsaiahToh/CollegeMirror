"""Unit tests for the IDML reader."""

import zipfile
from pathlib import Path

import pytest

from backend.app.idml.models import DesignLayout
from backend.app.idml.reader import IDMLReadError, read_idml


def test_read_idml_from_bytes(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    assert isinstance(layout, DesignLayout)


def test_read_idml_from_path(minimal_idml_file: Path) -> None:
    layout = read_idml(minimal_idml_file)
    assert isinstance(layout, DesignLayout)
    assert layout.source_filename == "test_doc.idml"


def test_page_dimensions_parsed(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    assert layout.page_width == 595.0
    assert layout.page_height == 842.0


def test_spread_parsed(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    assert len(layout.spreads) == 1
    spread = layout.spreads[0]
    assert spread.filename == "Spreads/Spread_0001.xml"


def test_text_frame_parsed(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    assert len(layout.spreads) == 1
    frames = layout.spreads[0].text_frames
    assert len(frames) == 1
    tf = frames[0]
    assert tf.self_id == "tf_0001"
    assert tf.story_id == "abc"
    # GeometricBounds="50 50 200 500" → top=50, left=50, bottom=200, right=500
    # → x=50, y=50, w=450, h=150
    assert tf.x == pytest.approx(50.0)
    assert tf.y == pytest.approx(50.0)
    assert tf.width == pytest.approx(450.0)
    assert tf.height == pytest.approx(150.0)
    assert "Body Text" in tf.applied_paragraph_style


def test_image_frame_parsed(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    frames = layout.spreads[0].image_frames
    assert len(frames) == 1
    assert frames[0].self_id == "img_0001"


def test_styles_parsed(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    styles = layout.style_catalog.paragraph_styles
    style_names = [s.name for s in styles]
    assert "Body Text" in style_names
    assert "Heading 1" in style_names

    body_style = next(s for s in styles if s.name == "Body Text")
    assert body_style.properties.font_family == "Times New Roman"
    assert body_style.properties.point_size == pytest.approx(11.0)


def test_color_swatches_parsed(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    names = [s.name for s in layout.color_swatches]
    assert "Brand Blue" in names
    assert "Dark Gray" in names


def test_story_content_parsed(minimal_idml_bytes: bytes) -> None:
    layout = read_idml(minimal_idml_bytes)
    assert len(layout.stories) == 1
    story = layout.stories[0]
    assert story.story_id == "abc"
    assert any("Sample body text" in p for p in story.paragraphs)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(IDMLReadError):
        read_idml(tmp_path / "does_not_exist.idml")


def test_invalid_zip_raises() -> None:
    with pytest.raises((IDMLReadError, zipfile.BadZipFile, Exception)):  # noqa: B017
        read_idml(b"this is not a zip file")
