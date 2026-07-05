#!/usr/bin/env python3
"""Apply SQL migrations to PostgreSQL."""

import sys
from pathlib import Path

import psycopg2

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> None:
    setup_logging()
    settings = get_settings()
    migrations_dir = Path(__file__).resolve().parents[1] / "sql" / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        logger.error("no_migrations_found", path=str(migrations_dir))
        sys.exit(1)

    conn = psycopg2.connect(settings.database_url)
    try:
        with conn.cursor() as cur:
            for migration in migration_files:
                sql = migration.read_text(encoding="utf-8")
                logger.info("applying_migration", file=migration.name)
                cur.execute(sql)
        conn.commit()
        logger.info("migrations_complete", count=len(migration_files))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
