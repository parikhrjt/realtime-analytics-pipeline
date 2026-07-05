"""Mock Slack webhook alert channel."""

from __future__ import annotations

import json
from urllib import error, request

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def send_slack_alert(title: str, message: str, severity: str = "warning") -> bool:
    settings = get_settings()
    webhook_url = settings.slack_webhook_url.strip()

    if not webhook_url:
        logger.info(
            "slack_alert_skipped",
            reason="SLACK_WEBHOOK_URL not configured",
            title=title,
            message=message,
        )
        return False

    payload = {
        "text": f"*[{severity.upper()}] {title}*\n{message}",
    }

    req = request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=5) as response:
            success = 200 <= response.status < 300
            logger.info("slack_alert_sent", title=title, success=success)
            return success
    except error.URLError as exc:
        logger.warning("slack_alert_failed", title=title, error=str(exc))
        return False
