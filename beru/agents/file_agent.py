"""
Enhanced File Agent for BERU
Complete file operations with additional capabilities
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from beru.core.agent import BaseAgent, AgentFactory, agent
from beru.core.llm import get_llm_client
from beru.plugins.base import Tool, ToolResult, ToolParameter, ToolType
from beru.utils.logger import get_logger

logger = get_logger("beru.agents.file")


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file",
            required=True,
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path")
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path, must_exist=True, check_size=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)
            content = path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output=content,
                metadata={"path": str(path), "size": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file",
            required=True,
        ),
        ToolParameter(
            name="content", type="string", description="Content to write", required=True
        ),
    ]
    dangerous = True
    requires_confirmation = True

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path")
        content = kwargs.get("content", "")
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Wrote {len(content)} chars to {path}",
                metadata={"path": str(path)},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "List contents of a directory"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="directory",
            type="string",
            description="Path to directory",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="List recursively",
            required=False,
            default=False,
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        directory = kwargs.get("directory", ".")
        recursive = kwargs.get("recursive", False)
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(directory, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or directory)
            items = list(path.rglob("*")) if recursive else list(path.iterdir())

            result = []
            for item in items[:500]:
                result.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    }
                )

            return ToolResult(
                success=True, output=result, metadata={"count": len(result)}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class DeleteFileTool(Tool):
    name = "delete_file"
    description = "Delete a file or empty directory"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="file_path", type="string", description="Path to delete", required=True
        ),
    ]
    dangerous = True
    requires_confirmation = True

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path")
        import shutil
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            return ToolResult(success=True, output=f"Deleted {path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class CreateDirectoryTool(Tool):
    name = "create_directory"
    description = "Create a new directory"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="directory_path",
            type="string",
            description="Path to create",
            required=True,
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        directory_path = kwargs.get("directory_path")
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(directory_path)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or directory_path)
            path.mkdir(parents=True, exist_ok=True)
            return ToolResult(success=True, output=f"Created directory: {path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Search for files matching a pattern"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob pattern (e.g., '*.py')",
            required=True,
        ),
        ToolParameter(
            name="directory",
            type="string",
            description="Directory to search",
            required=False,
            default=".",
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "*")
        directory = kwargs.get("directory", ".")
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(directory, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or directory)
            matches = list(path.glob(pattern))[:100]

            result = [
                {
                    "name": m.name,
                    "path": str(m),
                    "type": "directory" if m.is_dir() else "file",
                }
                for m in matches
            ]

            return ToolResult(
                success=True,
                output=result,
                metadata={"pattern": pattern, "count": len(result)},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class SummarizeFolderTool(Tool):
    name = "summarize_folder"
    description = "Generate summary of folder contents"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="directory", type="string", description="Path to folder", required=True
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        directory = kwargs.get("directory")
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(directory, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or directory)

            total_files = 0
            total_dirs = 0
            total_size = 0
            file_types = {}

            for item in path.rglob("*"):
                if item.is_file():
                    total_files += 1
                    total_size += item.stat().st_size
                    ext = item.suffix.lower() or "no_extension"
                    file_types[ext] = file_types.get(ext, 0) + 1
                elif item.is_dir():
                    total_dirs += 1

            summary = {
                "path": str(path),
                "total_files": total_files,
                "total_directories": total_dirs,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": dict(
                    sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10]
                ),
            }

            return ToolResult(
                success=True, output=summary, metadata={"path": str(path)}
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class OpenInAppTool(Tool):
    name = "open_in_app"
    description = "Open file/folder in an application"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="path", type="string", description="Path to open", required=True
        ),
        ToolParameter(
            name="app",
            type="string",
            description="Application (code, vim, firefox)",
            required=False,
            default="code",
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path")
        app = kwargs.get("app", "code")
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            resolved_path = Path(validation.sanitized or path)

            app_commands = {
                "code": ["code", str(resolved_path)],
                "vscode": ["code", str(resolved_path)],
                "vim": ["vim", str(resolved_path)],
                "nano": ["nano", str(resolved_path)],
                "firefox": ["firefox", str(resolved_path)],
                "chrome": ["google-chrome", str(resolved_path)],
                "files": ["nautilus", str(resolved_path)],
                "terminal": [
                    "gnome-terminal",
                    "--working-directory",
                    str(resolved_path),
                ],
            }

            cmd = app_commands.get(app.lower(), [app, str(resolved_path)])
            subprocess.Popen(cmd, start_new_session=True)

            return ToolResult(success=True, output=f"Opened {resolved_path} in {app}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class UpdateFileTool(Tool):
    name = "update_file"
    description = "Update an existing file by appending or replacing content"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="file_path", type="string", description="Path to file", required=True
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to add/replace",
            required=True,
        ),
        ToolParameter(
            name="mode",
            type="string",
            description="Mode: append or replace",
            required=False,
            default="append",
        ),
    ]
    dangerous = True

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path")
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "append")
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(file_path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or file_path)

            if mode == "replace":
                path.write_text(content, encoding="utf-8")
            else:
                with open(path, "a") as f:
                    f.write("\n" + content)

            return ToolResult(success=True, output=f"Updated {path}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


@agent
class FileAgent(BaseAgent):
    name = "file_agent"
    description = "Enhanced agent for file system operations"
    agent_type = "file"
    tools = [
        ReadFileTool,
        WriteFileTool,
        ListDirectoryTool,
        CreateDirectoryTool,
        DeleteFileTool,
        SearchFilesTool,
        SummarizeFolderTool,
        OpenInAppTool,
        UpdateFileTool,
    ]

    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.llm = get_llm_client()

    async def think(self, input_text: str) -> Dict[str, Any]:
        from beru.utils.helpers import extract_json

        lower_input = input_text.lower().strip()

        greetings = [
            "hi",
            "hello",
            "hlo",
            "hey",
            "hola",
            "sup",
            "yo",
            "howdy",
            "greetings",
        ]
        if (
            any(g in lower_input.split() for g in greetings)
            and len(lower_input.split()) <= 3
        ):
            return {
                "action": "answer",
                "final_answer": f"Hello! How can I help you today? I can assist with file operations, code, projects, and more!",
            }

        prompt = f"""You are BERU - a friendly AI assistant. You have file operation tools but you should ALSO be able to have normal conversations!

