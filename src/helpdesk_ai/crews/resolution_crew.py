"""ResolutionCrew — drafts a customer response, grounded in the corpus.

This crew demonstrates the #1 concept learners trip on: the distinction
between crew-level knowledge (shared by every agent on the crew) and
agent-level knowledge (visible only to that specific agent).

Our split:
  - Crew-level:   product docs, FAQs, SLA matrix
                  → every agent sees this. It's the "public" knowledge.
  - Agent-level:  refund policy (billing specialist only)
                  → the general responder NEVER sees internal refund
                    thresholds and approval playbooks. Scope-limited
                    knowledge is how we enforce "only the right agent
                    can see the right docs."

Under the hood: CrewAI stores agent-level knowledge in a separate ChromaDB
collection named after the agent's role, so there's hard isolation at the
storage layer.
"""

from __future__ import annotations

from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.knowledge.knowledge_config import KnowledgeConfig
from crewai.knowledge.source.csv_knowledge_source import CSVKnowledgeSource
from crewai.knowledge.source.json_knowledge_source import JSONKnowledgeSource
from crewai.knowledge.source.text_file_knowledge_source import (
    TextFileKnowledgeSource,
)
from crewai.project import CrewBase, agent, crew, task

from ..models import IssueCategory, ResolutionDraft


KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"


def _text_sources(*globs: str) -> list[TextFileKnowledgeSource]:
    """Helper: build a TextFileKnowledgeSource from a set of glob patterns."""
    matched: list[str] = []
    for pattern in globs:
        for p in KNOWLEDGE_DIR.glob(pattern):
            matched.append(str(p.relative_to(KNOWLEDGE_DIR)))
    return [TextFileKnowledgeSource(file_paths=matched)] if matched else []


@CrewBase
class ResolutionCrew:
    """Drafts a customer response grounded in the NimbusCloud knowledge base."""

    agents_config = "../config/resolution_agents.yaml"
    tasks_config = "../config/resolution_tasks.yaml"

    # Set by `for_category()` before `.crew()` is built.
    # Defaults to GENERAL so the crew is still usable without it.
    category: IssueCategory = IssueCategory.GENERAL

    def for_category(self, category: IssueCategory) -> "ResolutionCrew":
        """Chainable setter. Billing → billing_specialist, else generalist."""
        self.category = category
        return self

    # ── Crew-level knowledge (shared by every agent) ─────────────────

    @property
    def knowledge_sources(self):
        sources: list = []
        sources.extend(_text_sources("product_docs/*.md"))
        faqs = KNOWLEDGE_DIR / "faqs" / "top_faqs.json"
        if faqs.exists():
            sources.append(
                JSONKnowledgeSource(
                    file_paths=[str(faqs.relative_to(KNOWLEDGE_DIR))]
                )
            )
        sla = KNOWLEDGE_DIR / "sla_matrix.csv"
        if sla.exists():
            sources.append(
                CSVKnowledgeSource(
                    file_paths=[str(sla.relative_to(KNOWLEDGE_DIR))]
                )
            )
        return sources

    # ── Retrieval tuning ────────────────────────────────────────────
    # A little more generous than defaults because responses need breadth.
    knowledge_config = KnowledgeConfig(results_limit=8, score_threshold=0.4)

    # ── Agents ──────────────────────────────────────────────────────

    @agent
    def support_responder(self) -> Agent:
        return Agent(
            config=self.agents_config["support_responder"],
            verbose=True,
            allow_delegation=False,
            knowledge_config=self.knowledge_config,
        )

    @agent
    def billing_specialist(self) -> Agent:
        # AGENT-LEVEL knowledge: the refund policy.
        # Note we attach it here, NOT on the crew. Only this agent sees it.
        billing_policy_sources = _text_sources("billing/*.md")
        return Agent(
            config=self.agents_config["billing_specialist"],
            verbose=True,
            allow_delegation=False,
            knowledge_sources=billing_policy_sources,
            knowledge_config=self.knowledge_config,
        )

    # ── Task & crew ─────────────────────────────────────────────────

    @task
    def draft_response(self) -> Task:
        # Dynamically bind the task to the right agent based on category.
        # Billing → billing_specialist, everything else → support_responder.
        chosen_agent = (
            self.billing_specialist()
            if self.category == IssueCategory.BILLING
            else self.support_responder()
        )
        return Task(
            config=self.tasks_config["draft_response"],
            output_pydantic=ResolutionDraft,
            agent=chosen_agent,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            knowledge_sources=self.knowledge_sources,
            verbose=True,
        )