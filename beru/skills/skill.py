"""
Skill Definition for BERU
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Skill:
    name: str
    description: str = ""
    instructions: str = ""
    tools: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    category: str = "general"
    version: str = "1.0.0"
    author: str = "BERU"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_system_prompt(self) -> str:
        prompt = f"""You have the skill: {self.name}

{self.description}

## Instructions
{self.instructions}
"""

        if self.tools:
            prompt += f"\n## Required Tools\nUse these tools: {', '.join(self.tools)}\n"

        if self.examples:
            prompt += "\n## Examples\n"
            for ex in self.examples[:3]:
                prompt += f"\nInput: {ex.get('input', '')}\n"
                prompt += f"Output: {ex.get('output', '')}\n"

        return prompt

    def matches_trigger(self, text: str) -> bool:
        text_lower = text.lower()
        for trigger in self.triggers:
            if trigger.lower() in text_lower:
                return True
        return False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Skill:
        return cls(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            instructions=data.get("instructions", ""),
            tools=data.get("tools", []),
            examples=data.get("examples", []),
            triggers=data.get("triggers", []),
            category=data.get("category", "general"),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "BERU"),
            metadata=data.get("metadata", {}),
        )
