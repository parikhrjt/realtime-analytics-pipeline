"""Redis cache for latest KPI snapshots."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import redis

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisKpiCache:
    """Caches computed KPI payloads for fast dashboard/API reads."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                password=self.settings.redis_password or None,
                decode_responses=True,
            )
        return self._client

    def health_check(self) -> bool:
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False

    def set_latest_kpis(self, payload: dict[str, Any]) -> None:
        self.client.setex(
            self.settings.redis_kpi_key,
            self.settings.redis_kpi_ttl_seconds,
            json.dumps(payload),
        )
        logger.info("kpi_cache_updated", key=self.settings.redis_kpi_key)

    def get_latest_kpis(self) -> dict[str, Any] | None:
        raw = self.client.get(self.settings.redis_kpi_key)
        if not raw:
            return None
        return json.loads(raw)

    def invalidate(self) -> None:
        self.client.delete(self.settings.redis_kpi_key)


@lru_cache
def get_redis_cache() -> RedisKpiCache:
    return RedisKpiCache()
