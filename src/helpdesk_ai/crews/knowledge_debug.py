"""Knowledge debugging — subscribe to knowledge events to confirm
which agent retrieved for which task.

The events expose `agent_role` and `task_name` but not the rewritten
search query or the returned chunks themselves (on CrewAI 1.14.x).
What they DO confirm is the most-asked debugging question: "is the
right agent retrieving for the right task?" — and that alone catches
the majority of retrieval bugs.

Import this module once (e.g. at the top of main.py) and the listener
self-installs. Set HELPDESK_DEBUG_KNOWLEDGE=1 in your environment to
turn the output on.
"""

from __future__ import annotations

import os

from crewai.events import BaseEventListener

try:
    from crewai.events import (
        KnowledgeRetrievalCompletedEvent,
        KnowledgeRetrievalStartedEvent,
    )
except ImportError:
    KnowledgeRetrievalCompletedEvent = None
    KnowledgeRetrievalStartedEvent = None


def _fmt_role(event) -> str:
    """Extract and clean the agent role string from an event."""
    role = getattr(event, "agent_role", None) or "?"
    return role.strip()


def _fmt_task(event) -> str:
    return getattr(event, "task_name", None) or "?"


class KnowledgeDebugListener(BaseEventListener):
    """Prints which agent retrieves for which task. Debugging only."""

    def setup_listeners(self, crewai_event_bus):
        if KnowledgeRetrievalCompletedEvent is None:
            return

        @crewai_event_bus.on(KnowledgeRetrievalStartedEvent)
        def _on_started(source, event):
            if os.getenv("HELPDESK_DEBUG_KNOWLEDGE") != "1":
                return
            print(
                f"🔍 [knowledge] {_fmt_role(event)} "
                f"is retrieving for task '{_fmt_task(event)}'…"
            )

        @crewai_event_bus.on(KnowledgeRetrievalCompletedEvent)
        def _on_done(source, event):
            if os.getenv("HELPDESK_DEBUG_KNOWLEDGE") != "1":
                return
            print(
                f"🔍 [knowledge] {_fmt_role(event)} "
                f"finished retrieval for '{_fmt_task(event)}'"
            )


# Auto-install: just importing this module turns the listener on.
_listener = KnowledgeDebugListener()