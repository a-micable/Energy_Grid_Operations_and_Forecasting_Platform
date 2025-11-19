from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Generic, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")
U = TypeVar("U")


class PipelineStageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineContext:
    pipeline_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StageResult(Generic[T]):
    stage_name: str
    status: PipelineStageStatus
    output: T | None = None
    records_processed: int = 0
    records_failed: int = 0
    duration_ms: float = 0.0
    error: str | None = None


class PipelineStage(ABC, Generic[T, U]):
    name: str = "base_stage"

    @abstractmethod
    async def process(self, input_data: T, context: PipelineContext) -> U:
        ...

    async def validate_input(self, input_data: T) -> list[str]:
        return []

    async def on_error(self, error: Exception, context: PipelineContext) -> None:
        context.errors.append(f"{self.name}: {error}")


class ExtractSCADAStage(PipelineStage[dict, list[dict]]):
    name = "extract_scada"

    async def process(self, input_data: dict, context: PipelineContext) -> list[dict]:
        points = input_data.get("scada_points", [])
        extracted: list[dict] = []
        for point in points:
            extracted.append({
                "point_id": point.get("id"),
                "value": point.get("value"),
                "timestamp": point.get("timestamp"),
                "quality": point.get("quality", 0),
                "unit": point.get("unit", ""),
            })
        context.metadata["extracted_count"] = len(extracted)
        return extracted

    async def validate_input(self, input_data: dict) -> list[str]:
        issues: list[str] = []
        if "scada_points" not in input_data:
            issues.append("Missing scada_points in input")
        return issues


class TransformNormalizeStage(PipelineStage[list[dict], list[dict]]):
    name = "transform_normalize"

    UNIT_CONVERSIONS = {"KW": 0.001, "GW": 1000.0}

    async def process(self, input_data: list[dict], context: PipelineContext) -> list[dict]:
        normalized: list[dict] = []
        for record in input_data:
            value = float(record.get("value", 0))
            unit = record.get("unit", "MW").upper()
            if unit in self.UNIT_CONVERSIONS:
                value *= self.UNIT_CONVERSIONS[unit]
                unit = "MW"
            quality = record.get("quality", 0)
            if quality < 64:
                context.warnings.append(f"Low quality point: {record.get('point_id')}")
            normalized.append({
                **record,
                "value_mw": round(value, 4),
                "unit": unit,
                "normalized_at": datetime.now(timezone.utc).isoformat(),
            })
        return normalized


class ValidateQualityStage(PipelineStage[list[dict], list[dict]]):
    name = "validate_quality"

    def __init__(self, min_quality: int = 64, max_age_seconds: int = 300) -> None:
        self._min_quality = min_quality
        self._max_age = max_age_seconds

    async def process(self, input_data: list[dict], context: PipelineContext) -> list[dict]:
        valid: list[dict] = []
        now = datetime.now(timezone.utc)
        for record in input_data:
            if record.get("quality", 0) < self._min_quality:
                context.warnings.append(f"Rejected low quality: {record.get('point_id')}")
                continue
            ts_str = record.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    age = (now - ts).total_seconds()
                    if age > self._max_age:
                        context.warnings.append(f"Stale data: {record.get('point_id')}")
                        continue
                except ValueError:
                    context.warnings.append(f"Invalid timestamp: {record.get('point_id')}")
                    continue
            if record.get("value_mw", 0) < 0:
                context.warnings.append(f"Negative value: {record.get('point_id')}")
                continue
            valid.append(record)
        context.metadata["valid_count"] = len(valid)
        context.metadata["rejected_count"] = len(input_data) - len(valid)
        return valid


class AggregateHourlyStage(PipelineStage[list[dict], dict[str, float]]):
    name = "aggregate_hourly"

    async def process(self, input_data: list[dict], context: PipelineContext) -> dict[str, float]:
        hourly: dict[str, list[float]] = {}
        for record in input_data:
            ts_str = record.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                hour_key = ts.strftime("%Y-%m-%dT%H:00:00")
                hourly.setdefault(hour_key, []).append(record.get("value_mw", 0))
            except ValueError:
                continue
        aggregated = {k: sum(v) / len(v) for k, v in hourly.items() if v}
        context.metadata["hourly_buckets"] = len(aggregated)
        return aggregated


class LoadForecastInputStage(PipelineStage[dict[str, float], dict]):
    name = "load_forecast_input"

    async def process(self, input_data: dict[str, float], context: PipelineContext) -> dict:
        sorted_hours = sorted(input_data.keys())
        values = [input_data[h] for h in sorted_hours]
        return {
            "hourly_values": values,
            "hour_count": len(values),
            "mean_demand_mw": sum(values) / len(values) if values else 0,
            "peak_demand_mw": max(values) if values else 0,
            "min_demand_mw": min(values) if values else 0,
            "timestamps": sorted_hours,
        }


class DataPipeline:
    """Composable ETL pipeline for grid operational data."""

    def __init__(self, pipeline_id: str) -> None:
        self._pipeline_id = pipeline_id
        self._stages: list[PipelineStage] = []
        self._results: list[StageResult] = []

    def add_stage(self, stage: PipelineStage) -> DataPipeline:
        self._stages.append(stage)
        return self

    async def run(self, input_data: Any) -> tuple[Any, PipelineContext]:
        import time
        context = PipelineContext(pipeline_id=self._pipeline_id)
        current = input_data
        self._results.clear()

        for stage in self._stages:
            validation_issues = await stage.validate_input(current)
            if validation_issues:
                for issue in validation_issues:
                    context.errors.append(issue)
                self._results.append(StageResult(
                    stage_name=stage.name,
                    status=PipelineStageStatus.FAILED,
                    error="Validation failed",
                ))
                break

            start = time.perf_counter()
            try:
                current = await stage.process(current, context)
                duration = (time.perf_counter() - start) * 1000
                count = len(current) if isinstance(current, (list, dict)) else 1
                self._results.append(StageResult(
                    stage_name=stage.name,
                    status=PipelineStageStatus.COMPLETED,
                    output=current,
                    records_processed=count,
                    duration_ms=duration,
                ))
                logger.info("pipeline_stage_completed", stage=stage.name, duration_ms=round(duration, 2))
            except Exception as exc:
                duration = (time.perf_counter() - start) * 1000
                await stage.on_error(exc, context)
                self._results.append(StageResult(
                    stage_name=stage.name,
                    status=PipelineStageStatus.FAILED,
                    duration_ms=duration,
                    error=str(exc),
                ))
                logger.error("pipeline_stage_failed", stage=stage.name, error=str(exc))
                break

        return current, context

    @property
    def stage_results(self) -> list[StageResult]:
        return list(self._results)

    def get_summary(self) -> dict[str, Any]:
        completed = sum(1 for r in self._results if r.status == PipelineStageStatus.COMPLETED)
        failed = sum(1 for r in self._results if r.status == PipelineStageStatus.FAILED)
        total_duration = sum(r.duration_ms for r in self._results)
        total_processed = sum(r.records_processed for r in self._results)
        return {
            "pipeline_id": self._pipeline_id,
            "stages_total": len(self._stages),
            "stages_completed": completed,
            "stages_failed": failed,
            "total_duration_ms": total_duration,
            "total_records_processed": total_processed,
        }


def create_scada_to_forecast_pipeline() -> DataPipeline:
    return (
        DataPipeline("scada_to_forecast")
        .add_stage(ExtractSCADAStage())
        .add_stage(TransformNormalizeStage())
        .add_stage(ValidateQualityStage())
        .add_stage(AggregateHourlyStage())
        .add_stage(LoadForecastInputStage())
    )