User message: {input_text}

DECISION RULES:
1. If this is a GREETING, QUESTION, or GENERAL CHAT (not about files):
   → Respond with: {{"action": "answer", "final_answer": "your friendly response"}}
   
2. Only use tools when there's a CLEAR file operation request like:
   - "read the file..."
   - "list files in..."
   - "create a folder..."
   - "delete the file..."
   - "search for files..."
   - "summarize folder..."

3. If unsure, prefer "answer" action and have a natural conversation.

Examples of CONVERSATION (use action "answer"):
- "hlo" → {{"action": "answer", "final_answer": "Hello! How can I help?"}}
- "how are you" → {{"action": "answer", "final_answer": "I'm doing great! Ready to help!"}}
- "what can you do" → {{"action": "answer", "final_answer": "I can help with files, code, projects..."}}
- "thanks" → {{"action": "answer", "final_answer": "You're welcome!"}}

Examples of FILE OPERATIONS (use tools):
- "read config.py" → {{"action": "read_file", "action_input": {{"file_path": "/path/to/config.py"}}}}
- "list files in Downloads" → {{"action": "list_directory", "action_input": {{"directory": "/home/user171125/Downloads"}}}}

NOW, respond to: "{input_text}"

JSON response:"""

        try:
            response = await self.llm.generate(prompt, max_tokens=500, temperature=0.3)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text[:500]
                    if response.text
                    else "I'm here to help! What would you like to do?",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": f"I'm here to help! How can I assist you?",
            }

    async def act(self, thought: Dict[str, Any]) -> ToolResult:
        action = thought.get("action", "answer")
        action_input = thought.get("action_input", {})

        if action == "answer":
            return ToolResult(
                success=True, output=thought.get("final_answer", str(action_input))
            )

        if isinstance(action_input, str):
            return ToolResult(
                success=False, output=None, error="Tool parameters must be an object"
            )

        return await self.execute_tool(action, **action_input)
