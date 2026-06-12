def determine_applicability(company_context: dict) -> dict:
    gdpr_applicable = company_context.get("processes_personal_data", False) or company_context.get(
        "eu_data_subjects", False
    )

    cra_applicable = company_context.get("places_digital_products_eu", False)

    nis2_sectors = ["energy", "transport", "banking", "health", "water", "digital"]
    sector = company_context.get("nis2_sector", "")
    employees = company_context.get("employees", 0)
    nis2_applicable = (sector.lower() in nis2_sectors if sector else False) and (
        employees >= 50 or company_context.get("revenue_10m", False)
    )

    dora_applicable = company_context.get("dora_financial_entity", False)

    aiact_applicable = company_context.get("aiact_high_risk_system", False)

    return {
        "GDPR": {
            "applicable": gdpr_applicable,
            "confidence": "HIGH",
            "obligated_party": "CONTROLLER",
        },
        "CRA": {
            "applicable": cra_applicable,
            "confidence": "HIGH",
            "obligated_party": "MANUFACTURER",
        },
        "NIS2": {
            "applicable": nis2_applicable,
            "confidence": "HIGH",
            "obligated_party": "ESSENTIAL_OR_IMPORTANT_ENTITY",
        },
        "DORA": {
            "applicable": dora_applicable,
            "confidence": "HIGH",
            "obligated_party": "FINANCIAL_ENTITY",
        },
        "AIACT": {
            "applicable": aiact_applicable,
            "confidence": "HIGH",
            "obligated_party": "PROVIDER",
        },
    }
