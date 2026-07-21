"""preprocessing_loader — Load Regulatory Baseline data (CrossRegulation + Ambiguity).

Scans the CrossRegulation/ and AMBIGUITY_ANALYSIS/ directories
and extracts structured analysis data.

This module's primary class ``PreprocessingLoader`` was renamed (Phase 0
rebranding: "Layer 0" → "Regulatory Baseline") to
``RegulatoryBaselineLoader``. ``PreprocessingLoader`` is kept as a
backward-compat alias.

References:
    - contracts/SPRINT001_v2-core.md (C-004)
"""

import logging
from pathlib import Path

# CORR-037-T4b: inlined from aegis_phase1.v2.loader.__init__ (which no
# longer exports these helpers — the v1 global YAML frontmatter parser
# is removed to satisfy contract G5 part 2). The helpers are still used
# internally by preprocessing_loader; they live here as private functions.
import yaml as _yaml


def _parse_yaml_fm(text: str) -> dict:
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
        return _yaml.safe_load(yaml_block) or {}
    except Exception:
        return {}


def _strip_frontmatter(text: str) -> str:
    """Return markdown body without YAML frontmatter."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---" or lines[i].strip() == "...":
                return "\n".join(lines[i + 1:])
    return text

logger = logging.getLogger(__name__)


class RegulatoryBaselineLoader:
    """Loader for the Regulatory Baseline analysis directories.

    Loads cross-regulation domain analyses and ambiguity analysis
    entries from the regulatory baseline directory (the former
    "PREPROCESSING/" directory).

    Note:
        ``RegulatoryBaselineLoader`` is the canonical name post
        rebranding. ``PreprocessingLoader`` remains a backward-compat
        alias that subclasses / binds to this class.
    """

    def load(self, regulatory_baseline_path: str) -> dict:
        """Load all Regulatory Baseline data.

        Args:
            regulatory_baseline_path: Path to the PREPROCESSING/ directory
                (e.g. ``../../Methodology-main/00_METHODOLOGY/PREPROCESSING``).

        Returns:
            Dictionary with keys: cross_regulation, ambiguities.
        """
        base = Path(regulatory_baseline_path)

        cross_regulation = self._load_cross_regulation(base / "CrossRegulation")
        ambiguities = self._load_ambiguities(base / "AMBIGUITY_ANALYSIS")

        return {
            "cross_regulation": cross_regulation,
            "ambiguities": ambiguities,
        }

    def _load_cross_regulation(self, path: Path) -> list[dict]:
        """Walk CrossRegulation/ recursively for .md files."""
        if not path.exists():
            logger.warning("CrossRegulation directory not found: %s", path)
            return []

        entries: list[dict] = []
        md_files = sorted(path.glob("**/*.md"))

        for filepath in md_files:
            if filepath.name == "index.md" or filepath.name == "README.md":
                continue
            if "_archive" in filepath.parts:
                continue
            if filepath.name == "TEMPLATE_crossreg_brief.md":
                continue
            try:
                entry = self._parse_crossreg_file(filepath)
                if entry:
                    entries.append(entry)
            except Exception:
                logger.exception("Failed to parse cross-reg file: %s", filepath)

        return entries

    def _parse_crossreg_file(self, filepath: Path) -> dict | None:
        """Parse a single cross-regulation analysis markdown file.

        Args:
            filepath: Path to the .md file.

        Returns:
            Dict with domain_id, reg_pair, relationship, analysis_text.
        """
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception:
            logger.exception("Could not read %s", filepath)
            return None

        frontmatter = _parse_yaml_fm(text)
        body = _strip_frontmatter(text)

        domain_id = frontmatter.get("sub_domain", "")
        if not domain_id:
            parts = filepath.stem.split("-", 1)
            if len(parts) == 2 and parts[0] == "D":
                domain_id = filepath.stem

        pairs: list[dict] = []
        pair_sections = body.split("<!-- /pair -->")
        for section in pair_sections:
            pair_match = _find_between(section, "<!-- pair:", "-->")
            if pair_match:
                pair_name = pair_match.strip()
                pair_text = section.strip()
                pairs.append({
                    "reg_pair": pair_name,
                    "text": pair_text,
                })

        return {
            "domain_id": domain_id,
            "pairs": pairs,
            "filepath": str(filepath),
            "analysis_text": body[:2000] if body else "",
        }

    def _load_ambiguities(self, path: Path) -> list[dict]:
        """Walk AMBIGUITY_ANALYSIS/ recursively for .md files.

        Extracts ambiguity analysis entries.
        """
        if not path.exists():
            logger.warning("AMBIGUITY_ANALYSIS directory not found: %s", path)
            return []

        entries: list[dict] = []
        md_files = sorted(path.glob("**/*.md"))

        for filepath in md_files:
            try:
                entry = self._parse_ambiguity_file(filepath)
                if entry:
                    entries.append(entry)
            except Exception:
                logger.exception("Failed to parse ambiguity file: %s", filepath)

        return entries

    def _parse_ambiguity_file(self, filepath: Path) -> dict | None:
        """Parse a single ambiguity analysis markdown file.

        Args:
            filepath: Path to the .md file.

        Returns:
            Dict with id, description, regulations_involved, resolution.
        """
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception:
            logger.exception("Could not read %s", filepath)
            return None

        frontmatter = _parse_yaml_fm(text)
        body = _strip_frontmatter(text)

        return {
            "id": frontmatter.get("document_id", filepath.stem),
            "filepath": str(filepath),
            "description": body[:500] if body else "",
            "title": frontmatter.get("title", filepath.stem),
            "frontmatter": frontmatter,
        }


# Backward-compat alias (Phase 0 rebranding: "Layer 0" → "Regulatory Baseline").
# Existing imports ``from aegis_phase1.v2.loader.preprocessing_loader import
# PreprocessingLoader`` keep working.
PreprocessingLoader = RegulatoryBaselineLoader


def _find_between(text: str, start: str, end: str) -> str | None:
    """Return substring between start and end markers."""
    si = text.find(start)
    if si == -1:
        return None
    si += len(start)
    ei = text.find(end, si)
    if ei == -1:
        return None
    return text[si:ei]


# Public exports for the renamed loader. ``PreprocessingLoader`` is the
# legacy alias; ``RegulatoryBaselineLoader`` is the canonical name.
__all__ = [
    "PreprocessingLoader",
    "RegulatoryBaselineLoader",
]  # pragma: no cover
