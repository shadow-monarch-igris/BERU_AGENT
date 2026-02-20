"""
Skill Loader for BERU
Loads skills from markdown files dynamically
"""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from beru.skills.skill import Skill
from beru.utils.logger import get_logger

logger = get_logger("beru.skills.loader")


class SkillLoader:
    def __init__(self, skills_dir: str = "beru/skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}

    def parse_markdown_skill(self, content: str, filename: str = "") -> Skill:
        lines = content.split("\n")

        name = ""
        description = ""
        instructions = ""
        tools: List[str] = []
        triggers: List[str] = []
        examples: List[Dict[str, str]] = []

        current_section = ""
        section_content = []

        for line in lines:
            if line.startswith("# "):
                name = line[2:].strip()
            elif line.startswith("## "):
                if current_section and section_content:
                    result = self._process_section(current_section, section_content)
                    if result:
                        section_name, section_value = result
                        if section_name == "description":
                            description = section_value
                        elif section_name == "instructions":
                            instructions = section_value
                        elif section_name == "tools":
                            tools = section_value
                        elif section_name == "triggers":
                            triggers = section_value
                        elif section_name == "examples":
                            examples = section_value
                current_section = line[3:].strip().lower()
                section_content = []
            else:
                section_content.append(line)

        if current_section and section_content:
            result = self._process_section(current_section, section_content)
            if result:
                section_name, section_value = result
                if section_name == "description":
                    description = section_value
                elif section_name == "instructions":
                    instructions = section_value
                elif section_name == "tools":
                    tools = section_value
                elif section_name == "triggers":
                    triggers = section_value
                elif section_name == "examples":
                    examples = section_value

        if not name:
            name = filename.replace(".md", "").replace("_", " ").title()

        return Skill(
            name=name,
            description=description,
            instructions=instructions,
            tools=tools,
            triggers=triggers,
            examples=examples,
        )

    def _process_section(self, section: str, content: List[str]) -> Optional[tuple]:
        content_text = "\n".join(content).strip()

        if section in ["description", "about"]:
            return ("description", content_text)
        elif section in ["instructions", "how to use", "guidelines"]:
            return ("instructions", content_text)
        elif section in ["tools", "required tools"]:
            tools = []
            for line in content:
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    tool_name = line[2:].strip()
                    if tool_name:
                        tools.append(tool_name)
            return ("tools", tools)
        elif section in ["triggers", "trigger words", "keywords"]:
            triggers = []
            for line in content:
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    trigger = line[2:].strip().lower()
                    if trigger:
                        triggers.append(trigger)
            return ("triggers", triggers)
        elif section in ["examples", "example"]:
            examples = []
            current_input = ""
            current_output = ""
            for line in content:
                line = line.strip()
                if line.lower().startswith("input:"):
                    if current_input and current_output:
                        examples.append(
                            {"input": current_input, "output": current_output.strip()}
                        )
                    current_input = line[6:].strip()
                    current_output = ""
                elif line.lower().startswith("output:"):
                    current_output = line[7:].strip()
                elif current_input and not current_output:
                    current_output += line + "\n"

            if current_input and current_output:
                examples.append(
                    {"input": current_input, "output": current_output.strip()}
                )
            return ("examples", examples)

        return None

    def load_skill(self, path: Path) -> Optional[Skill]:
        try:
            with open(path, "r") as f:
                content = f.read()

            skill = self.parse_markdown_skill(content, path.name)
            skill.metadata["source_file"] = str(path)
            return skill
        except Exception as e:
            logger.error(f"Failed to load skill from {path}: {e}")
            return None

    def load_all(self) -> Dict[str, Skill]:
        search_dirs = [
            self.skills_dir / "templates",
            self.skills_dir / "custom",
        ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for skill_file in search_dir.glob("**/*.md"):
                skill = self.load_skill(skill_file)
                if skill and skill.name:
                    self.skills[skill.name.lower().replace(" ", "_")] = skill
                    logger.info(f"Loaded skill: {skill.name}")

        return self.skills

    def get_skill(self, name: str) -> Optional[Skill]:
        return self.skills.get(name.lower().replace(" ", "_"))

    def match_skill(self, text: str) -> Optional[Skill]:
        text_lower = text.lower()

        for skill in self.skills.values():
            if skill.matches_trigger(text_lower):
                return skill

        return None

    def list_skills(self) -> List[str]:
        return list(self.skills.keys())

    def create_skill_file(
        self,
        name: str,
        description: str,
        instructions: str = "",
        tools: List[str] = None,
        triggers: List[str] = None,
    ) -> Path:
        custom_dir = self.skills_dir / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)

        filename = name.lower().replace(" ", "_").replace("-", "_") + ".md"
        filepath = custom_dir / filename

        content = f"""# {name}

## Description
{description}

## Instructions
{instructions or "Use this skill to help the user with " + name.lower() + " tasks."}

## Tools
"""
        for tool in tools or []:
            content += f"- {tool}\n"

        content += "\n## Triggers\n"
        for trigger in triggers or [name.lower()]:
            content += f"- {trigger}\n"

        content += "\n## Examples\n\n"
        content += f"Input: Help me with {name.lower()}\n"
        content += f"Output: I'll help you with {name.lower()}!\n"

        with open(filepath, "w") as f:
            f.write(content)

        logger.info(f"Created skill file: {filepath}")
        return filepath


_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
        _skill_loader.load_all()
    return _skill_loader


def load_skills() -> Dict[str, Skill]:
    return get_skill_loader().skills
