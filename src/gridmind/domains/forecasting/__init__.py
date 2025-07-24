from gridmind.domains.forecasting.engine import BacktestResult, ForecastEngine, ForecastPointData

__all__ = [
    "BacktestResult",
    "ForecastEngine",
    "ForecastPointData",
]


def __getattr__(name: str):
    if name == "ForecastingService":
        from gridmind.domains.forecasting.service import ForecastingService
        return ForecastingService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
