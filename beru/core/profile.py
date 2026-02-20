"""
User Profile Manager for BERU
Stores and retrieves user information for personalized assistance
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class UserProfile:
    name: str = ""
    role: str = ""
    experience_level: str = ""
    projects: List[str] = field(default_factory=list)
    preferred_editor: str = ""
    preferred_language: str = ""
    frameworks: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    created_at: str = ""
    last_active: str = ""
    interaction_count: int = 0

    def to_markdown(self) -> str:
        return f"""# User Profile

## Personal Information
- **Name**: {self.name}
- **Role**: {self.role}
- **Experience Level**: {self.experience_level}

## Projects & Work
- **Current Projects**: {", ".join(self.projects) if self.projects else "None specified"}
- **Preferred Programming Language**: {self.preferred_language}
- **Frameworks Used**: {", ".join(self.frameworks) if self.frameworks else "None specified"}

## Preferences
- **Code Editor**: {self.preferred_editor}
- **Interests**: {", ".join(self.interests) if self.interests else "None specified"}
- **Goals**: {", ".join(self.goals) if self.goals else "None specified"}

## Statistics
- **Profile Created**: {self.created_at}
- **Last Active**: {self.last_active}
- **Total Interactions**: {self.interaction_count}
"""


class ProfileManager:
    def __init__(self, data_dir: str = "beru/data"):
        self.data_dir = Path(data_dir)
        self.profile_file = self.data_dir / "user.md"
        self.profile_json = self.data_dir / "user_profile.json"
        self.profile: Optional[UserProfile] = None

        self.data_dir.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self.profile_json.exists()

    def load(self) -> Optional[UserProfile]:
        if self.profile_json.exists():
            try:
                with open(self.profile_json, "r") as f:
                    data = json.load(f)
                    self.profile = UserProfile(**data)
                    return self.profile
            except Exception:
                pass
        return None

    def save(self, profile: UserProfile) -> None:
        profile.last_active = datetime.now().isoformat()

        with open(self.profile_json, "w") as f:
            json.dump(asdict(profile), f, indent=2)

        with open(self.profile_file, "w") as f:
            f.write(profile.to_markdown())

        self.profile = profile

    def update_interaction(self) -> None:
        if self.profile:
            self.profile.interaction_count += 1
            self.profile.last_active = datetime.now().isoformat()
            self.save(self.profile)

    def create_new(self) -> UserProfile:
        now = datetime.now().isoformat()
        return UserProfile(created_at=now, last_active=now)


def get_profile_manager() -> ProfileManager:
    return ProfileManager()
