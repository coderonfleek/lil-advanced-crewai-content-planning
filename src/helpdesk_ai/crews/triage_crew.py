"""TriageCrew — the first real LLM-driven crew in HelpDesk AI.

The crew owns no integrations and no memory. Its single job is to read a
ticket and return a TriageDecision. Clean separation of concerns.

Knowledge scoping: the triage agent gets crew-level knowledge (general
NimbusCloud docs, SLA matrix, top FAQs) because it needs breadth to
recognize any incoming issue.
"""

from __future__ import annotations

from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.knowledge.source.csv_knowledge_source import CSVKnowledgeSource
from crewai.knowledge.source.json_knowledge_source import JSONKnowledgeSource
from crewai.knowledge.source.text_file_knowledge_source import (
    TextFileKnowledgeSource,
)
from crewai.project import CrewBase, agent, crew, task

from ..models import TriageDecision


KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"


@CrewBase
class TriageCrew:
    """Classifies inbound tickets into category + priority + confidence."""

    agents_config = "../config/triage_agents.yaml"
    tasks_config = "../config/triage_tasks.yaml"

    # Crew-level knowledge: visible to every agent on this crew.
    @property
    def knowledge_sources(self):
        sources = []
        product_docs = list((KNOWLEDGE_DIR / "product_docs").glob("*.md"))
        if product_docs:
            rel_paths = [
                str(p.relative_to(KNOWLEDGE_DIR)) for p in product_docs
            ]
            sources.append(TextFileKnowledgeSource(file_paths=rel_paths))
        faqs_path = KNOWLEDGE_DIR / "faqs" / "top_faqs.json"
        if faqs_path.exists():
            sources.append(
                JSONKnowledgeSource(
                    file_paths=[str(faqs_path.relative_to(KNOWLEDGE_DIR))]
                )
            )
        sla_path = KNOWLEDGE_DIR / "sla_matrix.csv"
        if sla_path.exists():
            sources.append(
                CSVKnowledgeSource(
                    file_paths=[str(sla_path.relative_to(KNOWLEDGE_DIR))]
                )
            )
        return sources

    @agent
    def triage_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config["triage_specialist"],
            verbose=True,
            allow_delegation=False,
        )

    @task
    def classify_ticket(self) -> Task:
        return Task(
            config=self.tasks_config["classify_ticket"],
            output_pydantic=TriageDecision,
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