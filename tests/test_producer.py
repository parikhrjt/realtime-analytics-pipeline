"""Tests for event generator."""

from app.events.models import VALID_EVENT_TYPES
from app.events.producer import EventGenerator


class TestEventGenerator:
    def test_generate_event_has_required_fields(self):
        generator = EventGenerator(seed=42)
        event = generator.generate_event()
        assert event["event_type"] in VALID_EVENT_TYPES
        assert event["user_id"]
        assert event["event_id"]
        assert event["event_timestamp"]
        assert isinstance(event["payload"], dict)

    def test_generate_batch_returns_requested_count(self):
        generator = EventGenerator(seed=99)
        events = generator.generate_batch(10)
        assert len(events) == 10

    def test_purchase_events_have_positive_amount(self):
        generator = EventGenerator(seed=7)
        for _ in range(50):
            event = generator.generate_event()
            if event["event_type"] == "purchase":
                assert event["payload"]["amount"] > 0
                return
        raise AssertionError("No purchase event generated in 50 attempts")
