"""Test YAML input loader."""
from pathlib import Path
from aegis_phase1.v2.loader.yaml_input_loader import YamlInputLoader, has_yaml_input


def test_has_yaml_input_false_for_empty(tmp_path):
    assert has_yaml_input(tmp_path) is False


def test_has_yaml_input_true_when_classification_exists(tmp_path):
    (tmp_path / "input" / "company").mkdir(parents=True)
    (tmp_path / "input" / "company" / "classification.yaml").write_text("company: {}\n")
    assert has_yaml_input(tmp_path) is True


def test_load_missing_required_reports_error(tmp_path):
    loader = YamlInputLoader(tmp_path)
    result = loader.load()
    assert any("Missing required YAML" in e for e in result["errors"])


def test_load_valid_files(tmp_path):
    input_root = tmp_path / "input"
    (input_root / "company").mkdir(parents=True)
    (input_root / "company" / "classification.yaml").write_text(
        "company:\n  name: Test Co\n  scale: MICRO\n"
    )
    (input_root / "company" / "business_goals.yaml").write_text("goals: []\n")
    (input_root / "company" / "stakeholders.yaml").write_text("stakeholders: []\n")
    (input_root / "architecture").mkdir(parents=True)
    for f in ["systems", "data_stores", "data_flows", "cloud_services", "auth_systems"]:
        (input_root / "architecture" / f"{f}.yaml").write_text("test: data\n")
    (input_root / "regulatory").mkdir(parents=True)
    (input_root / "regulatory" / "applicability.yaml").write_text("test: data\n")

    loader = YamlInputLoader(tmp_path)
    result = loader.load()
    assert result["errors"] == []
    assert result["company"]["company"]["name"] == "Test Co"


def test_load_invalid_yaml(tmp_path):
    (tmp_path / "input" / "company").mkdir(parents=True)
    (tmp_path / "input" / "company" / "classification.yaml").write_text("invalid: : yaml\n")

    loader = YamlInputLoader(tmp_path)
    result = loader.load()
    assert any("YAML parse error" in e for e in result["errors"])


def test_optional_files_can_be_missing(tmp_path):
    (tmp_path / "input" / "company").mkdir(parents=True)
    (tmp_path / "input" / "company" / "classification.yaml").write_text("company: {}\n")
    # business_goals and stakeholders are optional

    loader = YamlInputLoader(tmp_path)
    result = loader.load()
    assert result["errors"] == []
    assert result["business_goals"] is None