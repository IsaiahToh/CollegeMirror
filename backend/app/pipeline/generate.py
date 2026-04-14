"""
Generation pipeline — orchestrates Word parsing, layout planning, and IDML writing
for a new document request.
"""

import datetime
import logging
from pathlib import Path

from backend.app.ai.planner import plan_layout
from backend.app.core.storage import Storage
from backend.app.idml.writer import IDMLWriter
from backend.app.models.design_schema import DesignSchema
from backend.app.models.job import Job, JobStatus
from backend.app.word.reader import read_docx

logger = logging.getLogger(__name__)


def _load_schema(example_set_id: str, storage: Storage) -> DesignSchema:
    raw = storage.load_schema(example_set_id)
    return DesignSchema.model_validate(raw)


def _find_template_idml(schema: DesignSchema, storage: Storage) -> Path:
    """Locate the primary template IDML file on disk."""
    if not schema.primary_template_idml:
        raise ValueError("DesignSchema has no primary_template_idml set")

    example_dir = storage.example_set_dir(schema.example_set_id)
    template_path = example_dir / schema.primary_template_idml
    if not template_path.exists():
        raise FileNotFoundError(
            f"Primary template IDML not found: {template_path}. "
            "Ensure the IDML files were uploaded before running generation."
        )
    return template_path


def run_generation(job_id: str, storage: Storage) -> None:
    """
    Execute the full generation pipeline for a job.

    This function is called as a background task. It reads the job meta,
    runs Word parsing + layout planning + IDML writing, and updates the job status.
    """
    # Load job metadata
    meta = storage.load_job_meta(job_id)
    job = Job.model_validate(meta)

    def _save_job(j: Job) -> None:
        storage.save_job_meta(j.id, j.model_dump(mode="json"))

    # Mark running
    job.status = JobStatus.RUNNING
    _save_job(job)

    try:
        # 1. Load the design schema
        logger.info("Loading schema for example_set_id=%s", job.example_set_id)
        schema = _load_schema(job.example_set_id, storage)

        # 2. Read the uploaded Word doc
        word_path = storage.job_dir(job_id) / "input.docx"
        logger.info("Parsing Word doc: %s", word_path)
        word_doc = read_docx(word_path)

        # 3. Run layout planner
        logger.info("Running layout planner")
        layout_plan = plan_layout(word_doc, schema)

        # 4. Find template IDML
        template_path = _find_template_idml(schema, storage)

        # 5. Write new IDML
        output_path = storage.job_output_path(job_id)
        logger.info("Writing IDML to %s", output_path)
        writer = IDMLWriter(template_path)
        warnings = writer.apply_plan(layout_plan, output_path)

        # 6. Update job to completed
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        job.warnings = warnings
        _save_job(job)

        logger.info(
            "Generation complete for job_id=%s warnings=%d", job_id, len(warnings)
        )

    except Exception as exc:
        logger.exception("Generation failed for job_id=%s", job_id)
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        _save_job(job)
