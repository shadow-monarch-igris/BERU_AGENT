from __future__ import annotations

import asyncio
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from beru.plugins.base import Tool, ToolResult, ToolRegistry, get_tool_registry
from beru.safety import get_safety_manager
from beru.utils.config import get_config
from beru.utils.logger import get_logger
from beru.utils.helpers import generate_id, extract_json

logger = get_logger("beru.agent")


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AgentContext:
    agent_id: str
    conversation: List[Message] = field(default_factory=list)
    state: AgentState = AgentState.IDLE
    current_task: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata) -> Message:
        message = Message(role=role, content=content, metadata=metadata)
        self.conversation.append(message)
        return message

    def get_history(self, limit: int = 10) -> List[Message]:
        return self.conversation[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "current_task": self.current_task,
            "tools_used": self.tools_used,
            "conversation": [m.to_dict() for m in self.conversation],
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = "Base agent class"
    agent_type: str = "base"
    tools: List[Type[Tool]] = []

    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id or generate_id()
        self.config = get_config()
        self.logger = get_logger(f"beru.agent.{self.name}")
        self.safety = get_safety_manager()
        self.registry = get_tool_registry()
        self.context = AgentContext(agent_id=self.agent_id)
        self._tool_instances: Dict[str, Tool] = {}

        self._register_tools()

    def _register_tools(self) -> None:
        for tool_class in self.tools:
            try:
                tool = tool_class()
                tool.set_agent(self)
                self._tool_instances[tool.name] = tool
                self.registry.register(tool)
            except Exception as e:
                self.logger.error(f"Failed to register tool {tool_class}: {e}")

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tool_instances.get(name) or self.registry.get(name)

    def get_available_tools(self) -> List[Tool]:
        return list(self._tool_instances.values())

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [tool.get_schema() for tool in self.get_available_tools()]

    @abstractmethod
    async def think(self, input_text: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def act(self, thought: Dict[str, Any]) -> ToolResult:
        pass

    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False, output=None, error=f"Tool not found: {tool_name}"
            )

        # Validate parameters first
        validation_error = tool.validate_params(**kwargs)
        if validation_error:
            return ToolResult(
                success=False,
                output=None,
                error=f"Parameter error: {validation_error}. Required params: {[p.name for p in tool.parameters if p.required]}",
            )

        self.safety.audit_logger.log_tool_execution(
            tool_name=tool_name,
            params=kwargs,
        )

        try:
            result = await tool.execute(**kwargs)
            self.safety.audit_logger.log_tool_execution(
                tool_name=tool_name,
                params=kwargs,
                result=result.output,
                error=result.error,
            )
            self.context.tools_used.append(tool_name)
            return result
        except Exception as e:
            self.logger.error(f"Tool execution failed: {tool_name} - {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def run(self, input_text: str) -> str:
        self.context.state = AgentState.THINKING
        self.context.current_task = input_text

        self.context.add_message("user", input_text)

        orchestrator_config = self.config.agents.get("orchestrator")
        max_iterations = (
            orchestrator_config.max_concurrent if orchestrator_config else 10
        )
        iteration = 0
        final_response = ""

        while iteration < max_iterations:
            try:
                thought = await self.think(input_text)

                if thought.get("final_answer"):
                    final_response = thought["final_answer"]
                    break

                self.context.state = AgentState.EXECUTING
                result = await self.act(thought)

                if result.success:
                    self.context.add_message(
                        "tool",
                        f"Tool result: {result.output}",
                        tool=thought.get("action"),
                    )
                    # Return tool result immediately after success
                    final_response = str(result.output) if result.output else "Done!"
                    break
                else:
                    self.context.add_message(
                        "tool_error",
                        f"Tool error: {result.error}",
                        tool=thought.get("action"),
                    )
                    final_response = f"Error: {result.error}"
                    break

                iteration += 1
                self.context.state = AgentState.THINKING

            except Exception as e:
                self.logger.error(f"Agent iteration failed: {e}")
                self.context.state = AgentState.ERROR
                return f"Error: {str(e)}"

        self.context.state = AgentState.COMPLETED
        self.context.add_message("assistant", final_response)

        return final_response

    def reset(self) -> None:
        self.context = AgentContext(agent_id=self.agent_id)
        self.context.state = AgentState.IDLE


class ReActAgent(BaseAgent):
    name = "react_agent"
    description = "ReAct-style agent with reasoning and acting"
    agent_type = "react"

    def __init__(
        self,
        agent_id: Optional[str] = None,
        llm_client: Optional[Any] = None,
    ):
        super().__init__(agent_id)
        self.llm_client = llm_client

    def _build_prompt(self, input_text: str) -> str:
        history = self.context.get_history(limit=5)
        history_str = "\n".join([f"{m.role}: {m.content}" for m in history])

        tools_desc = "\n".join(
            [
                f"- {tool.name}: {tool.description}"
                for tool in self.get_available_tools()
            ]
        )

        prompt = f"""You are {self.name}, an AI assistant.

Available tools:
{tools_desc}

Conversation history:
{history_str}

User input: {input_text}

Think step by step. You MUST respond in JSON format:
{{
    "thought": "your reasoning here",
    "action": "tool_name or 'answer'",
    "action_input": {{"param": "value"}} or "final answer text",
    "final_answer": null or "final answer if action is 'answer'"
}}

If you have enough information to answer the user, use action: "answer".
Otherwise, use a tool to gather more information.

Respond ONLY with valid JSON, no other text."""

        return prompt

    async def think(self, input_text: str) -> Dict[str, Any]:
        prompt = self._build_prompt(input_text)

        if self.llm_client:
            response = await self.llm_client.generate(prompt)
            raw_response = response.get("text", "")
        else:
            raw_response = '{"thought": "No LLM client configured", "action": "answer", "action_input": "I need an LLM client to function properly.", "final_answer": "I need an LLM client to function properly."}'

        parsed = extract_json(raw_response)
        if not parsed:
            parsed = {
                "thought": "Failed to parse response",
                "action": "answer",
                "final_answer": raw_response,
            }

        self.context.add_message(
            "thought",
            parsed.get("thought", ""),
            raw_response=raw_response,
        )

        return parsed

    async def act(self, thought: Dict[str, Any]) -> ToolResult:
        action = thought.get("action", "answer")
        action_input = thought.get("action_input", {})

        if action == "answer":
            return ToolResult(
                success=True,
                output=thought.get("final_answer", str(action_input)),
            )

        if isinstance(action_input, str):
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool {action} requires object parameters, got string",
            )

        return await self.execute_tool(action, **action_input)


class AgentFactory:
    _agents: Dict[str, Type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
        cls._agents[agent_class.name] = agent_class
        return agent_class

    @classmethod
    def create(
        cls,
        name: str,
        agent_id: Optional[str] = None,
        **kwargs,
    ) -> BaseAgent:
        if name not in cls._agents:
            raise ValueError(f"Unknown agent: {name}")
        return cls._agents[name](agent_id=agent_id, **kwargs)

    @classmethod
    def list_agents(cls) -> List[str]:
        return list(cls._agents.keys())


def agent(cls: Type[BaseAgent]) -> Type[BaseAgent]:
    return AgentFactory.register(cls)
