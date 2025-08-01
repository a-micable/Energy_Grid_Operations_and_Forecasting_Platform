from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.events import DomainEvent
from gridmind.core.types import BalancingMode
from gridmind.db.models.balancing import BalancingAction, BalancingSnapshot
from gridmind.db.repositories.balancing import (
    BalancingActionRepository,
    BalancingSnapshotRepository,
    ReserveCapacityRepository,
)
from gridmind.domains.balancing.engine import BalancingEngine
from gridmind.services.audit import AuditService

logger = structlog.get_logger(__name__)


class BalancingService:
    def __init__(
        self,
        session: AsyncSession,
        engine: BalancingEngine | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._session = session
        self._engine = engine or BalancingEngine()
        self._snapshot_repo = BalancingSnapshotRepository(session)
        self._action_repo = BalancingActionRepository(session)
        self._reserve_repo = ReserveCapacityRepository(session)
        self._audit = audit

    async def record_snapshot(
        self,
        zone_id: UUID,
        supply_mw: Decimal,
        demand_mw: Decimal,
        reserve_mw: Decimal,
        *,
        mode: BalancingMode = BalancingMode.REALTIME,
        frequency_hz: Decimal | None = None,
    ) -> BalancingSnapshot:
        state = self._engine.compute_state(supply_mw, demand_mw, reserve_mw, frequency_hz)
        snapshot = BalancingSnapshot(
            zone_id=zone_id,
            snapshot_at=datetime.now(timezone.utc),
            supply_mw=state.supply_mw,
            demand_mw=state.demand_mw,
            net_imbalance_mw=state.net_imbalance_mw,
            frequency_hz=state.frequency_hz,
            mode=mode.value,
            reserve_available_mw=state.reserve_available_mw,
        )
        await self._snapshot_repo.add(snapshot)
        return snapshot

    async def execute_balancing(
        self,
        zone_id: UUID,
        available_resources: list[dict],
        *,
        mode: BalancingMode = BalancingMode.REALTIME,
        actor: str = "system",
    ) -> list[BalancingAction]:
        latest = await self._snapshot_repo.get_latest(zone_id)
        if not latest:
            raise ValueError(f"No balancing snapshot for zone {zone_id}")

        state = self._engine.compute_state(
            latest.supply_mw, latest.demand_mw, latest.reserve_available_mw, latest.frequency_hz
        )
        plans = self._engine.plan_balancing_actions(state, available_resources, mode)
        actions: list[BalancingAction] = []
        for plan in plans:
            action = BalancingAction(
                zone_id=zone_id,
                snapshot_id=latest.id,
                resource_id=plan.resource_id,
                action_type=plan.action_type,
                mode=plan.mode.value,
                target_mw=plan.target_mw,
                status="pending",
                priority=plan.priority,
                initiated_at=datetime.now(timezone.utc),
                initiated_by=actor,
                reason=plan.reason,
            )
            await self._action_repo.add(action)
            actions.append(action)

        if self._audit and actions:
            await self._audit.record(
                "balancing",
                zone_id,
                "balancing_initiated",
                actor,
                after_state={"action_count": len(actions), "mode": mode.value},
            )
        return actions
