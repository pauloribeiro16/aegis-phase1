"""doc_06 — render 06_Clause_Mapping_Matrix.md.

Renders the clause-to-sub-domain mapping table from
``state.ontology.clause_mappings``. Each row corresponds to a single
clause, with columns: clause_id, regulation, article, description,
subdomain, normative_strength, obligated_party.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from aegis_phase1.v2.output._common import (
    generate_frontmatter,
    markdown_table,
    write_output,
)

logger = logging.getLogger(__name__)

_FILENAME = "06_Clause_Mapping_Matrix.md"


def render_doc_06(state: dict[str, Any], output_dir: str) -> dict[str, str]:
    """Render document 06 (clause-to-sub-domain mapping matrix).

    Args:
        state: Pipeline state.
        output_dir: Directory in which the document is written.

    Returns:
        Mapping ``AEGIS-P1-06`` -> absolute file path.
    """
    ontology = state.get("ontology") or {}
    clauses = ontology.get("clause_mappings", []) if isinstance(ontology, Mapping) else []
    regs = ontology.get("regulations", []) if isinstance(ontology, Mapping) else []

    parts: list[str] = []
    parts.append("# AEGIS-P1-06 Clause Mapping Matrix\n")
    parts.append("## 1. PURPOSE\n")
    parts.append(
        "Map every regulatory clause from the in-scope regulations "
        "to a security sub-domain. The mapping is the canonical "
        "input for the coverage matrix (07) and the Proportionality "
        "Profile (07b).\n"
    )

    parts.append("## 2. SUMMARY\n")
    parts.append(f"- **Total clauses mapped:** {len(clauses)}")
    per_reg: dict[str, int] = {}
    for c in clauses:
        if not isinstance(c, Mapping):
            continue
        per_reg[c.get("regulation_id", "?")] = per_reg.get(c.get("regulation_id", "?"), 0) + 1
    parts.append(
        "- **Clauses per regulation:** " + ", ".join(f"{k}={v}" for k, v in sorted(per_reg.items()))
    )
    parts.append("")

    parts.append("## 3. CLAUSE-TO-SUBDOMAIN MAPPINGS\n")
    parts.append(
        markdown_table(
            [
                "Clause ID",
                "Regulation",
                "Article",
                "Description",
                "Sub-domain",
                "Normative Strength",
                "Obligated Party",
            ],
            [_clause_row(c, regs) for c in clauses if isinstance(c, Mapping)],
        )
    )
    parts.append("")

    parts.append("## 4. NOTES\n")
    parts.append(
        "- Normative strength is encoded 1-3 in the ontology "
        "(see ``phase1_schema.yaml`` for the mapping).\n"
    )
    parts.append(
        "- Sub-domain IDs follow the ``D-XX.Y`` notation; see "
        "AEGIS-COMMON-00 (Taxonomy Reference).\n"
    )

    body = "\n".join(parts)
    frontmatter = generate_frontmatter(
        document_id="AEGIS-P1-06",
        title="Clause Mapping Matrix",
    )
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_06: wrote %s (rows=%d)", path, len(clauses))
    return {"AEGIS-P1-06": path}


def _clause_row(
    clause: Mapping[str, Any],
    regs: list[Any],
) -> tuple[str, str, str, str, str, str, str]:
    """Normalise a clause dict into the 7-column row tuple."""
    reg_id = clause.get("regulation_id", "")
    reg_abbr = _find_reg_abbreviation(regs, reg_id)
    article = str(clause.get("article", ""))
    description = str(clause.get("description", ""))
    subdomain = str(clause.get("maps_to_subdomain", ""))
    norm = clause.get("normative_strength")
    norm_str = str(norm) if norm is not None else "-"
    obligated = clause.get("obligated_party", "-")
    if isinstance(obligated, list):
        obligated = ", ".join(str(o) for o in obligated)
    return (
        str(clause.get("clause_id", "-")),
        reg_abbr,
        article,
        description,
        subdomain,
        norm_str,
        str(obligated),
    )


def _find_reg_abbreviation(regs: list[Any], reg_id: str) -> str:
    """Return ``abbreviation`` (or last path segment of ``id``) for ``reg_id``."""
    for reg in regs:
        if isinstance(reg, Mapping) and reg.get("id") == reg_id:
            abbr = reg.get("abbreviation")
            if abbr:
                return str(abbr)
            return str(reg_id).split("/")[-1]
    return str(reg_id).split("/")[-1]


__all__ = ["render_doc_06"]
