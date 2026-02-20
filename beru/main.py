#!/usr/bin/env python3
"""
BERU 2.0 - Dream AI Assistant
Your personal AI assistant with comprehensive capabilities
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

from beru.utils.config import get_config, reload_config
from beru.utils.logger import init_logging, get_logger
from beru.core.agent import AgentFactory
from beru.plugins import load_plugins
from beru.api.server import create_server

logger = get_logger("beru")


def setup() -> None:
    init_logging()
    load_plugins()

    from beru.agents import FileAgent, TerminalAgent, OrchestratorAgent
    from beru.agents.code_agent import CodeAgent
    from beru.agents.project_agent import ProjectAgent
    from beru.agents.web_agent import WebAgent

    logger.info(f"Loaded agents: {AgentFactory.list_agents()}")


def print_banner():
    print("\n" + "=" * 60)
    print("  BERU - AI Assistant")
    print("=" * 60)


def print_help():
    print("""
Commands:
  help              Show this help
  exit, quit, q     Exit the assistant
  clear             Clear conversation history
  
Agents:
  agent <name>      Switch to a different agent
  agents            List available agents
  
Skills:
  skills            List available skills
  add skill <name>  Add a new skill
  
Profile:
  profile           View your profile
  edit profile      Edit your profile
  
System:
  status            Show current status
  rescan            Rescan system for changes
  system info       View system information

