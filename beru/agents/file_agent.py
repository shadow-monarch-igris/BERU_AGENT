from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

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
            description="Path to the file to read",
            required=True,
        ),
    ]

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        from pathlib import Path
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
    description = "Write content to a file, creating it if necessary"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file to write",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to write to the file",
            required=True,
        ),
    ]
    dangerous = True
    requires_confirmation = True

    async def execute(self, file_path: str, content: str, **kwargs) -> ToolResult:
        from pathlib import Path
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
                output=f"Successfully wrote {len(content)} characters to {path}",
                metadata={"path": str(path), "size": len(content)},
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
            description="Path to the directory to list",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Whether to list recursively",
            required=False,
            default=False,
        ),
    ]

    async def execute(
        self,
        directory: str = ".",
        recursive: bool = False,
        **kwargs,
    ) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(directory, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or directory)

            if recursive:
                items = list(path.rglob("*"))
            else:
                items = list(path.iterdir())

            result = []
            for item in items[:1000]:
                result.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    }
                )

            return ToolResult(
                success=True,
                output=result,
                metadata={"count": len(result), "truncated": len(items) > 1000},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class DeleteFileTool(Tool):
    name = "delete_file"
    description = "Delete a file or empty directory"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to the file or directory to delete",
            required=True,
        ),
    ]
    dangerous = True
    requires_confirmation = True

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        from pathlib import Path
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

            return ToolResult(
                success=True,
                output=f"Successfully deleted {path}",
                metadata={"path": str(path)},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class CreateDirectoryTool(Tool):
    name = "create_directory"
    description = "Create a new directory/folder"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="directory_path",
            type="string",
            description="Path of the directory to create",
            required=True,
        ),
    ]

    def _resolve_path(self, path: str) -> "Path":
        """Resolve path, handling user directory names"""
        from pathlib import Path
        import os

        # Common user directories
        home = Path.home()
        user_dirs = {
            "downloads": home / "Downloads",
            "documents": home / "Documents",
            "desktop": home / "Desktop",
            "pictures": home / "Pictures",
            "videos": home / "Videos",
            "music": home / "Music",
        }

        path = path.strip()

        # Already absolute path
        if path.startswith("/") or path.startswith("~"):
            return Path(path).expanduser().resolve()

        # Check if it's a user directory name
        path_lower = path.lower()
        for dir_name, dir_path in user_dirs.items():
            if path_lower == dir_name or path_lower.startswith(dir_name + "/"):
                # Replace the directory name with absolute path
                remaining = (
                    path[len(dir_name) :] if path.lower().startswith(dir_name) else ""
                )
                return (dir_path / remaining.lstrip("/")).resolve()

        # Relative path - resolve from current directory
        return Path(path).resolve()

    async def execute(self, directory_path: str, **kwargs) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        try:
            # Resolve the path first
            resolved_path = self._resolve_path(directory_path)

            safety = get_safety_manager()
            validation = safety.validate_path(str(resolved_path))

            if not validation.allowed:
                return ToolResult(success=False, output=None, error=validation.reason)

            resolved_path.mkdir(parents=True, exist_ok=True)
            return ToolResult(
                success=True,
                output=f"Created directory: {resolved_path}",
                metadata={"path": str(resolved_path)},
            )
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
            description="Glob pattern to search for (e.g., '*.py')",
            required=True,
        ),
        ToolParameter(
            name="directory",
            type="string",
            description="Directory to search in",
            required=False,
            default=".",
        ),
    ]

    async def execute(
        self,
        pattern: str,
        directory: str = ".",
        **kwargs,
    ) -> ToolResult:
        from pathlib import Path
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


@agent
class FileAgent(BaseAgent):
    name = "file_agent"
    description = "Agent specialized in file system operations"
    agent_type = "file"
    tools = [
        ReadFileTool,
        WriteFileTool,
        ListDirectoryTool,
        CreateDirectoryTool,
        DeleteFileTool,
        SearchFilesTool,
    ]

    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.llm = get_llm_client()

    async def think(self, input_text: str) -> Dict[str, Any]:
        from beru.utils.helpers import extract_json

        # Check for simple greetings or non-tool queries
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
                "final_answer": "Hello! I'm BERU's File Agent. I can help you with:\n- Reading and writing files\n- Listing directories\n- Searching for files\n- Managing your files safely\n\nWhat would you like me to do?",
            }

        prompt = f"""User request: {input_text}

Tools (respond with JSON to use one):
- create_directory(directory_path) - Create a folder
- list_directory(directory) - List folder contents  
- read_file(file_path) - Read a file
- write_file(file_path, content) - Write to file
- delete_file(file_path) - Delete file
- search_files(pattern, directory) - Find files

IMPORTANT: 
- Respond with ONLY valid JSON, no explanation
- Use the EXACT path: /home/user171125/Downloads NOT /home/user/Downloads
- For Downloads use: /home/user171125/Downloads
- For Documents use: /home/user171125/Documents
- Example: {{"action": "create_directory", "action_input": {{"directory_path": "/home/user171125/Downloads/igris"}}}}

JSON response:"""

        try:
            response = await self.llm.generate(prompt, max_tokens=200, temperature=0.1)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text[:500]
                    if response.text
                    else "I'm not sure how to help with that.",
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
                error=f"Tool parameters must be an object",
            )

        return await self.execute_tool(action, **action_input)
