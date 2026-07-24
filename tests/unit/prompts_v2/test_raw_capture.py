"""Tests for raw call capture (CORR-061 S4).

Exercises :meth:`Phase1LLMInvoker._persist_raw_call` directly. The
method is a static helper, so we don't need a full invoker stack
(Ollama / PromptLoader / etc.) — only an ``AEGIS_RAW_OUTPUT_DIR``
env var pointing at a tmp dir.

Contract:
  * Creates ``<dir>/<spec_id>/<ts>__attempt<N>.md`` AND ``.json``.
  * The ``.md`` has YAML frontmatter + the full system/user prompts
    + the raw response.
  * The ``.json`` has the metadata + a 200-char preview of the
    raw response.
  * The spec-id subdirectory is created on demand (no need to
    pre-create it).
"""
import json

from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker


class TestPersistRawCall:
    def test_creates_md_and_json_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGIS_RAW_OUTPUT_DIR", str(tmp_path))
        Phase1LLMInvoker._persist_raw_call(
            spec_id="P1B-LLM-01-INTERPRETATION",
            attempt=1,
            prompt_system="You are a compliance analyst.",
            prompt_user="Analyse GDPR Art. 30.",
            raw_response="## Status\n- applicable: YES\n- confidence: HIGH\n",
            status="OK",
            latency_ms=12345.6,
            model="gemma4:e2b",
        )
        files = list((tmp_path / "P1B-LLM-01-INTERPRETATION").iterdir())
        assert len(files) == 2
        md_files = [f for f in files if f.suffix == ".md"]
        json_files = [f for f in files if f.suffix == ".json"]
        assert len(md_files) == 1
        assert len(json_files) == 1
        # Filename format
        assert "__attempt1.md" in md_files[0].name
        assert "__attempt1.json" in json_files[0].name

    def test_md_contains_yaml_frontmatter_and_prompt(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGIS_RAW_OUTPUT_DIR", str(tmp_path))
        Phase1LLMInvoker._persist_raw_call(
            spec_id="P1B-LLM-01",
            attempt=2,
            prompt_system="sys",
            prompt_user="user",
            raw_response="resp",
            status="OK",
            latency_ms=100.0,
            model="gemma4:e2b",
        )
        md_file = next((tmp_path / "P1B-LLM-01").glob("*.md"))
        content = md_file.read_text()
        assert content.startswith("---")
        assert "spec_id: P1B-LLM-01" in content
        assert "attempt: 2" in content
        assert "## Prompt (system)" in content
        assert "## Prompt (user)" in content
        assert "## Raw response" in content
        assert "sys" in content
        assert "user" in content
        assert "resp" in content

    def test_json_contains_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGIS_RAW_OUTPUT_DIR", str(tmp_path))
        Phase1LLMInvoker._persist_raw_call(
            spec_id="P1B-LLM-01",
            attempt=3,
            prompt_system="sys",
            prompt_user="user",
            raw_response="r" * 500,
            status="INSUFFICIENT_EVIDENCE",
            latency_ms=50.0,
            model="gemma4:e2b",
            error="response too short",
        )
        json_file = next((tmp_path / "P1B-LLM-01").glob("*.json"))
        data = json.loads(json_file.read_text())
        assert data["spec_id"] == "P1B-LLM-01"
        assert data["attempt"] == 3
        assert data["status"] == "INSUFFICIENT_EVIDENCE"
        assert data["error"] == "response too short"
        assert data["raw_response_chars"] == 500
        assert data["raw_response_preview"] == "r" * 200

    def test_creates_subdir_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AEGIS_RAW_OUTPUT_DIR", str(tmp_path))
        target = tmp_path / "P1C-LLM-03-STRATEGIC-SYNTHESIS"
        assert not target.exists()
        Phase1LLMInvoker._persist_raw_call(
            spec_id="P1C-LLM-03-STRATEGIC-SYNTHESIS",
            attempt=1,
            prompt_system="s",
            prompt_user="u",
            raw_response="r",
            status="OK",
            latency_ms=10.0,
            model="gemma4:e2b",
        )
        assert target.exists()
        assert target.is_dir()
        assert len(list(target.iterdir())) == 2
