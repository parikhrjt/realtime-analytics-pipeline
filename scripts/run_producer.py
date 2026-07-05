#!/usr/bin/env python3
"""CLI entry point for the event producer."""

from app.core.logging import setup_logging
from app.events.producer import run_producer_loop


def main() -> None:
    setup_logging()
    run_producer_loop()


if __name__ == "__main__":
    main()
