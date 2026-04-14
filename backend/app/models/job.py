import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.PENDING
    example_set_id: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    completed_at: datetime.datetime | None = None
    output_filename: str | None = None  # original docx filename, used to name the output
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
