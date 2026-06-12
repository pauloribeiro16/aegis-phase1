"""Centralized environment variable loading for AEGIS-KG.

This module is the ONLY place that calls load_dotenv(). All other modules
import from this module and call load_env() once at module load time.

Usage:
    from aegis_phase1.env import load_env
    load_env()
    # then use os.getenv() anywhere
"""

import logging
from pathlib import Path

from dotenv import load_dotenv

# logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_env() -> bool:
    """Load environment variables from .env file.

    Uses override=False so real shell env vars win over .env values
    (production safety). Called once at module import time.

    Returns:
        True if .env was found and loaded, False otherwise.
    """
    env_path = Path(__file__).parent.parent / ".env"
    logger.info(f"[env] Loading .env from {env_path}")

    if not env_path.exists():
        logger.warning(f"[env] .env file not found at {env_path}")
        return False

    load_dotenv(env_path, override=False)
    logger.info("[env] .env loaded successfully")
    return True


# Load on module import
load_env()
