"""SupportFlow — the orchestration spine of HelpDesk AI.

Lesson 1.2 goal: scaffold a Flow class that runs end-to-end with one
@start method. We don't model state or branching yet — those are
Lessons 1.3 and 1.4. The purpose of this file today is to prove the
package is correctly installed and crewai can find our flow.

Run it:
    uv run kickoff
"""

from __future__ import annotations

from dotenv import load_dotenv

from crewai.flow.flow import Flow, listen, or_, router, start

from .models import (
    Customer,
    CustomerTier,
    IssueCategory,
    ResolutionDraft,
    SupportState,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
    TriageDecision,
)

load_dotenv()


# ─── Mock inputs ─────────────────────────────────────────────────────
# These stand in for whatever intake channel we're wired to (email webhook,
# chat widget, Zendesk trigger). In production the payload arrives via
# the FastAPI request body or a webhook handler.

DEFAULT_INTAKE = {
    "customer_email": "alice@acme.corp",
    "customer_name": "Alice Rivera",
    "tier": "business",
    "subject": "Backup job failing with 'quota exceeded' but I'm on Business",
    "description": (
        "Hi — my nightly backup has been failing for three days with a "
        "'quota exceeded' error. I'm on the Business plan which says 2TB. "
        "Using about 400GB. Can someone look?"
    ),
}


# ─── The flow ────────────────────────────────────────────────────────

class SupportFlow(Flow[SupportState]):
    """End-to-end support flow. Flow-first, not crew-first."""

    # ── Step 1: intake ──────────────────────────────────────────────
    @start()
    def intake(self):
        """Parse the incoming request into typed state."""
        # Flow inputs arrive via kickoff(inputs={...}). The state's
        # `intake_payload` dict is populated automatically because the
        # key matches a field on SupportState.
        intake = self.state.intake_payload or DEFAULT_INTAKE

        customer = Customer(
            email=intake["customer_email"],
            name=intake.get("customer_name", ""),
            tier=CustomerTier(intake.get("tier", "free")),
        )
        ticket = Ticket(
            subject=intake["subject"],
            description=intake["description"],
        )

        self.state.customer = customer
        self.state.ticket = ticket
        self.state.trail.append(f"intake: ticket {ticket.ticket_id} for {customer.email}")
        print(f"📥 Intake: {ticket.ticket_id} — {customer.email} ({customer.tier.value})")
        return ticket

    # ── Step 2: triage ──────────────────────────────────────────────
    @listen(intake)
    def triage(self, ticket: Ticket):
        """Classify the ticket.

        The triage step's job is to produce a TriageDecision — category,
        priority, confidence, and whether a human is required. That
        decision then drives the @router below.
        """
        decision = _mock_triage(ticket, self.state.customer)

        self.state.triage = decision
        # Mirror triage into the ticket so downstream consumers don't
        # need to dereference state.triage to read priority/category.
        self.state.ticket.category = decision.category
        self.state.ticket.priority = decision.priority
        self.state.ticket.type = _type_from_category(decision.category)
        self.state.ticket.tags = decision.suggested_tags
        self.state.trail.append(
            f"triage: {decision.category.value} / {decision.priority.value} "
            f"(conf={decision.confidence:.2f})"
        )
        print(
            f"🏷️  Triage: {decision.category.value} / "
            f"{decision.priority.value} / conf={decision.confidence:.2f}"
        )
        return decision

    # ── Step 3: route ───────────────────────────────────────────────
    @router(triage)
    def route_on_triage(self, decision: TriageDecision):
        """Decide where the ticket goes next.

        The @router decorator is the CrewAI idiom for branching flows:
        it returns a string label that downstream @listen("label") methods
        catch.
        """
        if decision.needs_human or decision.confidence < 0.5:
            return "escalate"
        if decision.category in {IssueCategory.GENERAL, IssueCategory.ACCOUNT}:
            return "self_serve"
        return "needs_agent"

    # ── Step 4a: self-serve resolution ──────────────────────────────
    @listen("self_serve")
    def resolve_self_serve(self):
        """Generic/account issues. Cheap, fast, high-volume path."""        
        self.state.resolution = _mock_resolution(
            self.state.ticket,
            tone="self-service",
            confidence=0.85,
        )
        self.state.trail.append("resolve: self_serve path")
        print("✅ Self-serve resolution drafted")
        return self.state.resolution

    # ── Step 4b: specialist-agent resolution ────────────────────────
    @listen("needs_agent")
    def resolve_with_specialist(self):
        """Billing/technical/API issues. Needs domain knowledge."""
        self.state.resolution = _mock_resolution(
            self.state.ticket,
            tone="specialist",
            confidence=0.78,
        )
        self.state.trail.append(
            f"resolve: specialist path ({self.state.triage.category.value})"
        )
        print(f"🧑‍🔧 Specialist resolution drafted ({self.state.triage.category.value})")
        return self.state.resolution

    # ── Step 4c: human escalation ───────────────────────────────────
    @listen("escalate")
    def escalate_to_human(self):
        """Low-confidence or policy-sensitive tickets."""
        self.state.resolution = ResolutionDraft(
            response_text=(
                f"Hi {self.state.customer.name or 'there'} — we're escalating "
                "your ticket to a human specialist who'll be in touch shortly."
            ),
            confidence=0.0,
            suggested_next_action="escalate_to_human_agent",
        )
        self.state.trail.append("resolve: escalated to human")
        print("🚨 Escalated to human")
        return self.state.resolution

    # ── Step 5: respond ─────────────────────────────────────────────
    @listen(or_(resolve_self_serve, resolve_with_specialist, escalate_to_human))
    def respond(self):
        """Send the response — whichever resolution path fired above.

        `or_(...)` is the idiomatic way to fan multiple upstream methods
        into a single downstream step.
        """
        if not self.state.resolution:
            return  # defensive; shouldn't happen
        res = self.state.resolution
        self.state.ticket.status = TicketStatus.PENDING
        self.state.trail.append("respond: sent")
        print("\n" + "=" * 60)
        print("RESPONSE TO CUSTOMER")
        print("=" * 60)
        print(res.response_text)
        print("-" * 60)
        print(f"confidence={res.confidence:.2f}  next_action={res.suggested_next_action}")
        print("=" * 60)
        return self.state

