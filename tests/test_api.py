"""Tests for FastAPI endpoints with mocked dependencies."""

import pytest
from conftest import FakePostgresStore, FakeRedisCache
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    fake_store = FakePostgresStore(
        {
            "raw_events": [
                {
                    "event_id": "11111111-1111-1111-1111-111111111111",
                    "event_type": "page_view",
                    "user_id": "user_00001",
                    "event_timestamp": "2026-07-05T10:00:00+00:00",
                    "payload": {"page_path": "/"},
                    "ingested_at": "2026-07-05T10:00:01+00:00",
                }
            ],
            "kpi_history_by_metric": {
                "dau": [
                    {
                        "metric_date": "2026-07-05",
                        "metric_name": "dau",
                        "metric_value": 100,
                        "metadata": {},
                        "calculated_at": "2026-07-05T10:00:00+00:00",
                    }
                ]
            },
        }
    )
    fake_cache = FakeRedisCache()
    fake_cache.set_latest_kpis(
        {
            "metrics": {
                "dau": {
                    "metric_date": "2026-07-05",
                    "metric_name": "dau",
                    "metric_value": 100,
                    "metadata": {},
                    "calculated_at": "2026-07-05T10:00:00+00:00",
                }
            },
            "history": {"dau": []},
            "generated_at": "2026-07-05T10:00:00+00:00",
        }
    )

    monkeypatch.setattr("app.storage.postgres.get_postgres_store", lambda: fake_store)
    monkeypatch.setattr("app.storage.redis_cache.get_redis_cache", lambda: fake_cache)
    monkeypatch.setattr("app.api.routes.health.get_postgres_store", lambda: fake_store)
    monkeypatch.setattr("app.api.routes.health.get_redis_cache", lambda: fake_cache)
    monkeypatch.setattr("app.api.routes.events.get_postgres_store", lambda: fake_store)
    monkeypatch.setattr("app.api.routes.kpis.get_redis_cache", lambda: fake_cache)
    monkeypatch.setattr("app.api.routes.kpis.get_postgres_store", lambda: fake_store)

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.api.main import app

    with TestClient(app) as test_client:
        yield test_client


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data


class TestEventsEndpoint:
    def test_list_events(self, client: TestClient):
        response = client.get("/events?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["events"][0]["event_type"] == "page_view"


class TestKpisEndpoint:
    def test_get_kpis_from_cache(self, client: TestClient):
        response = client.get("/kpis")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "redis"
        assert "dau" in data["metrics"]
