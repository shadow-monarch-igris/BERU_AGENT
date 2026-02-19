from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Set

from aiohttp import web, WSMsgType
import aiohttp

from beru.core.agent import AgentFactory, AgentState
from beru.core.workflow import Workflow, WorkflowBuilder, Task, get_workflow_executor
from beru.utils.config import get_config
from beru.utils.logger import get_logger
from beru.utils.helpers import generate_id

logger = get_logger("beru.api")


class BERUServer:
    def __init__(self):
        self.config = get_config()
        self.app = web.Application()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._websocket_clients: Set[web.WebSocketResponse] = set()

        self._setup_routes()

    def _setup_routes(self) -> None:
        self.app.router.add_get("/", self.index)
        self.app.router.add_get("/api/health", self.health_check)
        self.app.router.add_get("/api/agents", self.list_agents)
        self.app.router.add_post("/api/chat", self.chat)
        self.app.router.add_post("/api/workflows", self.create_workflow)
        self.app.router.add_get(
            "/api/workflows/{workflow_id}", self.get_workflow_status
        )
        self.app.router.add_post(
            "/api/workflows/{workflow_id}/execute", self.execute_workflow
        )
        self.app.router.add_get("/ws", self.websocket_handler)

    async def index(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "name": "BERU 2.0",
                "version": "2.0.0",
                "description": "Production-grade multi-agent AI assistant",
                "endpoints": [
                    "GET /api/health",
                    "GET /api/agents",
                    "POST /api/chat",
                    "POST /api/workflows",
                    "GET /api/workflows/{id}",
                    "POST /api/workflows/{id}/execute",
                    "GET /ws",
                ],
            }
        )

    async def health_check(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "healthy",
                "agents_loaded": len(AgentFactory.list_agents()),
            }
        )

    async def list_agents(self, request: web.Request) -> web.Response:
        agents = AgentFactory.list_agents()
        return web.json_response(
            {
                "agents": [
                    {"name": name, "type": name.replace("_agent", "")}
                    for name in agents
                ],
            }
        )

    async def chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400,
            )

        message = data.get("message", "")
        agent_name = data.get("agent", "orchestrator")
        session_id = data.get("session_id") or generate_id()

        if not message:
            return web.json_response(
                {"error": "Message is required"},
                status=400,
            )

        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "agent": None,
                "history": [],
            }

        try:
            if agent_name not in AgentFactory.list_agents():
                return web.json_response(
                    {"error": f"Unknown agent: {agent_name}"},
                    status=400,
                )

            agent = AgentFactory.create(agent_name)

            self._sessions[session_id]["history"].append(
                {
                    "role": "user",
                    "content": message,
                }
            )

            response = await agent.run(message)

            self._sessions[session_id]["history"].append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )

            return web.json_response(
                {
                    "session_id": session_id,
                    "response": response,
                    "agent": agent_name,
                }
            )

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500,
            )

    async def create_workflow(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400,
            )

        name = data.get("name", "workflow")
        tasks = data.get("tasks", [])
        mode = data.get("mode", "sequential")

        if not tasks:
            return web.json_response(
                {"error": "Tasks are required"},
                status=400,
            )

        workflow = Workflow(name=name)

        from beru.core.workflow import Task

        wf_tasks = []
        for i, task_data in enumerate(tasks):
            t = Task.create(
                name=task_data.get("name", f"task_{i}"),
                input_text=task_data.get("input", ""),
                agent_name=task_data.get("agent", "file_agent"),
            )
            wf_tasks.append(t)

        if mode == "parallel":
            workflow.add_parallel_tasks(wf_tasks)
        else:
            workflow.add_sequential_tasks(wf_tasks)

        workflow_id = workflow.id

        return web.json_response(
            {
                "workflow_id": workflow_id,
                "name": name,
                "tasks": len(tasks),
                "mode": mode,
                "status": "created",
            }
        )

    async def get_workflow_status(
        self,
        request: web.Request,
    ) -> web.Response:
        workflow_id = request.match_info.get("workflow_id")

        return web.json_response(
            {
                "workflow_id": workflow_id,
                "status": "not_implemented",
            }
        )

    async def execute_workflow(
        self,
        request: web.Request,
    ) -> web.Response:
        workflow_id = request.match_info.get("workflow_id")

        return web.json_response(
            {
                "workflow_id": workflow_id,
                "status": "not_implemented",
            }
        )

    async def websocket_handler(
        self,
        request: web.Request,
    ) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._websocket_clients.add(ws)
        logger.info(
            f"WebSocket client connected. Total: {len(self._websocket_clients)}"
        )

        session_id = generate_id()
        agent = None

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        cmd = data.get("cmd", "chat")

                        if cmd == "init":
                            agent_name = data.get("agent", "orchestrator")
                            agent = AgentFactory.create(agent_name)
                            await ws.send_json(
                                {
                                    "type": "init",
                                    "session_id": session_id,
                                    "agent": agent_name,
                                }
                            )

                        elif cmd == "chat":
                            if not agent:
                                agent = AgentFactory.create("orchestrator")

                            message = data.get("message", "")

                            await ws.send_json(
                                {
                                    "type": "thinking",
                                    "message": "Processing...",
                                }
                            )

                            response = await agent.run(message)

                            await ws.send_json(
                                {
                                    "type": "response",
                                    "message": response,
                                }
                            )

                        elif cmd == "parallel":
                            tasks = data.get("tasks", [])

                            if not agent:
                                agent = AgentFactory.create("orchestrator")

                            if hasattr(agent, "run_parallel"):
                                result = await agent.run_parallel(tasks)
                                await ws.send_json(
                                    {
                                        "type": "parallel_result",
                                        "result": result,
                                    }
                                )
                            else:
                                await ws.send_json(
                                    {
                                        "type": "error",
                                        "message": "Agent does not support parallel execution",
                                    }
                                )

                        elif cmd == "ping":
                            await ws.send_json({"type": "pong"})

                    except json.JSONDecodeError:
                        await ws.send_json(
                            {
                                "type": "error",
                                "message": "Invalid JSON",
                            }
                        )

                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")

        finally:
            self._websocket_clients.discard(ws)
            logger.info(
                f"WebSocket client disconnected. Total: {len(self._websocket_clients)}"
            )

        return ws

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self._websocket_clients:
            return

        dead_clients = set()

        for ws in self._websocket_clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead_clients.add(ws)

        self._websocket_clients -= dead_clients

    def run(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        host = host or self.config.api.host
        port = port or self.config.api.port

        logger.info(f"Starting BERU server on {host}:{port}")
        web.run_app(self.app, host=host, port=port)


def create_server() -> BERUServer:
    return BERUServer()
