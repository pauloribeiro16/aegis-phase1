"""n01_parse_inputs — Read ontology YAML, intake, taxonomy, and ALL CSVs via loaders."""

import logging
import sys
from pathlib import Path

from aegis_phase1.parsers.applicability_rules import determine_applicability
from aegis_phase1.parsers.intake import (
    find_common_dir,
    load_markdown,
    load_ontology,
)
from aegis_phase1.state import Phase1State

logger = logging.getLogger(__name__)


def n01_parse_inputs(state: Phase1State) -> dict:
    """Parse all input files: ontology, markdown, and CSVs via typed loaders.

    Reads ontology YAML, intake markdown, taxonomy markdown, and all Phase 1
    CSV data files.  Company context is extracted from the CSV and merged with
    ontology data for backward compatibility.

    Args:
        state: Current Phase 1 workflow state.

    Returns:
        Dict with parsed inputs to be merged into state.
    """
    case_path = state.get("case_path", "")
    case_config = state.get("case_config", {})
    errors: list[str] = []

    logger.info("[n01] Parsing inputs for case_path=%s", case_path)

    # ── Ontology + markdown ──────────────────────────────────────────
    common_dir = find_common_dir(case_path, case_config)
    ontology = load_ontology(common_dir)
    intake_md = load_markdown(common_dir, "01_Company_Context.md")
    taxonomy_md = load_markdown(common_dir, "00_Taxonomy_Reference.md")

    # ── CSV loaders (SC-2026-45) ────────────────────────────────────
    try:
        sys.path.insert(0, str(Path(case_path)))
        from data.load_phase1_data import (
            load_clause_subdomain_mapping,
            load_clauses,
            load_company_context,
            load_complementarity_analyses,
            load_conditional_extensions,
            load_domain_coverages,
            load_domain_elaborations,
            load_domains,
            load_implementation_mappings,
            load_regulations,
            load_regulatory_interactions,
            load_subdomains,
        )

        regulations = load_regulations()
        clauses = load_clauses()
        domains = load_domains()
        subdomains = load_subdomains()
        clause_mapping = load_clause_subdomain_mapping()
        complementarity = load_complementarity_analyses()
        company_ctx_rows = load_company_context()
        domain_coverages = load_domain_coverages()
        domain_elaborations = load_domain_elaborations()
        impl_mappings = load_implementation_mappings()
        cond_extensions = load_conditional_extensions()
        reg_interactions = load_regulatory_interactions()

        logger.info(
            "[n01] Loaded CSVs: regulations=%d, clauses=%d, domains=%d, "
            "subdomains=%d, clause_mapping=%d, complementarity=%d, "
            "company_ctx=%d, domain_coverages=%d, domain_elaborations=%d, "
            "impl_mappings=%d, cond_extensions=%d, reg_interactions=%d",
            len(regulations),
            len(clauses),
            len(domains),
            len(subdomains),
            len(clause_mapping),
            len(complementarity),
            len(company_ctx_rows),
            len(domain_coverages),
            len(domain_elaborations),
            len(impl_mappings),
            len(cond_extensions),
            len(reg_interactions),
        )
    except Exception:
        logger.exception("[n01] Failed to load CSV data")
        errors.append("n01_parse_inputs: CSV load failed")
        regulations = []
        clauses = []
        domains = []
        subdomains = []
        clause_mapping = []
        complementarity = []
        company_ctx_rows = []
        domain_coverages = []
        domain_elaborations = []
        impl_mappings = []
        cond_extensions = []
        reg_interactions = []

    # ── Extract company_context from CSV (primary source) + ontology fallback ──
    # CSV column names use camelCase; the contract requires snake_case field names.
    # Map CSV columns to the canonical CompanyContext schema.
    company_context = {}
    if company_ctx_rows:
        row = company_ctx_rows[0]
        # dataTypes like "Emails;Names;Passwords;Task content" indicates personal data
        has_personal_data = bool(row.get("dataTypes", "").strip())
        has_ai = row.get("aiSystems", "").upper() in ("YES", "TRUE", "1")
        has_financial = row.get("financialEntity", "").upper() in ("YES", "TRUE", "1")
        # NIS2 sector — only set if CSV marks it
        nis2_sector = (
            row.get("industry", "")
            if row.get("criticalInfrastructure", "").upper() in ("YES", "TRUE", "1")
            else ""
        )
        # CRA applies if company places digital products in EU — inferred from size + dataTypes
        places_digital = row.get("industry", "").lower() in (
            "technology",
            "saas",
            "software",
            "iot",
        )

        company_context = {
            "sector": row.get("industry", ""),
            "size": row.get("size", ""),
            "processes_personal_data": has_personal_data,
            "places_digital_products_eu": places_digital,
            "dora_financial_entity": has_financial,
            "nis2_sector": nis2_sector,
            "aiact_high_risk_system": has_ai,
            "technological_control_plane": row.get("technologicalControlPlane", "")
            or row.get("location", ""),
            "employees": int(row.get("employeeCount", 0) or 0),
        }
    else:
        company_context = ontology.get("company", {})

    # ── Extract applicable regulations using deterministic rules ──
    # Normalize flag names to snake_case for applicability_rules
    cc_for_rules = dict(company_context)
    cc_for_rules.setdefault(
        "processes_personal_data", company_context.get("processes_personal_data", False)
    )
    cc_for_rules.setdefault(
        "places_digital_products_eu", company_context.get("places_digital_products_eu", False)
    )
    cc_for_rules.setdefault(
        "dora_financial_entity", company_context.get("dora_financial_entity", False)
    )
    cc_for_rules.setdefault("nis2_sector", company_context.get("nis2_sector", ""))
    cc_for_rules.setdefault(
        "aiact_high_risk_system", company_context.get("aiact_high_risk_system", False)
    )
    cc_for_rules.setdefault("employees", company_context.get("employees", 0))

    applicability = determine_applicability(cc_for_rules)
    applicable_regulations = [
        reg_id for reg_id, info in applicability.items() if info.get("applicable")
    ]

    if not applicable_regulations:
        # Safety net: at least the regulations present in the case data
        applicable_regulations = [r.get("regulationId", r.get("id", "")) for r in regulations]
        applicable_regulations = [r for r in applicable_regulations if r]
        logger.warning("[n01] No regulations matched applicability rules; using all loaded")

    # ── Build security_control_domains from domains + subdomains ──
    security_control_domains: list[dict] = []
    for d in domains:
        domain_id = d.get("domainId", d.get("id", ""))
        for sd in subdomains:
            if sd.get("domainId", sd.get("parentId", "")) == domain_id or not sd.get("domainId"):
                sd_id = sd.get("subDomainId", sd.get("id", ""))
                sd_name = sd.get("name", "")
                if sd_id:
                    security_control_domains.append(
                        {
                            "domainId": domain_id,
                            "subDomainId": sd_id,
                            "name": sd_name,
                            "description": sd.get("description", ""),
                            "referenceSource": sd.get("referenceSource", ""),
                        }
                    )

    logger.info("[n01] Built %d security_control_domains", len(security_control_domains))

    return {
        "case_path": case_path,
        "case_config": case_config,
        "ontology": ontology,
        "intake_markdown": intake_md,
        "taxonomy_markdown": taxonomy_md,
        "company_context": company_context,
        "applicable_regulations": applicable_regulations,
        "regulations": regulations,
        # NOTE: regulatory_clauses is intentionally NOT set here.
        # b01_load_regulations and b02_load_clauses_batch will populate it
        # (with applicable-filtered + enriched clauses).
        "security_control_domains": security_control_domains,
        "clause_subdomain_mapping": clause_mapping,
        "complementarity_analyses_data": complementarity,
        "domain_coverages_data": domain_coverages,
        "domain_elaborations_data": domain_elaborations,
        "implementation_mappings_data": impl_mappings,
        "conditional_extensions_data": cond_extensions,
        "regulatory_interactions_data": reg_interactions,
        # Raw clauses for b02 to read (via the _data suffix to avoid add-merge)
        "raw_clauses": clauses,
        "current_phase": "PARSED",
        "errors": errors,
        "degraded": False,
    }
