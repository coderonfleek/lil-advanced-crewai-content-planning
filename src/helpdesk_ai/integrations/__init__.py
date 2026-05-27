"""Integration layer — Zendesk and Slack via MCP, abstracted by dispatcher."""

from .dispatcher import IntegrationDispatcher, LocalDispatcher, build_dispatcher

__all__ = ["IntegrationDispatcher", "LocalDispatcher", "build_dispatcher"]