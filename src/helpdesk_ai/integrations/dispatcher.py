"""IntegrationDispatcher — the abstract seam between flow and external systems.

Two concrete implementations exist:

  - LocalDispatcher  → calls the in-process mock servers directly. No network,
                       no MCP wire, no AMP token required. Used by default
                       and during testing.

  - AMPDispatcher    → builds narrowly-scoped CrewAI Agents with `apps=[...]`
                       lists, delegating actual writes to CrewAI AMP's hosted
                       MCP servers. Built later in this chapter.

Pick at flow-construction time via `build_dispatcher()`.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from crewai import Agent, Crew, Process, Task

from . import mcp_slack_mock, mcp_zendesk_mock

if TYPE_CHECKING:
    from ..models import (
        Customer, CustomerTier, ResolutionDraft, Ticket,
        TicketPriority, TriageDecision,
    )


# ─── Channel routing + message formatting ───────────────────────────

def _choose_slack_channel(customer, triage) -> str:
    """Pick the Slack channel for a notification.

    Order matters: VIP takes precedence over escalation; escalation
    takes precedence over default triage.
    """
    # Import here to avoid forward-reference issues at module load time
    from ..models import CustomerTier, TicketPriority

    if customer.tier == CustomerTier.ENTERPRISE:
        return os.getenv("SLACK_CHANNEL_VIP", "#support-vip")
    if triage.needs_human or triage.priority == TicketPriority.URGENT:
        return os.getenv("SLACK_CHANNEL_ESCALATION", "#support-escalations")
    return os.getenv("SLACK_CHANNEL_TRIAGE", "#support-triage")


def _format_slack_notification(
    *, customer, ticket, triage, resolution, zendesk_id: str
) -> str:
    """Format a Slack mrkdwn notification message.

    All fields come from typed state — no LLM, no creativity. Deterministic.
    """
    citations = ", ".join(resolution.citations) if resolution.citations else "(none)"
    zendesk_link = (
        f"<https://nimbuscloud.zendesk.example/tickets/{zendesk_id}|#{zendesk_id}>"
    )
    return (
        f":ticket: *Ticket #{zendesk_id}* — `{triage.category.value}` / "
        f"`{triage.priority.value}` (confidence {triage.confidence:.2f})\n"
        f"*Customer*: {customer.email} ({customer.tier.value})\n"
        f"*Subject*: {ticket.subject}\n"
        f"*Triage*: {triage.reasoning}\n"
        f"*Drafted response confidence*: {resolution.confidence:.2f}\n"
        f"*Citations*: {citations}\n"
        f"*Zendesk*: {zendesk_link}"
    )


# ─── Abstract base ──────────────────────────────────────────────────

class IntegrationDispatcher(ABC):
    """One object the flow calls instead of touching external systems directly."""

    @abstractmethod
    def create_or_update_zendesk_ticket(
        self,
        *,
        flow_state_id: str,
        customer: "Customer",
        ticket: "Ticket",
        triage: "TriageDecision",
    ) -> str:
        """Sync the ticket to Zendesk. Returns the Zendesk ticket ID."""

    @abstractmethod
    def add_zendesk_comment(
        self, *, zendesk_id: str, body: str, is_public: bool = True
    ) -> None:
        """Post a comment on an existing Zendesk ticket."""

    @abstractmethod
    def notify_slack(
        self,
        *,
        customer: "Customer",
        ticket: "Ticket",
        triage: "TriageDecision",
        resolution: "ResolutionDraft",
        zendesk_id: str,
    ) -> None:
        """Send a structured notification to the appropriate Slack channel."""


# ─── Local implementation ───────────────────────────────────────────

class LocalDispatcher(IntegrationDispatcher):
    """Calls the in-process Zendesk + Slack mocks directly."""

    def create_or_update_zendesk_ticket(
        self,
        *,
        flow_state_id: str,
        customer: "Customer",
        ticket: "Ticket",
        triage: "TriageDecision",
    ) -> str:
        result = mcp_zendesk_mock.create_or_update_ticket(
            external_id=flow_state_id,
            subject=ticket.subject,
            description=ticket.description,
            priority=ticket.priority.value,
            ticket_type=ticket.type.value,
            requester_email=customer.email,
            tags=ticket.tags,
        )
        return result["id"]

    def add_zendesk_comment(
        self, *, zendesk_id: str, body: str, is_public: bool = True
    ) -> None:
        mcp_zendesk_mock.add_comment(
            ticket_id=zendesk_id, body=body, is_public=is_public
        )

    def notify_slack(
        self,
        *,
        customer,
        ticket,
        triage,
        resolution,
        zendesk_id: str,
    ) -> None:
        channel = _choose_slack_channel(customer, triage)
        text = _format_slack_notification(
            customer=customer,
            ticket=ticket,
            triage=triage,
            resolution=resolution,
            zendesk_id=zendesk_id,
        )
        mcp_slack_mock.send_message(channel=channel, text=text)


# ─── AMP implementation ─────────────────────────────────────────────

class AMPDispatcher(IntegrationDispatcher):
    """Routes Slack through CrewAI AMP via narrowly-scoped agents.

    Zendesk operations stay on the local mock for now — AMP lists Zendesk
    in its catalog but the integration has been rolling out to accounts in
    a staggered way. When Zendesk lands in your dashboard, swap the body
    of the two Zendesk methods to use the same narrowly-scoped-agent shape
    as `notify_slack`. The narrow-scope principle, agent backstories, and
    task descriptions transfer cleanly.

    Requires CREWAI_PLATFORM_INTEGRATION_TOKEN in the environment and
    Slack connected in your AMP account.
    """

    def create_or_update_zendesk_ticket(
        self,
        *,
        flow_state_id: str,
        customer,
        ticket,
        triage,
    ) -> str:
        # Until Zendesk ships to AMP, defer to the local mock.
        # When it ships, swap the body to build a narrowly-scoped agent
        # with apps=["zendesk/create_ticket", "zendesk/update_ticket",
        # "zendesk/search_tickets"] and a task description that uses
        # external_id={flow_state_id} for idempotency.
        result = mcp_zendesk_mock.create_or_update_ticket(
            external_id=flow_state_id,
            subject=ticket.subject,
            description=ticket.description,
            priority=ticket.priority.value,
            ticket_type=ticket.type.value,
            requester_email=customer.email,
            tags=ticket.tags,
        )
        return result["id"]

    def add_zendesk_comment(
        self, *, zendesk_id: str, body: str, is_public: bool = True
    ) -> None:
        # Same as above — defers to the local mock until AMP ships Zendesk.
        # When it ships, swap to a narrowly-scoped agent with
        # apps=["zendesk/add_comment_to_ticket"].
        mcp_zendesk_mock.add_comment(
            ticket_id=zendesk_id, body=body, is_public=is_public
        )

    def notify_slack(
        self,
        *,
        customer,
        ticket,
        triage,
        resolution,
        zendesk_id: str,
    ) -> None:
        channel = _choose_slack_channel(customer, triage)
        text = _format_slack_notification(
            customer=customer,
            ticket=ticket,
            triage=triage,
            resolution=resolution,
            zendesk_id=zendesk_id,
        )
        agent = Agent(
            role="Slack Notifier",
            goal="Post one notification message to the specified Slack channel.",
            backstory=(
                "You only do one thing: post the provided text to the specified "
                "Slack channel. You never modify the text."
            ),
            apps=["slack/send_message"],
            allow_delegation=False,
            verbose=False,
        )
        task = Task(
            description=(
                f"Send the following message to Slack channel `{channel}`. "
                f"Do NOT modify the text.\n\n"
                f"--- MESSAGE TEXT ---\n{text}\n--- END MESSAGE ---"
            ),
            expected_output="Confirmation that the message was sent.",
            agent=agent,
        )
        Crew(
            agents=[agent], tasks=[task], process=Process.sequential, verbose=False
        ).kickoff()


# ─── Factory ────────────────────────────────────────────────────────

def build_dispatcher() -> IntegrationDispatcher:
    """Pick the dispatcher based on USE_AMP_APPS and token availability."""
    use_amp = os.getenv("USE_AMP_APPS", "false").lower() == "true"
    has_token = bool(os.getenv("CREWAI_PLATFORM_INTEGRATION_TOKEN"))

    if use_amp and has_token:
        return AMPDispatcher()
    if use_amp and not has_token:
        print(
            "⚠️  USE_AMP_APPS=true but CREWAI_PLATFORM_INTEGRATION_TOKEN is not "
            "set. Falling back to LocalDispatcher."
        )
    return LocalDispatcher()

