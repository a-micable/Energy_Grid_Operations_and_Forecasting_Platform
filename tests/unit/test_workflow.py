from __future__ import annotations

import pytest

from gridmind.domains.forecasting.pipeline import ForecastPipeline
from gridmind.services.workflow import WorkflowOrchestrator, WorkflowStep


class TestWorkflowOrchestrator:
    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self) -> None:
        orchestrator = WorkflowOrchestrator()
        results: list = []

        async def step1(params, ctx):
            results.append("step1")
            return {"value": 1}

        async def step2(params, ctx):
            results.append("step2")
            return {"value": ctx["value"] + 1}

        orchestrator.register_handler("step1", step1)
        orchestrator.register_handler("step2", step2)

        instance = orchestrator.create_workflow("test", [
            WorkflowStep(name="s1", handler="step1"),
            WorkflowStep(name="s2", handler="step2"),
        ])
        completed = await orchestrator.execute(instance.workflow_id)
        assert completed.status.value == "completed"
        assert results == ["step1", "step2"]
        assert completed.context["value"] == 2
