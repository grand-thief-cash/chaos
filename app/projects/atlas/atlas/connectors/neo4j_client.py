"""Neo4j client — delegates to PhoenixA data middleware.

Atlas does NOT connect to Neo4j directly. All graph operations go through
PhoenixA's /api/v1/graph/* endpoints which manage the Neo4j connection.

This module provides backward-compatible sync wrappers for legacy callers.
New code should use phoenixa_client graph methods directly.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from typing import Generator

from atlas.connectors import phoenixa_client

logger = logging.getLogger(__name__)


class _PhoenixASession:
    """Sync-compatible session that delegates to phoenixa_client async graph methods."""

    def run(self, cypher: str, **kwargs) -> "_ResultProxy":
        """Run a Cypher query via PhoenixA.  Returns a ResultProxy for .data() / .single()."""
        loop = _get_or_create_event_loop()
        rows = loop.run_until_complete(phoenixa_client.run_cypher(cypher, kwargs or None))
        return _ResultProxy(rows)


class _ResultProxy:
    """Mimics the neo4j Result interface with .data() and .single()."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def data(self) -> list[dict]:
        return self._rows

    def single(self) -> dict | None:
        return self._rows[0] if self._rows else None


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


@contextmanager
def get_session() -> Generator[_PhoenixASession, None, None]:
    """Returns a PhoenixA-backed session (sync interface for legacy compatibility)."""
    yield _PhoenixASession()


async def ensure_schema():
    """Create Neo4j constraints and indexes via PhoenixA."""
    await phoenixa_client.graph_ensure_schema()
    logger.info("Neo4j schema ensured via PhoenixA")


async def close():
    """No-op — connection lifecycle is managed by PhoenixA."""
    pass
