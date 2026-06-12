"""load_phase1_data — Typed loader functions for Phase 1 CSV data.

Loads CSV files from the case data directory and returns typed dicts
with camelCase keys matching the methodology class diagram attributes.

References:
    - execution/contracts/phase1/CONTRACT-phase1A-data.md
    - .opencode/skills/project-conventions/SKILL.md
"""

# ─── Standard library ────────────────────────────────────────────────
import csv
import logging
from pathlib import Path

# ─── Module logger (MANDATORY) ───────────────────────────────────────
logger = logging.getLogger(__name__)

# ─── Module-level constants ──────────────────────────────────────────
_DATA_DIR = Path(__file__).parent / "phase1"


def _snake_to_camel(name: str) -> str:
    """Convert snake_case CSV header to camelCase.

    Args:
        name: The snake_case header string.

    Returns:
        The camelCase version.
    """
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _load_csv(filename: str, case: str = "case1") -> list[dict]:
    """Load a CSV file and return rows as camelCase dicts.

    Filters rows by the ``case`` column when present.

    Args:
        filename: CSV filename relative to the phase1 data directory.
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of dicts with camelCase keys.
    """
    csv_path = _DATA_DIR / filename
    if not csv_path.exists():
        logger.warning("CSV file not found: %s", csv_path)
        return []

    rows: list[dict] = []
    try:
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                clean = {k: v for k, v in row.items() if k is not None}
                if "case" in clean and clean["case"] != case:
                    continue
                camel_row = {_snake_to_camel(k): v for k, v in clean.items()}
                rows.append(camel_row)
    except Exception:
        logger.exception("Failed to load CSV: %s", csv_path)
        return []

    logger.info("Loaded %d rows from %s (case=%s)", len(rows), filename, case)
    return rows


# ─── Public API ──────────────────────────────────────────────────────


def load_clauses(case: str = "case1") -> list[dict]:
    """Load clause definitions from 04_clauses.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of clause dicts with camelCase keys.
    """
    return _load_csv("04_clauses.csv", case)


def load_regulations(case: str = "case1") -> list[dict]:
    """Load regulation metadata from 00_regulations.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of regulation dicts with camelCase keys.
    """
    return _load_csv("00_regulations.csv", case)


def load_domains(case: str = "case1") -> list[dict]:
    """Load domain definitions from 01_domains.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of domain dicts with camelCase keys.
    """
    return _load_csv("01_domains.csv", case)


def load_subdomains(case: str = "case1") -> list[dict]:
    """Load subdomain definitions from 02_subdomains.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of subdomain dicts with camelCase keys.
    """
    return _load_csv("02_subdomains.csv", case)


def load_articles(case: str = "case1") -> list[dict]:
    """Load article definitions from 03_articles.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of article dicts with camelCase keys.
    """
    return _load_csv("03_articles.csv", case)


def load_clause_subdomain_mapping(case: str = "case1") -> list[dict]:
    """Load clause-to-subdomain mappings from 07_clause_subdomain_mapping.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of mapping dicts with camelCase keys.
    """
    return _load_csv("07_clause_subdomain_mapping.csv", case)


def load_complementarity_analyses(case: str = "case1") -> list[dict]:
    """Load complementarity analyses from 06_complementarity_analysis.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of analysis dicts with camelCase keys.
    """
    return _load_csv("06_complementarity_analysis.csv", case)


def load_regulatory_timelines(case: str = "case1") -> list[dict]:
    """Load regulatory timelines from 08_regulatory_timelines.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of timeline dicts with camelCase keys.
    """
    return _load_csv("08_regulatory_timelines.csv", case)


def load_company_context(case: str = "case1") -> list[dict]:
    """Load company context from 05_company_context.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of context dicts with camelCase keys.
    """
    return _load_csv("05_company_context.csv", case)


def load_domain_coverages(case: str = "case1") -> list[dict]:
    """Load domain coverage entries from domain_coverage_entries.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of coverage dicts with camelCase keys.
    """
    return _load_csv("domain_coverage_entries.csv", case)


def load_domain_elaborations(case: str = "case1") -> list[dict]:
    """Load domain elaboration entries from domain_elaboration_entries.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of elaboration dicts with camelCase keys.
    """
    return _load_csv("domain_elaboration_entries.csv", case)


def load_implementation_mappings(case: str = "case1") -> list[dict]:
    """Load implementation mappings from implementation_mappings.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of mapping dicts with camelCase keys.
    """
    return _load_csv("implementation_mappings.csv", case)


def load_conditional_extensions(case: str = "case1") -> list[dict]:
    """Load conditional extensions from conditional_extensions.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of extension dicts with camelCase keys.
    """
    return _load_csv("conditional_extensions.csv", case)


def load_regulatory_interactions(case: str = "case1") -> list[dict]:
    """Load regulatory interactions from regulatory_interactions.csv.

    Args:
        case: Case identifier to filter by. Defaults to ``"case1"``.

    Returns:
        List of interaction dicts with camelCase keys.
    """
    return _load_csv("regulatory_interactions.csv", case)


__all__ = [
    "load_clauses",
    "load_regulations",
    "load_domains",
    "load_subdomains",
    "load_articles",
    "load_clause_subdomain_mapping",
    "load_complementarity_analyses",
    "load_regulatory_timelines",
    "load_company_context",
    "load_domain_coverages",
    "load_domain_elaborations",
    "load_implementation_mappings",
    "load_conditional_extensions",
    "load_regulatory_interactions",
]
