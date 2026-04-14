"""Integration tests for the generation pipeline (Claude mocked)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.models.job import Job


def _write_minimal_job(storage: MagicMock, job: Job, job_dir: Path, idml_bytes: bytes) -> None:
    """Helper to set up a job on a mock storage."""
    job_dir.mkdir(parents=True, exist_ok=True)
    meta_path = job_dir / "meta.json"
    meta_path.write_text(json.dumps(job.model_dump(mode="json")), encoding="utf-8")

    # Write a minimal input Word doc (empty bytes — word reader will fail gracefully)
    word_path = job_dir / "input.docx"
    word_path.write_bytes(b"")

    storage.load_job_meta.return_value = job.model_dump(mode="json")
    storage.job_dir.return_value = job_dir
    storage.job_output_path.return_value = job_dir / "output.idml"


def test_run_generation_happy_path(tmp_path: Path, minimal_idml_bytes: bytes) -> None:
    """
    Smoke test for the full generation pipeline with Claude mocked.
    Skipped until fixture IDML and docx files are available.
    """
    from backend.app.models.design_schema import DesignSchema, SemanticRole
    from backend.app.models.layout_plan import ContentAssignment, LayoutPlan, SpreadPlan

    schema = DesignSchema(
        example_set_id="test_set",
        primary_template_idml="test_doc.idml",
    )

    mock_plan = LayoutPlan(
        document_title="Generated Doc",
        total_spreads=1,
        spreads=[
            SpreadPlan(
                spread_index=0,
                spread_purpose="body",
                template_spread_source="Spreads/Spread_0001.xml",
                assignments=[
                    ContentAssignment(
                        role=SemanticRole.BODY,
                        paragraph_style="ParagraphStyle/Body Text",
                        text="Hello world",
                        frame_index=0,
                    )
                ],
            )
        ],
    )

    with (
        patch("backend.app.pipeline.generate._load_schema", return_value=schema),
        patch("backend.app.pipeline.generate.plan_layout", return_value=mock_plan),
        patch("backend.app.pipeline.generate.read_docx", return_value=MagicMock()),
        patch("backend.app.pipeline.generate._find_template_idml") as mock_tmpl,
    ):
        tmpl_path = tmp_path / "test_doc.idml"
        tmpl_path.write_bytes(minimal_idml_bytes)
        mock_tmpl.return_value = tmpl_path

        storage = MagicMock()
        job = Job(id="job_001", example_set_id="test_set")
        job_dir = tmp_path / "jobs" / "job_001"
        _write_minimal_job(storage, job, job_dir, minimal_idml_bytes)
        storage.job_output_path.return_value = job_dir / "output.idml"

        from backend.app.pipeline.generate import run_generation
        run_generation("job_001", storage)

        updated_calls = [c for c in storage.save_job_meta.call_args_list]
        assert updated_calls, "save_job_meta should have been called"
