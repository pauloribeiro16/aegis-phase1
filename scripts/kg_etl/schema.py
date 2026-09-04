"""scripts/kg_etl/schema.py — DDL manager and executor for Neo4j schema constraints & indexes.

References:
    - scripts/kg_etl/schema.cypher
    - docs/NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md §4
"""

# ─── Standard library ────────────────────────────────────────────────
import logging
from pathlib import Path
from typing import TYPE_CHECKING

# ─── Local ───────────────────────────────────────────────────────────

if TYPE_CHECKING:
    from neo4j import Session

logger = logging.getLogger(__name__)

SCHEMA_CYPHER_PATH = Path(__file__).parent / "schema.cypher"


def load_schema_statements(cypher_path: Path | None = None) -> list[str]:
    """Parse schema.cypher into individual DDL statements.

    Args:
        cypher_path: Optional path to .cypher file. Defaults to schema.cypher.

    Returns:
        list[str]: Cleaned list of executable Cypher DDL statements.
    """
    path = cypher_path or SCHEMA_CYPHER_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Schema file not found at {path}")

    raw = path.read_text(encoding="utf-8")
    statements: list[str] = []

    # Remove single-line comments and split by semicolon
    for line_group in raw.split(";"):
        cleaned_lines = []
        for line in line_group.splitlines():
            line_str = line.strip()
            if line_str.startswith("//"):
                continue
            if line_str:
                cleaned_lines.append(line_str)
        stmt = " ".join(cleaned_lines).strip()
        if stmt:
            statements.append(stmt)

    return statements


def apply_schema(session: "Session") -> int:
    """Execute all schema constraints and indexes against an active Neo4j session.

    Args:
        session: Active Neo4j session.

    Returns:
        int: Number of statements executed.
    """
    statements = load_schema_statements()
    executed = 0
    for stmt in statements:
        logger.debug("Applying DDL: %s", stmt)
        session.run(stmt)
        executed += 1
    logger.info("Successfully applied %d schema statements", executed)
    return executed


__all__ = [
    "SCHEMA_CYPHER_PATH",
    "apply_schema",
    "load_schema_statements",
]
