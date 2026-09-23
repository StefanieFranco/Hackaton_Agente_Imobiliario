"""Estado compartilhado do grafo multiagente."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], operator.add]
    user_query: str
    intent: str
    lead_id: str | None
    model_name: str | None
    agent_outputs: dict[str, str]
    retrieved_docs: list[dict[str, Any]]
    properties_found: list[dict[str, Any]]
    schedule_draft: dict[str, Any] | None
    reengagement: list[dict[str, Any]]
    final_response: str
    route: list[str]
