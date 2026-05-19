"""Ticket, triage, and resolution models.

These map cleanly to Zendesk fields. We use string enums so serialization
via `@persist` stays human-readable in SQLite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


# ─── Zendesk-aligned enums ──────────────────────────────────────────

class TicketPriority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TicketType(str, Enum):
    PROBLEM = "problem"
    INCIDENT = "incident"
    QUESTION = "question"
    TASK = "task"


class TicketStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    HOLD = "hold"
    SOLVED = "solved"
    CLOSED = "closed"


class IssueCategory(str, Enum):
    """Internal categorization used for routing. Broader than Zendesk's type."""

    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    API = "api"
    GENERAL = "general"


# ─── Core models ────────────────────────────────────────────────────

class Ticket(BaseModel):
    """A support ticket — the unit of work flowing through the system."""

    ticket_id: str = Field(default_factory=lambda: f"tkt_{uuid4().hex[:10]}")
    subject: str
    description: str
    priority: TicketPriority = TicketPriority.NORMAL
    type: TicketType = TicketType.QUESTION
    status: TicketStatus = TicketStatus.NEW
    category: IssueCategory = IssueCategory.GENERAL
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Populated after the Zendesk round-trip
    zendesk_id: str | None = None


class TriageDecision(BaseModel):
    """The triage step's structured output — drives routing."""

    category: IssueCategory
    priority: TicketPriority
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    suggested_tags: list[str] = Field(default_factory=list)
    needs_human: bool = False


class ResolutionDraft(BaseModel):
    """A proposed response to the customer, awaiting delivery."""

    response_text: str
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_next_action: str = ""