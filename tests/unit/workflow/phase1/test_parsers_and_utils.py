"""Unit tests for parsers (applicability_rules, intake) and constants."""

from aegis_phase1.constants import MAX_INTAKE_LEN, MAX_RESPONSE_TOKENS, MAX_TAXONOMY_LEN
from aegis_phase1.parsers.applicability_rules import determine_applicability
from aegis_phase1.parsers.intake import (
    extract_company_profile,
    load_markdown,
)


def _ctx(**kwargs):
    defaults = {
        "processes_personal_data": False,
        "eu_data_subjects": False,
        "places_digital_products_eu": False,
        "nis2_sector": "",
        "employees": 0,
        "dora_financial_entity": False,
        "aiact_high_risk_system": False,
    }
    defaults.update(kwargs)
    return defaults


def test_gdpr_applicable_when_personal_data():
    result = determine_applicability(_ctx(processes_personal_data=True))
    assert result["GDPR"]["applicable"] is True
    assert result["GDPR"]["obligated_party"] == "CONTROLLER"


def test_gdpr_applicable_when_eu_data_subjects():
    result = determine_applicability(_ctx(eu_data_subjects=True))
    assert result["GDPR"]["applicable"] is True


def test_gdpr_not_applicable_when_neither():
    result = determine_applicability(_ctx())
    assert result["GDPR"]["applicable"] is False


def test_cra_applicable_when_digital_products_eu():
    result = determine_applicability(_ctx(places_digital_products_eu=True))
    assert result["CRA"]["applicable"] is True
    assert result["CRA"]["obligated_party"] == "MANUFACTURER"


def test_cra_not_applicable_when_false():
    result = determine_applicability(_ctx())
    assert result["CRA"]["applicable"] is False


def test_nis2_applicable_when_sector_and_employees():
    result = determine_applicability(_ctx(nis2_sector="energy", employees=100))
    assert result["NIS2"]["applicable"] is True
    assert result["NIS2"]["obligated_party"] == "ESSENTIAL_OR_IMPORTANT_ENTITY"


def test_nis2_not_applicable_when_small_company():
    result = determine_applicability(_ctx(nis2_sector="energy", employees=10))
    assert result["NIS2"]["applicable"] is False


def test_nis2_not_applicable_when_wrong_sector():
    result = determine_applicability(_ctx(nis2_sector="retail", employees=100))
    assert result["NIS2"]["applicable"] is False


def test_dora_applicable_when_financial_entity():
    result = determine_applicability(_ctx(dora_financial_entity=True))
    assert result["DORA"]["applicable"] is True
    assert result["DORA"]["obligated_party"] == "FINANCIAL_ENTITY"


def test_aiact_applicable_when_high_risk_system():
    result = determine_applicability(_ctx(aiact_high_risk_system=True))
    assert result["AIACT"]["applicable"] is True
    assert result["AIACT"]["obligated_party"] == "PROVIDER"


def test_load_markdown_returns_content(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Hello\n\nWorld", encoding="utf-8")
    result = load_markdown(str(tmp_path), "test.md")
    assert result == "# Hello\n\nWorld"


def test_load_markdown_returns_empty_when_missing(tmp_path):
    result = load_markdown(str(tmp_path), "nonexistent.md")
    assert result == ""


def test_extract_company_profile_with_full_ontology():
    ontology = {
        "company": {
            "sector": "tech",
            "size": "SME",
            "processes_personal_data": True,
            "places_digital_products_eu": True,
            "dora_financial_entity": False,
            "nis2_sector": "digital",
            "aiact_high_risk_system": True,
            "technological_control_plane": "cloud",
        }
    }
    profile = extract_company_profile(ontology)
    assert profile["sector"] == "tech"
    assert profile["processes_personal_data"] is True
    assert profile["aiact_high_risk_system"] is True
    assert profile["technological_control_plane"] == "cloud"


def test_extract_company_profile_with_empty_ontology():
    profile = extract_company_profile({})
    assert profile["sector"] == ""
    assert profile["processes_personal_data"] is False
    assert profile["aiact_high_risk_system"] is False


def test_constants_have_correct_values():
    assert MAX_INTAKE_LEN == 3000
    assert MAX_TAXONOMY_LEN == 2000
    assert MAX_RESPONSE_TOKENS == 2000


def test_all_regulations_returned_by_determine_applicability():
    result = determine_applicability(_ctx())
    assert set(result.keys()) == {"GDPR", "CRA", "NIS2", "DORA", "AIACT"}
    for reg in result.values():
        assert "applicable" in reg
        assert "confidence" in reg
        assert reg["confidence"] == "HIGH"
