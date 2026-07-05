"""Anomaly detection for KPI drops."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.storage.postgres import PostgresStore

logger = get_logger(__name__)

MONITORED_METRICS = ("dau", "revenue")


class AnomalyDetector:
    """Detects unusual drops in revenue and active users using rolling averages."""

    def __init__(
        self,
        store: PostgresStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store or PostgresStore(settings)
        self.settings = settings or get_settings()

    def detect_for_metric(self, metric_name: str, metric_date: date) -> dict[str, Any] | None:
        lookback = self.settings.anomaly_lookback_days + 1
        history = self.store.get_kpi_history(metric_name, days=lookback)
        if len(history) < 2:
            return None

        target = metric_date.isoformat()
        current = next((row for row in history if row["metric_date"] == target), None)
        if current is None:
            return None

        prior_values = [
            Decimal(str(row["metric_value"]))
            for row in history
            if row["metric_date"] != metric_date.isoformat()
        ]
        if not prior_values:
            return None

        expected = sum(prior_values) / Decimal(len(prior_values))
        current_value = Decimal(str(current["metric_value"]))

        if expected <= 0:
            return None

        deviation_pct = ((expected - current_value) / expected * Decimal("100")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        if deviation_pct < Decimal(str(self.settings.anomaly_drop_threshold_pct)):
            return None

        severity = "critical" if deviation_pct >= Decimal("50") else "warning"
        message = (
            f"{metric_name} dropped {deviation_pct}% on {metric_date.isoformat()} "
            f"(current={current_value}, expected≈{expected.quantize(Decimal('0.01'))})"
        )

        anomaly = {
            "metric_name": metric_name,
            "metric_date": metric_date,
            "current_value": float(current_value),
            "expected_value": float(expected.quantize(Decimal("0.01"))),
            "deviation_pct": float(deviation_pct),
            "severity": severity,
            "message": message,
        }

        logger.warning("anomaly_detected", **anomaly)
        return anomaly

    def scan_all(self, metric_date: date) -> list[dict[str, Any]]:
        if not self.settings.anomaly_enabled:
            return []

        anomalies: list[dict[str, Any]] = []
        for metric_name in MONITORED_METRICS:
            anomaly = self.detect_for_metric(metric_name, metric_date)
            if anomaly:
                self.store.store_anomaly(anomaly)
                anomalies.append(anomaly)
        return anomalies
