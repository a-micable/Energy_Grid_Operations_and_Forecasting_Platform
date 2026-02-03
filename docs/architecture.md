# GridMind Architecture

## Overview

GridMind is a domain-driven energy grid operations platform built on an event-driven
architecture with clear separation between API, service, repository, and domain layers.

## Layer Responsibilities

### API Layer (`gridmind.api`)
- FastAPI routers with Pydantic request/response schemas
- HTTP error mapping from domain exceptions
- Dependency injection for database sessions

### Service Layer (`gridmind.domains.*.service`)
- Orchestrates business workflows across repositories
- Publishes domain events
- Records audit trails
- Enforces state machine transitions

### Domain Layer (`gridmind.domains.*.engine`)
- Pure business logic without infrastructure dependencies
- Forecasting algorithms, optimization solvers, state machines
- Conflict detection, dependency graph analysis

### Repository Layer (`gridmind.db.repositories`)
- Data access abstraction over SQLAlchemy models
- Query optimization for operational workloads
- No business logic

### Infrastructure
- **PostgreSQL**: Primary data store for all operational data
- **Redis**: Event bus, caching, worker coordination
- **Workers**: Background processing for forecasts, events, balancing

## Event Flow

```
Sensor/SCADA → Event Ingestion → Event Queue → Event Processor → Domain Handlers
                                                      ↓
                                              Audit Trail Recording
```

## Cross-Cutting Concerns

### Forecast Drift Detection
When forecast revisions exceed 15% delta from previous version, the system flags
drift and requires explicit override via the `force` parameter.

### Event Ordering
Events carry sequence numbers per aggregate. Out-of-order events are rejected
and routed to the dead-letter queue for manual investigation.

### Cache Invalidation
Forecast and dispatch caches use version tracking. Stale reads trigger
`CacheInvalidationError` when version mismatches are detected.

### Historical Reconstruction
Audit entries store before/after states enabling point-in-time entity reconstruction
for compliance investigations.
