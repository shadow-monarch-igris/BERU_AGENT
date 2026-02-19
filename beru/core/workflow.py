from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
import uuid

from beru.core.agent import BaseAgent, AgentState
from beru.utils.config import get_config
from beru.utils.logger import get_logger
from beru.utils.helpers import generate_id

logger = get_logger("beru.workflow")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    id: str
    name: str
    description: str = ""
    agent_name: str = "react_agent"
    input_text: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    dependencies: List[str] = field(default_factory=list)
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        input_text: str,
        agent_name: str = "react_agent",
        **kwargs,
    ) -> Task:
        return cls(
            id=generate_id(),
            name=name,
            input_text=input_text,
            agent_name=agent_name,
            **kwargs,
        )


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowResult:
    workflow_id: str
    status: WorkflowStatus
    task_results: Dict[str, TaskResult] = field(default_factory=dict)
    total_duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_successful_tasks(self) -> List[TaskResult]:
        return [
            r for r in self.task_results.values() if r.status == TaskStatus.COMPLETED
        ]

    def get_failed_tasks(self) -> List[TaskResult]:
        return [r for r in self.task_results.values() if r.status == TaskStatus.FAILED]


class Workflow:
    def __init__(
        self,
        name: str,
        description: str = "",
        workflow_id: Optional[str] = None,
    ):
        self.id = workflow_id or generate_id()
        self.name = name
        self.description = description
        self.tasks: Dict[str, Task] = {}
        self.status = WorkflowStatus.PENDING
        self.result: Optional[WorkflowResult] = None
        self._task_order: List[str] = []

    def add_task(self, task: Task) -> str:
        self.tasks[task.id] = task
        self._task_order.append(task.id)
        return task.id

    def add_parallel_tasks(self, tasks: List[Task]) -> List[str]:
        task_ids = []
        for task in tasks:
            task_id = self.add_task(task)
            task_ids.append(task_id)
        return task_ids

    def add_sequential_tasks(self, tasks: List[Task]) -> List[str]:
        task_ids = []
        prev_task_id = None

        for task in tasks:
            if prev_task_id:
                task.dependencies.append(prev_task_id)
            task_id = self.add_task(task)
            task_ids.append(task_id)
            prev_task_id = task_id

        return task_ids

    def get_ready_tasks(self, completed: set) -> List[Task]:
        ready = []
        for task_id, task in self.tasks.items():
            if task.status != TaskStatus.PENDING:
                continue
            if task_id in completed:
                continue
            if all(dep in completed for dep in task.dependencies):
                ready.append(task)
        return ready

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)


class WorkflowExecutor:
    def __init__(self, max_parallel: int = 5):
        self.config = get_config()
        self.max_parallel = max_parallel or self.config.workflows.max_parallel_tasks
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._agents: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    async def execute_task(
        self,
        task: Task,
        agent: BaseAgent,
    ) -> TaskResult:
        import time

        start_time = time.time()

        try:
            task.status = TaskStatus.RUNNING
            output = await asyncio.wait_for(
                agent.run(task.input_text),
                timeout=task.timeout,
            )

            duration = time.time() - start_time
            task.status = TaskStatus.COMPLETED

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output=output,
                duration=duration,
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            task.status = TaskStatus.FAILED
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=f"Task timed out after {task.timeout}s",
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            task.status = TaskStatus.FAILED
            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration=duration,
            )

    async def execute_workflow(self, workflow: Workflow) -> WorkflowResult:
        import time

        start_time = time.time()

        workflow.status = WorkflowStatus.RUNNING
        result = WorkflowResult(workflow_id=workflow.id, status=WorkflowStatus.RUNNING)

        completed: set = set()
        failed: set = set()

        while True:
            ready_tasks = workflow.get_ready_tasks(completed | failed)

            if not ready_tasks:
                if len(completed) + len(failed) >= len(workflow.tasks):
                    break
                await asyncio.sleep(0.1)
                continue

            running_count = len(self._running_tasks)
            available_slots = self.max_parallel - running_count

            tasks_to_run = ready_tasks[:available_slots]

            for task in tasks_to_run:
                agent = self.get_agent(task.agent_name)
                if not agent:
                    result.task_results[task.id] = TaskResult(
                        task_id=task.id,
                        status=TaskStatus.FAILED,
                        error=f"Agent not found: {task.agent_name}",
                    )
                    failed.add(task.id)
                    continue

                async_task = asyncio.create_task(self.execute_task(task, agent))
                self._running_tasks[task.id] = async_task

            if self._running_tasks:
                done, _ = await asyncio.wait(
                    self._running_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for async_task in done:
                    task_result = async_task.result()
                    task_id = task_result.task_id
                    result.task_results[task_id] = task_result

                    del self._running_tasks[task_id]

                    if task_result.status == TaskStatus.COMPLETED:
                        completed.add(task_id)
                    else:
                        failed.add(task_id)

        total_duration = time.time() - start_time
        result.total_duration = total_duration

        if failed:
            result.status = WorkflowStatus.FAILED
            workflow.status = WorkflowStatus.FAILED
        else:
            result.status = WorkflowStatus.COMPLETED
            workflow.status = WorkflowStatus.COMPLETED

        workflow.result = result
        return result


class WorkflowBuilder:
    def __init__(self, name: str = "workflow"):
        self.workflow = Workflow(name=name)

    def parallel(self, *tasks: Union[Task, Dict[str, Any]]) -> WorkflowBuilder:
        task_objs = []
        for t in tasks:
            if isinstance(t, Task):
                task_objs.append(t)
            else:
                task_objs.append(Task.create(**t))
        self.workflow.add_parallel_tasks(task_objs)
        return self

    def sequential(self, *tasks: Union[Task, Dict[str, Any]]) -> WorkflowBuilder:
        task_objs = []
        for t in tasks:
            if isinstance(t, Task):
                task_objs.append(t)
            else:
                task_objs.append(Task.create(**t))
        self.workflow.add_sequential_tasks(task_objs)
        return self

    def task(self, **kwargs) -> WorkflowBuilder:
        task = Task.create(**kwargs)
        self.workflow.add_task(task)
        return self

    def build(self) -> Workflow:
        return self.workflow


_executor: Optional[WorkflowExecutor] = None


def get_workflow_executor() -> WorkflowExecutor:
    global _executor
    if _executor is None:
        _executor = WorkflowExecutor()
    return _executor
