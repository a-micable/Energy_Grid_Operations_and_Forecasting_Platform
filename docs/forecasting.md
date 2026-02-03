# Forecasting Engine

## Supported Forecast Types

| Type | Horizon | Description |
|------|---------|-------------|
| demand | hourly, daily | Grid load forecasting |
| solar | hourly | Solar irradiance-based generation |
| wind | hourly | Wind speed-based generation |
| renewable | hourly | Combined renewable output |

## Revision Workflow

1. Operator submits revised forecast points
2. Engine computes delta against current version
3. If delta > 15%, `ForecastDriftError` is raised
4. Operator may force revision with audit trail
5. New version supersedes current; old version retained

## Backtesting

Compare forecast points against actuals to compute MAE, RMSE, MAPE, and bias metrics.
Used for model validation and continuous improvement.

## Versioning

Each forecast run maintains a version chain:
- Version 1: Initial forecast
- Version N: Nth revision with linked previous version
- Only one version marked `is_current` at a time
