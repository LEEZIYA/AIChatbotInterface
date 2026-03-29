"""
Base Agent
----------
All specialist agents inherit from this.
Accepts full conversation history so agents understand multi-turn context.
The agentic loop: LLM decides tools → execute → feed results back → repeat → final answer.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool

from app.config import settings

logger = logging.getLogger("voyager.base_agent")


class BaseAgent:
    name: str = "base"
    system_prompt: str = "You are a helpful travel assistant."
    tools: List[BaseTool] = []

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_MINI,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.5,
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools) if self.tools else self.llm
        self.tool_map: Dict[str, BaseTool] = {t.name: t for t in self.tools}

    async def run(
        self,
        conversation_history: List[Dict[str, str]],
        destination: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the agentic tool-calling loop with full conversation history.
        Agents see all prior messages so they understand follow-up references.
        """
        logger.info(f"[{self.name}] Starting — {len(conversation_history)} messages in history")

        # Build messages: system prompt first, then full conversation history
        messages = [SystemMessage(content=self._build_system_prompt(destination, extra_context))]

        for msg in conversation_history:
            role    = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        tool_outputs = {}

        # Agentic loop — max 3 tool-calling rounds
        for iteration in range(3):
            response = await self.llm_with_tools.ainvoke(messages)
            messages.append(response)

            if not response.tool_calls:
                logger.info(f"[{self.name}] Done in {iteration + 1} iteration(s)")
                break

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id   = tool_call["id"]
                logger.info(f"[{self.name}] Tool: {tool_name}({tool_args})")

                if tool_name in self.tool_map:
                    try:
                        tool_result = await self.tool_map[tool_name].arun(tool_args)
                        tool_outputs[tool_name] = tool_result
                        result_content = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                    except Exception as e:
                        logger.error(f"[{self.name}] Tool error: {e}")
                        result_content = f"Tool error: {str(e)}"
                else:
                    result_content = f"Tool {tool_name} not available"

                messages.append(ToolMessage(content=result_content, tool_call_id=tool_id))

        # Extract final text
        final_text = ""
        if hasattr(response, "content"):
            if isinstance(response.content, str):
                final_text = response.content
            elif isinstance(response.content, list):
                final_text = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in response.content
                )

        return {
            "agent":    self.name,
            "response": final_text,
            "data":     tool_outputs if tool_outputs else None,
            "error":    None,
        }

    def _build_system_prompt(self, destination: Optional[str], extra_context: Optional[str]) -> str:
        prompt = self.system_prompt
        if destination:
            prompt += f"\n\nDestination: {destination}"
        if extra_context:
            prompt += f"\nContext: {extra_context}"
        return prompt
