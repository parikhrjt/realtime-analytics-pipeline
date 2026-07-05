"""Pytest fixtures and shared test utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest


@pytest.fixture
def sample_signup_event() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": "user_signup",
        "user_id": "user_00001",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {"signup_source": "organic", "country": "US"},
    }


@pytest.fixture
def sample_page_view_event() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": "page_view",
        "user_id": "user_00002",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "page_path": "/pricing",
            "session_id": "sess_abc123",
            "referrer": "google",
        },
    }


@pytest.fixture
def sample_purchase_event() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": "purchase",
        "user_id": "user_00003",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "amount": 49.99,
            "currency": "USD",
            "product_id": "plan_pro_monthly",
        },
    }


@pytest.fixture
def sample_cancellation_event() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": "subscription_cancelled",
        "user_id": "user_00004",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "plan_tier": "pro",
            "reason": "too_expensive",
            "months_subscribed": 6,
        },
    }


@pytest.fixture
def sample_referral_event() -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "event_type": "referral_created",
        "user_id": "user_00005",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "referrer_id": "user_00001",
            "referred_user_id": "user_00099",
            "campaign": "spring_promo",
        },
    }


class FakeCursor:
    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.executed: list[tuple[str, tuple | None]] = []
        self._last_query = ""

    def execute(self, query: str, params: tuple | None = None) -> None:
        self._last_query = " ".join(query.split()).lower()
        self.executed.append((query, params))

    def fetchone(self) -> dict[str, Any] | None:
        if "count(distinct user_id) as dau" in self._last_query:
            return {"dau": self.responses.get("dau", 0)}
        if "coalesce(sum(amount), 0) as revenue" in self._last_query:
            return {
                "revenue": self.responses.get("revenue", Decimal("0")),
                "purchase_count": self.responses.get("purchase_count", 0),
            }
        if "count(distinct user_id) as viewers" in self._last_query:
            return {"viewers": self.responses.get("viewers", 0)}
        if "count(distinct user_id) as buyers" in self._last_query:
            return {"buyers": self.responses.get("buyers", 0)}
        if "count(*) as cancellations" in self._last_query:
            return {"cancellations": self.responses.get("cancellations", 0)}
        if "count(distinct user_id) as active_base" in self._last_query:
            return {"active_base": self.responses.get("active_base", 0)}
        if "count(*) as referrals" in self._last_query:
            return {"referrals": self.responses.get("referrals", 0)}
        if "count(*) as signups" in self._last_query and "user_signups" in self._last_query:
            return {"signups": self.responses.get("signups", 0)}
        if self._last_query.startswith("select 1"):
            return {"ok": 1}
        return None

    def fetchall(self) -> list[dict[str, Any]]:
        if "from kpi_snapshots" in self._last_query:
            return self.responses.get("kpi_history", [])
        if "from raw_events" in self._last_query:
            return self.responses.get("raw_events", [])
        if "from anomalies" in self._last_query:
            return self.responses.get("anomalies", [])
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePostgresStore:
    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.snapshots: list[dict[str, Any]] = []
        self.anomalies: list[dict[str, Any]] = []
        self.raw_events: list[dict[str, Any]] = []

    def cursor(self):
        from contextlib import contextmanager

        @contextmanager
        def _cursor():
            yield FakeCursor(self.responses)

        return _cursor()

    def health_check(self) -> bool:
        return True

    def store_raw_event(self, event, cur=None) -> None:
        self.raw_events.append({"event_id": str(event.event_id)})

    def store_transformed_event(self, event, cur=None) -> None:
        return None

    def upsert_kpi_snapshot(self, metric_date, metric_name, metric_value, metadata=None) -> None:
        self.snapshots.append(
            {
                "metric_date": metric_date,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metadata": metadata or {},
            }
        )

    def get_kpi_history(self, metric_name: str, days: int = 30) -> list[dict[str, Any]]:
        return self.responses.get("kpi_history_by_metric", {}).get(metric_name, [])

    def get_latest_kpis(self, days: int = 7) -> dict[str, Any]:
        return {
            "metrics": {},
            "history": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def store_anomaly(self, anomaly: dict[str, Any]) -> None:
        self.anomalies.append(anomaly)

    def list_recent_events(
        self,
        limit: int = 50,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        events = self.responses.get("raw_events", self.raw_events)
        if event_type:
            events = [event for event in events if event.get("event_type") == event_type]
        return events[:limit]


class FakeRedisCache:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    def health_check(self) -> bool:
        return True

    def set_latest_kpis(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def get_latest_kpis(self) -> dict[str, Any] | None:
        return self.payload

    def invalidate(self) -> None:
        self.payload = None
