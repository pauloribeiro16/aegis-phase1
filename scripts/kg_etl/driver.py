"""scripts/kg_etl/driver.py — Neo4j driver and session management.

References:
    - scripts/kg_etl/config.py
    - .agents/skills/neo4j-verify/SKILL.md
"""

# ─── Standard library ────────────────────────────────────────────────
import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

# ─── Third-party ─────────────────────────────────────────────────────
from neo4j import Driver, GraphDatabase, Session

# ─── Local ───────────────────────────────────────────────────────────
from scripts.kg_etl.config import Neo4jConfig, get_neo4j_config

logger = logging.getLogger(__name__)


def create_neo4j_driver(config: Neo4jConfig | None = None) -> Driver:
    """Create and return a Neo4j driver using validated configuration.

    Args:
        config: Optional Neo4jConfig instance. If omitted, loads from env/defaults.

    Returns:
        Driver: Active Neo4j Bolt driver.
    """
    cfg = config or get_neo4j_config()
    auth = (cfg.user, cfg.password) if cfg.password else None
    logger.debug("Creating Neo4j driver for %s (database: %s)", cfg.bolt_url, cfg.database)
    return GraphDatabase.driver(cfg.bolt_url, auth=auth)


@contextmanager
def get_session(
    driver: Driver | None = None,
    config: Neo4jConfig | None = None,
) -> Generator[Session, None, None]:
    """Context manager yielding a Neo4j session and ensuring proper closure.

    Args:
        driver: Optional existing Driver. If None, a new driver is managed.
        config: Optional Neo4jConfig.

    Yields:
        Session: Neo4j session.
    """
    cfg = config or get_neo4j_config()
    owns_driver = driver is None
    active_driver = driver or create_neo4j_driver(cfg)

    session = active_driver.session(database=cfg.database)
    try:
        yield session
    finally:
        session.close()
        if owns_driver:
            active_driver.close()


def run_unwind_batch(
    session: Session,
    query: str,
    rows: list[dict[str, Any]],
    batch_size: int = 500,
    param_name: str = "rows",
) -> int:
    """Execute batch queries using UNWIND over parameterized batches.

    Args:
        session: Active Neo4j session.
        query: Cypher query starting with UNWIND $<param_name> AS row ...
        rows: List of row dictionaries.
        batch_size: Number of items per batch chunk.
        param_name: Name of parameter in Cypher query. Defaults to 'rows'.

    Returns:
        int: Total number of rows processed.
    """
    total = len(rows)
    if total == 0:
        return 0

    for i in range(0, total, batch_size):
        chunk = rows[i : i + batch_size]
        session.run(query, {param_name: chunk})

    return total


__all__ = [
    "create_neo4j_driver",
    "get_session",
    "run_unwind_batch",
]
