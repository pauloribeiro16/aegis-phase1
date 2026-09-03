"""Dry-run for CORR-111 — proves the quant-transparency chain end-to-end WITHOUT
the cluster.

Does:
  1. Creates a fake manifest for ``gemma4:31b @ q4_K_M`` in a temp dir.
  2. Sets AEGIS_QUANT_MANIFEST_ROOT + AEGIS_JOB_ID env vars.
  3. Builds a Phase1Orchestrator with a MagicMock llm_invoker pointing at
     ``gemma4:31b`` / ``ollama``.
  4. Calls ``orch.init_model_capabilities()`` and prints what landed in
     ``state["v2_model_capabilities"]``.
  5. Calls ``doc_preamble(state)`` and prints the header that Doc 01-09
     would now lead with.
  6. Calls ``strip_aegis_frontmatter()`` on a piece of mock markdown that
     would have been written by ``_capture_per_spec_markdown`` and prints
     the result.

No GPU. No Ollama server. No sbatch. Just the CORR-111 plumbing. Run with:

    PYTHONPATH=src python tests/manual/dryrun_corr111.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# project root = parent of tests/
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

print("=" * 70)
print("CORR-111 DRY-RUN — quant-transparency chain (no cluster)")
print("=" * 70)

# Step 1: a fake manifest in a temp dir
TMP = Path(tempfile.mkdtemp(prefix="aegis_corr111_dryrun_"))
os.environ["AEGIS_QUANT_MANIFEST_ROOT"] = str(TMP)
os.environ["AEGIS_JOB_ID"] = "DRYRUN-001"
print(f"[setup] temp manifest root = {TMP}")
print(f"[setup] AEGIS_JOB_ID      = {os.environ['AEGIS_JOB_ID']}")

from aegis_phase1.llm import quant_manifest as qm  # noqa: E402

m = qm.QuantManifest(
    model="gemma4:31b",
    provider="ollama",
    quantization="q4_K_M",
    quantization_provenance="ollama-pull",
    pulled_at="2026-09-02T20:14:00Z",
    source="registry.ollama.ai/library/gemma4:31b",
    size_bytes=17_400_000_000,
    digest_sha256="abc123…",
)
sidecar_path = qm.write_manifest(m)
print(f"[setup] wrote sidecar     = {sidecar_path}")
print(f"[setup] sidecar content   = {sidecar_path.read_text()}")

# Step 2-4: orchestrator + init_model_capabilities
from unittest.mock import MagicMock  # noqa: E402

from aegis_phase1.v2.orchestrator import Phase1Orchestrator  # noqa: E402

work = TMP / "work"
work.mkdir()
invoker = MagicMock()
invoker.model = "gemma4:31b"
invoker.provider = "ollama"

orch = Phase1Orchestrator(work_dir=str(work), llm_invoker=invoker)
cap = orch.init_model_capabilities()

print("\n[init_model_capabilities]")
for k, v in cap.items():
    print(f"  {k:32} = {v!r}")

# Verify state is populated
assert "v2_model_capabilities" in orch.state
assert orch.state["v2_model_capabilities"]["quantization"] == "q4_K_M"
assert orch.state["v2_model_capabilities"]["manifest_path"].endswith(".json")
print("  ✓ state['v2_model_capabilities']['quantization'] == 'q4_K_M'")

# Step 5: doc_preamble produces the visible header
from aegis_phase1.v2.output._common import doc_preamble  # noqa: E402

header = doc_preamble(orch.state)
print("\n[doc_preamble on real state]")
print("-" * 70)
print(header.rstrip("\n"))
print("-" * 70)
assert "Model: gemma4:31b @ q4_K_M (job DRYRUN-001)" in header
print("  ✓ header has 'Model: gemma4:31b @ q4_K_M (job DRYRUN-001)'")

# Step 6: strip_aegis_frontmatter on a mock frontmatter-written markdown
from aegis_phase1.v2.output._common import strip_aegis_frontmatter  # noqa: E402

mock_md = (
    "<!-- aegis:model=\"gemma4:31b\" provider=\"ollama\" quant=\"q4_K_M\" "
    "job=\"DRYRUN-001\" spec=\"P1B-LLM-01-INTERPRETATION\" ts=\"2026-09-02T20:14:00Z\" -->\n"
    "## Status\n"
    "- applicable: true\n"
    "- confidence: HIGH\n\n"
    "## Findings\n"
    "Article 13 + Anexo VII are the right anchors for the case profile.\n"
)
clean = strip_aegis_frontmatter(mock_md)
print("\n[strip_aegis_frontmatter]")
print("--- BEFORE ---")
print(mock_md[:80] + ("…" if len(mock_md) > 80 else ""))
print("--- AFTER ---")
print(clean[:80] + ("…" if len(clean) > 80 else ""))
assert clean.startswith("## Status")
assert "aegis:" not in clean
print("  ✓ frontmatter stripped; body intact")

# Bonus: show what happens with NO manifest dir (fallback to provider_default)
print("\n[Fallback check — no manifest dir]")
del os.environ["AEGIS_QUANT_MANIFEST_ROOT"]
invoker.provider = "ollama"
cap2 = orch.init_model_capabilities()
# the state was already populated with q4_K_M from earlier, so we expect the
# first-call-wins behaviour here. Confirm:
print(f"  recorded (first call): quant={cap2['quantization']!r}")
print(f"  recorded (first call): manifest={cap2['manifest_path']!r}")
assert cap2["quantization"] == "q4_K_M", "first call wins (idempotent)"
print("  ✓ first call wins (idempotent — no silent fallback)")

# Construct a fresh orchestrator to actually test the fallback path:
invoker2 = MagicMock()
invoker2.model = "unknown-model:99"
invoker2.provider = "ollama"
orch2 = Phase1Orchestrator(work_dir=str(work / "orch2"), llm_invoker=invoker2)
cap3 = orch2.init_model_capabilities()
print(f"\n[Fresh orchestrator — no manifest found]")
print(f"  quant             = {cap3['quantization']!r}")
print(f"  provenance        = {cap3['quantization_provenance']!r}")
assert cap3["quantization"] == "provider_default", (
    f"expected provider_default (no ollama probe binary), got {cap3['quantization']!r}"
)
print("  ✓ ollama + no manifest → provider_default (per user decision 2026-09-02)")

# Render doc_preamble for that fallback
header2 = doc_preamble(orch2.state)
print("\n[Fallback header]")
print("-" * 70)
print(header2.rstrip("\n"))
print("-" * 70)
assert "[quant = provider default — declare explicitly if reproducible]" in header2
print("  ✓ caveat visible to reader")

print("\n" + "=" * 70)
print("DRY-RUN COMPLETE — chain works end-to-end")
print("=" * 70)
