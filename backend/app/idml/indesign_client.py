"""
Async MCP client for the InDesign MCP server (github.com/lucdesign/indesign-mcp-server).

Spawns the Node.js server via stdio and keeps a single session alive for the
duration of one operation (one ingestion or one generation job). Designed to be
used as an async context manager:

    async with InDesignClient() as client:
        await client.open_document(path)
        data = await client.execute_script_json(script)
        await client.close_document()

Requires:
- Node.js on PATH
- INDESIGN_MCP_SERVER_PATH set to the absolute path of index.js
- Adobe InDesign running on the same machine
"""

import json
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


class InDesignMCPError(Exception):
    pass


class InDesignClient:
    """Async context manager wrapping a single InDesign MCP stdio session."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.indesign_mcp_server_path:
            raise InDesignMCPError(
                "INDESIGN_MCP_SERVER_PATH is not set. "
                "Point it to the index.js of your indesign-mcp-server checkout."
            )
        self._server_path = settings.indesign_mcp_server_path
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "InDesignClient":
        self._exit_stack = AsyncExitStack()
        server_params = StdioServerParameters(
            command="node",
            args=[self._server_path],
        )
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        logger.info("InDesign MCP session ready (server=%s)", self._server_path)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
        self._session = None
        self._exit_stack = None

    # ── Low-level tool call ───────────────────────────────────────────────────

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call an InDesign MCP tool and return its text response."""
        if self._session is None:
            raise InDesignMCPError("InDesignClient must be used as an async context manager.")

        logger.debug("InDesign MCP → %s %s", tool_name, list(arguments.keys()))
        result = await self._session.call_tool(tool_name, arguments)

        if result.isError:
            content_text = " ".join(
                getattr(block, "text", str(block)) for block in result.content
            )
            raise InDesignMCPError(
                f"InDesign MCP tool '{tool_name}' returned an error: {content_text}"
            )

        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                return text  # type: ignore[return-value]
        return ""

    # ── Scripting ────────────────────────────────────────────────────────────

    async def execute_script(self, code: str) -> str:
        """Run arbitrary ExtendScript in the active InDesign document."""
        return await self.call("execute_indesign_code", {"code": code})

    async def execute_script_json(self, code: str) -> Any:
        """Run ExtendScript that returns a JSON string; parse and return it."""
        raw = await self.execute_script(code)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InDesignMCPError(
                f"ExtendScript returned non-JSON output (first 300 chars): {raw[:300]}"
            ) from exc

    # ── Document helpers ─────────────────────────────────────────────────────

    async def open_document(self, path: Path) -> None:
        await self.call("open_document", {"filePath": str(path)})
        logger.info("Opened document: %s", path.name)

    async def close_document(self, save: bool = False) -> None:
        await self.call("close_document", {"save": save})

    async def export_as_idml(self, output_path: Path) -> None:
        """Export the active document as IDML via ExtendScript."""
        script = f"""
(function() {{
    app.scriptPreferences.userInteractionLevel = UserInteractionLevels.NEVER_INTERACT;
    var doc = app.activeDocument;
    var f = new File("{str(output_path).replace(chr(92), "/")}");
    doc.exportFile(ExportFormat.INDESIGN_MARKUP, f, false);
    return "exported";
}})();
"""
        result = await self.execute_script(script)
        if "exported" not in result:
            raise InDesignMCPError(
                f"IDML export may have failed — unexpected response: {result[:200]}"
            )
        logger.info("Exported IDML to %s", output_path)
