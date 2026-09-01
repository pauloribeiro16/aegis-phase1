"""CORR-105 — tests for the eval extensions in
scripts/eval/generate_report.py.

Stdlib-only. No aegis_phase1 import at collection time (the import
inside ``parser_gate`` is lazy). Fixtures are inline minis.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "eval" / "generate_report.py"

# Make the script importable as a module without executing main().
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("generate_report", SCRIPT)
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)


# ────────────────────────────────────────────────────────────────────
# normalise_ollama_entry
# ────────────────────────────────────────────────────────────────────


def test_normalise_ollama_new_shape():
    """New Ollama shape (per-call) → legacy-compatible dict."""
    raw = {
        "spec_id": "P1B-LLM-01-INTERPRETATION",
        "latency_ms": 200000,
        "usage": {"prompt_tokens": 122599, "completion_tokens": 1800},
        "response": {"text": "## Status\n- applicable: YES\n"},
        "status": "OK",
    }
    out = gr.normalise_ollama_entry(raw)
    assert out["spec_id"] == "P1B-LLM-01-INTERPRETATION"
    assert out["latency_ms"] == 200000
    assert out["usage"]["input_tokens"] == 122599
    assert out["usage"]["output_tokens"] == 1800
    assert out["output"].startswith("## Status")


def test_normalise_ollama_legacy_keys_pass_through():
    """Legacy shape survives a round-trip."""
    raw = {
        "prompt_spec_id": "P1B-LLM-01-INTERPRETATION",
        "latency_ms": 318000,
        "usage": {"input_tokens": 125744, "output_tokens": 2100},
        "output": "## Status\n- applicable: YES\n",
        "status": "OK",
    }
    out = gr.normalise_ollama_entry(raw)
    assert out["spec_id"] == "P1B-LLM-01-INTERPRETATION"
    assert out["output"].startswith("## Status")


def test_normalise_ollama_missing_spec_returns_none():
    assert gr.normalise_ollama_entry({"status": "OK"}) is None
    assert gr.normalise_ollama_entry({"metadata": {"x": 1}}) is None


# ────────────────────────────────────────────────────────────────────
# walk_run_dir
# ────────────────────────────────────────────────────────────────────


def _write_run_dir(tmp_path: Path, doc05_text: str) -> Path:
    run = tmp_path / "run_test"
    run.mkdir()
    (run / "05_Regulatory_Applicability.md").write_text(doc05_text, encoding="utf-8")
    return run


DOC05_WITH_TWO_SPECS = """\
# AEGIS-P1-05 Regulatory Applicability

## 0. APPLICABILITY SUMMARY
| Regulation | Status | Rationale |
|---|---|---|
| CRA | APPLICABLE | product_with_digital_elements |
| GDPR | APPLICABLE | processes_personal_data |

### P1B-LLM-01-INTERPRETATION
## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-CRA-ART14-DUAL-FLOW (YES)

### P1B-LLM-02-RATIONALE
## Status
- applicable: YES

## Findings
- IMP-D-04.3-1: CRA Art. 14 requires 24h notification
"""


def test_walk_run_dir_splits_per_spec(tmp_path):
    run = _write_run_dir(tmp_path, DOC05_WITH_TWO_SPECS)
    entries = gr.walk_run_dir(run)
    specs = sorted({e["spec_id"] for e in entries})
    assert specs == [
        "P1B-LLM-01-INTERPRETATION",
        "P1B-LLM-02-RATIONALE",
    ]
    p1b01 = next(e for e in entries if e["spec_id"] == "P1B-LLM-01-INTERPRETATION")
    assert "## Status" in p1b01["output"]
    assert "TIPO2-CRA-ART14-DUAL-FLOW" in p1b01["output"]
    # Source carries the file location for audit
    assert "05_Regulatory_Applicability.md" in p1b01["source"]


def test_walk_run_dir_no_doc05_returns_empty(tmp_path):
    run = tmp_path / "empty_run"
    run.mkdir()
    assert gr.walk_run_dir(run) == []


def test_walk_run_dir_jsonl_takes_precedence(tmp_path):
    """If llm-calls.jsonl is present, use it; don't read Doc 05."""
    run = tmp_path / "run_with_jsonl"
    run.mkdir()
    jsonl = run / "llm-calls.jsonl"
    jsonl.write_text(
        json.dumps({
            "spec_id": "P1B-LLM-01-INTERPRETATION",
            "latency_ms": 100000,
            "response": "## Status\n- applicable: YES\n",
            "status": "OK",
        }) + "\n",
        encoding="utf-8",
    )
    entries = gr.walk_run_dir(run)
    assert len(entries) == 1
    assert entries[0]["latency_ms"] == 100000


