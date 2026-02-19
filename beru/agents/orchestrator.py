from __future__ import annotations

from typing import Any, Dict, List, Optional

from beru.core.agent import BaseAgent, AgentFactory, agent
from beru.core.llm import get_llm_client
from beru.core.workflow import (
    Workflow,
    WorkflowBuilder,
    WorkflowExecutor,
    get_workflow_executor,
)
from beru.plugins.base import ToolResult
from beru.utils.logger import get_logger
from beru.utils.helpers import extract_json

logger = get_logger("beru.agents.orchestrator")


@agent
class OrchestratorAgent(BaseAgent):
    name = "orchestrator"
    description = "Main orchestrator that coordinates multiple specialized agents"
    agent_type = "orchestrator"
    tools = []

    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(agent_id)
        self.llm = get_llm_client()
        self.workflow_executor = get_workflow_executor()
        self._specialized_agents: Dict[str, BaseAgent] = {}

        self._load_specialized_agents()

    def _load_specialized_agents(self) -> None:
        agent_types = ["file_agent", "terminal_agent", "code_agent"]

        for agent_name in agent_types:
            try:
                if agent_name in AgentFactory.list_agents():
                    agent = AgentFactory.create(agent_name)
                    self._specialized_agents[agent_name] = agent
                    self.workflow_executor.register_agent(agent)
                    logger.info(f"Loaded specialized agent: {agent_name}")
            except Exception as e:
                logger.warning(f"Failed to load agent {agent_name}: {e}")

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._specialized_agents.get(name)

    async def _plan_workflow(self, input_text: str) -> Dict[str, Any]:
        available_agents = list(self._specialized_agents.keys())

        prompt = f"""You are an orchestrator. Analyze the task and create a plan.

Available agents:
{chr(10).join(f"- {a}" for a in available_agents)}

Task: {input_text}

Analyze if this task needs:
1. Parallel execution - multiple independent tasks can run simultaneously
2. Sequential execution - tasks must run in order
3. Single agent - one agent can handle it

Respond in JSON format:
{{
    "analysis": "brief analysis of the task",
    "strategy": "parallel" or "sequential" or "single",
    "tasks": [
        {{
            "agent": "agent_name",
            "input": "specific input for this agent",
            "dependencies": ["task_id"] // for sequential
        }}
    ],
    "explanation": "why this approach"
}}"""

        try:
            response = await self.llm.generate(prompt)
            parsed = extract_json(response.text)

            if not parsed:
                return {
                    "analysis": "Default to single agent",
                    "strategy": "single",
                    "tasks": [{"agent": "file_agent", "input": input_text}],
                }

            return parsed
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return {
                "analysis": f"Error: {e}",
                "strategy": "single",
                "tasks": [{"agent": "file_agent", "input": input_text}],
            }

    async def think(self, input_text: str) -> Dict[str, Any]:
        plan = await self._plan_workflow(input_text)

        self.context.add_message(
            "plan",
            f"Strategy: {plan.get('strategy')}\nTasks: {len(plan.get('tasks', []))}",
        )

        return {
            "thought": plan.get("analysis", ""),
            "action": "execute_workflow",
            "action_input": plan,
        }

    async def act(self, thought: Dict[str, Any]) -> ToolResult:
        plan = thought.get("action_input", {})
        strategy = plan.get("strategy", "single")
        tasks = plan.get("tasks", [])

        if not tasks:
            return ToolResult(
                success=False,
                output=None,
                error="No tasks to execute",
            )

        if strategy == "single":
            task = tasks[0]
            agent_name = task.get("agent", "file_agent")
            agent = self.get_agent(agent_name)

            if not agent:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Agent not found: {agent_name}",
                )

            try:
                result = await agent.run(task.get("input", ""))
                return ToolResult(success=True, output=result)
            except Exception as e:
                return ToolResult(success=False, output=None, error=str(e))

        workflow = Workflow(name="orchestrated_workflow")

        if strategy == "parallel":
            from beru.core.workflow import Task

            workflow_tasks = []
            for i, task in enumerate(tasks):
                t = Task.create(
                    name=f"task_{i}",
                    input_text=task.get("input", ""),
                    agent_name=task.get("agent", "file_agent"),
                )
                workflow_tasks.append(t)

            workflow.add_parallel_tasks(workflow_tasks)

        elif strategy == "sequential":
            from beru.core.workflow import Task

            workflow_tasks = []
            for i, task in enumerate(tasks):
                t = Task.create(
                    name=f"task_{i}",
                    input_text=task.get("input", ""),
                    agent_name=task.get("agent", "file_agent"),
                )
                workflow_tasks.append(t)

            workflow.add_sequential_tasks(workflow_tasks)

        try:
            result = await self.workflow_executor.execute_workflow(workflow)

            outputs = []
            for task_id, task_result in result.task_results.items():
                outputs.append(f"Task {task_id}: {task_result.output}")

            return ToolResult(
                success=result.status.value == "completed",
                output="\n\n".join(outputs),
                metadata={
                    "workflow_result": result.to_dict()  # type: ignore
                    if hasattr(result, "to_dict")
                    else {}
                },
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    async def run_parallel(self, tasks: List[Dict[str, str]]) -> Dict[str, Any]:
        workflow = Workflow(name="parallel_tasks")

        from beru.core.workflow import Task

        wf_tasks = []
        for i, task in enumerate(tasks):
            t = Task.create(
                name=f"parallel_{i}",
                input_text=task.get("input", ""),
                agent_name=task.get("agent", "file_agent"),
            )
            wf_tasks.append(t)

        workflow.add_parallel_tasks(wf_tasks)
        result = await self.workflow_executor.execute_workflow(workflow)

        return {
            "status": result.status.value,
            "results": {
                task_id: r.output for task_id, r in result.task_results.items()
            },
        }

    async def run_sequential(self, tasks: List[Dict[str, str]]) -> Dict[str, Any]:
        workflow = Workflow(name="sequential_tasks")

        from beru.core.workflow import Task

        wf_tasks = []
        for i, task in enumerate(tasks):
            t = Task.create(
                name=f"sequential_{i}",
                input_text=task.get("input", ""),
                agent_name=task.get("agent", "file_agent"),
            )
            wf_tasks.append(t)

        workflow.add_sequential_tasks(wf_tasks)
        result = await self.workflow_executor.execute_workflow(workflow)

        return {
            "status": result.status.value,
            "results": {
                task_id: r.output for task_id, r in result.task_results.items()
            },
        }
