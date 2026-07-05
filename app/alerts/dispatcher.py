"""Alert dispatch orchestration."""

from __future__ import annotations

from typing import Any

from app.alerts.console import send_console_alert
from app.alerts.slack import send_slack_alert
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def dispatch_anomaly_alerts(anomalies: list[dict[str, Any]]) -> None:
    settings = get_settings()
    for anomaly in anomalies:
        title = f"KPI anomaly: {anomaly['metric_name']}"
        message = anomaly["message"]
        severity = anomaly.get("severity", "warning")

        if settings.alert_console_enabled:
            send_console_alert(title, message, severity=severity)

        send_slack_alert(title, message, severity=severity)

    if anomalies:
        logger.info("alerts_dispatched", count=len(anomalies))
