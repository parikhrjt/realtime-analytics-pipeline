"""Pydantic schemas for API request/response models."""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    components: dict[str, bool]


class EventResponse(BaseModel):
    event_id: str
    event_type: str
    user_id: str
    event_timestamp: str
    payload: dict[str, Any]
    ingested_at: str | None = None


class EventsListResponse(BaseModel):
    events: list[EventResponse]
    count: int


class KpiMetricSnapshot(BaseModel):
    metric_date: str
    metric_name: str
    metric_value: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    calculated_at: str | None = None


class KpisResponse(BaseModel):
    metrics: dict[str, KpiMetricSnapshot | None]
    history: dict[str, list[KpiMetricSnapshot]]
    generated_at: str
    source: str = "postgres"


class AnomalyResponse(BaseModel):
    metric_name: str
    metric_date: str
    current_value: float | None = None
    expected_value: float | None = None
    deviation_pct: float | None = None
    severity: str
    message: str
    detected_at: str | None = None


class ErrorResponse(BaseModel):
    error: str
    details: dict | None = None
