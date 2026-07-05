"""Streamlit dashboard for realtime analytics KPIs."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def fetch_json(path: str) -> dict | list | None:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"Failed to reach API at {API_BASE_URL}{path}: {exc}")
        return None


def render_metric_card(label: str, value: str, delta: str | None = None) -> None:
    st.metric(label=label, value=value, delta=delta)


def main() -> None:
    st.set_page_config(
        page_title="Realtime Analytics Dashboard",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 Realtime Product Analytics")
    st.caption("Streaming pipeline demo — Redpanda · PostgreSQL · Redis · FastAPI")

    health = fetch_json("/health")
    if health:
        status = health.get("status", "unknown")
        color = "🟢" if status == "healthy" else "🟡"
        st.sidebar.markdown(f"{color} API status: **{status}**")
        components = health.get("components", {})
        for name, ok in components.items():
            icon = "✅" if ok else "❌"
            st.sidebar.write(f"{icon} {name}")

    kpis = fetch_json("/kpis?days=14")
    if not kpis:
        st.warning("KPI data unavailable. Start the producer and consumer services.")
        return

    metrics = kpis.get("metrics", {})
    history = kpis.get("history", {})
    source = kpis.get("source", "unknown")

    st.sidebar.markdown(f"Data source: `{source}`")
    st.sidebar.markdown(f"Generated: {kpis.get('generated_at', 'n/a')}")

    col1, col2, col3, col4, col5 = st.columns(5)

    metric_labels = {
        "dau": "Daily Active Users",
        "revenue": "Revenue (USD)",
        "conversion_rate": "Conversion Rate (%)",
        "churn_rate": "Churn Rate (%)",
        "referral_performance": "Referral Rate (%)",
    }

    columns = [col1, col2, col3, col4, col5]
    for col, (key, label) in zip(columns, metric_labels.items()):
        snapshot = metrics.get(key)
        with col:
            if snapshot:
                value = snapshot.get("metric_value", 0)
                if key == "revenue":
                    display = f"${value:,.2f}"
                elif key == "dau":
                    display = f"{int(value):,}"
                else:
                    display = f"{value:.2f}%"
                render_metric_card(label, display)
            else:
                render_metric_card(label, "—")

    st.divider()
    st.subheader("Trends (14 days)")

    tabs = st.tabs(list(metric_labels.values()))
    for tab, (key, label) in zip(tabs, metric_labels.items()):
        rows = history.get(key, [])
        with tab:
            if not rows:
                st.info("No history yet for this metric.")
                continue
            df = pd.DataFrame(rows)
            df["metric_date"] = pd.to_datetime(df["metric_date"])
            df = df.sort_values("metric_date")
            chart_df = df.set_index("metric_date")[["metric_value"]]
            st.line_chart(chart_df, height=300)
            st.dataframe(df[["metric_date", "metric_value", "metadata"]], use_container_width=True)

    st.divider()
    st.subheader("Recent Events")

    events_payload = fetch_json("/events?limit=25")
    if events_payload and events_payload.get("events"):
        events_df = pd.DataFrame(events_payload["events"])
        st.dataframe(
            events_df[["event_timestamp", "event_type", "user_id", "payload"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No events ingested yet.")

    st.caption(f"Dashboard refreshed at {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    main()
