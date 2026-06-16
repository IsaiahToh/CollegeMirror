import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import examples, generate, jobs
from backend.app.core.config import get_settings

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(
    title="CollegeMirror",
    description="Automated InDesign document generation from examples",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(examples.router, prefix="/examples", tags=["examples"])
app.include_router(generate.router, prefix="/generate", tags=["generate"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
