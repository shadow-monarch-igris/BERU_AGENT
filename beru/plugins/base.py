from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class ToolType(Enum):
    FILE = "file"
    CODE = "code"
    TERMINAL = "terminal"
    PROJECT = "project"
    MEMORY = "memory"
    UTILITY = "utility"


@dataclass
class ToolResult:
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


class Tool(ABC):
    name: str = ""
    description: str = ""
    tool_type: ToolType = ToolType.UTILITY
    parameters: List[ToolParameter] = []
    dangerous: bool = False
    requires_confirmation: bool = False

    _agent: Optional[Any] = None

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def get_schema(self) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param in self.parameters:
            prop: Dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def set_agent(self, agent: Any) -> None:
        self._agent = agent

    def validate_params(self, **kwargs) -> Optional[str]:
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return f"Missing required parameter: {param.name}"

        return None


def tool(
    name: str,
    description: str,
    tool_type: ToolType = ToolType.UTILITY,
    parameters: Optional[List[ToolParameter]] = None,
    dangerous: bool = False,
    requires_confirmation: bool = False,
):
    def decorator(func: Callable):
        func._is_tool = True  # type: ignore
        func._tool_name = name  # type: ignore
        func._tool_description = description  # type: ignore
        func._tool_type = tool_type  # type: ignore
        func._tool_parameters = parameters or []  # type: ignore
        func._tool_dangerous = dangerous  # type: ignore
        func._tool_requires_confirmation = requires_confirmation  # type: ignore
        return func

    return decorator


class FunctionTool(Tool):
    def __init__(
        self,
        func: Callable,
        name: str,
        description: str,
        tool_type: ToolType = ToolType.UTILITY,
        parameters: Optional[List[ToolParameter]] = None,
        dangerous: bool = False,
        requires_confirmation: bool = False,
    ):
        self._func = func
        self.name = name
        self.description = description
        self.tool_type = tool_type
        self.parameters = parameters or []
        self.dangerous = dangerous
        self.requires_confirmation = requires_confirmation

    async def execute(self, **kwargs) -> ToolResult:
        try:
            error = self.validate_params(**kwargs)
            if error:
                return ToolResult(success=False, output=None, error=error)

            if inspect.iscoroutinefunction(self._func):
                result = await self._func(**kwargs)
            else:
                result = self._func(**kwargs)

            if isinstance(result, ToolResult):
                return result

            return ToolResult(success=True, output=result)

        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("Tool must have a name")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> Dict[str, Tool]:
        return self._tools.copy()

    def get_by_type(self, tool_type: ToolType) -> List[Tool]:
        return [t for t in self._tools.values() if t.tool_type == tool_type]

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.get_schema() for tool in self._tools.values()]

    def register_function(self, func: Callable) -> None:
        if hasattr(func, "_is_tool") and func._is_tool:  # type: ignore
            tool = FunctionTool(
                func=func,
                name=func._tool_name,  # type: ignore
                description=func._tool_description,  # type: ignore
                tool_type=func._tool_type,  # type: ignore
                parameters=func._tool_parameters,  # type: ignore
                dangerous=func._tool_dangerous,  # type: ignore
                requires_confirmation=func._tool_requires_confirmation,  # type: ignore
            )
            self.register(tool)


_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
