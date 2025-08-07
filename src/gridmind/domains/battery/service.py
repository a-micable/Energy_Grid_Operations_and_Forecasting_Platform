from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.exceptions import NotFoundError, StateTransitionError
from gridmind.core.types import BatteryState
from gridmind.db.models.battery import BatteryAsset, BatteryCycle, BatterySchedule
from gridmind.db.repositories.battery import (
    BatteryAssetRepository,
    BatteryCycleRepository,
    BatteryScheduleRepository,
)
from gridmind.domains.battery.engine import BatteryOptimizationEngine, BatteryProfile
from gridmind.services.audit import AuditService


class BatteryService:
    VALID_TRANSITIONS = {
        BatteryState.IDLE: {BatteryState.CHARGING, BatteryState.DISCHARGING, BatteryState.MAINTENANCE},
        BatteryState.CHARGING: {BatteryState.IDLE},
        BatteryState.DISCHARGING: {BatteryState.IDLE, BatteryState.EMERGENCY_DISCHARGE},
        BatteryState.EMERGENCY_DISCHARGE: {BatteryState.IDLE},
        BatteryState.MAINTENANCE: {BatteryState.IDLE},
    }

    def __init__(
        self,
        session: AsyncSession,
        engine: BatteryOptimizationEngine | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._session = session
        self._engine = engine or BatteryOptimizationEngine()
        self._asset_repo = BatteryAssetRepository(session)
        self._cycle_repo = BatteryCycleRepository(session)
        self._schedule_repo = BatteryScheduleRepository(session)
        self._audit = audit

    def _to_profile(self, asset: BatteryAsset) -> BatteryProfile:
        return BatteryProfile(
            nameplate_capacity_mwh=asset.name_capacity_mwh,
            usable_capacity_mwh=asset.usable_capacity_mwh,
            max_charge_mw=asset.max_charge_mw,
            max_discharge_mw=asset.max_discharge_mw,
            state_of_charge_pct=asset.state_of_charge_pct,
            degradation_pct=asset.degradation_pct,
            round_trip_efficiency=asset.round_trip_efficiency,
            cycle_count=asset.cycle_count,
        )

    async def transition_state(
        self, battery_id: UUID, new_state: BatteryState, *, actor: str
    ) -> BatteryAsset:
        asset = await self._asset_repo.get_by_id_or_raise(battery_id)
        current = BatteryState(asset.state)
        allowed = self.VALID_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise StateTransitionError("battery", battery_id, current.value, new_state.value)
        old_state = asset.state
        asset.state = new_state.value
        await self._session.flush()
        if self._audit:
            await self._audit.record(
                "battery", battery_id, "state_change", actor,
                before_state={"state": old_state},
                after_state={"state": new_state.value},
            )
        return asset

    async def schedule_dispatch(
        self,
        battery_id: UUID,
        action: str,
        power_mw: Decimal,
        duration_minutes: int,
        scheduled_at: datetime,
        *,
        is_emergency: bool = False,
    ) -> BatterySchedule:
        asset = await self._asset_repo.get_by_id_or_raise(battery_id)
        overlapping = await self._schedule_repo.find_overlapping(
            battery_id, scheduled_at, scheduled_at
        )
        if overlapping and not is_emergency:
            from gridmind.core.exceptions import SchedulingConflictError
            raise SchedulingConflictError(
                f"Battery {battery_id} has conflicting schedule at {scheduled_at}"
            )
        schedule = BatterySchedule(
            battery_id=battery_id,
            scheduled_at=scheduled_at,
            action=action,
            target_power_mw=power_mw,
            duration_minutes=duration_minutes,
            is_emergency=is_emergency,
        )
        await self._schedule_repo.add(schedule)
        return schedule

    async def record_cycle(
        self, battery_id: UUID, energy_charged: Decimal, energy_discharged: Decimal
    ) -> BatteryCycle:
        asset = await self._asset_repo.get_by_id_or_raise(battery_id)
        latest = await self._cycle_repo.get_latest_cycle(battery_id)
        cycle_num = (latest.cycle_number + 1) if latest else 1
        dod = energy_discharged / asset.usable_capacity_mwh if asset.usable_capacity_mwh else Decimal("0")
        degradation = self._engine.compute_degradation(dod)
        cycle = BatteryCycle(
            battery_id=battery_id,
            cycle_number=cycle_num,
            started_at=datetime.now(timezone.utc),
            energy_charged_mwh=energy_charged,
            energy_discharged_mwh=energy_discharged,
            depth_of_discharge_pct=dod,
            degradation_delta_pct=degradation,
        )
        await self._cycle_repo.add(cycle)
        asset.cycle_count = cycle_num
        asset.degradation_pct += degradation
        await self._session.flush()
        return cycle
