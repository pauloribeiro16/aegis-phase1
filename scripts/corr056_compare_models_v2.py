"""CORR-056 fair A/B comparison: gemma4:e2b (Ollama) vs google/gemma-4-E2B-it (transformers).

v2 — fair comparison (CORR-056 §B.11). Differences from v1:
  - System role preserved (not concatenated into user content)
  - Same `messages` list sent to both backends
  - Ollama: SystemMessage + HumanMessage (langchain)
  - transformers: messages=[{system}, {user}] via apply_chat_template

Usage:
    PYTHONPATH=src .venv/bin/python scripts/corr056_compare_models_v2.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROMPTS_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS")

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


def render_p1b_llm_01():
    """Render the P1B-LLM-01 prompt — returns (system, user) separately."""
    from aegis_phase1.prompts_v2.loader import PromptLoader

    loader = PromptLoader(root=PROMPTS_ROOT)
    rendered = loader.render("P1B-LLM-01-INTERPRETATION", INPUTS)
    return rendered["system"], rendered["user"]


def invoke_ollama(system: str, user: str):
    """Ollama via langchain SystemMessage + HumanMessage (fair path)."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from aegis_phase1.v2.llm import build_llm_invoker

    inv = build_llm_invoker(model="gemma4:e2b", provider="ollama")
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    t0 = time.perf_counter()
    # Bypass UnifiedInvoker.invoke_raw (which concatenates) and call
    # chat.invoke directly so the SystemMessage is honoured.
    response = inv.chat.invoke(messages)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    raw = response.content if isinstance(response.content, str) else str(response.content)
    return inv, {
        "raw": raw,
        "status": "OK",
        "usage": {
            "prompt_tokens": -1,  # Not extracted in this path; Ollama metadata
            "completion_tokens": -1,
            "total_tokens": -1,
        },
    }, latency_ms


def invoke_transformers(system: str, user: str):
    """transformers via the new system_prompt arg (fair path)."""
    from aegis_phase1.v2.llm import build_llm_invoker

    inv = build_llm_invoker(
        model="google/gemma-4-E2B-it", provider="transformers"
    )
    t0 = time.perf_counter()
    result = inv.invoke(user, system_prompt=system)
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
    if usage and usage.get("total_tokens", -1) >= 0:
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
    print(raw[:4000])
    if len(raw) > 4000:
        print(f"... [truncated, {len(raw) - 4000} more chars]")
    print("=" * 78)


def structural_compliance(raw: str) -> dict:
    """Score how well the output follows the P1B-LLM-01 expected structure."""
    return {
        "## Status": "## Status" in raw,
        "## Interpretations": "## Interpretations" in raw or "## Interpretation" in raw,
        "## Derogations": "## Derogations" in raw or "## Derogation" in raw,
        "### INT-01": "### INT-01" in raw or "INT-01" in raw,
        "### DER-01": "### DER-01" in raw or "DER-01" in raw,
        "mentions catalogs missing": any(
            kw in raw.lower()
            for kw in ("catalog", "yaml", "subdomain", "not provided", "missing", "cannot determine", "insufficient")
        ),
    }


def main() -> int:
    print("Rendering P1B-LLM-01 prompt (Case_01 + GDPR + Controller/LOW)…")
    system, user = render_p1b_llm_01()
    print(f"  system : {len(system)} chars (passed as SYSTEM role)")
    print(f"  user   : {len(user)} chars (passed as USER role)")
    print(f"  total  : {len(system) + len(user)} chars (≈ {(len(system) + len(user)) // 4} tokens)")

    print("\n>>> [1/2] Ollama (gemma4:e2b) — SystemMessage + HumanMessage…")
    inv_oll, res_oll, lat_oll = invoke_ollama(system, user)
    show_result("Ollama · gemma4:e2b", inv_oll, res_oll, lat_oll)

    print("\n>>> [2/2] transformers (google/gemma-4-E2B-it) — system_prompt arg…")
    inv_tf, res_tf, lat_tf = invoke_transformers(system, user)
    show_result("transformers · google/gemma-4-E2B-it", inv_tf, res_tf, lat_tf)

    # Comparison
    print("\n" + "=" * 78)
    print("  FAIR A/B COMPARISON SUMMARY (system role preserved in both)")
    print("=" * 78)
    print(f"  latency    : ollama={lat_oll}ms ({lat_oll/1000:.1f}s)  "
          f"transformers={lat_tf}ms ({lat_tf/1000:.1f}s)  "
          f"ratio={lat_tf / max(lat_oll, 1):.1f}x")
    print(f"  status     : ollama={res_oll.get('status')}  transformers={res_tf.get('status')}")
    print(f"  out length : ollama={len(res_oll.get('raw',''))}c  "
          f"transformers={len(res_tf.get('raw',''))}c")
    print()
    print("  Structural compliance (P1B-LLM-01 expected format):")
    s_oll = structural_compliance(res_oll.get("raw", ""))
    s_tf = structural_compliance(res_tf.get("raw", ""))
    for key in s_oll:
        mark_o = "✓" if s_oll[key] else "✗"
        mark_t = "✓" if s_tf[key] else "✗"
        print(f"    {key:30s}  ollama={mark_o}  transformers={mark_t}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
