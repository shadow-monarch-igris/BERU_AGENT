#!/usr/bin/env python3
"""
BERU 2.0 - Production-grade multi-agent AI assistant
"""

from __future__ import annotations

import asyncio
import argparse
import sys
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

    logger.info(f"Loaded agents: {AgentFactory.list_agents()}")


def run_cli() -> None:
    setup()

    print("\n" + "=" * 60)
    print("BERU 2.0 - Multi-Agent AI Assistant")
    print("=" * 60)
    print("Type 'help' for commands, 'exit' to quit\n")

    from beru.core.agent import AgentFactory

    # Default to file_agent for faster responses
    agent = AgentFactory.create("file_agent")

    while True:
        try:
            user_input = input("beru> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            if user_input.lower() == "help":
                print("""
Commands:
  help              Show this help
  exit, quit, q     Exit the assistant
  clear             Clear conversation history
  agent <name>      Switch to a different agent
  agents            List available agents
  tools             List available tools
  status            Show current status

Or just type your message and BERU will help you!
""")
                continue

            if user_input.lower() == "clear":
                agent.reset()
                print("Conversation cleared.\n")
                continue

            if user_input.lower() == "agents":
                agents = AgentFactory.list_agents()
                print(f"Available agents: {', '.join(agents)}\n")
                continue

            if user_input.lower() == "tools":
                tools = agent.get_available_tools()
                print("Available tools:")
                for t in tools:
                    params = [p.name for p in t.parameters if p.required]
                    print(
                        f"  - {t.name}: {', '.join(params) if params else 'no params'}"
                    )
                print()
                continue

            if user_input.lower().startswith("agent "):
                agent_name = user_input[6:].strip()
                if agent_name in AgentFactory.list_agents():
                    agent = AgentFactory.create(agent_name)
                    print(f"Switched to {agent_name}\n")
                else:
                    print(
                        f"Unknown agent. Available: {', '.join(AgentFactory.list_agents())}\n"
                    )
                continue

            if user_input.lower() == "status":
                print(f"Agent: {agent.name}")
                print(f"State: {agent.context.state.value}")
                print(f"Tasks completed: {len(agent.context.tools_used)}\n")
                continue

            print("\nThinking...\n")

            response = asyncio.run(agent.run(user_input))
            print(f"{response}\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'exit' to quit.")
        except EOFError:
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\nError: {e}\n")


def run_server(host: Optional[str] = None, port: Optional[int] = None) -> None:
    setup()

    config = get_config()
    server = create_server()
    server.run(host=host, port=port)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BERU 2.0 - Production-grade multi-agent AI assistant"
    )

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
        help="Server host (default: from config)",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Server port (default: from config)",
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
