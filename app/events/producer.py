"""Realistic product event generator and Kafka producer."""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.events.models import EventType

logger = get_logger(__name__)

COUNTRIES = ["US", "GB", "DE", "IN", "CA", "AU", "FR", "BR"]
SIGNUP_SOURCES = ["organic", "paid_search", "social", "referral", "email"]
PAGE_PATHS = ["/", "/pricing", "/dashboard", "/settings", "/docs", "/checkout"]
PLAN_TIERS = ["free", "starter", "pro", "enterprise"]
CANCEL_REASONS = ["too_expensive", "not_using", "competitor", "other"]
PRODUCTS = [
    {"product_id": "plan_starter_monthly", "base_price": 19.99},
    {"product_id": "plan_pro_monthly", "base_price": 49.99},
    {"product_id": "plan_enterprise_monthly", "base_price": 199.99},
    {"product_id": "addon_storage", "base_price": 9.99},
]


class EventGenerator:
    """Generates realistic product analytics events with weighted distributions."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._user_pool: list[str] = [f"user_{i:05d}" for i in range(1, 501)]
        self._session_pool: dict[str, str] = {}

    def _random_user(self) -> str:
        return self._rng.choice(self._user_pool)

    def _session_for_user(self, user_id: str) -> str:
        if user_id not in self._session_pool:
            self._session_pool[user_id] = f"sess_{uuid4().hex[:12]}"
        return self._session_pool[user_id]

    def _weighted_event_type(self) -> EventType:
        roll = self._rng.random()
        if roll < 0.45:
            return EventType.PAGE_VIEW
        if roll < 0.62:
            return EventType.USER_SIGNUP
        if roll < 0.78:
            return EventType.PURCHASE
        if roll < 0.88:
            return EventType.REFERRAL_CREATED
        return EventType.SUBSCRIPTION_CANCELLED

    def generate_event(self, *, timestamp: datetime | None = None) -> dict[str, Any]:
        event_type = self._weighted_event_type()
        user_id = self._random_user()
        ts = timestamp or datetime.now(timezone.utc)

        base: dict[str, Any] = {
            "event_id": str(uuid4()),
            "event_type": event_type.value,
            "user_id": user_id,
            "event_timestamp": ts.isoformat(),
            "payload": {},
        }

        if event_type == EventType.USER_SIGNUP:
            base["payload"] = {
                "signup_source": self._rng.choice(SIGNUP_SOURCES),
                "country": self._rng.choice(COUNTRIES),
            }
        elif event_type == EventType.PAGE_VIEW:
            base["payload"] = {
                "page_path": self._rng.choice(PAGE_PATHS),
                "session_id": self._session_for_user(user_id),
                "referrer": self._rng.choice(["direct", "google", "twitter", "email"]),
            }
        elif event_type == EventType.PURCHASE:
            product = self._rng.choice(PRODUCTS)
            variance = self._rng.uniform(0.95, 1.05)
            base["payload"] = {
                "amount": round(product["base_price"] * variance, 2),
                "currency": "USD",
                "product_id": product["product_id"],
            }
        elif event_type == EventType.SUBSCRIPTION_CANCELLED:
            base["payload"] = {
                "plan_tier": self._rng.choice(PLAN_TIERS[1:]),
                "reason": self._rng.choice(CANCEL_REASONS),
                "months_subscribed": self._rng.randint(1, 24),
            }
        elif event_type == EventType.REFERRAL_CREATED:
            referrer = self._random_user()
            referred = self._random_user()
            while referred == referrer:
                referred = self._random_user()
            base["payload"] = {
                "referrer_id": referrer,
                "referred_user_id": referred,
                "campaign": self._rng.choice(["default", "spring_promo", "partner"]),
            }

        return base

    def generate_batch(
        self,
        count: int,
        *,
        start_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        start = start_time or datetime.now(timezone.utc) - timedelta(seconds=count)
        events: list[dict[str, Any]] = []
        for i in range(count):
            ts = start + timedelta(seconds=i)
            events.append(self.generate_event(timestamp=ts))
        return events


class KafkaEventProducer:
    """Publishes validated events to Redpanda/Kafka."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._producer = None

    def _get_producer(self):
        if self._producer is None:
            from kafka import KafkaProducer

            self._producer = KafkaProducer(
                bootstrap_servers=self.settings.kafka_bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
            )
        return self._producer

    def publish(self, event: dict[str, Any]) -> None:
        producer = self._get_producer()
        key = event.get("user_id", "")
        future = producer.send(self.settings.kafka_topic, value=event, key=key)
        future.get(timeout=10)
        logger.info(
            "event_published",
            event_id=event.get("event_id"),
            event_type=event.get("event_type"),
            topic=self.settings.kafka_topic,
        )

    def publish_batch(self, events: list[dict[str, Any]]) -> int:
        for event in events:
            self.publish(event)
        return len(events)

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush()
            self._producer.close()
            self._producer = None


def run_producer_loop(settings: Settings | None = None, max_events: int | None = None) -> None:
    """Continuously generate and publish events (used by scripts/run_producer.py)."""
    settings = settings or get_settings()
    generator = EventGenerator()
    producer = KafkaEventProducer(settings)
    published = 0

    logger.info(
        "producer_started",
        topic=settings.kafka_topic,
        interval=settings.producer_interval_seconds,
    )

    try:
        while max_events is None or published < max_events:
            batch = generator.generate_batch(settings.producer_batch_size)
            producer.publish_batch(batch)
            published += len(batch)
            time.sleep(settings.producer_interval_seconds)
    except KeyboardInterrupt:
        logger.info("producer_stopped", published=published)
    finally:
        producer.close()
