"""
BERU 2.0 - Production-grade multi-agent AI assistant

A modular, production-ready AI agent system with:
- Multi-agent architecture
- Parallel workflow execution
- Plugin system for extensible tools
- Safety and sandboxing
- REST API and WebSocket support
- Local LLM support via Ollama
"""

from beru.utils.config import get_config, reload_config
from beru.utils.logger import init_logging, get_logger

__version__ = "2.0.0"
__author__ = "BERU Team"

from beru.core.agent import (
    BaseAgent,
    ReActAgent,
    AgentFactory,
    AgentState,
    AgentContext,
    Message,
    agent,
)

from beru.core.workflow import (
    Task,
    Workflow,
    WorkflowBuilder,
    WorkflowExecutor,
    get_workflow_executor,
)

from beru.plugins.base import (
    Tool,
    ToolResult,
    ToolParameter,
    ToolType,
    ToolRegistry,
    get_tool_registry,
)

from beru.api.server import create_server

__all__ = [
    "__version__",
    "get_config",
    "reload_config",
    "init_logging",
    "get_logger",
    "BaseAgent",
    "ReActAgent",
    "AgentFactory",
    "AgentState",
    "AgentContext",
    "Message",
    "agent",
    "Task",
    "Workflow",
    "WorkflowBuilder",
    "WorkflowExecutor",
    "get_workflow_executor",
    "Tool",
    "ToolResult",
    "ToolParameter",
    "ToolType",
    "ToolRegistry",
    "get_tool_registry",
    "create_server",
]
