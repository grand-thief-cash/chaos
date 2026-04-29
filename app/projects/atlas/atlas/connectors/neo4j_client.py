"""Neo4j driver wrapper — manages connection pool and provides typed helpers."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from neo4j import GraphDatabase, Driver, Session

from atlas.core.config import get_config

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        cfg = get_config()["neo4j"]
        _driver = GraphDatabase.driver(
            cfg["uri"],
            auth=(cfg["username"], cfg["password"]),
            max_connection_pool_size=cfg.get("max_connection_pool_size", 50),
        )
        _driver.verify_connectivity()
        logger.info("Neo4j driver connected to %s", cfg["uri"])
    return _driver


@contextmanager
def get_session() -> Generator[Session, None, None]:
    driver = get_driver()
    cfg = get_config()["neo4j"]
    with driver.session(database=cfg.get("database", "neo4j")) as session:
        yield session


def close():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


# ── Schema initialization ─────────────────────────────────────────────────────

_CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.normalized_name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Resource) REQUIRE r.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Technology) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy) REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Market) REQUIRE m.name IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Asset) REQUIRE a.name IS UNIQUE",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX IF NOT EXISTS FOR (c:Company) ON (c.ticker)",
    "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.time)",
]


def ensure_schema():
    """Create constraints and indexes if they don't exist."""
    with get_session() as session:
        for stmt in _CONSTRAINTS + _INDEXES:
            session.run(stmt)
    logger.info("Neo4j schema constraints & indexes ensured")

