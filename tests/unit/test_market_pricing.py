from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from gridmind.integrations.market.pricing import BidOffer, MarketPricingEngine, MarketType


class TestMarketPricingEngine:
    def setup_method(self) -> None:
        self.engine = MarketPricingEngine(default_price=Decimal("45"))
        self.start = datetime(2025, 7, 15, 0, 0, tzinfo=timezone.utc)

    def test_generate_day_ahead_prices(self) -> None:
        prices = self.engine.generate_day_ahead_prices("ZONE-01", self.start, 24)
        assert len(prices) == 24
        peak_prices = [p for p in prices if 17 <= p.timestamp.hour <= 21]
        off_peak = [p for p in prices if 0 <= p.timestamp.hour < 6]
        assert max(p.price_per_mwh for p in peak_prices) > max(p.price_per_mwh for p in off_peak)

    def test_market_clearing(self) -> None:
        bids = [
            BidOffer("R1", self.start, Decimal("100"), Decimal("30")),
            BidOffer("R2", self.start, Decimal("200"), Decimal("50")),
            BidOffer("R3", self.start, Decimal("150"), Decimal("45")),
        ]
        result = self.engine.clear_market(Decimal("250"), bids)
        assert result.cleared_quantity_mw == Decimal("250")
        assert len(result.accepted_bids) >= 2
        assert result.clearing_price == Decimal("45")

    def test_spark_spread(self) -> None:
        spread = self.engine.compute_spark_spread(
            Decimal("50"), Decimal("3.50")
        )
        assert spread < Decimal("50")

    def test_price_volatility(self) -> None:
        prices = self.engine.generate_day_ahead_prices("ZONE-01", self.start, 24)
        vol = self.engine.analyze_price_volatility(prices)
        assert vol["range"] > 0
        assert vol["volatility"] > 0

    def test_optimize_bids(self) -> None:
        prices = self.engine.generate_day_ahead_prices("ZONE-01", self.start, 24)
        resources = [
            {"id": "R1", "capacity_mw": 100, "marginal_cost": 40},
            {"id": "R2", "capacity_mw": 200, "marginal_cost": 55},
        ]
        bids = self.engine.optimize_bids(resources, prices)
        assert len(bids) > 0
        assert all(b.price_per_mwh >= Decimal("42") for b in bids)
