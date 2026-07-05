"""Application-specific exception hierarchy."""

from typing import Any


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EventValidationError(AppError):
    """Raised when an incoming event fails schema validation."""


class StorageError(AppError):
    """Raised when database or cache operations fail."""


class KafkaError(AppError):
    """Raised when Kafka producer/consumer operations fail."""


class ValidationError(AppError):
    """Raised when API input validation fails."""
