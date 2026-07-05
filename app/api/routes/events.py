"""Recent events API endpoint."""

from fastapi import APIRouter, Query

from app.api.schemas import EventResponse, EventsListResponse
from app.storage.postgres import get_postgres_store

router = APIRouter()


@router.get("/events", response_model=EventsListResponse)
async def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None),
) -> EventsListResponse:
    store = get_postgres_store()
    rows = store.list_recent_events(limit=limit, event_type=event_type)

    events = [
        EventResponse(
            event_id=str(row["event_id"]),
            event_type=row["event_type"],
            user_id=row["user_id"],
            event_timestamp=row["event_timestamp"],
            payload=row["payload"] if isinstance(row["payload"], dict) else {},
            ingested_at=row.get("ingested_at"),
        )
        for row in rows
    ]

    return EventsListResponse(events=events, count=len(events))
