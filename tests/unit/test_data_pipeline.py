from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gridmind.pipeline.etl import (
    AggregateHourlyStage,
    DataPipeline,
    ExtractSCADAStage,
    LoadForecastInputStage,
    TransformNormalizeStage,
    ValidateQualityStage,
    create_scada_to_forecast_pipeline,
)


class TestDataPipeline:
    @pytest.fixture
    def sample_scada_input(self) -> dict:
        ts = datetime(2025, 7, 15, 10, 30, tzinfo=timezone.utc).isoformat()
        return {
            "scada_points": [
                {"id": "P1", "value": 1500, "timestamp": ts, "quality": 192, "unit": "MW"},
                {"id": "P2", "value": 800, "timestamp": ts, "quality": 192, "unit": "KW"},
                {"id": "P3", "value": -100, "timestamp": ts, "quality": 192, "unit": "MW"},
            ]
        }

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_scada_input: dict) -> None:
        pipeline = create_scada_to_forecast_pipeline()
        result, context = await pipeline.run(sample_scada_input)
        summary = pipeline.get_summary()
        assert summary["stages_completed"] >= 4
        assert "mean_demand_mw" in result

    @pytest.mark.asyncio
    async def test_extract_stage(self, sample_scada_input: dict) -> None:
        stage = ExtractSCADAStage()
        from gridmind.pipeline.etl import PipelineContext
        ctx = PipelineContext(pipeline_id="test")
        result = await stage.process(sample_scada_input, ctx)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_normalize_kw_to_mw(self) -> None:
        stage = TransformNormalizeStage()
        from gridmind.pipeline.etl import PipelineContext
        ctx = PipelineContext(pipeline_id="test")
        result = await stage.process([{"value": 500, "unit": "KW", "quality": 192}], ctx)
        assert result[0]["value_mw"] == 0.5

    @pytest.mark.asyncio
    async def test_validate_rejects_negative(self) -> None:
        stage = ValidateQualityStage()
        from gridmind.pipeline.etl import PipelineContext
        ctx = PipelineContext(pipeline_id="test")
        ts = datetime.now(timezone.utc).isoformat()
        result = await stage.process([
            {"point_id": "P1", "value_mw": -50, "quality": 192, "timestamp": ts}
        ], ctx)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_aggregate_hourly(self) -> None:
        stage = AggregateHourlyStage()
        from gridmind.pipeline.etl import PipelineContext
        ctx = PipelineContext(pipeline_id="test")
        ts1 = datetime(2025, 7, 15, 10, 0, tzinfo=timezone.utc).isoformat()
        ts2 = datetime(2025, 7, 15, 10, 30, tzinfo=timezone.utc).isoformat()
        result = await stage.process([
            {"timestamp": ts1, "value_mw": 100},
            {"timestamp": ts2, "value_mw": 200},
        ], ctx)
        assert len(result) == 1
        assert list(result.values())[0] == 150.0
