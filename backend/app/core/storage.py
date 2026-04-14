"""File I/O abstraction. All path construction goes through here — never hardcode paths."""

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

import aiofiles

from backend.app.core.config import Settings


class Storage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── Example sets ──────────────────────────────────────────────────────────

    def example_set_dir(self, example_set_id: str) -> Path:
        path = self._settings.examples_dir / example_set_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def new_example_set_id(self) -> str:
        return uuid.uuid4().hex

    def schema_path(self, example_set_id: str) -> Path:
        return self.example_set_dir(example_set_id) / "design_schema.json"

    def list_example_sets(self) -> list[str]:
        return [p.name for p in self._settings.examples_dir.iterdir() if p.is_dir()]

    def save_schema(self, example_set_id: str, schema_data: dict[str, Any]) -> None:
        self.schema_path(example_set_id).write_text(
            json.dumps(schema_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_schema(self, example_set_id: str) -> dict[str, Any]:
        path = self.schema_path(example_set_id)
        if not path.exists():
            raise FileNotFoundError(f"No design schema found for example set '{example_set_id}'")
        return json.loads(path.read_text(encoding="utf-8"))

    # ── Ingestion status ──────────────────────────────────────────────────────

    def ingestion_status_path(self, example_set_id: str) -> Path:
        return self.example_set_dir(example_set_id) / "ingestion_status.json"

    def save_ingestion_status(self, example_set_id: str, status: dict[str, Any]) -> None:
        self.ingestion_status_path(example_set_id).write_text(
            json.dumps(status, ensure_ascii=False), encoding="utf-8"
        )

    def load_ingestion_status(self, example_set_id: str) -> dict[str, Any] | None:
        path = self.ingestion_status_path(example_set_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def job_dir(self, job_id: str) -> Path:
        path = self._settings.jobs_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def new_job_id(self) -> str:
        return uuid.uuid4().hex

    def job_meta_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "meta.json"

    def job_output_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "output.idml"

    def save_job_meta(self, job_id: str, meta: dict[str, Any]) -> None:
        self.job_meta_path(job_id).write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_job_meta(self, job_id: str) -> dict[str, Any]:
        path = self.job_meta_path(job_id)
        if not path.exists():
            raise FileNotFoundError(f"No job found with id '{job_id}'")
        return json.loads(path.read_text(encoding="utf-8"))

    # ── Async file helpers ────────────────────────────────────────────────────

    async def write_upload(self, dest: Path, data: bytes) -> None:
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)

    def copy_file(self, src: Path, dest: Path) -> None:
        shutil.copy2(src, dest)

    def delete_dir(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)
