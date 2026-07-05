#!/usr/bin/env python3
"""CLI entry point for the Kafka consumer."""

from app.consumer.processor import KafkaConsumerRunner
from app.core.logging import setup_logging


def main() -> None:
    setup_logging()
    runner = KafkaConsumerRunner()
    runner.run()


if __name__ == "__main__":
    main()