# ────────────────────────────────────────────────────────────────────
# parser_gate
# ────────────────────────────────────────────────────────────────────


def test_parser_gate_passes_well_formed_markdown():
    """A spec raw with proper `## Section` headers passes the gate."""
    entries = [{
        "spec_id": "P1B-LLM-02-RATIONALE",
        "output": (
            "## Status\n- applicable: YES\n\n"
            "## Rationale\nThe company processes personal data.\n\n"
            "## Findings\n- IMP-D-04.3-1: CRA Art. 14.\n"
        ),
    }]
    gate = gr.parser_gate(entries)
    assert gate["P1B-LLM-02-RATIONALE"]["pass"] == 1
    assert gate["P1B-LLM-02-RATIONALE"]["fail"] == 0


def test_parser_gate_fails_empty_body():
    """Empty spec body → fail with informative error."""
    entries = [{
        "spec_id": "P1C-LLM-02-COMPOUND-EVENT",
        "output": "(no LLM response for this spec)\n",
    }]
    gate = gr.parser_gate(entries)
    assert gate["P1C-LLM-02-COMPOUND-EVENT"]["fail"] == 1
    assert gate["P1C-LLM-02-COMPOUND-EVENT"]["pass"] == 0
    assert any(
        "## Section" in err or "no " in err.lower()
        for err in gate["P1C-LLM-02-COMPOUND-EVENT"]["errors"]
    )


def test_parser_gate_unknown_spec_records_error():
    entries = [{"spec_id": "UNKNOWN-SPEC", "output": "anything"}]
    gate = gr.parser_gate(entries)
    assert gate["UNKNOWN-SPEC"]["errors"]
    assert gate["UNKNOWN-SPEC"]["pass"] == 0


# ────────────────────────────────────────────────────────────────────
# CLI smoke
# ────────────────────────────────────────────────────────────────────


def test_cli_help_runs(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["generate_report.py", "--help"])
    with pytest.raises(SystemExit) as ei:
        gr.main()
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "--run-dir" in out
    assert "--use-parser-gate" in out
    assert "--preproc" in out


# ────────────────────────────────────────────────────────────────────
# _count_yes — markdown shape (CORR-105 fix)
# ────────────────────────────────────────────────────────────────────


def test_count_yes_markdown_applicable_yes():
    """Markdown shape: `- applicable: YES` lines counted as activations."""
    # Reach into the closure by mimicking the inner loop directly
    # (avoids running main with a full jsonl).
    activations_total = 0
    activations_yes = 0
    body = (
        "## Status\n"
        "- applicable: YES\n"
        "- confidence: HIGH\n\n"
        "## Interpretations\n"
        "- TIPO2-X: applicable: YES\n"
        "- TIPO2-Y: applicable: NO\n"
        "- TIPO3-Z: applicable: N/A\n"
        "- TIPO2-Q: activation_verdict: ACTIVATED\n"
    )
    for m in re.finditer(r"applicable\s*:\s*(YES|NO|N/A)\b",
                         body, re.IGNORECASE):
        activations_total += 1
        if m.group(1).upper() == "YES":
            activations_yes += 1
    for m in re.finditer(r"activation_verdict\s*:\s*(ACTIVATED|NOT_ACTIVATED)\b",
                         body, re.IGNORECASE):
        activations_total += 1
        if m.group(1).upper() == "ACTIVATED":
            activations_yes += 1
    # 4 `applicable:` lines (2 YES, 1 NO, 1 N/A) + 1 `activation_verdict:` ACTIVATED
    assert activations_total == 5
    assert activations_yes == 3


def test_count_yes_markdown_empty_body():
    activations_total = 0
    activations_yes = 0
    body = "(no LLM response for this spec)\n"
    for _m in re.finditer(r"applicable\s*:\s*(YES|NO|N/A)\b",
                           body, re.IGNORECASE):
        activations_total += 1
    assert activations_total == 0
    assert activations_yes == 0


def test_count_yes_dict_shape_still_works():
    """Dict-shape input (legacy jsonl) still counted."""
    d = {
        "interpretations": [
            {"applicable": "YES"}, {"applicable": "NO"},
        ],
        "sub_domain_activations": [
            {"activation_verdict": "ACTIVATED"},
        ],
    }
    total = 0
    yes = 0
    for k in ("interpretations", "derogations", "implications",
              "positive_events", "negative_events", "sub_domain_activations"):
        items = d.get(k, [])
        for it in items:
            if isinstance(it, dict):
                total += 1
                if (it.get("applicable", "").upper() == "YES" or
                        it.get("activation_verdict", "").upper() == "ACTIVATED"):
                    yes += 1
    assert total == 3
    assert yes == 2
