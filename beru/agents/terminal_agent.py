from __future__ import annotations

from typing import Any, Dict, Optional

from beru.core.agent import BaseAgent, agent
from beru.core.llm import get_llm_client
from beru.plugins.base import Tool, ToolResult, ToolParameter, ToolType
from beru.utils.logger import get_logger

logger = get_logger("beru.agents.terminal")


class ExecuteCommandTool(Tool):
    name = "execute_command"
    description = "Execute a shell command safely"
    tool_type = ToolType.TERMINAL
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="Command to execute",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Timeout in seconds",
            required=False,
            default=60,
        ),
    ]
    dangerous = True
    requires_confirmation = True

    async def execute(
        self,
        command: str,
        timeout: int = 60,
        **kwargs,
    ) -> ToolResult:
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_command(command)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            returncode, stdout, stderr = safety.execute_command(
                command,
                timeout=timeout,
            )

            if returncode == 0:
                return ToolResult(
                    success=True,
                    output=stdout or "Command executed successfully",
                    metadata={"returncode": returncode, "stderr": stderr},
                )
            else:
                return ToolResult(
                    success=False,
                    output=stdout,
                    error=f"Command failed with code {returncode}: {stderr}",
                    metadata={"returncode": returncode},
                )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class RunScriptTool(Tool):
    name = "run_script"
    description = "Run a Python or shell script"
    tool_type = ToolType.TERMINAL
    parameters = [
        ToolParameter(
            name="script_path",
            type="string",
            description="Path to the script file",
            required=True,
        ),
        ToolParameter(
            name="args",
            type="string",
            description="Arguments to pass to the script",
            required=False,
            default="",
        ),
    ]
    dangerous = True
    requires_confirmation = True

    async def execute(
        self,
        script_path: str,
        args: str = "",
        **kwargs,
    ) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(script_path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        path = Path(validation.sanitized or script_path)

        if path.suffix == ".py":
            command = f"python {path} {args}"
        else:
            command = f"bash {path} {args}"

        cmd_validation = safety.validate_command(command)
        if not cmd_validation.allowed:
            return ToolResult(success=False, output=None, error=cmd_validation.reason)

        try:
            returncode, stdout, stderr = safety.execute_command(command)

            if returncode == 0:
                return ToolResult(
                    success=True,
                    output=stdout or "Script executed successfully",
                    metadata={"returncode": returncode},
                )
            else:
                return ToolResult(
                    success=False,
                    output=stdout,
                    error=f"Script failed: {stderr}",
                )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


@agent
class TerminalAgent(BaseAgent):
    name = "terminal_agent"
    description = "Agent specialized in terminal/command execution"
    agent_type = "terminal"
    tools = [ExecuteCommandTool, RunScriptTool]

    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.llm = get_llm_client()

    async def think(self, input_text: str) -> Dict[str, Any]:
        from beru.utils.helpers import extract_json

        # Check for simple greetings
        simple_greetings = [
            "hi",
            "hello",
            "hlo",
            "hey",
            "how are you",
            "what can you do",
            "help",
        ]
        if (
            any(g in input_text.lower().strip() for g in simple_greetings)
            and len(input_text.split()) < 5
        ):
            return {
                "action": "answer",
                "final_answer": "Hello! I'm BERU's Terminal Agent. I can execute shell commands safely. What would you like me to run?",
            }

        prompt = f"""You are a terminal command executor. Be safe and careful.

User: {input_text}

Available tools:
- execute_command: needs command and timeout (optional)
- run_script: needs script_path and args (optional)

Safety rules:
- NEVER run: rm -rf, sudo, mkfs, dd
- Always use safe commands

Respond in JSON:
{{"action": "tool_name", "action_input": {{"param": "value"}}}}
OR:
{{"action": "answer", "final_answer": "your response"}}"""

        try:
            response = await self.llm.generate(prompt, max_tokens=200, temperature=0.1)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text[:500]
                    if response.text
                    else "I'm not sure what you want me to do.",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": f"I encountered an error: {e}. Please try again.",
            }

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
                error="Tool parameters must be an object",
            )

        return await self.execute_tool(action, **action_input)
