"""loader — shared helpers for the v2 input loaders.

Exposes the YAML frontmatter utilities used by ``common_loader`` and
``subdomain_loader`` so that loaders can ``from aegis_phase1.v2.loader
import _parse_yaml_frontmatter`` instead of duplicating the helpers.
"""

from __future__ import annotations

import logging

import yaml

logger = logging.getLogger(__name__)


def _parse_yaml_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter between ``---`` markers."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---" or lines[i].strip() == "...":
            end_idx = i
            break
    if end_idx is None:
        return {}
    yaml_block = "\n".join(lines[1:end_idx])
    try:
        return yaml.safe_load(yaml_block) or {}
    except Exception:
        logger.debug("Could not parse YAML frontmatter", exc_info=True)
        return {}


def _strip_frontmatter(text: str) -> str:
    """Return markdown body without YAML frontmatter."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---" or lines[i].strip() == "...":
                return "\n".join(lines[i + 1:])
    return text


__all__ = ["_parse_yaml_frontmatter", "_strip_frontmatter"]
