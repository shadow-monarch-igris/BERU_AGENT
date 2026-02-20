"""
Project Agent for BERU
Handles project scaffolding, structure creation, and dependency management
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from beru.core.agent import BaseAgent, agent
from beru.core.llm import get_llm_client
from beru.plugins.base import Tool, ToolResult, ToolParameter, ToolType
from beru.utils.logger import get_logger

logger = get_logger("beru.agents.project")


PROJECT_TEMPLATES = {
    "fastapi": {
        "structure": [
            "app/__init__.py",
            "app/main.py",
            "app/api/__init__.py",
            "app/api/routes.py",
            "app/models/__init__.py",
            "app/services/__init__.py",
            "app/utils/__init__.py",
            "tests/__init__.py",
            "tests/test_main.py",
            ".gitignore",
            "requirements.txt",
            "README.md",
            ".env.example",
        ],
        "requirements": ["fastapi", "uvicorn", "pydantic", "python-dotenv"],
    },
    "flask": {
        "structure": [
            "app/__init__.py",
            "app/routes.py",
            "app/models.py",
            "app/templates/base.html",
            "app/templates/index.html",
            "app/static/css/style.css",
            "tests/__init__.py",
            "tests/test_app.py",
            ".gitignore",
            "requirements.txt",
            "README.md",
            "config.py",
        ],
        "requirements": ["flask", "flask-sqlalchemy", "python-dotenv"],
    },
    "python_package": {
        "structure": [
            "src/__init__.py",
            "src/main.py",
            "tests/__init__.py",
            "tests/test_main.py",
            ".gitignore",
            "setup.py",
            "requirements.txt",
            "README.md",
            "pyproject.toml",
        ],
        "requirements": ["pytest", "black", "flake8"],
    },
    "node_api": {
        "structure": [
            "src/index.js",
            "src/routes/index.js",
            "src/controllers/index.js",
            "src/middleware/index.js",
            "src/models/index.js",
            "src/utils/index.js",
            "tests/index.test.js",
            ".gitignore",
            "package.json",
            "README.md",
            ".env.example",
        ],
        "requirements": [],
    },
    "react_app": {
        "structure": [
            "src/App.jsx",
            "src/index.jsx",
            "src/components/index.js",
            "src/pages/index.js",
            "src/hooks/index.js",
            "src/utils/index.js",
            "src/styles/index.css",
            "public/index.html",
            ".gitignore",
            "package.json",
            "README.md",
        ],
        "requirements": [],
    },
}


class CreateProjectTool(Tool):
    name = "create_project"
    description = "Create a new project with predefined structure"
    tool_type = ToolType.PROJECT
    parameters = [
        ToolParameter(
            name="project_name",
            type="string",
            description="Name of the project",
            required=True,
        ),
        ToolParameter(
            name="template",
            type="string",
            description="Project template (fastapi, flask, python_package, node_api, react_app)",
            required=True,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Where to create the project",
            required=False,
            default=".",
        ),
    ]

    async def execute(
        self, project_name: str, template: str, path: str = ".", **kwargs
    ) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        if template.lower() not in PROJECT_TEMPLATES:
            available = ", ".join(PROJECT_TEMPLATES.keys())
            return ToolResult(
                success=False,
                output=None,
                error=f"Unknown template '{template}'. Available: {available}",
            )

        safety = get_safety_manager()
        validation = safety.validate_path(path)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            base_path = Path(validation.sanitized or path) / project_name
            base_path.mkdir(parents=True, exist_ok=True)

            template_data = PROJECT_TEMPLATES[template.lower()]
            created_files = []

            for file_path in template_data["structure"]:
                file_full_path = base_path / file_path
                file_full_path.parent.mkdir(parents=True, exist_ok=True)
                file_full_path.touch()
                created_files.append(str(file_full_path))

            requirements_file = base_path / "requirements.txt"
            if template_data["requirements"] and not requirements_file.exists():
                requirements_file.write_text(
                    "\n".join(template_data["requirements"]) + "\n"
                )

            return ToolResult(
                success=True,
                output=f"Created {template} project '{project_name}' with {len(created_files)} files",
                metadata={
                    "path": str(base_path),
                    "template": template,
                    "files": created_files,
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class CreateFolderTool(Tool):
    name = "create_folder"
    description = "Create a new folder/directory"
    tool_type = ToolType.FILE
    parameters = [
        ToolParameter(
            name="folder_path",
            type="string",
            description="Path of the folder to create",
            required=True,
        ),
    ]

    async def execute(self, folder_path: str, **kwargs) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager

        safety = get_safety_manager()
        validation = safety.validate_path(folder_path)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or folder_path)
            path.mkdir(parents=True, exist_ok=True)

            return ToolResult(
                success=True,
                output=f"Created folder: {path}",
                metadata={"path": str(path)},
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class InstallDependenciesTool(Tool):
    name = "install_dependencies"
    description = "Install project dependencies"
    tool_type = ToolType.PROJECT
    parameters = [
        ToolParameter(
            name="project_path",
            type="string",
            description="Path to the project",
            required=True,
        ),
        ToolParameter(
            name="package_manager",
            type="string",
            description="Package manager (pip, npm, yarn)",
            required=False,
            default="pip",
        ),
    ]
    dangerous = True

    async def execute(
        self, project_path: str, package_manager: str = "pip", **kwargs
    ) -> ToolResult:
        from pathlib import Path
        from beru.safety import get_safety_manager
        import subprocess

        safety = get_safety_manager()
        validation = safety.validate_path(project_path, must_exist=True)

        if not validation.allowed:
            return ToolResult(success=False, output=None, error=validation.reason)

        try:
            path = Path(validation.sanitized or project_path)

            if package_manager == "pip":
                req_file = path / "requirements.txt"
                if req_file.exists():
                    result = subprocess.run(
                        ["pip", "install", "-r", "requirements.txt"],
                        cwd=str(path),
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    return ToolResult(
                        success=result.returncode == 0,
                        output=result.stdout or "Dependencies installed",
                        error=result.stderr if result.returncode != 0 else None,
                    )
            elif package_manager in ["npm", "yarn"]:
                result = subprocess.run(
                    [package_manager, "install"],
                    cwd=str(path),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return ToolResult(
                    success=result.returncode == 0,
                    output=result.stdout or "Dependencies installed",
                    error=result.stderr if result.returncode != 0 else None,
                )

            return ToolResult(
                success=False,
                output=None,
                error="No dependency file found or unknown package manager",
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


@agent
class ProjectAgent(BaseAgent):
    name = "project_agent"
    description = "Agent specialized in project scaffolding and structure"
    agent_type = "project"
    tools = [CreateProjectTool, CreateFolderTool, InstallDependenciesTool]

    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.llm = get_llm_client()

    async def think(self, input_text: str) -> Dict[str, Any]:
        from beru.utils.helpers import extract_json

        prompt = f"""You are BERU's Project Agent - an expert in project scaffolding and structure.

User request: {input_text}

Available tools (use the EXACT action name):
- action: "create_project" - Create new project (params: {{"project_name": "name", "template": "fastapi|flask|python_package|node_api|react_app", "path": "/path"}})
- action: "create_folder" - Create folder (params: {{"folder_path": "/path/to/folder"}})
- action: "install_dependencies" - Install deps (params: {{"project_path": "/path", "package_manager": "pip|npm|yarn"}})

Available templates: fastapi, flask, python_package, node_api, react_app

Guidelines:
- For general questions: use action "answer"
- For project creation: suggest template based on user needs
- Always confirm before creating
- Use user's home: /home/user171125

IMPORTANT: Use actual paths: /home/user171125/Downloads, /home/user171125/Documents

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
                    else "I'm not sure how to help.",
                }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": f"Error: {e}. Please try again.",
            }
            return parsed
        except Exception as e:
            return {
                "action": "answer",
                "final_answer": f"Error: {e}. Please try again.",
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