# ─── Mock helpers ────────────────────────────────────────────────────
# Deterministic, rules-based stand-ins for the real triage and resolution
# crews. The whole point is to exercise the flow skeleton without LLM
# cost/latency — same flow, no API calls.

def _mock_triage(ticket: Ticket, customer: Customer | None) -> TriageDecision:
    """Rules-based triage."""
    text = (ticket.subject + " " + ticket.description).lower()

    if any(k in text for k in ("refund", "invoice", "charge", "billing", "quota")):
        category = IssueCategory.BILLING
    elif any(k in text for k in ("api", "token", "rate limit", "401", "403")):
        category = IssueCategory.API
    elif any(k in text for k in ("password", "login", "2fa", "can't access")):
        category = IssueCategory.ACCOUNT
    elif any(k in text for k in ("error", "fail", "sync", "crash", "slow")):
        category = IssueCategory.TECHNICAL
    else:
        category = IssueCategory.GENERAL

    # Tier-based priority nudge
    if customer and customer.tier in {CustomerTier.BUSINESS, CustomerTier.ENTERPRISE}:
        priority = TicketPriority.HIGH
    elif any(k in text for k in ("urgent", "asap", "down", "broken")):
        priority = TicketPriority.URGENT
    else:
        priority = TicketPriority.NORMAL

    return TriageDecision(
        category=category,
        priority=priority,
        confidence=0.78,
        reasoning=f"Keyword match → {category.value}; tier-based priority → {priority.value}",
        suggested_tags=[category.value, f"tier:{customer.tier.value}" if customer else "tier:free"],
        needs_human=False,
    )


def _mock_resolution(ticket: Ticket, tone: str, confidence: float) -> ResolutionDraft:
    return ResolutionDraft(
        response_text=(
            f"[{tone}] Thanks for reaching out about '{ticket.subject}'. "
            f"We see this is a {ticket.category.value} issue and we're "
            f"looking into it. We'll be in touch shortly with next steps."
        ),
        citations=[],
        confidence=confidence,
        suggested_next_action="await_customer_reply",
    )


def _type_from_category(category: IssueCategory) -> TicketType:
    return {
        IssueCategory.BILLING: TicketType.QUESTION,
        IssueCategory.ACCOUNT: TicketType.QUESTION,
        IssueCategory.TECHNICAL: TicketType.PROBLEM,
        IssueCategory.API: TicketType.PROBLEM,
        IssueCategory.GENERAL: TicketType.QUESTION,
    }[category]



# ─── Entry points ────────────────────────────────────────────────────

def kickoff():
    """Run the flow with the default mock intake. Wired to `uv run kickoff`."""
    flow = SupportFlow()
    final = flow.kickoff(inputs={"intake_payload": DEFAULT_INTAKE})
    print("\nFlow trail:")
    for step in final.trail:
        print(f"• {step}")
    return final


def plot():
    """Generate an interactive HTML diagram of the flow."""
    flow = SupportFlow()
    flow.plot("support_flow.html")
    print("✓ Wrote support_flow.html")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "plot":
        plot()
    else:
        kickoff()