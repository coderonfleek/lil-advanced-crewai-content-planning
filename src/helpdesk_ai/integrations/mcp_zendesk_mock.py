"""A local MCP stdio server that simulates Zendesk's ticket API.

This module serves two purposes:

  1. It's a real MCP server. Run as `python -m helpdesk_ai.integrations.mcp_zendesk_mock`
     and any MCP client (CrewAI, Claude Desktop, etc.) can connect to it over stdio.

  2. Its core functions (create_or_update_ticket, add_comment, get_ticket) are
     callable directly. LocalDispatcher uses them in-process, skipping the MCP
     wire for speed and clarity. The two paths exercise the same logic.

State persists to ~/.helpdesk-ai/zendesk.json. Inspect that file to see what
the system has written.
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


STATE_FILE = Path.home() / ".helpdesk-ai" / "zendesk.json"


# ─── State management ───────────────────────────────────────────────

def _read_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"tickets": {}, "next_id": 1}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        # Corrupted file — reset rather than crash.
        return {"tickets": {}, "next_id": 1}


def _write_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_by_external_id(state: dict, external_id: str) -> dict | None:
    for ticket in state["tickets"].values():
        if ticket.get("external_id") == external_id:
            return ticket
    return None


# ─── Core operations (also callable directly) ───────────────────────

def create_or_update_ticket(
    *,
    external_id: str,
    subject: str,
    description: str,
    priority: str,
    ticket_type: str,
    requester_email: str,
    tags: list[str],
) -> dict[str, Any]:
    """Create a new ticket OR update an existing one matching external_id.

    Returns the resulting ticket dict (with `id`).
    """
    state = _read_state()
    existing = _find_by_external_id(state, external_id)

    if existing:
        # Update path — keep id, comments, created_at; refresh everything else.
        existing.update(
            subject=subject,
            description=description,
            priority=priority,
            type=ticket_type,
            tags=tags,
            updated_at=_now(),
        )
        ticket = existing
    else:
        # Create path — allocate new id, start with empty comments.
        new_id = str(state["next_id"])
        state["next_id"] += 1
        ticket = {
            "id": new_id,
            "external_id": external_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "type": ticket_type,
            "status": "open",
            "requester_email": requester_email,
            "tags": tags,
            "comments": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        state["tickets"][new_id] = ticket

    _write_state(state)
    return ticket


def add_comment(*, ticket_id: str, body: str, is_public: bool = True) -> dict:
    state = _read_state()
    if ticket_id not in state["tickets"]:
        raise ValueError(f"Zendesk mock: ticket {ticket_id} not found")
    comment = {"body": body, "is_public": is_public, "created_at": _now()}
    state["tickets"][ticket_id]["comments"].append(comment)
    state["tickets"][ticket_id]["updated_at"] = _now()
    _write_state(state)
    return comment


def get_ticket(*, ticket_id: str) -> dict | None:
    return _read_state()["tickets"].get(ticket_id)


# ─── MCP server (stdio) ─────────────────────────────────────────────

app = Server("zendesk-mock")


@app.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="zendesk/create_ticket",
            description="Create or update a Zendesk ticket. Idempotent on external_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "external_id": {"type": "string"},
                    "subject": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"},
                    "ticket_type": {"type": "string"},
                    "requester_email": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "external_id", "subject", "description",
                    "priority", "ticket_type", "requester_email", "tags",
                ],
            },
        ),
        Tool(
            name="zendesk/add_comment_to_ticket",
            description="Add a comment to an existing Zendesk ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "body": {"type": "string"},
                    "is_public": {"type": "boolean"},
                },
                "required": ["ticket_id", "body"],
            },
        ),
    ]


@app.call_tool()
async def _call_tool(name: str, args: dict[str, Any]) -> list[TextContent]:
    if name == "zendesk/create_ticket":
        ticket = create_or_update_ticket(**args)
        return [TextContent(type="text", text=json.dumps(ticket, default=str))]
    if name == "zendesk/add_comment_to_ticket":
        comment = add_comment(**args)
        return [TextContent(type="text", text=json.dumps(comment, default=str))]
    raise ValueError(f"Unknown tool: {name}")


async def _run_server():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_run_server())