"""Kafka consumer event processor."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.alerts.dispatcher import dispatch_anomaly_alerts
from app.analytics.anomaly_detector import AnomalyDetector
from app.analytics.kpi_calculator import KpiCalculator
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.events.validator import validate_event_payload
from app.storage.postgres import PostgresStore
from app.storage.redis_cache import RedisKpiCache

logger = get_logger(__name__)


class EventProcessor:
    """Validates, persists, and triggers downstream KPI refresh for each event."""

    def __init__(
        self,
        store: PostgresStore | None = None,
        cache: RedisKpiCache | None = None,
        kpi_calculator: KpiCalculator | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store or PostgresStore(settings)
        self.cache = cache or RedisKpiCache(settings)
        self.kpi_calculator = kpi_calculator or KpiCalculator(self.store, settings)
        self.anomaly_detector = anomaly_detector or AnomalyDetector(self.store, settings)
        self.settings = settings or get_settings()
        self._events_since_kpi_refresh = 0
        self._kpi_refresh_every = 25

    def process_message(self, raw_message: dict[str, Any] | str | bytes) -> dict[str, Any]:
        if isinstance(raw_message, (bytes, bytearray)):
            payload = json.loads(raw_message.decode("utf-8"))
        elif isinstance(raw_message, str):
            payload = json.loads(raw_message)
        else:
            payload = raw_message

        event = validate_event_payload(payload)

        with self.store.cursor() as cur:
            self.store.store_raw_event(event, cur=cur)
            self.store.store_transformed_event(event, cur=cur)

        self._events_since_kpi_refresh += 1
        kpi_payload: dict[str, Any] | None = None
        anomalies: list[dict[str, Any]] = []

        if self._events_since_kpi_refresh >= self._kpi_refresh_every:
            metric_date = event.event_timestamp.date()
            kpi_payload = self.kpi_calculator.refresh_snapshots(metric_date)
            anomalies = self.anomaly_detector.scan_all(metric_date)
            if kpi_payload:
                self.cache.set_latest_kpis(kpi_payload)
            if anomalies:
                dispatch_anomaly_alerts(anomalies)
            self._events_since_kpi_refresh = 0

        logger.info(
            "event_processed",
            event_id=str(event.event_id),
            event_type=event.event_type.value,
            user_id=event.user_id,
        )

        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type.value,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "kpi_refreshed": kpi_payload is not None,
            "anomalies_detected": len(anomalies),
        }


class KafkaConsumerRunner:
    """Long-running Kafka consumer loop."""

    def __init__(
        self,
        processor: EventProcessor | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.processor = processor or EventProcessor(settings=settings)
        self.settings = settings or get_settings()
        self._consumer = None

    def _get_consumer(self):
        if self._consumer is None:
            from kafka import KafkaConsumer

            self._consumer = KafkaConsumer(
                self.settings.kafka_topic,
                bootstrap_servers=self.settings.kafka_bootstrap_servers.split(","),
                group_id=self.settings.kafka_consumer_group,
                auto_offset_reset=self.settings.kafka_auto_offset_reset,
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
        return self._consumer

    def run(self, max_messages: int | None = None) -> int:
        consumer = self._get_consumer()
        processed = 0

        logger.info(
            "consumer_started",
            topic=self.settings.kafka_topic,
            group=self.settings.kafka_consumer_group,
        )

        try:
            for message in consumer:
                self.processor.process_message(message.value)
                processed += 1
                if max_messages is not None and processed >= max_messages:
                    break
        except KeyboardInterrupt:
            logger.info("consumer_stopped", processed=processed)
        finally:
            consumer.close()
            self._consumer = None

        return processed
