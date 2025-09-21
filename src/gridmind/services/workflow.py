from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import structlog

from gridmind.core.exceptions import WorkflowCorruptionError

logger = structlog.get_logger(__name__)


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"


@dataclass
class WorkflowStep:
    name: str
    handler: str
    params: dict[str, Any] = field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    compensation_handler: str | None = None


@dataclass
class WorkflowInstance:
    workflow_id: UUID
    workflow_type: str
    steps: list[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: UUID = field(default_factory=uuid4)


class WorkflowOrchestrator:
    """Multi-step workflow execution with compensation support."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}
        self._compensation_handlers: dict[str, Any] = {}
        self._instances: dict[UUID, WorkflowInstance] = {}

    def register_handler(self, name: str, handler: Any) -> None:
        self._handlers[name] = handler

    def register_compensation(self, name: str, handler: Any) -> None:
        self._compensation_handlers[name] = handler

    def create_workflow(
        self, workflow_type: str, steps: list[WorkflowStep], context: dict | None = None
    ) -> WorkflowInstance:
        instance = WorkflowInstance(
            workflow_id=uuid4(),
            workflow_type=workflow_type,
            steps=steps,
            context=context or {},
        )
        self._instances[instance.workflow_id] = instance
        return instance

    async def execute(self, workflow_id: UUID) -> WorkflowInstance:
        instance = self._instances.get(workflow_id)
        if not instance:
            raise WorkflowCorruptionError(f"Workflow {workflow_id} not found")
        instance.status = WorkflowStatus.RUNNING
        completed_steps: list[WorkflowStep] = []

        for step in instance.steps:
            step.status = WorkflowStatus.RUNNING
            step.started_at = datetime.now(timezone.utc)
            handler = self._handlers.get(step.handler)
            if not handler:
                step.status = WorkflowStatus.FAILED
                step.error = f"Handler {step.handler} not registered"
                instance.status = WorkflowStatus.FAILED
                await self._compensate(completed_steps, instance)
                raise WorkflowCorruptionError(step.error)

            try:
                result = await handler(step.params, instance.context)
                step.result = result if isinstance(result, dict) else {"value": result}
                step.status = WorkflowStatus.COMPLETED
                step.completed_at = datetime.now(timezone.utc)
                instance.context.update(step.result)
                completed_steps.append(step)
                logger.info("workflow_step_completed", workflow=str(workflow_id), step=step.name)
            except Exception as exc:
                step.status = WorkflowStatus.FAILED
                step.error = str(exc)
                instance.status = WorkflowStatus.FAILED
                logger.error("workflow_step_failed", workflow=str(workflow_id), step=step.name, error=str(exc))
                await self._compensate(completed_steps, instance)
                raise

        instance.status = WorkflowStatus.COMPLETED
        return instance

    async def _compensate(self, completed_steps: list[WorkflowStep], instance: WorkflowInstance) -> None:
        instance.status = WorkflowStatus.COMPENSATING
        for step in reversed(completed_steps):
            if not step.compensation_handler:
                continue
            handler = self._compensation_handlers.get(step.compensation_handler)
            if handler:
                try:
                    await handler(step.result or {}, instance.context)
                    logger.info("workflow_step_compensated", step=step.name)
                except Exception as exc:
                    logger.error("workflow_compensation_failed", step=step.name, error=str(exc))

    def get_instance(self, workflow_id: UUID) -> WorkflowInstance | None:
        return self._instances.get(workflow_id)
