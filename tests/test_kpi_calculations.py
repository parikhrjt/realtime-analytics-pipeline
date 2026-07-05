"""Tests for KPI calculation logic."""

from datetime import date
from decimal import Decimal

import pytest
from conftest import FakePostgresStore

from app.analytics.anomaly_detector import AnomalyDetector
from app.analytics.kpi_calculator import KpiCalculator


class TestKpiCalculations:
    @pytest.fixture
    def store(self):
        return FakePostgresStore(
            {
                "dau": 120,
                "revenue": Decimal("1500.50"),
                "purchase_count": 25,
                "viewers": 200,
                "buyers": 20,
                "cancellations": 4,
                "active_base": 1000,
                "referrals": 15,
                "signups": 50,
            }
        )

    @pytest.fixture
    def calculator(self, store):
        return KpiCalculator(store=store)

    def test_calculate_dau(self, calculator):
        result = calculator.calculate_dau(date(2026, 7, 5))
        assert result.metric_name == "dau"
        assert result.metric_value == Decimal("120")

    def test_calculate_revenue(self, calculator):
        result = calculator.calculate_revenue(date(2026, 7, 5))
        assert result.metric_name == "revenue"
        assert result.metric_value == Decimal("1500.50")
        assert result.metadata["purchase_count"] == 25

    def test_calculate_conversion_rate(self, calculator):
        result = calculator.calculate_conversion_rate(date(2026, 7, 5))
        assert result.metric_name == "conversion_rate"
        assert result.metric_value == Decimal("10.0000")
        assert result.metadata["viewers"] == 200
        assert result.metadata["buyers"] == 20

    def test_calculate_churn_rate(self, calculator):
        result = calculator.calculate_churn_rate(date(2026, 7, 5))
        assert result.metric_name == "churn_rate"
        assert result.metric_value == Decimal("0.4000")

    def test_calculate_referral_performance(self, calculator):
        result = calculator.calculate_referral_performance(date(2026, 7, 5))
        assert result.metric_name == "referral_performance"
        assert result.metric_value == Decimal("30.0000")

    def test_conversion_rate_zero_viewers(self):
        store = FakePostgresStore({"viewers": 0, "buyers": 0})
        calculator = KpiCalculator(store=store)
        result = calculator.calculate_conversion_rate(date(2026, 7, 5))
        assert result.metric_value == Decimal("0")

    def test_refresh_snapshots_persists_all_metrics(self, calculator, store):
        target = date(2026, 7, 5)
        calculator.refresh_snapshots(target)
        assert len(store.snapshots) == 5
        metric_names = {snap["metric_name"] for snap in store.snapshots}
        assert metric_names == {
            "dau",
            "revenue",
            "conversion_rate",
            "churn_rate",
            "referral_performance",
        }


class TestAnomalyDetection:
    def test_detects_revenue_drop(self):
        store = FakePostgresStore(
            {
                "kpi_history_by_metric": {
                    "revenue": [
                        {"metric_date": "2026-07-05", "metric_value": 500.0},
                        {"metric_date": "2026-07-04", "metric_value": 1000.0},
                        {"metric_date": "2026-07-03", "metric_value": 1100.0},
                        {"metric_date": "2026-07-02", "metric_value": 1050.0},
                    ]
                }
            }
        )
        detector = AnomalyDetector(store=store)
        anomaly = detector.detect_for_metric("revenue", date(2026, 7, 5))
        assert anomaly is not None
        assert anomaly["metric_name"] == "revenue"
        assert anomaly["deviation_pct"] > 30

    def test_no_anomaly_when_within_threshold(self):
        store = FakePostgresStore(
            {
                "kpi_history_by_metric": {
                    "dau": [
                        {"metric_date": "2026-07-05", "metric_value": 950.0},
                        {"metric_date": "2026-07-04", "metric_value": 1000.0},
                        {"metric_date": "2026-07-03", "metric_value": 980.0},
                    ]
                }
            }
        )
        detector = AnomalyDetector(store=store)
        anomaly = detector.detect_for_metric("dau", date(2026, 7, 5))
        assert anomaly is None

    def test_scan_all_stores_anomalies(self):
        store = FakePostgresStore(
            {
                "kpi_history_by_metric": {
                    "revenue": [
                        {"metric_date": "2026-07-05", "metric_value": 100.0},
                        {"metric_date": "2026-07-04", "metric_value": 1000.0},
                    ],
                    "dau": [
                        {"metric_date": "2026-07-05", "metric_value": 50.0},
                        {"metric_date": "2026-07-04", "metric_value": 500.0},
                    ],
                }
            }
        )
        detector = AnomalyDetector(store=store)
        anomalies = detector.scan_all(date(2026, 7, 5))
        assert len(anomalies) == 2
        assert len(store.anomalies) == 2