Or just type your message and BERU will help you!
""")


async def run_onboarding():
    from beru.core.onboarding import run_onboarding_if_needed
    from beru.services.system_scanner import SystemScanner

    profile = await run_onboarding_if_needed()

    if profile:
        scanner = SystemScanner()

        if scanner.needs_rescan():
            print("\n  Scanning your system...")
            scan_data = scanner.run_and_save()

            apps_found = sum(
                len(apps) for apps in scan_data.get("installed_apps", {}).values()
            )
            langs_found = len(scan_data.get("languages", {}))
            projects_found = len(scan_data.get("recent_projects", []))

            print(
                f"  Found: {apps_found} apps, {langs_found} languages, {projects_found} projects"
            )

        return profile

    return None


def run_cli() -> None:
    setup()
    print_banner()

    profile = asyncio.run(run_onboarding())

    if profile:
        print(f"\n  Welcome, {profile.name}! I'm ready to help.")

    print("\n  Type 'help' for commands, 'exit' to quit\n")

    from beru.core.agent import AgentFactory

    agent = AgentFactory.create("file_agent")

    while True:
        try:
            user_input = input("beru> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\n  Goodbye! See you next time!\n")
                break

            if user_input.lower() == "help":
                print_help()
                continue

            if user_input.lower() == "clear":
                agent.reset()
                print("  Conversation cleared.\n")
                continue

            if user_input.lower() == "agents":
                agents = AgentFactory.list_agents()
                print(f"\n  Available agents:\n")
                for a in agents:
                    print(f"    - {a}")
                print()
                continue

            if user_input.lower() == "skills":
                from beru.skills import get_skill_loader

                loader = get_skill_loader()
                skills = loader.list_skills()
                print(f"\n  Available skills:\n")
                for s in skills:
                    skill = loader.get_skill(s)
                    if skill:
                        desc = (
                            skill.description
                            if skill.description
                            else f"Help with {skill.name.lower()} tasks"
                        )
                        triggers = (
                            ", ".join(skill.triggers[:3])
                            if skill.triggers
                            else "ask about " + skill.name.lower()
                        )
                        print(f"    - {skill.name}")
                        print(f"      {desc}")
                        print(f"      Triggers: {triggers}\n")
                print()
                continue

            if user_input.lower() in ["view profile", "profile"]:
                if profile:
                    print(f"\n  Your Profile:\n")
                    print(f"    Name: {profile.name}")
                    print(f"    Role: {profile.role}")
                    print(f"    Experience: {profile.experience_level}")
                    print(f"    Language: {profile.preferred_language}")
                    print(f"    Editor: {profile.preferred_editor}")
                    print(
                        f"    Projects: {', '.join(profile.projects) if profile.projects else 'None'}"
                    )
                    print(
                        f"    Frameworks: {', '.join(profile.frameworks) if profile.frameworks else 'None'}"
                    )
                    print(
                        f"    Interests: {', '.join(profile.interests) if profile.interests else 'None'}"
                    )
                    print(
                        f"    Goals: {', '.join(profile.goals) if profile.goals else 'None'}\n"
                    )
                else:
                    print("\n  No profile found. Run onboarding first.\n")
                continue

            if user_input.lower() == "edit profile":
                if not profile:
                    print("\n  No profile found. Run onboarding first.\n")
                    continue

                print("\n  Edit Profile (leave blank to keep current value):\n")

                # Edit name
                new_name = input(f"  Name [{profile.name}]: ").strip()
                if new_name:
                    profile.name = new_name

                # Edit role
                new_role = input(f"  Role [{profile.role}]: ").strip()
                if new_role:
                    profile.role = new_role

                # Edit language
                new_lang = input(
                    f"  Preferred Language [{profile.preferred_language}]: "
                ).strip()
                if new_lang:
                    profile.preferred_language = new_lang

                # Edit editor
                new_editor = input(f"  Editor [{profile.preferred_editor}]: ").strip()
                if new_editor:
                    profile.preferred_editor = new_editor

                # Edit projects
                current_projects = (
                    ", ".join(profile.projects) if profile.projects else ""
                )
                new_projects = input(f"  Projects [{current_projects}]: ").strip()
                if new_projects:
                    profile.projects = [p.strip() for p in new_projects.split(",")]

                # Edit interests
                current_interests = (
                    ", ".join(profile.interests) if profile.interests else ""
                )
                new_interests = input(f"  Interests [{current_interests}]: ").strip()
                if new_interests:
                    profile.interests = [i.strip() for i in new_interests.split(",")]

                # Save profile
                from beru.core.profile import ProfileManager

                ProfileManager().save(profile)
                print("\n  Profile updated successfully!\n")
                continue

            if user_input.lower().startswith("add skill"):
                skill_name = user_input[9:].strip()
                if not skill_name:
                    print("\n  Usage: add skill <skill_name>")
                    print("  Example: add skill email_sender\n")
                    continue

                print(f"\n  Describe what the '{skill_name}' skill should do:")
                description = input("  Description: ").strip()

                if description:
                    from beru.skills import get_skill_loader

                    loader = get_skill_loader()
                    filepath = loader.create_skill_file(skill_name, description)
                    loader.load_skill(filepath)
                    print(f"\n  Skill '{skill_name}' created successfully!")
                    print(f"  You can now use it by mentioning: {skill_name}\n")
                continue

            if user_input.lower() == "status":
                print(f"\n  Agent: {agent.name}")
                print(f"  State: {agent.context.state.value}")
                print(f"  Tasks completed: {len(agent.context.tools_used)}")
                if profile:
                    print(f"  User: {profile.name}")
                    print(f"  Interactions: {profile.interaction_count}")
                print()
                continue

            if user_input.lower() == "rescan":
                from beru.services.system_scanner import SystemScanner

                print("\n  Rescanning system...")
                scanner = SystemScanner()
                scan_data = scanner.run_and_save()
                print(
                    f"  Scan complete. Found {len(scan_data.get('recent_projects', []))} projects.\n"
                )
                continue

            if user_input.lower() == "system info":
                from beru.services.system_scanner import SystemScanner
                import json

                scanner = SystemScanner()
                data = scanner.load()

                if data:
                    print("\n  System Information:\n")
                    sys_info = data.get("system", {})
                    print(f"    OS: {sys_info.get('os', 'Unknown')}")
                    print(f"    Distro: {sys_info.get('distro', 'Unknown')}")
                    print(f"    Username: {sys_info.get('username', 'Unknown')}")
                    print(f"    Home: {sys_info.get('home_dir', 'Unknown')}")

                    print("\n  Installed Languages:")
                    for lang, info in data.get("languages", {}).items():
                        print(f"    - {lang}: v{info.get('version', 'unknown')}")

                    print("\n  Installed Apps:")
                    apps = data.get("installed_apps", {})
                    for category, app_list in apps.items():
                        if app_list:
                            names = [a.get("name") for a in app_list]
                            print(f"    {category}: {', '.join(names[:5])}")

                    print("\n  Recent Projects:")
                    for proj in data.get("recent_projects", [])[:5]:
                        print(
                            f"    - {proj.get('name', 'Unknown')} ({proj.get('type', 'unknown')})"
                        )
                    print()
                else:
                    print("\n  No system data found. Run 'rescan' first.\n")
                continue

            if user_input.lower().startswith("agent "):
                agent_name = user_input[6:].strip()
                if agent_name in AgentFactory.list_agents():
                    agent = AgentFactory.create(agent_name)
                    print(f"\n  Switched to {agent_name}\n")
                else:
                    print(
                        f"\n  Unknown agent. Available: {', '.join(AgentFactory.list_agents())}\n"
                    )
                continue

            print("\n  Thinking...\n")

            response = asyncio.run(agent.run(user_input))
            print(f"  {response}\n")

            if profile:
                from beru.core.profile import ProfileManager

                ProfileManager().update_interaction()

        except KeyboardInterrupt:
            print("\n\n  Interrupted. Type 'exit' to quit.")
        except EOFError:
            print("\n\n  Goodbye!\n")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\n  Error: {e}\n")


def run_server(host: Optional[str] = None, port: Optional[int] = None) -> None:
    setup()

    config = get_config()
    server = create_server()
    server.run(host=host, port=port)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="BERU 2.0 - Your Dream AI Assistant")

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )

    parser.add_argument(
        "--server",
        "-s",
        action="store_true",
        help="Run as API server",
    )

    parser.add_argument(
        "--host",
        type=str,
        help="Server host",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Server port",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="BERU 2.0.0",
    )

    args = parser.parse_args()

    reload_config(args.config)

    if args.server:
        run_server(host=args.host, port=args.port)
    else:
        run_cli()


if __name__ == "__main__":
    main()
