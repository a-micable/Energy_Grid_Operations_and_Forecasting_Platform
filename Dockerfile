FROM python:3.12-slim AS builder
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --prefix=/app/deps -r /app/requirements.txt

COPY pyproject.toml README.md alembic.ini /app/
COPY src/ /app/src/
COPY alembic/ /app/alembic/

FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app/deps/lib/python3.12/site-packages \
    PATH=/app/deps/bin:/usr/local/bin:/usr/bin:/bin

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "gridmind.main:app", "--host", "0.0.0.0", "--port", "8000"]
