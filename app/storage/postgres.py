"""PostgreSQL storage layer for raw and transformed events."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any, Generator

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PGConnection

from app.core.config import Settings, get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.events.models import BaseEvent, EventType

logger = get_logger(__name__)


class PostgresStore:
    """Handles persistence of raw events and denormalized fact tables."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def connect(self) -> PGConnection:
        try:
            return psycopg2.connect(self.settings.database_url)
        except psycopg2.Error as exc:
            raise StorageError(
                "Failed to connect to PostgreSQL",
                details={"error": str(exc)},
            ) from exc

    @contextmanager
    def cursor(self) -> Generator[Any, None, None]:
        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def health_check(self) -> bool:
        try:
            with self.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                row = cur.fetchone()
                return row is not None and row["ok"] == 1
        except StorageError:
            return False

    def store_raw_event(self, event: BaseEvent, cur: Any | None = None) -> None:
        query = """
            INSERT INTO raw_events (event_id, event_type, user_id, event_timestamp, payload)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
        """
        params = (
            str(event.event_id),
            event.event_type.value,
            event.user_id,
            event.event_timestamp,
            json.dumps(event.payload),
        )
        if cur is not None:
            cur.execute(query, params)
            return

        with self.cursor() as managed_cur:
            managed_cur.execute(query, params)

    def store_transformed_event(self, event: BaseEvent, cur: Any | None = None) -> None:
        handlers = {
            EventType.USER_SIGNUP: self._store_signup,
            EventType.PAGE_VIEW: self._store_page_view,
            EventType.PURCHASE: self._store_purchase,
            EventType.SUBSCRIPTION_CANCELLED: self._store_cancellation,
            EventType.REFERRAL_CREATED: self._store_referral,
        }
        handler = handlers[event.event_type]

        if cur is not None:
            handler(event, cur)
            return

        with self.cursor() as managed_cur:
            handler(event, managed_cur)

    def _store_signup(self, event: BaseEvent, cur: Any) -> None:
        cur.execute(
            """
            INSERT INTO user_signups (event_id, user_id, signup_source, country, event_timestamp)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                str(event.event_id),
                event.user_id,
                event.payload.get("signup_source", "organic"),
                event.payload.get("country", "US"),
                event.event_timestamp,
            ),
        )

    def _store_page_view(self, event: BaseEvent, cur: Any) -> None:
        cur.execute(
            """
            INSERT INTO page_views (
                event_id, user_id, page_path, session_id, referrer, event_timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                str(event.event_id),
                event.user_id,
                event.payload["page_path"],
                event.payload["session_id"],
                event.payload.get("referrer"),
                event.event_timestamp,
            ),
        )

    def _store_purchase(self, event: BaseEvent, cur: Any) -> None:
        cur.execute(
            """
            INSERT INTO purchases (event_id, user_id, amount, currency, product_id, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                str(event.event_id),
                event.user_id,
                Decimal(str(event.payload["amount"])),
                event.payload.get("currency", "USD"),
                event.payload["product_id"],
                event.event_timestamp,
            ),
        )

    def _store_cancellation(self, event: BaseEvent, cur: Any) -> None:
        cur.execute(
            """
            INSERT INTO subscription_cancellations
                (event_id, user_id, plan_tier, reason, months_subscribed, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                str(event.event_id),
                event.user_id,
                event.payload["plan_tier"],
                event.payload.get("reason", "unknown"),
                event.payload.get("months_subscribed"),
                event.event_timestamp,
            ),
        )

    def _store_referral(self, event: BaseEvent, cur: Any) -> None:
        cur.execute(
            """
            INSERT INTO referrals
                (event_id, user_id, referrer_id, referred_user_id, campaign, event_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                str(event.event_id),
                event.user_id,
                event.payload["referrer_id"],
                event.payload["referred_user_id"],
                event.payload.get("campaign"),
                event.event_timestamp,
            ),
        )

    def list_recent_events(
        self,
        limit: int = 50,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT event_id, event_type, user_id, event_timestamp, payload, ingested_at
            FROM raw_events
        """
        params: list[Any] = []
        if event_type:
            query += " WHERE event_type = %s"
            params.append(event_type)
        query += " ORDER BY event_timestamp DESC LIMIT %s"
        params.append(limit)

        with self.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [self._serialize_row(row) for row in rows]

    def upsert_kpi_snapshot(
        self,
        metric_date: date,
        metric_name: str,
        metric_value: Decimal | float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kpi_snapshots (metric_date, metric_name, metric_value, metadata)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (metric_date, metric_name)
                DO UPDATE SET
                    metric_value = EXCLUDED.metric_value,
                    metadata = EXCLUDED.metadata,
                    calculated_at = NOW()
                """,
                (
                    metric_date,
                    metric_name,
                    Decimal(str(metric_value)),
                    json.dumps(metadata or {}),
                ),
            )

    def get_kpi_history(self, metric_name: str, days: int = 30) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT metric_date, metric_name, metric_value, metadata, calculated_at
                FROM kpi_snapshots
                WHERE metric_name = %s
                ORDER BY metric_date DESC
                LIMIT %s
                """,
                (metric_name, days),
            )
            rows = cur.fetchall()
        return [self._serialize_row(row) for row in rows]

    def get_latest_kpis(self, days: int = 7) -> dict[str, Any]:
        metrics = ["dau", "revenue", "conversion_rate", "churn_rate", "referral_performance"]
        result: dict[str, Any] = {"metrics": {}, "history": {}}

        for metric in metrics:
            history = self.get_kpi_history(metric, days=days)
            result["history"][metric] = history
            if history:
                result["metrics"][metric] = history[0]

        result["generated_at"] = datetime.utcnow().isoformat() + "Z"
        return result

    def store_anomaly(self, anomaly: dict[str, Any]) -> None:
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO anomalies
                    (metric_name, metric_date, current_value, expected_value,
                     deviation_pct, severity, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    anomaly["metric_name"],
                    anomaly["metric_date"],
                    anomaly.get("current_value"),
                    anomaly.get("expected_value"),
                    anomaly.get("deviation_pct"),
                    anomaly.get("severity", "warning"),
                    anomaly["message"],
                ),
            )

    def list_recent_anomalies(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT metric_name, metric_date, current_value, expected_value,
                       deviation_pct, severity, message, detected_at
                FROM anomalies
                ORDER BY detected_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [self._serialize_row(row) for row in rows]

    @staticmethod
    def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
        serialized: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, date):
                serialized[key] = value.isoformat()
            elif isinstance(value, Decimal):
                serialized[key] = float(value)
            elif key == "metadata" and isinstance(value, str):
                serialized[key] = json.loads(value)
            elif key == "payload" and isinstance(value, str):
                serialized[key] = json.loads(value)
            else:
                serialized[key] = value
        return serialized


@lru_cache
def get_postgres_store() -> PostgresStore:
    return PostgresStore()
