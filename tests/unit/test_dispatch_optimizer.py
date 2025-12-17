from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from gridmind.core.exceptions import OptimizationError
from gridmind.domains.dispatch.optimizer import DispatchOptimizer, ResourceOffer


class TestDispatchOptimizer:
    def setup_method(self) -> None:
        self.optimizer = DispatchOptimizer()
        self.start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        self.end = datetime(2025, 6, 1, 1, 0, tzinfo=timezone.utc)

    def _make_resources(self) -> list[ResourceOffer]:
        return [
            ResourceOffer(
                resource_id=uuid4(),
                resource_type="solar_farm",
                min_output_mw=Decimal("0"),
                max_output_mw=Decimal("200"),
                marginal_cost=Decimal("0"),
                emission_rate=Decimal("0"),
                dispatch_priority=10,
                ramp_rate_mw_per_min=Decimal("5"),
            ),
            ResourceOffer(
                resource_id=uuid4(),
                resource_type="gas_plant",
                min_output_mw=Decimal("50"),
                max_output_mw=Decimal("500"),
                marginal_cost=Decimal("45"),
                emission_rate=Decimal("400"),
                dispatch_priority=50,
                ramp_rate_mw_per_min=Decimal("10"),
            ),
        ]

    def test_optimize_meets_demand(self) -> None:
        result = self.optimizer.optimize(
            Decimal("300"), self._make_resources(), self.start, self.end
        )
        assert result.total_output_mw >= Decimal("300")
        assert result.solver_status in ("optimal", "partial", "priority_fallback")

    def test_cheaper_resources_dispatched_first(self) -> None:
        result = self.optimizer.optimize(
            Decimal("150"), self._make_resources(), self.start, self.end
        )
        solar_allocs = [a for a in result.allocations if a.cost == Decimal("0")]
        assert len(solar_allocs) > 0

    def test_empty_resources_raises(self) -> None:
        with pytest.raises(OptimizationError):
            self.optimizer.optimize(Decimal("100"), [], self.start, self.end)

    def test_emission_constraint_limits_dispatch(self) -> None:
        constrained = DispatchOptimizer(max_emissions_kg=Decimal("10000"))
        result = constrained.optimize(
            Decimal("400"), self._make_resources(), self.start, self.end
        )
        assert result.total_emissions_kg <= Decimal("10000") or result.unmet_demand_mw > 0
