"""
GET /jobs/{id} — Poll job status.
GET /jobs/{id}/download — Download the generated IDML.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.api.deps import get_storage
from backend.app.core.storage import Storage
from backend.app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)
router = APIRouter()


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    example_set_id: str
    warnings: list[str]
    error: str | None
    download_url: str | None


def _get_job_or_404(job_id: str, storage: Storage) -> Job:
    try:
        meta = storage.load_job_meta(job_id)
        return Job.model_validate(meta)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.") from None


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str, storage: Storage = Depends(get_storage)
) -> JobStatusResponse:
    """Poll the status of a generation job."""
    job = _get_job_or_404(job_id, storage)
    download_url = f"/jobs/{job_id}/download" if job.status == JobStatus.COMPLETED else None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        example_set_id=job.example_set_id,
        warnings=job.warnings,
        error=job.error,
        download_url=download_url,
    )


@router.get("/{job_id}/download")
def download_idml(
    job_id: str, storage: Storage = Depends(get_storage)
) -> FileResponse:
    """Download the generated IDML file for a completed job."""
    job = _get_job_or_404(job_id, storage)

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not completed yet (status={job.status}). Try again later.",
        )

    output_path: Path = storage.job_output_path(job_id)
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="Output file not found on server.")

    # Derive a friendly filename from the input docx name. Reduce to a basename
    # (stripping any path separators) so job metadata can never inject a path.
    raw_name = (job.output_filename or "output").replace("\\", "/")
    base_name = Path(raw_name).name.removesuffix(".docx") or "output"
    download_name = f"{base_name}_generated.idml"

    return FileResponse(
        path=str(output_path),
        media_type="application/octet-stream",
        filename=download_name,
    )
