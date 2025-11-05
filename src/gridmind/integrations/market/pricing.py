from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MarketType(StrEnum):
    DAY_AHEAD = "day_ahead"
    REALTIME = "realtime"
    ANCILLARY = "ancillary"
    CAPACITY = "capacity"


class PriceComponent(StrEnum):
    ENERGY = "energy"
    CONGESTION = "congestion"
    LOSS = "loss"
    ANCILLARY = "ancillary"


@dataclass
class MarketPrice:
    timestamp: datetime
    market_type: MarketType
    zone_id: str
    price_per_mwh: Decimal
    components: dict[str, Decimal] = field(default_factory=dict)
    currency: str = "USD"


@dataclass
class BidOffer:
    resource_id: str
    hour: datetime
    quantity_mw: Decimal
    price_per_mwh: Decimal
    bid_type: str = "supply"


@dataclass
class MarketClearingResult:
    cleared_quantity_mw: Decimal
    clearing_price: Decimal
    total_cost: Decimal
    accepted_bids: list[BidOffer]
    rejected_bids: list[BidOffer]


class MarketPricingEngine:
    """Energy market pricing and bid optimization."""

    def __init__(self, default_price: Decimal = Decimal("45.00")) -> None:
        self._default_price = default_price
        self._price_history: list[MarketPrice] = []

    def generate_day_ahead_prices(
        self,
        zone_id: str,
        start: datetime,
        hours: int,
        *,
        base_price: Decimal | None = None,
        peak_multiplier: float = 1.5,
    ) -> list[MarketPrice]:
        base = base_price or self._default_price
        prices: list[MarketPrice] = []
        for h in range(hours):
            ts = start + timedelta(hours=h)
            hour = ts.hour
            if 7 <= hour <= 10 or 17 <= hour <= 21:
                multiplier = Decimal(str(peak_multiplier))
            elif 0 <= hour < 6:
                multiplier = Decimal("0.7")
            else:
                multiplier = Decimal("1.0")
            energy_price = base * multiplier
            congestion = energy_price * Decimal("0.05")
            loss = energy_price * Decimal("0.02")
            prices.append(MarketPrice(
                timestamp=ts,
                market_type=MarketType.DAY_AHEAD,
                zone_id=zone_id,
                price_per_mwh=energy_price + congestion + loss,
                components={
                    PriceComponent.ENERGY.value: energy_price,
                    PriceComponent.CONGESTION.value: congestion,
                    PriceComponent.LOSS.value: loss,
                },
            ))
        self._price_history.extend(prices)
        return prices

    def clear_market(
        self,
        demand_mw: Decimal,
        bids: list[BidOffer],
    ) -> MarketClearingResult:
        sorted_bids = sorted(bids, key=lambda b: b.price_per_mwh)
        accepted: list[BidOffer] = []
        rejected: list[BidOffer] = []
        remaining = demand_mw
        clearing_price = Decimal("0")
        total_cost = Decimal("0")

        for bid in sorted_bids:
            if remaining <= 0:
                rejected.append(bid)
                continue
            cleared = min(remaining, bid.quantity_mw)
            if cleared > 0:
                accepted.append(BidOffer(
                    resource_id=bid.resource_id,
                    hour=bid.hour,
                    quantity_mw=cleared,
                    price_per_mwh=bid.price_per_mwh,
                ))
                clearing_price = bid.price_per_mwh
                total_cost += cleared * bid.price_per_mwh
                remaining -= cleared
            if cleared < bid.quantity_mw:
                rejected.append(bid)

        return MarketClearingResult(
            cleared_quantity_mw=demand_mw - remaining,
            clearing_price=clearing_price,
            total_cost=total_cost,
            accepted_bids=accepted,
            rejected_bids=rejected,
        )

    def compute_spark_spread(
        self,
        power_price: Decimal,
        gas_price_per_mmbtu: Decimal,
        heat_rate_btu_kwh: Decimal = Decimal("7000"),
    ) -> Decimal:
        fuel_cost = gas_price_per_mmbtu * heat_rate_btu_kwh / Decimal("1000")
        return power_price - fuel_cost

    def optimize_bids(
        self,
        resources: list[dict[str, Any]],
        prices: list[MarketPrice],
        *,
        margin_pct: Decimal = Decimal("0.05"),
    ) -> list[BidOffer]:
        bids: list[BidOffer] = []
        for price in prices:
            for resource in resources:
                marginal_cost = Decimal(str(resource.get("marginal_cost", 45)))
                min_price = marginal_cost * (Decimal("1") + margin_pct)
                market_price = price.price_per_mwh
                if market_price >= min_price:
                    bids.append(BidOffer(
                        resource_id=str(resource.get("id", "")),
                        hour=price.timestamp,
                        quantity_mw=Decimal(str(resource.get("capacity_mw", 100))),
                        price_per_mwh=min_price,
                    ))
        return bids

    def analyze_price_volatility(
        self, prices: list[MarketPrice], window_hours: int = 24
    ) -> dict[str, float]:
        if len(prices) < 2:
            return {"volatility": 0, "mean": 0, "range": 0}
        values = [float(p.price_per_mwh) for p in prices[:window_hours]]
        import numpy as np
        arr = np.array(values)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "range": float(np.max(arr) - np.min(arr)),
            "volatility": float(np.std(arr) / np.mean(arr)) if np.mean(arr) else 0,
        }

    def compute_revenue(
        self, cleared_bids: list[BidOffer], prices: dict[datetime, Decimal]
    ) -> Decimal:
        total = Decimal("0")
        for bid in cleared_bids:
            price = prices.get(bid.hour, bid.price_per_mwh)
            total += bid.quantity_mw * price
        return total
