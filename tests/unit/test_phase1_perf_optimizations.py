"""Tests for Phase 1 performance optimizations (SC-2026-30)."""

import os
import tempfile
import time
from pathlib import Path


def test_n13_skips_doc04():
    from aegis_phase1.shared.document_producer import PHASE1_TEMPLATES_N13

    assert "04_Company_Context_Assessment.md" not in PHASE1_TEMPLATES_N13
    assert len(PHASE1_TEMPLATES_N13) == 3


def test_num_ctx_default_8192():
    from aegis_phase1.llm.ollama import OllamaClient

    c = OllamaClient({})
    assert c.num_ctx == 8192


def test_num_ctx_override():
    from aegis_phase1.llm.ollama import OllamaClient

    c = OllamaClient({"num_ctx": 4096})
    assert c.num_ctx == 4096


def test_idempotency_skips_recent_file():
    from aegis_phase1.shared.document_producer import DocumentProducer

    with tempfile.TemporaryDirectory() as tmp:
        tpl_dir = Path(tmp) / "templates" / "phase1"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "T01_test.md").write_text("# Test\n\n[placeholder]")

        out_dir = Path(tmp) / "output" / "phase1"
        out_dir.mkdir(parents=True)
        (out_dir / "T01_test_filled.md").write_text("OLD CONTENT")

        producer = DocumentProducer(tmp, {}, phase=1)
        result = producer.write_output("T01_test.md", "NEW CONTENT", force_rebuild=False)

        content = (out_dir / "T01_test_filled.md").read_text()
        assert content == "OLD CONTENT", f"File was overwritten: {content[:80]}"
        assert result == "T01_test_filled.md"


def test_idempotency_overwrites_old_file():
    from aegis_phase1.shared.document_producer import DocumentProducer

    with tempfile.TemporaryDirectory() as tmp:
        tpl_dir = Path(tmp) / "templates" / "phase1"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "T02_test.md").write_text("# Test\n\n[placeholder]")

        out_dir = Path(tmp) / "output" / "phase1"
        out_dir.mkdir(parents=True)
        old_path = out_dir / "T02_test_filled.md"
        old_path.write_text("OLD CONTENT")
        old_time = time.time() - 7200
        os.utime(old_path, (old_time, old_time))

        producer = DocumentProducer(tmp, {}, phase=1)
        result = producer.write_output("T02_test.md", "NEW CONTENT", force_rebuild=False)

        content = old_path.read_text()
        assert content != "OLD CONTENT", "File was NOT overwritten despite being old"
        assert result == "T02_test_filled.md"


def test_force_rebuild_bypasses_idempotency():
    from aegis_phase1.shared.document_producer import DocumentProducer

    with tempfile.TemporaryDirectory() as tmp:
        tpl_dir = Path(tmp) / "templates" / "phase1"
        tpl_dir.mkdir(parents=True)
        (tpl_dir / "T03_test.md").write_text("# Test\n\n[placeholder]")

        out_dir = Path(tmp) / "output" / "phase1"
        out_dir.mkdir(parents=True)
        (out_dir / "T03_test_filled.md").write_text("OLD CONTENT")

        producer = DocumentProducer(tmp, {}, phase=1)
        result = producer.write_output("T03_test.md", "NEW CONTENT", force_rebuild=True)

        content = (out_dir / "T03_test_filled.md").read_text()
        assert content != "OLD CONTENT", "force_rebuild should overwrite"
        assert result == "T03_test_filled.md"
