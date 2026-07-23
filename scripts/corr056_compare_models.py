"""CORR-056 ad-hoc comparison: gemma4:e2b (Ollama) vs google/gemma-4-E2B-it (transformers).

Renders a real P1B-LLM-01 prompt from the Methodology-main PROMPTS/
directory using minimal Case_01 / GDPR inputs, then invokes the same
prompt on two different backends and prints the results side by side.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/corr056_compare_models.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROMPTS_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS")
REG_BASELINE = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PREPROCESSING/SubDomains")

# Minimal inputs — Case_01 TinyTask, GDPR, Controller/LOW.
# This is the SAME shape the production pipeline feeds to P1B-LLM-01.
INPUTS = {
    "case_id": "Case_01_TinyTask_SaaS",
    "lane_id": "GDPR",
    "applicable_regs": ["GDPR"],
    "classification": {
        "role": "Controller",
        "tier": "LOW",
        "classification_basis": "Doc 04 §5: SaaS <500 employees, EU-only",
    },
    "company_facts": {
        "architecture_ref": "DOC04:ARCH-01 (single-tenant SaaS, EU region)",
        "data_categories": ["personal_data", "non_personal_data"],
        "products": ["TaskTracker (B2B SaaS for SMB task management)"],
        "role_obligations": ["controller for user account data", "processor for customer tenant data"],
    },
    "layer0_catalog": {
        "tipo2": "./catalogs/tipo2_interpretations.yaml",
        "tipo3": "./catalogs/tipo3_derogations.yaml",
    },
    "layer0_subdomain_refs": ["SubDomains/D-01.1.md", "SubDomains/D-04.3.md"],
}


def render_p1b_llm_01_prompt():
    """Render the P1B-LLM-01 prompt using PromptLoader (same path the pipeline uses)."""
    from aegis_phase1.prompts_v2.loader import PromptLoader

    loader = PromptLoader(root=PROMPTS_ROOT)
    rendered = loader.render("P1B-LLM-01-INTERPRETATION", INPUTS)
    return rendered["system"], rendered["user"]


def invoke_ollama(system: str, user: str):
    """Run via Ollama (gemma4:e2b) using the v2 factory."""
    from aegis_phase1.v2.llm import build_llm_invoker

    inv = build_llm_invoker(model="gemma4:e2b", provider="ollama")
    # UnifiedInvoker uses .invoke(prompt, feedback="") for the light path
    full_prompt = f"{system}\n\n{user}"
    t0 = time.perf_counter()
    result = inv.invoke(full_prompt)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return inv, result, latency_ms


def invoke_transformers(system: str, user: str):
    """Run via HuggingFace transformers (google/gemma-4-E2B-it)."""
    from aegis_phase1.v2.llm import build_llm_invoker

    inv = build_llm_invoker(
        model="google/gemma-4-E2B-it", provider="transformers"
    )
    full_prompt = f"{system}\n\n{user}"
    t0 = time.perf_counter()
    result = inv.invoke(full_prompt)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return inv, result, latency_ms


def show_result(label: str, inv, result, latency_ms: int) -> None:
    print("\n" + "=" * 78)
    print(f"  {label}")
    print("=" * 78)
    print(f"  model         : {getattr(inv, 'model_id', inv.model)}")
    print(f"  provider      : {type(inv).__name__}")
    print(f"  latency_ms    : {latency_ms}")
    print(f"  status        : {result.get('status')}")
    usage = result.get("usage", {})
    if usage:
        print(
            f"  tokens        : {usage.get('prompt_tokens', '?')} prompt "
            f"+ {usage.get('completion_tokens', '?')} completion "
            f"= {usage.get('total_tokens', '?')} total"
        )
    raw = result.get("raw", "")
    print(f"  output length : {len(raw)} chars")
    print("-" * 78)
    print("RAW OUTPUT:")
    print("-" * 78)
    print(raw[:4000])  # truncate for readability
    if len(raw) > 4000:
        print(f"... [truncated, {len(raw) - 4000} more chars]")
    print("=" * 78)


def main() -> int:
    print("Rendering P1B-LLM-01 prompt (Case_01 + GDPR + Controller/LOW)…")
    system, user = render_p1b_llm_01_prompt()
    full = f"{system}\n\n{user}"
    print(f"  system: {len(system)} chars")
    print(f"  user  : {len(user)} chars")
    print(f"  total : {len(full)} chars (≈ {len(full) // 4} tokens)")

    print("\n>>> Invoking Ollama (gemma4:e2b)…")
    inv_oll, res_oll, lat_oll = invoke_ollama(system, user)
    show_result("Ollama · gemma4:e2b", inv_oll, res_oll, lat_oll)

    print("\n>>> Invoking transformers (google/gemma-4-E2B-it)…")
    inv_tf, res_tf, lat_tf = invoke_transformers(system, user)
    show_result("transformers · google/gemma-4-E2B-it", inv_tf, res_tf, lat_tf)

    # Brief comparison summary
    print("\n" + "=" * 78)
    print("  COMPARISON SUMMARY")
    print("=" * 78)
    print(f"  latency  : ollama={lat_oll}ms  transformers={lat_tf}ms  (ratio {lat_tf / max(lat_oll, 1):.1f}x)")
    print(f"  status   : ollama={res_oll.get('status')}  transformers={res_tf.get('status')}")
    print(f"  output   : ollama={len(res_oll.get('raw', ''))}c  transformers={len(res_tf.get('raw', ''))}c")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
