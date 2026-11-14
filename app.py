"""Entry point: python app.py  ->  MCP server (streamable HTTP) at /mcp"""
import os

from server.mcp_server import mcp

if __name__ == "__main__":
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = int(os.environ.get("PORT", 8001))
    mcp.run(transport="streamable-http")
