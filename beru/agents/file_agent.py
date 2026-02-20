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


class OpenWebsiteTool(Tool):
    name = "open_website"
    description = "Open a website in browser"
    tool_type = ToolType.UTILITY
    parameters = [
        ToolParameter(
            name="url", type="string", description="Website URL", required=True
        ),
        ToolParameter(
            name="browser",
            type="string",
            description="Browser (chrome, firefox)",
            required=False,
            default="default",
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        import webbrowser

        url = kwargs.get("url", "")
        browser = kwargs.get("browser", "default")

        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            # Add .com if it's just a domain name
            if "." not in url.split("//")[-1]:
                url = url + ".com"

            if browser == "default":
                webbrowser.open(url)
            else:
                browsers = {
                    "chrome": "google-chrome",
                    "firefox": "firefox",
                    "chromium": "chromium-browser",
                }
                cmd = browsers.get(browser, browser)
                subprocess.Popen([cmd, url], start_new_session=True)

            return ToolResult(success=True, output=f"Opened {url} in {browser} browser")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


@agent
class FileAgent(BaseAgent):
    name = "file_agent"
    description = "Enhanced agent for file system operations and web"
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
        OpenWebsiteTool,
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

        # Handle website opening - extract website name properly
        known_websites = [
            "youtube",
            "google",
            "github",
            "leetcode",
            "udemy",
            "stackoverflow",
            "reddit",
            "facebook",
            "twitter",
            "linkedin",
            "instagram",
            "amazon",
            "netflix",
            "gmail",
            "outlook",
            "spotify",
            "discord",
            "slack",
        ]

        if "open" in lower_input:
            # Handle YouTube with search/channel
            if "youtube" in lower_input:
                # Extract search terms
                text_after_youtube = lower_input.split("youtube")[-1].strip()
                text_after_youtube = (
                    text_after_youtube.replace("channel", "").replace("on", "").strip()
                )

                if text_after_youtube and len(text_after_youtube) > 0:
                    # Open with search
                    search_query = text_after_youtube.replace(" ", "+")
                    url = f"https://www.youtube.com/results?search_query={search_query}"
                else:
                    url = "https://youtube.com"

                return {
                    "action": "open_website",
                    "action_input": {"url": url},
                }

            # Check other known websites
            for site in known_websites:
                if site in lower_input:
                    browser = "default"
                    if "chrome" in lower_input:
                        browser = "chrome"
                    elif "firefox" in lower_input:
                        browser = "firefox"
                    return {
                        "action": "open_website",
                        "action_input": {"url": site, "browser": browser},
                    }

        conversation_history = self._build_conversation_context()

        prompt = f"""You are BERU, a helpful AI assistant. Use tools for operations!

{conversation_history}

User: {input_text}

TOOLS:
- open_website: Open websites (youtube, google) - params: {{"url": "youtube.com"}}
- search_files: Find files - params: {{"pattern": "*name*", "directory": "/home/user171125/Documents"}}
- list_directory: List folders - params: {{"directory": "/path"}}
- read_file: Read files - params: {{"file_path": "/path/file"}}
- open_in_app: Open files in apps - params: {{"path": "/path", "app": "code"}}

EXAMPLES:
"open youtube" -> {{"action": "open_website", "action_input": {{"url": "https://youtube.com"}}}}
"open google in chrome" -> {{"action": "open_website", "action_input": {{"url": "https://google.com", "browser": "chrome"}}}}
"search mosaic in documents" -> {{"action": "search_files", "action_input": {{"pattern": "*mosaic*", "directory": "/home/user171125/Documents"}}}}
"read app.py" -> {{"action": "read_file", "action_input": {{"file_path": "/path/from/context/app.py"}}}}

Respond with JSON only:"""

        try:
            response = await self.llm.generate(prompt, max_tokens=1500, temperature=0.3)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text
                    if response.text
                    else "I'm here to help!",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": "I'm here to help! How can I assist you?",
            }

        try:
            response = await self.llm.generate(prompt, max_tokens=1500, temperature=0.3)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text
                    if response.text
                    else "I'm here to help!",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": "I'm here to help! How can I assist you?",
            }

        conversation_history = self._build_conversation_context()

        prompt = f"""You are BERU, a helpful AI assistant. Give COMPLETE and DETAILED responses.

{conversation_history}

User: {input_text}

Rules:
- For questions/explanations → use action "answer" and provide FULL detailed response
- For file operations → use tools with paths like /home/user171125/Documents/...
- Give COMPLETE answers, do not cut off mid-sentence

Respond with JSON:
{{"action": "answer", "final_answer": "your complete detailed response here"}}"""

        try:
            response = await self.llm.generate(prompt, max_tokens=1500, temperature=0.5)
            parsed = extract_json(response.text)
            if not parsed:
                parsed = {
                    "action": "answer",
                    "final_answer": response.text
                    if response.text
                    else "I'm here to help!",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": "I'm here to help! How can I assist you?",
            }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": "I'm here to help! How can I assist you?",
            }

    def _build_conversation_context(self, limit: int = 10) -> str:
        history = self.context.get_history(limit)
        if not history:
            return "CONVERSATION HISTORY: (This is the start of our conversation)"

        context_lines = ["CONVERSATION HISTORY:"]
        for msg in history:
            role = msg.role.upper()
            content = msg.content
            if role == "USER":
                context_lines.append(f"User: {content}")
            elif role == "ASSISTANT":
                # For tool results, show full content so LLM can use the paths!
                if "[" in content and "{" in content:
                    context_lines.append(f"BERU found: {content}")
                else:
                    context_lines.append(f"BERU: {content[:300]}...")
            elif role == "TOOL":
                context_lines.append(f"[Tool result: {content[:200]}...]")

        context_lines.append("")
        return "\n".join(context_lines)

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
