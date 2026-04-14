"""
POST /generate — Upload a new Word doc and kick off generation.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.api.deps import get_storage
from backend.app.core.storage import Storage
from backend.app.models.job import Job
from backend.app.pipeline.generate import run_generation

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateResponse(BaseModel):
    job_id: str
    message: str


@router.post("", response_model=GenerateResponse, status_code=202)
async def generate_document(
    word_file: UploadFile,
    example_set_id: str,
    background_tasks: BackgroundTasks,
    storage: Storage = Depends(get_storage),
) -> GenerateResponse:
    """
    Upload a new Word document and generate an InDesign IDML file from it,
    using the design patterns learned from the specified example set.

    Returns a job_id immediately. Poll /jobs/{job_id} to check status.
    Download the result from /jobs/{job_id}/download when status is 'completed'.
    """
    if not (word_file.filename or "").lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are accepted.")

    # Verify the example set has a schema
    if not storage.schema_path(example_set_id).exists():
        raise HTTPException(
            status_code=404,
            detail=f"No design schema found for example_set_id='{example_set_id}'. "
                   "Run ingestion first via POST /examples.",
        )

    job_id = storage.new_job_id()
    job = Job(id=job_id, example_set_id=example_set_id, output_filename=word_file.filename)

    # Save initial job metadata
    storage.save_job_meta(job_id, job.model_dump(mode="json"))

    # Save the uploaded Word doc
    word_path = storage.job_dir(job_id) / "input.docx"
    await storage.write_upload(word_path, await word_file.read())

    background_tasks.add_task(run_generation, job_id, storage)

    return GenerateResponse(
        job_id=job_id,
        message=f"Generation started. Poll /jobs/{job_id} for status.",
    )
