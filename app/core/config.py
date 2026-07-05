"""Centralized application configuration via environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Realtime Analytics Pipeline"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    # Streamlit
    streamlit_port: int = 8501

    # Redpanda / Kafka
    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_topic: str = "product-events"
    kafka_consumer_group: str = "analytics-consumer"
    kafka_auto_offset_reset: str = "earliest"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_user: str = "analytics"
    postgres_password: str = "analytics"
    postgres_db: str = "analytics_pipeline"
    database_url: str = "postgresql://analytics:analytics@localhost:5433/analytics_pipeline"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_kpi_key: str = "analytics:latest_kpis"
    redis_kpi_ttl_seconds: int = 300

    # Producer
    producer_interval_seconds: float = 1.0
    producer_batch_size: int = 1

    # Anomaly detection
    anomaly_lookback_days: int = 7
    anomaly_drop_threshold_pct: float = 30.0
    anomaly_enabled: bool = True

    # Alerts
    slack_webhook_url: str = ""
    alert_console_enabled: bool = True

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        return v.upper()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
