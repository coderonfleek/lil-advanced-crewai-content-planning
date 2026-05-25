"""Memory layer — durable, per-entity context across flow executions.

Everything in this module is a thin wrapper around CrewAI's unified
`Memory()` API. The goal is to:

  1. Centralize Memory() construction in `build_support_memory()` so
     tests and overrides have one place to patch.
  2. Provide scope helpers (`customer_scope`, `ticket_scope`) so scope
     strings are constructed consistently — a typo can never silently
     split memories across two scopes that should be one.
  3. Provide high-level helpers for the operations the flow actually
     performs — `load_customer_context`, `remember_ticket_outcome` —
     so flow code reads at the right level of abstraction.

Scope tree we use:
    /customer/{email}/profile        — tier, named AM, signup date
    /customer/{email}/preferences    — channel, language
    /customer/{email}/history        — past ticket categories + outcomes
    /ticket/{id}/triage              — the TriageDecision summary
    /ticket/{id}/resolution          — what was drafted, citations used
    /ticket/{id}/outcome             — final disposition
    /company/policies/...            — org-wide patterns (set externally)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crewai.memory.unified_memory import Memory, MemoryMatch

if TYPE_CHECKING:
    from ..models import Customer, ResolutionDraft, Ticket, TriageDecision

# ─── Scope helpers ───────────────────────────────────────────────────

def customer_scope(email: str, facet: str | None = None) -> str:
    """Scope for per-customer memories. Email is normalized."""
    base = f"/customer/{email.lower().strip()}"
    return f"{base}/{facet}" if facet else base


def ticket_scope(ticket_id: str, facet: str | None = None) -> str:
    """Scope for per-ticket memories."""
    base = f"/ticket/{ticket_id}"
    return f"{base}/{facet}" if facet else base


def company_scope(facet: str | None = None) -> str:
    """Scope for organization-wide policies and patterns."""
    base = "/company/policies"
    return f"{base}/{facet}" if facet else base


# ─── Factory ─────────────────────────────────────────────────────────

def build_support_memory() -> Memory:
    """Construct the system's Memory() with support-tuned defaults.

    Tuning rationale:
      - recency_weight bumped from default 0.3 to 0.4 because in
        support, the most recent ticket matters more than topical
        similarity to an old one.
      - recency_half_life_days bumped from default 30 to 60 because
        support events have a longer relevance window than chat.
      - Other knobs left at defaults — revisited later in this chapter.
    """
    return Memory(
        llm="gpt-4o-mini",
        storage="lancedb",
        recency_weight=0.4,
        semantic_weight=0.4,
        importance_weight=0.2,
        recency_half_life_days=60,
    )

# ─── High-level helpers ──────────────────────────────────────────────

def load_customer_context(
    memory: Memory, email: str, limit_per_facet: int = 5
) -> dict[str, list[str]]:
    """Read the three customer facets and return a structured snapshot.

    Returns a dict with keys `profile`, `preferences`, `history`, each
    a list of memory content strings (most-recent first). Empty lists
    are returned for facets with no entries.

    Uses `list_records` rather than `recall(query="")` because we want
    everything under each facet ordered by recency — not a semantic
    search. Empty-query semantic search returns nothing in CrewAI
    (no embedding → no matches).
    """
    return {
        facet: [
            r.content for r in memory.list_records(
                scope=customer_scope(email, facet), limit=limit_per_facet
            )
        ]
        for facet in ("profile", "preferences", "history")
    }

def remember_ticket_outcome(
    memory: Memory,
    *,
    customer: "Customer",
    ticket: "Ticket",
    triage: "TriageDecision",
    resolution: "ResolutionDraft",
) -> None:
    """Persist a ticket's outcome to both its own scope and the customer's history.

    Writes three records:
      - /ticket/{id}/triage         — the triage decision summary
      - /ticket/{id}/resolution     — citations + confidence + action
      - /customer/{email}/history   — a single-line summary so future
                                       intake reads find it quickly
    """
    # Per-ticket detail (denser; useful for audits)
    memory.remember(
        content=(
            f"Triage: {triage.category.value} / {triage.priority.value} "
            f"(confidence {triage.confidence:.2f}). "
            f"Reasoning: {triage.reasoning}"
        ),
        scope=ticket_scope(ticket.ticket_id, "triage"),
        importance=0.4,
    )
    memory.remember(
        content=(
            f"Response drafted with confidence {resolution.confidence:.2f}, "
            f"next action: {resolution.suggested_next_action}. "
            f"Citations: {', '.join(resolution.citations) or 'none'}."
        ),
        scope=ticket_scope(ticket.ticket_id, "resolution"),
        importance=0.5,
    )
    # Single-line summary on the customer's history feed
    memory.remember(
        content=(
            f"{ticket.ticket_id}: {triage.category.value} ticket — "
            f"\"{ticket.subject}\" (priority {triage.priority.value}). "
            f"Resolution confidence {resolution.confidence:.2f}."
        ),
        scope=customer_scope(customer.email, "history"),
        importance=0.6,  # history is what intake-enrichment reads, so bump it
    )


__all__ = [
    "Memory",
    "MemoryMatch",
    "build_support_memory",
    "customer_scope",
    "ticket_scope",
    "company_scope",
    "load_customer_context",
    "remember_ticket_outcome",
]