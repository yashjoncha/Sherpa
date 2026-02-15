"""MCP server implementation for Sherpa tools."""

from __future__ import annotations


class SherpaServer:
    """Expose Sherpa capabilities as MCP tools."""

    def __init__(self) -> None:
        """Initialise the server and tool registry."""
        self.tools: dict[str, dict] = {}

    def register_tools(self) -> None:
        """Register all available Sherpa tools."""

    def handle_request(self, method: str, params: dict) -> dict:
        """Route an incoming MCP request to the appropriate handler.

        Args:
            method: The MCP method name.
            params: Request parameters.

        Returns:
            A dict with the response payload.
        """
        return {}

    def list_tools(self) -> list[dict]:
        """Return metadata for all registered tools.

        Returns:
            A list of tool description dicts.
        """
        return []
