"""
Base Agent — agentic tool loop with full conversation history.
Handles both dict messages and LangChain message objects safely.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage
)

from app.config import settings

logger = logging.getLogger("travelbuddy.base")

MAX_TOOL_ROUNDS = 5


def _get_role(msg) -> str:
    """Extract role from either a dict or a LangChain message object."""
    if isinstance(msg, dict):
        return msg.get("role", "user")
    if isinstance(msg, HumanMessage):
        return "user"
    if isinstance(msg, AIMessage):
        return "assistant"
    if isinstance(msg, SystemMessage):
        return "system"
    if hasattr(msg, "type"):
        t = msg.type
        if t == "human":   return "user"
        if t == "ai":      return "assistant"
        if t == "system":  return "system"
    return "user"


def _get_content(msg) -> str:
    """Extract content from either a dict or a LangChain message object."""
    if isinstance(msg, dict):
        return msg.get("content", "")
    if isinstance(msg, BaseMessage):
        c = msg.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in c
            )
    return str(msg)


class BaseAgent:
    name: str = "base"
    tools: list = []
    system_prompt: str = "You are a helpful travel assistant."

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_MINI,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.3,
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.tool_map = {t.name: t for t in self.tools}

    def _build_system(self, destination: Optional[str],
                      extra_context: Optional[str]) -> str:
        parts = [self.system_prompt]
        if extra_context:
            parts.append(f"\n{extra_context}")
        if destination and extra_context and destination not in extra_context:
            parts.append(f"\nDestination: {destination}")
        return "\n".join(parts)

    def _build_messages(self, conversation_history: List, system: str) -> List:
        """
        Build LangChain message list.
        Safely handles both dict messages and LangChain message objects.
        Uses last 10 messages only to keep token usage low.
        """
        msgs = [SystemMessage(content=system)]
        for msg in conversation_history[-10:]:
            role    = _get_role(msg)
            content = _get_content(msg)
            if not content:
                continue
            if role == "user":
                msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                msgs.append(AIMessage(content=content))
        return msgs

    async def run(self,
                  conversation_history: List,
                  destination: Optional[str] = None,
                  extra_context: Optional[str] = None) -> Dict[str, Any]:

        system   = self._build_system(destination, extra_context)
        messages = self._build_messages(conversation_history, system)

        tool_results_combined: Dict[str, Any] = {}
        response_text = ""

        for round_num in range(MAX_TOOL_ROUNDS):
            response = await self.llm_with_tools.ainvoke(messages)

            if not response.tool_calls:
                response_text = _get_content(response)
                break

            messages.append(response)

            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_fn   = self.tool_map.get(tool_name)

                logger.info(
                    f"  [{self.name}] tool: {tool_name}"
                    f"({', '.join(f'{k}={str(v)[:30]}' for k,v in tool_args.items())})"
                )

                if tool_fn:
                    try:
                        if hasattr(tool_fn, "ainvoke"):
                            result = await tool_fn.ainvoke(tool_args)
                        else:
                            result = tool_fn.invoke(tool_args)
                        if isinstance(result, dict):
                            tool_results_combined.update(result)
                        tool_str = (
                            json.dumps(result)
                            if isinstance(result, (dict, list))
                            else str(result)
                        )
                    except Exception as e:
                        logger.error(f"  [{self.name}] tool {tool_name} error: {e}")
                        tool_str = f"Error calling {tool_name}: {e}"
                else:
                    logger.warning(f"  [{self.name}] unknown tool: {tool_name}")
                    tool_str = f"Tool {tool_name} not available"

                messages.append(ToolMessage(
                    content=tool_str,
                    tool_call_id=tc["id"],
                ))

        if not response_text:
            try:
                final = await self.llm_with_tools.ainvoke(messages)
                response_text = _get_content(final)
            except Exception as e:
                logger.error(f"  [{self.name}] final response error: {e}")
                response_text = ""

        return {
            "agent":    self.name,
            "active":   True,
            "response": response_text,
            **tool_results_combined,
        }
