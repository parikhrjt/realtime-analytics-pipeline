"""Tests for event schema validation."""

import pytest

from app.core.exceptions import EventValidationError
from app.events.models import BaseEvent, EventType, parse_event
from app.events.validator import validate_event_payload


class TestEventValidation:
    def test_valid_signup_event(self, sample_signup_event):
        event = validate_event_payload(sample_signup_event)
        assert event.event_type == EventType.USER_SIGNUP
        assert event.user_id == "user_00001"
        assert event.payload["country"] == "US"

    def test_valid_page_view_event(self, sample_page_view_event):
        event = validate_event_payload(sample_page_view_event)
        assert event.event_type == EventType.PAGE_VIEW
        assert event.payload["page_path"] == "/pricing"

    def test_valid_purchase_event(self, sample_purchase_event):
        event = validate_event_payload(sample_purchase_event)
        assert event.event_type == EventType.PURCHASE
        assert float(event.payload["amount"]) == pytest.approx(49.99)

    def test_valid_cancellation_event(self, sample_cancellation_event):
        event = validate_event_payload(sample_cancellation_event)
        assert event.event_type == EventType.SUBSCRIPTION_CANCELLED

    def test_valid_referral_event(self, sample_referral_event):
        event = validate_event_payload(sample_referral_event)
        assert event.event_type == EventType.REFERRAL_CREATED

    def test_rejects_invalid_event_type(self, sample_signup_event):
        sample_signup_event["event_type"] = "unknown_event"
        with pytest.raises(EventValidationError) as exc:
            validate_event_payload(sample_signup_event)
        assert "Invalid event_type" in exc.value.message

    def test_rejects_blank_user_id(self, sample_signup_event):
        sample_signup_event["user_id"] = "   "
        with pytest.raises(EventValidationError):
            validate_event_payload(sample_signup_event)

    def test_rejects_negative_purchase_amount(self, sample_purchase_event):
        sample_purchase_event["payload"]["amount"] = -10
        with pytest.raises(EventValidationError):
            validate_event_payload(sample_purchase_event)

    def test_rejects_missing_page_path(self, sample_page_view_event):
        del sample_page_view_event["payload"]["page_path"]
        with pytest.raises(EventValidationError):
            validate_event_payload(sample_page_view_event)

    def test_rejects_self_referral(self, sample_referral_event):
        payload = sample_referral_event["payload"]
        payload["referred_user_id"] = payload["referrer_id"]
        with pytest.raises(EventValidationError):
            validate_event_payload(sample_referral_event)

    def test_normalizes_naive_timestamp(self, sample_signup_event):
        sample_signup_event["event_timestamp"] = "2026-07-05T12:00:00"
        event = parse_event(sample_signup_event)
        assert event.event_timestamp.tzinfo is not None

    def test_to_kafka_dict_is_json_serializable(self, sample_purchase_event):
        event = BaseEvent.model_validate(sample_purchase_event)
        payload = event.to_kafka_dict()
        assert payload["event_type"] == "purchase"
        assert "event_id" in payload

    def test_rejects_non_object_payload(self):
        with pytest.raises(EventValidationError):
            validate_event_payload("not-a-dict")  # type: ignore[arg-type]
