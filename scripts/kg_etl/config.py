"""scripts/kg_etl/config.py — Configuration and connection settings for Neo4j ETL.

References:
    - docs/NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md
    - .agents/skills/neo4j-verify/SKILL.md
"""

# ─── Standard library ────────────────────────────────────────────────
import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse

# ─── Module-level constants ──────────────────────────────────────────
CANONICAL_BOLT_PORT = 7688
CANONICAL_HTTP_PORT = 7475
PROHIBITED_PORTS = {7687, 7474}

DEFAULT_BOLT_URL = f"bolt://localhost:{CANONICAL_BOLT_PORT}"
DEFAULT_HTTP_URL = f"http://localhost:{CANONICAL_HTTP_PORT}"
DEFAULT_USER = "neo4j"
DEFAULT_DATABASE = "neo4j"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Neo4jConfig:
    """Holds validated Neo4j connection parameters."""

    bolt_url: str
    http_url: str
    user: str
    password: str
    database: str


def validate_port_safety(url_str: str) -> None:
    """Validate that the given URL does not use prohibited external ports (7687, 7474).

    Raises:
        ValueError: If a prohibited port is detected.
    """
    parsed = urlparse(url_str)
    port = parsed.port
    if port in PROHIBITED_PORTS:
        raise ValueError(
            f"Prohibited port {port} detected in URL '{url_str}'. "
            f"AEGIS-KG strictly requires Bolt:{CANONICAL_BOLT_PORT} and HTTP:{CANONICAL_HTTP_PORT}."
        )


def get_neo4j_config() -> Neo4jConfig:
    """Load and validate Neo4j connection configuration from environment or defaults.

    Returns:
        Neo4jConfig: Validated configuration.

    Raises:
        ValueError: If prohibited ports are found in environment variables.
    """
    bolt_url = os.getenv("NEO4J_BOLT_URL") or os.getenv("NEO4J_URI") or DEFAULT_BOLT_URL
    # Ensure scheme compatibility if NEO4J_URI passed http
    if bolt_url.startswith("http://"):
        bolt_url = bolt_url.replace("http://", "bolt://")
    elif bolt_url.startswith("https://"):
        bolt_url = bolt_url.replace("https://", "neo4j+s://")

    http_url = os.getenv("NEO4J_HTTP_URL") or DEFAULT_HTTP_URL
    user = os.getenv("NEO4J_USER", DEFAULT_USER)
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", DEFAULT_DATABASE)

    validate_port_safety(bolt_url)
    validate_port_safety(http_url)

    return Neo4jConfig(
        bolt_url=bolt_url,
        http_url=http_url,
        user=user,
        password=password,
        database=database,
    )


__all__ = [
    "CANONICAL_BOLT_PORT",
    "CANONICAL_HTTP_PORT",
    "DEFAULT_BOLT_URL",
    "DEFAULT_DATABASE",
    "DEFAULT_HTTP_URL",
    "DEFAULT_USER",
    "PROHIBITED_PORTS",
    "Neo4jConfig",
    "get_neo4j_config",
    "validate_port_safety",
]
