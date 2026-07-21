"""doc_06 — render 06_Clause_Mapping_Matrix.md.

Renders the clause-to-sub-domain mapping table from the canonical
``ClauseMappingContext`` (CORR-039-T2). Pre-CORR-039 this read from
``state.ontology.clause_mappings`` — which the v1-compat shim never
populated, so Doc 06 always rendered 0 rows. Post-CORR-039 the
context builder walks the preproc catalog + SRs and produces
~222 rows for case1 (72 GDPR + 150 CRA).
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.context.clause_mapping_context import (
    ClauseMappingContext,
    ClauseMappingEntry,
    build_clause_mapping_context,
)
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
        state: Pipeline state. Reads v2_* keys populated by
            _load_v2_catalog (CORR-037-T3a + CORR-039-T1).
        output_dir: Directory in which the document is written.

    Returns:
        Mapping ``AEGIS-P1-06`` -> absolute file path.
    """
    ctx = build_clause_mapping_context(state)
    return _render_from_context(ctx, output_dir)


def _render_from_context(
    ctx: ClauseMappingContext,
    output_dir: str,
) -> dict[str, str]:
    """Render Doc 06 from a pre-built ClauseMappingContext.

    Exposed for direct invocation (--run-clauses CLI flag, T5).
    """
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
    parts.append(f"- **Total clauses mapped:** {ctx.total_clauses}")
    parts.append(
        "- **Clauses per regulation:** "
        + ", ".join(f"{k}={v}" for k, v in sorted(ctx.per_reg_count.items()))
    )
    if ctx.unmapped_count:
        parts.append(
            f"- **Unmapped clauses (no SR link):** {ctx.unmapped_count} "
            "(see §4 NOTES)"
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
            [_clause_row(e) for e in ctx.entries],
        )
    )
    parts.append("")

    parts.append("## 4. NOTES\n")
    parts.append(
        "- Normative strength is encoded 1-3 in the ontology "
        "(see ``phase1_schema.yaml`` for the mapping). Default 2 (medium) "
        "until clause-level metadata is enriched.\n"
    )
    parts.append(
        "- Sub-domain IDs follow the ``D-XX.Y`` notation; see "
        "AEGIS-COMMON-00 (Taxonomy Reference).\n"
    )
    if ctx.unmapped_count:
        parts.append(
            f"- {ctx.unmapped_count} clause(s) had no SR link and are "
            "excluded from the mapping table. These orphans are listed "
            "in the next contract (CORR-040) for review.\n"
        )

    body = "\n".join(parts)
    frontmatter = generate_frontmatter(
        document_id="AEGIS-P1-06",
        title="Clause Mapping Matrix",
    )
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info("render_doc_06: wrote %s (rows=%d)", path, len(ctx.entries))
    return {"AEGIS-P1-06": path}


def _clause_row(entry: ClauseMappingEntry) -> tuple[str, str, str, str, str, str, str]:
    """Normalise a ClauseMappingEntry into the 7-column row tuple."""
    reg_abbr = entry.regulation or "-"
    article = entry.article or "-"
    # Truncate title for readability in the table
    description = entry.title or "-"
    if len(description) > 80:
        description = description[:77] + "..."
    subdomain = entry.maps_to_subdomain or entry.subdomain_id or "-"
    norm_str = str(entry.normative_strength)
    obligated = entry.obligated_party or "-"
    return (
        entry.clause_id,
        reg_abbr,
        article,
        description,
        subdomain,
        norm_str,
        obligated,
    )


__all__ = ["render_doc_06"]
