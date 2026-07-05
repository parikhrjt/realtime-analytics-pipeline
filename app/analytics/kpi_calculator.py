"""KPI calculation engine over PostgreSQL fact tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.storage.postgres import PostgresStore

logger = get_logger(__name__)

KPI_METRICS = ("dau", "revenue", "conversion_rate", "churn_rate", "referral_performance")


@dataclass(frozen=True)
class DailyKpiResult:
    metric_date: date
    metric_name: str
    metric_value: Decimal
    metadata: dict[str, Any]

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "metric_date": self.metric_date,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "metadata": self.metadata,
        }


class KpiCalculator:
    """Computes daily KPIs from denormalized event tables."""

    def __init__(
        self,
        store: PostgresStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store or PostgresStore(settings)
        self.settings = settings or get_settings()

    def calculate_dau(self, metric_date: date) -> DailyKpiResult:
        start, end = self._day_bounds(metric_date)
        with self.store.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT user_id) AS dau
                FROM page_views
                WHERE event_timestamp >= %s AND event_timestamp < %s
                """,
                (start, end),
            )
            row = cur.fetchone()
        dau = int(row["dau"] or 0)
        return DailyKpiResult(
            metric_date=metric_date,
            metric_name="dau",
            metric_value=Decimal(dau),
            metadata={"distinct_users": dau},
        )

    def calculate_revenue(self, metric_date: date) -> DailyKpiResult:
        start, end = self._day_bounds(metric_date)
        with self.store.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS revenue, COUNT(*) AS purchase_count
                FROM purchases
                WHERE event_timestamp >= %s AND event_timestamp < %s
                """,
                (start, end),
            )
            row = cur.fetchone()
        raw_revenue = Decimal(str(row["revenue"] or 0))
        revenue = raw_revenue.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return DailyKpiResult(
            metric_date=metric_date,
            metric_name="revenue",
            metric_value=revenue,
            metadata={"purchase_count": int(row["purchase_count"] or 0)},
        )

    def calculate_conversion_rate(self, metric_date: date) -> DailyKpiResult:
        start, end = self._day_bounds(metric_date)
        with self.store.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT user_id) AS viewers
                FROM page_views
                WHERE event_timestamp >= %s AND event_timestamp < %s
                """,
                (start, end),
            )
            viewers = int(cur.fetchone()["viewers"] or 0)

            cur.execute(
                """
                SELECT COUNT(DISTINCT user_id) AS buyers
                FROM purchases
                WHERE event_timestamp >= %s AND event_timestamp < %s
                """,
                (start, end),
            )
            buyers = int(cur.fetchone()["buyers"] or 0)

        rate = Decimal("0")
        if viewers > 0:
            rate = (Decimal(buyers) / Decimal(viewers) * Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        return DailyKpiResult(
            metric_date=metric_date,
            metric_name="conversion_rate",
            metric_value=rate,
            metadata={"viewers": viewers, "buyers": buyers},
        )

    def calculate_churn_rate(self, metric_date: date) -> DailyKpiResult:
        start, end = self._day_bounds(metric_date)
        with self.store.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cancellations
                FROM subscription_cancellations
                WHERE event_timestamp >= %s AND event_timestamp < %s
                """,
                (start, end),
            )
            cancellations = int(cur.fetchone()["cancellations"] or 0)

            cur.execute(
                """
                SELECT COUNT(DISTINCT user_id) AS active_base
                FROM (
                    SELECT user_id FROM user_signups WHERE event_timestamp < %s
                    UNION
                    SELECT user_id FROM purchases WHERE event_timestamp < %s
                ) active_users
                """,
                (end, end),
            )
            active_base = int(cur.fetchone()["active_base"] or 0)

        rate = Decimal("0")
        if active_base > 0:
            rate = (Decimal(cancellations) / Decimal(active_base) * Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        return DailyKpiResult(
            metric_date=metric_date,
            metric_name="churn_rate",
            metric_value=rate,
            metadata={"cancellations": cancellations, "active_base": active_base},
        )

    def calculate_referral_performance(self, metric_date: date) -> DailyKpiResult:
        start, end = self._day_bounds(metric_date)
        with self.store.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS referrals
                FROM referrals
                WHERE event_timestamp >= %s AND event_timestamp < %s
                """,
                (start, end),
            )
            referrals = int(cur.fetchone()["referrals"] or 0)

            cur.execute(
                """
                SELECT COUNT(*) AS signups
                FROM user_signups
                WHERE event_timestamp >= %s AND event_timestamp < %s
                """,
                (start, end),
            )
            signups = int(cur.fetchone()["signups"] or 0)

        rate = Decimal("0")
        if signups > 0:
            rate = (Decimal(referrals) / Decimal(signups) * Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        return DailyKpiResult(
            metric_date=metric_date,
            metric_name="referral_performance",
            metric_value=rate,
            metadata={"referrals": referrals, "signups": signups},
        )

    def calculate_all_for_date(self, metric_date: date) -> list[DailyKpiResult]:
        return [
            self.calculate_dau(metric_date),
            self.calculate_revenue(metric_date),
            self.calculate_conversion_rate(metric_date),
            self.calculate_churn_rate(metric_date),
            self.calculate_referral_performance(metric_date),
        ]

    def refresh_snapshots(self, metric_date: date | None = None) -> dict[str, Any]:
        target_date = metric_date or datetime.now(timezone.utc).date()
        results = self.calculate_all_for_date(target_date)

        for result in results:
            self.store.upsert_kpi_snapshot(
                metric_date=result.metric_date,
                metric_name=result.metric_name,
                metric_value=result.metric_value,
                metadata=result.metadata,
            )

        payload = self.store.get_latest_kpis(days=7)
        logger.info("kpi_snapshots_refreshed", metric_date=str(target_date))
        return payload

    @staticmethod
    def _day_bounds(metric_date: date) -> tuple[datetime, datetime]:
        start = datetime.combine(metric_date, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return start, end
