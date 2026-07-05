"""Console alert channel."""

from app.core.logging import get_logger

logger = get_logger(__name__)


def send_console_alert(title: str, message: str, severity: str = "warning") -> None:
    banner = "=" * 60
    logger.warning(
        "console_alert",
        title=title,
        severity=severity,
        message=message,
    )
    print(f"\n{banner}\nALERT [{severity.upper()}]: {title}\n{message}\n{banner}\n")
