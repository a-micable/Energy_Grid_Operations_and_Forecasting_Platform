from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gridmind.core.exceptions import ConflictError, NotFoundError, ValidationError
from gridmind.db.models.grid import GenerationResource, GridZone
from gridmind.db.repositories.grid import GenerationResourceRepository, GridZoneRepository
from gridmind.services.audit import AuditService


class GridZoneService:
    """Manage grid zones and generation resources."""

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._session = session
        self._zone_repo = GridZoneRepository(session)
        self._resource_repo = GenerationResourceRepository(session)
        self._audit = audit

    async def create_zone(
        self,
        code: str,
        name: str,
        region: str,
        peak_demand_mw: Decimal,
        *,
        timezone: str = "UTC",
        actor: str = "system",
    ) -> GridZone:
        existing = await self._zone_repo.get_by_code(code)
        if existing:
            raise ConflictError(f"Zone code {code} already exists")
        zone = GridZone(
            code=code,
            name=name,
            region=region,
            peak_demand_mw=peak_demand_mw,
            timezone=timezone,
        )
        await self._zone_repo.add(zone)
        if self._audit:
            await self._audit.record("grid_zone", zone.id, "created", actor, after_state={"code": code})
        return zone

    async def register_resource(
        self,
        zone_id: UUID,
        code: str,
        name: str,
        resource_type: str,
        capacity_mw: Decimal,
        marginal_cost_per_mwh: Decimal,
        *,
        min_output_mw: Decimal = Decimal("0"),
        emission_rate: Decimal = Decimal("0"),
        dispatch_priority: int = 100,
        is_renewable: bool = False,
        actor: str = "system",
    ) -> GenerationResource:
        zone = await self._zone_repo.get_by_id(zone_id)
        if not zone:
            raise NotFoundError(f"Zone {zone_id} not found")
        if capacity_mw <= 0:
            raise ValidationError("Capacity must be positive")
        if min_output_mw > capacity_mw:
            raise ValidationError("Min output cannot exceed capacity")
        existing = await self._resource_repo.get_by_code(code)
        if existing:
            raise ConflictError(f"Resource code {code} already exists")
        resource = GenerationResource(
            zone_id=zone_id,
            code=code,
            name=name,
            resource_type=resource_type,
            capacity_mw=capacity_mw,
            min_output_mw=min_output_mw,
            marginal_cost_per_mwh=marginal_cost_per_mwh,
            emission_rate_kg_co2_per_mwh=emission_rate,
            dispatch_priority=dispatch_priority,
            is_renewable=is_renewable,
        )
        await self._resource_repo.add(resource)
        if self._audit:
            await self._audit.record(
                "generation_resource", resource.id, "registered", actor,
                after_state={"code": code, "capacity_mw": str(capacity_mw)},
            )
        return resource

    async def get_zone_capacity_summary(self, zone_id: UUID) -> dict:
        zone = await self._zone_repo.get_by_id_or_raise(zone_id)
        resources = await self._resource_repo.list_by_zone(zone_id)
        total_capacity = sum(r.capacity_mw for r in resources)
        renewable_capacity = sum(r.capacity_mw for r in resources if r.is_renewable)
        available = [r for r in resources if r.is_available]
        return {
            "zone_code": zone.code,
            "total_capacity_mw": float(total_capacity),
            "renewable_capacity_mw": float(renewable_capacity),
            "renewable_pct": float(renewable_capacity / total_capacity) if total_capacity else 0,
            "available_resources": len(available),
            "total_resources": len(resources),
            "peak_demand_mw": float(zone.peak_demand_mw),
            "capacity_margin_pct": float((total_capacity - zone.peak_demand_mw) / zone.peak_demand_mw)
            if zone.peak_demand_mw else 0,
        }

    async def set_resource_availability(
        self, resource_id: UUID, is_available: bool, *, reason: str, actor: str
    ) -> GenerationResource:
        resource = await self._resource_repo.get_by_id_or_raise(resource_id)
        old = resource.is_available
        resource.is_available = is_available
        await self._session.flush()
        if self._audit:
            await self._audit.record(
                "generation_resource", resource_id,
                "availability_changed", actor,
                before_state={"is_available": old},
                after_state={"is_available": is_available},
                reason=reason,
            )
        return resource
