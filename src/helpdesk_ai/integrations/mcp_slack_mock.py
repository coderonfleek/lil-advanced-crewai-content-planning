"""A local MCP stdio server that simulates Slack's messaging API.

Two purposes (same as the Zendesk mock):

  1. Real stdio MCP server. Run as
     `python -m helpdesk_ai.integrations.mcp_slack_mock`
     and any MCP client can connect over stdio.

  2. In-process API. LocalDispatcher calls send_message() directly,
     skipping the wire. Same logic; faster path.

State persists to ~/.helpdesk-ai/slack.jsonl — one JSON object per
line. Inspect with `tail` or `wc -l`.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


LOG_FILE = Path.home() / ".helpdesk-ai" / "slack.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Core operations ────────────────────────────────────────────────

def send_message(*, channel: str, text: str) -> dict[str, Any]:
    """Append a message to the JSONL log. Returns the appended record."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {"channel": channel, "text": text, "ts": _now()}
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_mock_messages() -> list[dict[str, Any]]:
    """Read every notification ever sent. Useful for tests and debugging."""
    if not LOG_FILE.exists():
        return []
    return [
        json.loads(line)
        for line in LOG_FILE.read_text().splitlines()
        if line.strip()
    ]


# ─── MCP server (stdio) ─────────────────────────────────────────────

app = Server("slack-mock")


@app.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="slack/send_message_to_channel",
            description="Send a message to a Slack channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["channel", "text"],
            },
        ),
    ]


@app.call_tool()
async def _call_tool(name: str, args: dict[str, Any]) -> list[TextContent]:
    if name == "slack/send_message_to_channel":
        record = send_message(**args)
        return [TextContent(type="text", text=json.dumps(record, default=str))]
    raise ValueError(f"Unknown tool: {name}")


async def _run_server():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_run_server())