# GridMind

**GridMind** is an enterprise Energy Grid Operations & Forecasting Platform used by utility
companies to manage power generation, demand forecasting, outage planning, battery storage
systems, and grid balancing decisions.

## Quick Start

```bash
cd /home/amicable/Music/Gridmind
docker compose up -d postgres redis
cp .env.example .env
pip install -e ".[dev]"
alembic upgrade head
uvicorn gridmind.main:app --reload
python -m gridmind.workers.runner
pytest
```

GridMind uses **port 5434** (Postgres) and **6380** (Redis) locally to avoid
conflicts with system Postgres on 5432 and other projects.

Or run the full stack in Docker:

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
```

API: http://localhost:8000/docs  
Health: http://localhost:8000/health

## Push to GitHub

Remote is configured for your **private** repository:

```bash
gh auth login
git push -u origin main
```

Repository: `a-micable/Energy_Grid_Operations_and_Forecasting_Platform`

## Platform Capabilities

| Domain | Capabilities |
|--------|-------------|
| Forecasting Engine | Hourly/daily demand, renewable output, revisions, backtesting |
| Grid Balancing | Real-time balancing, reserve capacity, emergency dispatch |
| Battery Storage | SOC tracking, degradation, scheduling, emergency discharge |
| Outage Planning | Planned/emergency outages, conflict detection, dependencies |
| Resource Dispatch | Multi-resource dispatch with cost and emission constraints |
| Event Processing | Sensor events, routing, retries, dead-letter queues |
| Optimization | Multi-stage constraint solving, scenario simulation |
| Audit & Compliance | Decision trails, historical reconstruction, reporting |

## Development

```bash
pytest tests/ -v --cov=gridmind
ruff check src/
mypy src/gridmind
docker build -t gridmind .
```

## License

Proprietary — GridMind Technologies Inc.
