"""Domain models for HelpDesk AI.

Everything is Pydantic so it serializes cleanly for `@persist` and for
the FastAPI layer.
"""

from .customer import Customer, CustomerTier
from .state import SupportState
from .ticket import (
    IssueCategory,
    ResolutionDraft,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
    TriageDecision,
)

__all__ = [
    "Customer",
    "CustomerTier",
    "IssueCategory",
    "ResolutionDraft",
    "SupportState",
    "Ticket",
    "TicketPriority",
    "TicketStatus",
    "TicketType",
    "TriageDecision",
]