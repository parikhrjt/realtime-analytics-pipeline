"""Event validation utilities."""

from typing import Any

from app.core.exceptions import EventValidationError
from app.events.models import VALID_EVENT_TYPES, BaseEvent, parse_event


def validate_event_payload(data: dict[str, Any]) -> BaseEvent:
    """Validate a raw event dictionary and return a typed event model."""
    if not isinstance(data, dict):
        raise EventValidationError("Event payload must be a JSON object")

    event_type = data.get("event_type")
    if event_type not in VALID_EVENT_TYPES:
        raise EventValidationError(
            f"Invalid event_type: {event_type!r}",
            details={"valid_types": sorted(VALID_EVENT_TYPES)},
        )

    try:
        return parse_event(data)
    except Exception as exc:
        raise EventValidationError(
            "Event validation failed",
            details={"errors": str(exc)},
        ) from exc
