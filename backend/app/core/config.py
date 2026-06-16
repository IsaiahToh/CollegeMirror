from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── LLM provider ─────────────────────────────────────────────────────────
    # Set to "anthropic" or "gemini". Only the key for the chosen provider is required.
    llm_provider: str = "anthropic"

    # Anthropic / Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Google / Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # ── InDesign MCP ─────────────────────────────────────────────────────────
    # Set INDESIGN_MCP_ENABLED=true and point INDESIGN_MCP_SERVER_PATH to the
    # index.js of the indesign-mcp-server checkout. Requires InDesign running.
    indesign_mcp_enabled: bool = False
    indesign_mcp_server_path: str = ""

    # ── Storage & server ─────────────────────────────────────────────────────
    storage_path: Path = Path("./storage")
    frontend_url: str = "http://localhost:5173"
    log_level: str = "INFO"

    @property
    def frontend_origins(self) -> list[str]:
        """`frontend_url` may be a single origin or a comma-separated list."""
        return [url.strip() for url in self.frontend_url.split(",") if url.strip()]

    @property
    def examples_dir(self) -> Path:
        return self.storage_path / "examples"

    @property
    def jobs_dir(self) -> Path:
        return self.storage_path / "jobs"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.examples_dir.mkdir(parents=True, exist_ok=True)
        _settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    return _settings
