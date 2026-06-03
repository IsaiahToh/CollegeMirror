"""
POST /examples — Upload IDML + Word doc pairs and trigger ingestion.

Each IDML may be paired with one or more Word documents via a `grouping` JSON
field. Example grouping:

    [
      {"idml": "brochure.idml", "words": ["overview.docx", "data.docx"]},
      {"idml": "report.idml",   "words": ["report_body.docx"]}
    ]

If `grouping` is omitted the files are paired by upload order (first IDML with
first Word doc), preserving backwards-compatibility with single-doc uploads.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.api.deps import get_storage
from backend.app.core.storage import Storage
from backend.app.pipeline.ingest import run_ingestion

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestResponse(BaseModel):
    example_set_id: str
    message: str


class ExampleSetInfo(BaseModel):
    example_set_id: str
    has_schema: bool


async def _save_all_uploads(
    files: list[UploadFile],
    example_set_id: str,
    storage: Storage,
) -> dict[str, Path]:
    """Save all uploaded files to disk, return filename → path mapping."""
    dest_dir = storage.example_set_dir(example_set_id)
    saved: dict[str, Path] = {}
    for f in files:
        name = f.filename or "upload"
        dest = dest_dir / name
        await storage.write_upload(dest, await f.read())
        saved[name] = dest
    return saved


def _build_pairs(
    saved: dict[str, Path],
    grouping_raw: str | None,
) -> list[tuple[Path, list[Path]]]:
    """
    Resolve the grouping spec into (idml_path, [word_paths]) tuples.

    If no grouping is given, infer single-file pairs by separating .idml and
    .docx files by extension and matching by order.
    """
    if grouping_raw:
        try:
            grouping = json.loads(grouping_raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid `grouping` JSON: {exc}") from None

        pairs: list[tuple[Path, list[Path]]] = []
        for entry in grouping:
            idml_name = entry.get("idml", "")
            word_names = entry.get("words", [])
            if idml_name not in saved:
                raise HTTPException(
                    status_code=400,
                    detail=f"Grouping references '{idml_name}' but it was not uploaded.",
                )
            for wn in word_names:
                if wn not in saved:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Grouping references '{wn}' but it was not uploaded.",
                    )
            pairs.append((saved[idml_name], [saved[wn] for wn in word_names]))
        return pairs

    # Fallback: pair by order
    idml_paths = sorted(p for n, p in saved.items() if n.lower().endswith(".idml"))
    word_paths = sorted(p for n, p in saved.items() if n.lower().endswith(".docx"))
    if len(idml_paths) != len(word_paths):
        raise HTTPException(
            status_code=400,
            detail=(
                "Without a `grouping` field, IDML and Word file counts must match "
                f"(got {len(idml_paths)} IDML, {len(word_paths)} Word)."
            ),
        )
    return [(idml, [word]) for idml, word in zip(idml_paths, word_paths, strict=True)]


async def _run_ingestion_bg(
    example_set_id: str,
    pairs: list[tuple[Path, list[Path]]],
    storage: Storage,
) -> None:
    storage.save_ingestion_status(example_set_id, {"status": "running", "error": None})
    try:
        await run_ingestion(example_set_id, pairs, storage)
        storage.save_ingestion_status(example_set_id, {"status": "completed", "error": None})
    except Exception as exc:
        logger.exception("Ingestion failed for example_set_id=%s", example_set_id)
        storage.save_ingestion_status(example_set_id, {"status": "failed", "error": str(exc)})


@router.post("", response_model=IngestResponse, status_code=202)
async def upload_examples(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    grouping: str | None = Form(default=None),
    storage: Storage = Depends(get_storage),
) -> IngestResponse:
    """
    Upload any mix of IDML and Word (.docx) files.

    Use the optional `grouping` JSON form field to declare which Word docs
    belong to which IDML. Without it, files are paired by upload order
    (one IDML : one Word doc).

    Ingestion (Claude analysis) runs in the background. The response returns
    immediately with the example_set_id. Check /examples/{id}/schema to confirm
    ingestion is complete.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    example_set_id = storage.new_example_set_id()
    saved = await _save_all_uploads(files, example_set_id, storage)
    pairs = _build_pairs(saved, grouping)

    if not pairs:
        raise HTTPException(status_code=400, detail="Could not build any IDML+Word pairs from uploads.")

    background_tasks.add_task(_run_ingestion_bg, example_set_id, pairs, storage)

    return IngestResponse(
        example_set_id=example_set_id,
        message=f"Ingestion started for {len(pairs)} example pair(s). Check /examples/{example_set_id}/schema when ready.",
    )


@router.get("", response_model=list[ExampleSetInfo])
def list_example_sets(storage: Storage = Depends(get_storage)) -> list[ExampleSetInfo]:
    """List all uploaded example sets."""
    sets = storage.list_example_sets()
    return [
        ExampleSetInfo(
            example_set_id=s,
            has_schema=storage.schema_path(s).exists(),
        )
        for s in sets
    ]


@router.get("/{example_set_id}/status")
def get_ingestion_status(
    example_set_id: str, storage: Storage = Depends(get_storage)
) -> dict:
    """Poll ingestion status: 'running' | 'completed' | 'failed'."""
    status = storage.load_ingestion_status(example_set_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Example set '{example_set_id}' not found.")
    return status


@router.get("/{example_set_id}/schema")
def get_schema(
    example_set_id: str, storage: Storage = Depends(get_storage)
) -> dict:
    """Return the raw DesignSchema JSON for an example set."""
    try:
        return storage.load_schema(example_set_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Schema not found for example_set_id='{example_set_id}'. Ingestion may still be running.",
        ) from None
