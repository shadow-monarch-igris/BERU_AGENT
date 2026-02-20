"""
Onboarding Flow for BERU
Interactive first-time setup experience
"""

from __future__ import annotations

import asyncio
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from beru.core.profile import ProfileManager, UserProfile
from beru.core.llm import get_llm_client
from beru.utils.logger import get_logger

logger = get_logger("beru.onboarding")


class OnboardingFlow:
    def __init__(self):
        self.profile_manager = ProfileManager()
        self.llm = get_llm_client()
        self.profile = UserProfile()

        self.questions = [
            {
                "key": "name",
                "question": "What's your name?",
                "followup": lambda answer: f"Nice to meet you, {answer}! I'm BERU, your personal AI assistant.",
            },
            {
                "key": "role",
                "question": "What do you do? (e.g., developer, student, data scientist, designer)",
                "followup": lambda answer: f"Great! As a {answer}, I can help you with many tasks.",
            },
            {
                "key": "experience_level",
                "question": "What's your experience level? (beginner, intermediate, advanced)",
                "followup": lambda answer: f"Got it! I'll tailor my responses to your level.",
            },
            {
                "key": "preferred_language",
                "question": "What's your preferred programming language?",
                "followup": lambda answer: f"Excellent choice! {answer} is a powerful language.",
            },
            {
                "key": "projects",
                "question": "What projects are you currently working on? (comma-separated, or 'none')",
                "process": lambda answer: [p.strip() for p in answer.split(",")]
                if answer.lower() not in ["none", "n/a", ""]
                else [],
                "followup": lambda answer: f"Interesting projects! I'd love to help with those."
                if answer
                else "No worries, we can work on new projects together!",
            },
            {
                "key": "preferred_editor",
                "question": "What's your preferred code editor? (e.g., VS Code, PyCharm, Vim)",
                "followup": lambda answer: f"Perfect! I can open files in {answer} for you.",
            },
            {
                "key": "frameworks",
                "question": "What frameworks do you use? (comma-separated, or 'none')",
                "process": lambda answer: [f.strip() for f in answer.split(",")]
                if answer.lower() not in ["none", "n/a", ""]
                else [],
                "followup": lambda answer: f"Great frameworks! I can help you build with these."
                if answer
                else "We can explore frameworks together!",
            },
            {
                "key": "interests",
                "question": "What are your interests? (e.g., AI, web dev, mobile apps, data science)",
                "process": lambda answer: [i.strip() for i in answer.split(",")]
                if answer
                else [],
                "followup": lambda answer: f"Exciting interests! I can help you explore these areas.",
            },
            {
                "key": "goals",
                "question": "What goals would you like to achieve with my help?",
                "process": lambda answer: [g.strip() for g in answer.split(",")]
                if answer
                else [],
                "followup": lambda answer: f"Great goals! I'll do my best to help you achieve them.",
            },
        ]

    def get_input(self, prompt: str) -> str:
        try:
            return input(prompt + "\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    async def run(self) -> UserProfile:
        print("\n" + "=" * 60)
        print("  WELCOME TO BERU - Your Personal AI Assistant!")
        print("=" * 60)
        print("\n  This seems to be our first meeting!")
        print("  I'd love to get to know you better so I can")
        print("  assist you more effectively.\n")
        print("  Let me ask you a few quick questions...\n")

        for i, q in enumerate(self.questions, 1):
            print(f"[{i}/{len(self.questions)}] {q['question']}")
            answer = self.get_input("")

            if "process" in q:
                answer = q["process"](answer)

            setattr(self.profile, q["key"], answer)

            followup = q["followup"](
                answer
                if isinstance(answer, str)
                else ", ".join(answer)
                if answer
                else "none"
            )
            print(f"\n{followup}\n")

            await asyncio.sleep(0.2)

        print("\n" + "=" * 60)
        print("  PROFILE SUMMARY")
        print("=" * 60 + "\n")
        print(f"  Name: {self.profile.name}")
        print(f"  Role: {self.profile.role}")
        print(f"  Experience: {self.profile.experience_level}")
        print(f"  Language: {self.profile.preferred_language}")
        print(
            f"  Projects: {', '.join(self.profile.projects) if self.profile.projects else 'None'}"
        )
        print(f"  Editor: {self.profile.preferred_editor}")
        print(
            f"  Frameworks: {', '.join(self.profile.frameworks) if self.profile.frameworks else 'None'}"
        )
        print(
            f"  Interests: {', '.join(self.profile.interests) if self.profile.interests else 'None'}"
        )
        print(
            f"  Goals: {', '.join(self.profile.goals) if self.profile.goals else 'None'}"
        )

        print("\n" + "-" * 60)
        confirm = self.get_input("\nDoes this look correct? (yes/no)")

        if confirm.lower() in ["yes", "y", ""]:
            self.profile_manager.save(self.profile)
            print("\n  Profile saved successfully!")
            return self.profile
        else:
            print("\n  Let's try again...\n")
            return await self.run()

    async def run_quick(self) -> UserProfile:
        print("\n" + "=" * 60)
        print("  QUICK SETUP")
        print("=" * 60)
        print("\n  Let's set up your profile quickly!\n")

        print("What's your name?")
        name = self.get_input("")
        self.profile.name = name

        print(f"\nNice to meet you, {name}! What do you do?")
        role = self.get_input("")
        self.profile.role = role

        print(f"\nWhat's your preferred code editor? (VS Code, PyCharm, etc.)")
        editor = self.get_input("")
        self.profile.preferred_editor = editor

        self.profile_manager.save(self.profile)
        print(f"\n  All set, {name}! Let me scan your system...\n")

        return self.profile


def check_first_time() -> bool:
    return not ProfileManager().exists()


async def run_onboarding_if_needed() -> Optional[UserProfile]:
    manager = ProfileManager()

    if manager.exists():
        profile = manager.load()
        if profile:
            profile.interaction_count += 1
            manager.save(profile)
        return profile

    onboarding = OnboardingFlow()
    profile = await onboarding.run()
    return profile
