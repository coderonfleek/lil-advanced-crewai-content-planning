"""SupportState — the Flow state schema.

This is the single source of truth the flow mutates as it runs. Keeping
the schema tight and Pydantic-typed pays dividends in three places:

1. `flow.state.ticket.subject` autocompletes in your IDE
2. `@persist` serializes this cleanly to SQLite
3. The FastAPI layer can reuse the same model for its response contract

Key design rule: only store what must survive between steps. Don't cache
knowledge retrievals or LLM raw responses here — those live inside the
crews that need them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .customer import Customer
from .ticket import ResolutionDraft, Ticket, TriageDecision


class SupportState(BaseModel):
    """The single source of truth for a single support ticket's lifecycle."""

    # Intake payload. Populated via kickoff(inputs={...}). Kept as a dict
    # rather than a typed model so different channels (email, chat, API)
    # can feed it without forcing us into a tagged-union upfront.
    intake_payload: dict = Field(default_factory=dict)

    # Populated at intake
    customer: Customer | None = None
    ticket: Ticket | None = None

    # Populated during triage
    triage: TriageDecision | None = None

    # Populated during resolution
    resolution: ResolutionDraft | None = None

    # Bookkeeping — what happened, in order. Useful for debugging & replay.
    trail: list[str] = Field(default_factory=list)