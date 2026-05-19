"""Customer domain model.

Customers are the people writing to support. Their `tier` maps to SLA
expectations and routing rules elsewhere in the flow.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CustomerTier(str, Enum):
    """NimbusCloud subscription tiers. Drives SLA + routing."""

    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class Customer(BaseModel):
    """A customer writing to NimbusCloud support.

    Identity, plan tier, and a small set of fields populated by memory
    enrichment when prior history is available.
    """

    email: str
    name: str = ""
    tier: CustomerTier = CustomerTier.FREE
    account_id: str | None = None

    # Populated by memory enrichment when prior history is available
    preferences: dict = Field(default_factory=dict)
    past_ticket_count: int = 0