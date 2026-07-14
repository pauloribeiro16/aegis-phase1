"""Load company input from structured YAML files (input/*.yaml)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class YamlInputLoader:
    """Load all YAML files under a case's input/ directory."""

    def __init__(self, case_path: str | Path):
        self.case_path = Path(case_path)
        self.input_root = self.case_path / "input"
        self._errors: list[str] = []

    def load(self) -> dict[str, Any]:
        return {
            "company": self._load_company(),
            "business_goals": self._load_business_goals(),
            "stakeholders": self._load_stakeholders(),
            "architecture": self._load_architecture(),
            "regulatory": self._load_regulatory(),
            "errors": list(self._errors),
        }

    def _read_yaml(self, path: Path, required: bool = True) -> dict | None:
        if not path.exists():
            if required:
                self._errors.append(f"Missing required YAML: {path}")
            return None
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            self._errors.append(f"YAML parse error in {path}: {exc}")
            return None
        if not isinstance(data, dict):
            self._errors.append(f"YAML root not a dict in {path}: got {type(data).__name__}")
            return None
        return data

    def _load_company(self) -> dict | None:
        return self._read_yaml(self.input_root / "company" / "classification.yaml")

    def _load_business_goals(self) -> dict | None:
        return self._read_yaml(self.input_root / "company" / "business_goals.yaml", required=False)

    def _load_stakeholders(self) -> dict | None:
        return self._read_yaml(self.input_root / "company" / "stakeholders.yaml", required=False)

    def _load_architecture(self) -> dict[str, Any]:
        arch_root = self.input_root / "architecture"
        return {
            "systems": self._read_yaml(arch_root / "systems.yaml", required=False) or {},
            "data_stores": self._read_yaml(arch_root / "data_stores.yaml", required=False) or {},
            "data_flows": self._read_yaml(arch_root / "data_flows.yaml", required=False) or {},
            "cloud_services": self._read_yaml(arch_root / "cloud_services.yaml", required=False) or {},
            "auth_systems": self._read_yaml(arch_root / "auth_systems.yaml", required=False) or {},
        }

    def _load_regulatory(self) -> dict | None:
        return self._read_yaml(self.input_root / "regulatory" / "applicability.yaml", required=False)


def has_yaml_input(case_path: str | Path) -> bool:
    """True if a case has structured YAML input (input/company/classification.yaml)."""
    return (Path(case_path) / "input" / "company" / "classification.yaml").exists()