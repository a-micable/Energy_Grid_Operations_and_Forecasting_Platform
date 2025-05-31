from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://gridmind:gridmind@localhost:5434/gridmind"
    )
    redis_url: RedisDsn = Field(default="redis://localhost:6380/0")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    gridmind_env: Literal["development", "staging", "production"] = "development"

    forecast_cache_ttl_seconds: int = 300
    dispatch_optimization_timeout_seconds: int = 120
    event_max_retries: int = 5
    event_dead_letter_ttl_hours: int = 168
    balancing_reserve_margin_pct: float = 0.15
    battery_min_soc_pct: float = 0.10
    battery_max_soc_pct: float = 0.95
    outage_conflict_lookahead_days: int = 90
    audit_retention_days: int = 2555  # ~7 years


@lru_cache
def get_settings() -> Settings:
    return Settings()
