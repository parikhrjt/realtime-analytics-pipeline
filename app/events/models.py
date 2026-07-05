"""Product event schemas and validation models."""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class EventType(str, Enum):
    USER_SIGNUP = "user_signup"
    PAGE_VIEW = "page_view"
    PURCHASE = "purchase"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    REFERRAL_CREATED = "referral_created"


VALID_EVENT_TYPES = {event.value for event in EventType}


class BaseEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    user_id: str = Field(..., min_length=1, max_length=100)
    event_timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_id")
    @classmethod
    def strip_user_id(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("user_id cannot be blank")
        return stripped

    @field_validator("event_timestamp")
    @classmethod
    def normalize_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_payload_for_type(self) -> "BaseEvent":
        validators = {
            EventType.USER_SIGNUP: _validate_signup_payload,
            EventType.PAGE_VIEW: _validate_page_view_payload,
            EventType.PURCHASE: _validate_purchase_payload,
            EventType.SUBSCRIPTION_CANCELLED: _validate_cancellation_payload,
            EventType.REFERRAL_CREATED: _validate_referral_payload,
        }
        validators[self.event_type](self.payload)
        return self

    def to_kafka_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        return data


def _validate_signup_payload(payload: dict[str, Any]) -> None:
    source = payload.get("signup_source", "organic")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("signup_source must be a non-empty string")
    country = payload.get("country", "US")
    if not isinstance(country, str) or len(country) != 2:
        raise ValueError("country must be a 2-letter ISO code")


def _validate_page_view_payload(payload: dict[str, Any]) -> None:
    page_path = payload.get("page_path")
    if not isinstance(page_path, str) or not page_path.startswith("/"):
        raise ValueError("page_path must start with '/'")
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id is required for page_view events")


def _validate_purchase_payload(payload: dict[str, Any]) -> None:
    amount = payload.get("amount")
    if amount is None:
        raise ValueError("amount is required for purchase events")
    try:
        value = Decimal(str(amount))
    except Exception as exc:
        raise ValueError("amount must be a valid decimal") from exc
    if value <= 0:
        raise ValueError("amount must be positive")
    currency = payload.get("currency", "USD")
    if not isinstance(currency, str) or len(currency) != 3:
        raise ValueError("currency must be a 3-letter ISO code")
    product_id = payload.get("product_id")
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id is required for purchase events")


def _validate_cancellation_payload(payload: dict[str, Any]) -> None:
    plan_tier = payload.get("plan_tier")
    if not isinstance(plan_tier, str) or not plan_tier.strip():
        raise ValueError("plan_tier is required for subscription_cancelled events")
    reason = payload.get("reason", "unknown")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")


def _validate_referral_payload(payload: dict[str, Any]) -> None:
    referrer_id = payload.get("referrer_id")
    referred_user_id = payload.get("referred_user_id")
    if not isinstance(referrer_id, str) or not referrer_id.strip():
        raise ValueError("referrer_id is required for referral_created events")
    if not isinstance(referred_user_id, str) or not referred_user_id.strip():
        raise ValueError("referred_user_id is required for referral_created events")
    if referrer_id == referred_user_id:
        raise ValueError("referrer_id and referred_user_id must differ")


def parse_event(data: dict[str, Any]) -> BaseEvent:
    """Parse and validate a raw event dictionary."""
    return BaseEvent.model_validate(data)
