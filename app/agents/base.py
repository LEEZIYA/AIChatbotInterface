"""
Base Agent
----------
All specialist agents inherit from this. It handles:
- Binding tools to the LLM
- Calling the LLM with the right system prompt
- Invoking tools when the LLM requests them (agentic loop)
- Returning a structured AgentResponse

The agentic loop works like this:
  1. LLM receives system prompt + conversation context
  2. LLM decides which tool(s) to call
  3. We call the tool(s) and send results back to LLM
  4. LLM produces final natural language response
  5. We return that as AgentResponse
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool

from app.config import settings

logger = logging.getLogger("TRAVELBUDDY.base_agent")


class BaseAgent:
    """
    Base class for all TRAVELBUDDY specialist agents.
    Subclasses set: name, system_prompt, tools
    """

    name: str = "base"
    system_prompt: str = "You are a helpful travel assistant."
    tools: List[BaseTool] = []

    def __init__(self):
        # Use mini model for sub-agents to reduce cost
        # Supervisor uses full gpt-4o for routing decisions
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_MINI,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.5,
        )
        # Bind tools so the LLM knows it can call them
        if self.tools:
            self.llm_with_tools = self.llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = self.llm

        # Build a lookup map: tool_name → tool function
        self.tool_map: Dict[str, BaseTool] = {t.name: t for t in self.tools}

    async def run(
        self,
        user_query: str,
        destination: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the agentic loop for this agent.
        Returns an AgentResponse dict.
        """
        logger.info(f"[{self.name}] Starting — query='{user_query[:60]}...'")

        # Build initial messages
        context_str = f"\nDestination context: {destination}" if destination else ""
        extra_str = f"\nAdditional context: {extra_context}" if extra_context else ""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"{user_query}{context_str}{extra_str}"),
        ]

        tool_outputs = {}

        # ── Agentic loop ──────────────────────────────────────────────────────
        # Max 3 iterations to prevent infinite loops
        for iteration in range(3):
            response = await self.llm_with_tools.ainvoke(messages)
            messages.append(response)  # add AI response to history

            # Check if LLM wants to call any tools
            if not response.tool_calls:
                # No tool calls — LLM is done, extract final answer
                logger.info(f"[{self.name}] Completed in {iteration + 1} iteration(s)")
                break

            # ── Execute each requested tool ───────────────────────────────────
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id   = tool_call["id"]

                logger.info(f"[{self.name}] Calling tool: {tool_name}({tool_args})")

                if tool_name in self.tool_map:
                    try:
                        # Execute the tool
                        tool_result = await self.tool_map[tool_name].arun(tool_args)
                        tool_outputs[tool_name] = tool_result
                        result_content = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                    except Exception as e:
                        logger.error(f"[{self.name}] Tool {tool_name} failed: {e}")
                        result_content = f"Tool error: {str(e)}"
                else:
                    result_content = f"Tool {tool_name} not available"

                # Add tool result back into message history so LLM can see it
                messages.append(
                    ToolMessage(content=result_content, tool_call_id=tool_id)
                )

        # ── Extract final text response ───────────────────────────────────────
        final_text = ""
        if hasattr(response, "content"):
            if isinstance(response.content, str):
                final_text = response.content
            elif isinstance(response.content, list):
                # Some models return content as list of blocks
                final_text = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in response.content
                )

        return {
            "agent": self.name,
            "response": final_text,
            "data": tool_outputs if tool_outputs else None,
            "error": None,
        }
