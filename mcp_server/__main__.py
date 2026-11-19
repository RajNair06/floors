"""Stdio entrypoint for the MCP server.

Run with: python -m mcp_server
"""

from mcp_server.app import mcp

if __name__ == "__main__":
    mcp.run()
