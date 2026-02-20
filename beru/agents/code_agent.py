"""
Code Agent for BERU
Handles code writing, review, refactoring, and analysis
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from beru.core.agent import BaseAgent, agent
from beru.core.llm import get_llm_client
from beru.plugins.base import Tool, ToolResult, ToolParameter, ToolType
from beru.utils.logger import get_logger

logger = get_logger("beru.agents.code")


class WriteCodeTool(Tool):
    name = "write_code"
    description = "Write code to a file based on requirements"
    tool_type = ToolType.CODE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to save the code file",
            required=True,
        ),
        ToolParameter(
            name="code",
            type="string",
            description="The code content to write",
            required=True,
        ),
        ToolParameter(
            name="language",
            type="string",
            description="Programming language (python, javascript, etc.)",
            required=False,
            default="python",
        ),
    ]

    async def execute(
        self, file_path: str, code: str, language: str = "python", **kwargs
    ) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"Code written to {path}",
                metadata={
                    "path": str(path),
                    "language": language,
                    "lines": len(code.split("\n")),
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ReviewCodeTool(Tool):
    name = "review_code"
    description = "Review code for bugs, security issues, and best practices"
    tool_type = ToolType.CODE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the code file to review",
            required=True,
        ),
    ]

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)
            code = path.read_text(encoding="utf-8")

            return ToolResult(
                success=True,
                output=code,
                metadata={"path": str(path), "size": len(code)},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class AnalyzeSecurityTool(Tool):
    name = "analyze_security"
    description = "Analyze code for security vulnerabilities"
    tool_type = ToolType.CODE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the code file to analyze",
            required=True,
        ),
    ]

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)
            code = path.read_text(encoding="utf-8")

            return ToolResult(success=True, output=code, metadata={"path": str(path)})
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class GenerateDocumentationTool(Tool):
    name = "generate_docs"
    description = "Generate documentation for code files"
    tool_type = ToolType.CODE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the code file",
            required=True,
        ),
        ToolParameter(
            name="doc_type",
            type="string",
            description="Type of documentation (docstrings, readme, api)",
            required=False,
            default="docstrings",
        ),
    ]

    async def execute(
        self, file_path: str, doc_type: str = "docstrings", **kwargs
    ) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)
            code = path.read_text(encoding="utf-8")

            return ToolResult(
                success=True,
                output=code,
                metadata={"path": str(path), "doc_type": doc_type},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


@agent
class CodeAgent(BaseAgent):
    name = "code_agent"
    description = "Agent specialized in code writing, review, and analysis"
    agent_type = "code"
    tools = [
        WriteCodeTool,
        ReviewCodeTool,
        AnalyzeSecurityTool,
        GenerateDocumentationTool,
    ]

    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.llm = get_llm_client()

    async def think(self, input_text: str) -> Dict[str, Any]:
        from beru.utils.helpers import extract_json

        prompt = f"""You are BERU's Code Agent - an expert programmer and code reviewer.

User request: {input_text}

Available tools (use the EXACT action name):
- action: "write_code" - Write code to file (params: {{"file_path": "path", "code": "code_content", "language": "python"}})
- action: "review_code" - Review code for issues (params: {{"file_path": "path"}})
- action: "analyze_security" - Security analysis (params: {{"file_path": "path"}})
- action: "generate_docs" - Generate documentation (params: {{"file_path": "path", "doc_type": "docstrings"}})

Guidelines:
- For general coding questions without file operations: use action "answer"
- For code tasks: use the appropriate tool
- Write clean, well-documented code
- Follow best practices
- Be helpful and explain your code

IMPORTANT: Use the user's actual home path: /home/user171125

Respond ONLY with valid JSON:
{{"action": "answer", "final_answer": "your response"}}
OR
{{"action": "tool_name", "action_input": {{"param": "value"}}}}

JSON response:"""

        try:
            response = await self.llm.generate(prompt, max_tokens=1500, temperature=0.5)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text
                    if response.text
                    else "I'm not sure how to help with that.",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": f"I encountered an error: {e}. Please try again.",
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
