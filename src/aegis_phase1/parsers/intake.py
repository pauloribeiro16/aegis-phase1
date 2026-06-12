import os

import yaml


def load_ontology(case_common_path: str) -> dict:
    ontology_path = os.path.join(case_common_path, "phase1_ontology.yaml")
    if os.path.exists(ontology_path):
        with open(ontology_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def load_markdown(case_common_path: str, filename: str) -> str:
    filepath = os.path.join(case_common_path, filename)
    if os.path.exists(filepath):
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    return ""


def extract_company_profile(ontology: dict) -> dict:
    company = ontology.get("company", {})
    return {
        "sector": company.get("sector", ""),
        "size": company.get("size", ""),
        "processes_personal_data": company.get("processes_personal_data", False),
        "places_digital_products_eu": company.get("places_digital_products_eu", False),
        "dora_financial_entity": company.get("dora_financial_entity", False),
        "nis2_sector": company.get("nis2_sector"),
        "aiact_high_risk_system": company.get("aiact_high_risk_system", False),
        "technological_control_plane": company.get("technological_control_plane", ""),
    }


_CASE_DIR_MAP = {
    "case1": "Case_01_TinyTask_SaaS",
    "case2": "Case_02_SecureBorder_Solutions",
    "case3": "Case_03_OmniBank_Financial",
}

_DEFAULT_METHODOLOGY_CASES = ""


def find_common_dir(case_path: str, case_config: dict | None = None) -> str:
    candidates = [
        os.path.join(case_path, "00_COMMON"),
        os.path.join(case_path, "context"),
        os.path.join(case_path, "01_PHASE1_CONTEXT", "..", "00_COMMON"),
    ]
    methodology_path = os.getenv("METHODOLOGY_CASES_PATH") or (
        case_config.get("methodology_path") if case_config else None
    )
    if not methodology_path:
        methodology_path = _DEFAULT_METHODOLOGY_CASES
    if methodology_path:
        for key, case_dir in _CASE_DIR_MAP.items():
            if key in os.path.basename(os.path.normpath(case_path)).lower():
                candidates.append(os.path.join(methodology_path, case_dir, "00_COMMON"))
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.isdir(normalized) and os.path.exists(
            os.path.join(normalized, "phase1_ontology.yaml")
        ):
            return normalized
    return os.path.join(case_path, "00_COMMON")
