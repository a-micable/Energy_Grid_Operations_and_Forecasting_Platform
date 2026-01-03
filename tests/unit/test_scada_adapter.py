from __future__ import annotations

from decimal import Decimal

import pytest

from gridmind.integrations.scada.adapter import (
    SCADAAdapter,
    SCADAConnectionConfig,
    SCADAPoint,
    SCADAPointType,
)


class TestSCADAAdapter:
    @pytest.fixture
    def adapter(self) -> SCADAAdapter:
        config = SCADAConnectionConfig(host="10.0.0.1", port=4840)
        return SCADAAdapter(config)

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, adapter: SCADAAdapter) -> None:
        assert await adapter.connect()
        assert adapter.is_connected
        await adapter.disconnect()
        assert not adapter.is_connected

    @pytest.mark.asyncio
    async def test_read_resource_output(self, adapter: SCADAAdapter) -> None:
        await adapter.connect()
        adapter.register_point_mapping("GAS-01", {"output_mw": "GAS01_OUTPUT_MW"})
        output = await adapter.read_resource_output("GAS-01")
        assert output is not None
        assert output > 0

    @pytest.mark.asyncio
    async def test_write_setpoint(self, adapter: SCADAAdapter) -> None:
        await adapter.connect()
        adapter.register_point_mapping("GAS-01", {"setpoint_mw": "GAS01_SETPOINT_MW"})
        result = await adapter.write_dispatch_setpoint("GAS-01", Decimal("450"))
        assert result is True

    def test_validate_bad_quality(self, adapter: SCADAAdapter) -> None:
        from datetime import datetime, timezone
        point = SCADAPoint(
            point_id="TEST_MW", point_type=SCADAPointType.ANALOG,
            value=100, quality=0, timestamp=datetime.now(timezone.utc),
        )
        valid, issues = adapter.validate_point_quality(point)
        assert not valid
        assert len(issues) > 0

    @pytest.mark.asyncio
    async def test_subscription_management(self, adapter: SCADAAdapter) -> None:
        from gridmind.integrations.scada.adapter import SCADASubscription
        await adapter.connect()
        adapter.add_subscription("sub1", SCADASubscription(point_ids=["P1", "P2"]))
        results = await adapter.read_all_subscribed()
        assert "sub1" in results
        assert len(results["sub1"]) == 2
