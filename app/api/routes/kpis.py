"""KPI metrics API endpoint."""

from fastapi import APIRouter, Query

from app.analytics.kpi_calculator import KpiCalculator
from app.api.schemas import KpiMetricSnapshot, KpisResponse
from app.storage.postgres import get_postgres_store
from app.storage.redis_cache import get_redis_cache

router = APIRouter()


def _normalize_snapshot(row: dict) -> KpiMetricSnapshot:
    return KpiMetricSnapshot(
        metric_date=row["metric_date"],
        metric_name=row["metric_name"],
        metric_value=float(row["metric_value"]),
        metadata=row.get("metadata") or {},
        calculated_at=row.get("calculated_at"),
    )


@router.get("/kpis", response_model=KpisResponse)
async def get_kpis(days: int = Query(default=7, ge=1, le=90)) -> KpisResponse:
    cache = get_redis_cache()
    cached = cache.get_latest_kpis()

    if cached and cached.get("history"):
        metrics = {
            name: _normalize_snapshot(row) if row else None
            for name, row in cached.get("metrics", {}).items()
        }
        history = {
            name: [_normalize_snapshot(row) for row in rows]
            for name, rows in cached.get("history", {}).items()
        }
        return KpisResponse(
            metrics=metrics,
            history=history,
            generated_at=cached.get("generated_at", ""),
            source="redis",
        )

    store = get_postgres_store()
    calculator = KpiCalculator(store)
    payload = calculator.refresh_snapshots()

    metrics = {
        name: _normalize_snapshot(row) if row else None
        for name, row in payload.get("metrics", {}).items()
    }
    history = {
        name: [_normalize_snapshot(row) for row in rows]
        for name, rows in payload.get("history", {}).items()
    }

    return KpisResponse(
        metrics=metrics,
        history=history,
        generated_at=payload.get("generated_at", ""),
        source="postgres",
    )
