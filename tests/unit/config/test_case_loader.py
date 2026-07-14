"""Tests for config/case_loader."""


class TestLoadCaseYaml:
    def test_loads_case1_config(self, case1_path):
        from aegis_phase1.config.case_loader import load_case_yaml

        config = load_case_yaml(case1_path)
        assert isinstance(config, dict)
        assert config.get("case") == "case1"
        assert "llm" in config

    def test_load_case_config_typed(self, case1_path):
        from aegis_phase1.config.case_loader import load_case_config

        config = load_case_config(case1_path)
        assert config.case == "case1"
        assert config.llm.provider == "ollama"
        assert config.llm.model == "gemma4:e4b"  # expanded from .env

    def test_returns_empty_dict_for_missing(self, tmp_path):
        from aegis_phase1.config.case_loader import load_case_yaml

        result = load_case_yaml(tmp_path / "nonexistent")
        assert result == {}

    def test_raises_on_missing_with_typed(self, tmp_path):
        import pytest

        from aegis_phase1.config.case_loader import load_case_config

        with pytest.raises(FileNotFoundError):
            load_case_config(tmp_path / "nonexistent")


class TestDefaults:
    def test_defaults_have_expected_values(self):
        from aegis_phase1.config.defaults import (
            DEFAULT_LLM_MODEL,
            DEFAULT_LLM_NUM_CTX,
            DEFAULT_LLM_PROVIDER,
            OLLAMA_BASE_URL,
        )

        assert DEFAULT_LLM_PROVIDER == "ollama"
        assert DEFAULT_LLM_NUM_CTX == 8192
        assert isinstance(DEFAULT_LLM_MODEL, str)
        assert OLLAMA_BASE_URL.startswith("http")
