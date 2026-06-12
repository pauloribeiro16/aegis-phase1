"""Tests for LLM client layer."""


class TestCreateLLMClient:
    def test_create_ollama_client(self):
        from aegis_phase1.llm.base import create_llm_client

        config = {"provider": "ollama", "base_url": "http://localhost:11434", "model": "test-model"}
        client = create_llm_client(config)
        assert client is not None
        assert callable(client.generate)

    def test_create_llm_client_with_mock_env(self, monkeypatch):
        monkeypatch.setenv("MOCK_LLM", "true")
        from aegis_phase1.llm.base import create_llm_client

        config = {"provider": "ollama", "base_url": "http://localhost:11434", "model": "test-model"}
        client = create_llm_client(config)
        assert client is not None


class TestOllamaClient:
    def test_can_instantiate(self):
        from aegis_phase1.llm.ollama import OllamaClient

        client = OllamaClient({"base_url": "http://localhost:11434", "model": "test"})
        assert client.model == "test"
        assert client.base_url == "http://localhost:11434"

    def test_generate_returns_dict(self):
        from aegis_phase1.llm.ollama import OllamaClient

        client = OllamaClient({"base_url": "http://localhost:11434", "model": "test"})
        result = client.generate("hello", system="be brief")
        assert isinstance(result, dict)
        assert "raw" in result
