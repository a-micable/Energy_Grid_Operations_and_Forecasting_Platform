# GridMind API Reference

Base URL: `/api/v1`

## Forecasting

| Method | Path | Description |
|--------|------|-------------|
| POST | /forecasts | Create new forecast run |
| GET | /forecasts/{run_id} | Get forecast run details |
| POST | /forecasts/{run_id}/revise | Submit forecast revision |

## Balancing

| Method | Path | Description |
|--------|------|-------------|
| POST | /balancing/snapshots | Record grid state snapshot |
| GET | /balancing/zones/{zone_id}/latest | Get latest zone snapshot |
| POST | /balancing/execute | Execute balancing actions |

## Outages

| Method | Path | Description |
|--------|------|-------------|
| POST | /outages | Create outage plan |
| POST | /outages/{id}/transition | Change outage status |
| POST | /outages/{id}/dependencies | Add outage dependency |

## Dispatch

| Method | Path | Description |
|--------|------|-------------|
| POST | /dispatch/plans | Create optimized dispatch plan |
| GET | /dispatch/plans/{plan_id} | Get dispatch plan |

## Audit

| Method | Path | Description |
|--------|------|-------------|
| GET | /audit/entities/{type}/{id}/history | Entity audit history |
| GET | /audit/entities/{type}/{id}/reconstruct | Point-in-time reconstruction |
| POST | /audit/compliance-reports | Generate compliance report |
