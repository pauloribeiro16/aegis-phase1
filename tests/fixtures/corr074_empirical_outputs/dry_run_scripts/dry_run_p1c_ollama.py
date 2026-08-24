#!/usr/bin/env python3
"""Ollama dry-run v3: P1C-LLM-01/02/03 with gemma4:e2b.

Usage:
  dry_run_p1c_ollama.py <model_name> <p1c01|p1c02|p1c03>

CORR-074 validation: regenerates the gemma4_e2b fixtures for the 3 P1C
specs using Ollama as backend. The script patches the corresponding
ChatMinimax dry-run script's invocation but keeps its inputs/prompts.
"""
import json
import sys
import time
from pathlib import Path

from aegis_phase1.prompts_v2.loader import PromptLoader

OUT_DIR = Path("/tmp/corr074-ollama")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OLLAMA_BASE_URL = "http://127.0.0.1:11435"

SPECS = {
    "p1c01": ("P1C-LLM-01-OVERLAP-CLASSIFICATION", "D-01"),
    "p1c02": ("P1C-LLM-02-COMPOUND-EVENT", "D-04"),
    "p1c03": ("P1C-LLM-03-STRATEGIC-SYNTHESIS", "ALL"),
}

PARSERS = {
    "p1c01": "P1CLLM01Parser",
    "p1c02": "P1CLLM02Parser",
    "p1c03": "P1CLLM03Parser",
}

CASE = "case1-tinytask"


def build_inputs(spec_key: str) -> dict:
    """Build the minimal inputs dict required by each spec.

    Mirrors the ChatMinimax dry-runs but stripped of M3-specific extras.
    """
    if spec_key == "p1c01":
        return {
            "case_id": CASE,
            "lane_id": "D-01",
            "domain_id": "D-01",
            "domain_overview": {
                "domain_name": "Data Protection & Encryption",
                "sub_domain_ids": ["D-01.1", "D-01.2"],
            },
            "applicable_regs": ["GDPR", "CRA"],
            "p1b_outputs_by_reg": {
                "GDPR": {"interpretations": [], "derogations": [], "synthesis": {"rationale": "..."}},
                "CRA": {"interpretations": [], "derogations": [], "synthesis": {"rationale": "..."}},
            },
            "company_facts": {
                "scope": "DOC04:ARCH-SYS-01",
                "products": ["Main SaaS Application"],
                "data_categories": ["non_personal_data", "personal_data"],
                "roles": ["controller"],
            },
            "layer0_subdomain_files": {
                "D-01.1": "SubDomains/D-01_Data-Protection/D-01.1.md",
            },
            "layer0_annotation": "annotations/D-01.yaml",
            "layer0_overlap_predicates": "catalogs/scope_overlap_predicates.yaml",
        }
    if spec_key == "p1c02":
        return {
            "case_id": CASE,
            "domain_id": "D-04",
            "applicable_regs": ["GDPR", "CRA"],
            "p1c01_outputs_by_domain": {
                "D-04": {
                    "status": "OK",
                    "sub_domain_activations": [],
                },
            },
            "company_facts": {
                "products": ["Main SaaS Application"],
                "sector": "saas_software",
            },
            "layer0_catalog": "catalogs/compound_event_templates.yaml",
        }
    # p1c03
    return {
        "case_id": CASE,
        "applicable_regs": ["GDPR", "CRA", "NIS2"],
        "p1c02_outputs_by_domain": {"D-04": {"compound_events": []}},
        "p1c01_outputs_by_domain": {"D-01": {"sub_domain_activations": []}},
        "company_facts": {
            "products": ["Main SaaS Application"],
            "sector": "saas_software",
            "role": "controller",
        },
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: dry_run_p1c_ollama.py <model_name> <p1c01|p1c02|p1c03>", file=sys.stderr)
        return 2
    model_name = sys.argv[1]
    spec_key = sys.argv[2]
    if spec_key not in SPECS:
        print(f"unknown spec {spec_key}; pick one of {list(SPECS)}", file=sys.stderr)
        return 2

    spec_id, _ = SPECS[spec_key]
    model_slug = model_name.replace(":", "_")

    loader = PromptLoader()
    inputs = build_inputs(spec_key)
    prompt = loader.render(spec_id, inputs)
    system, user = prompt["system"], prompt["user"]
    print(f"[{model_name}/{spec_key}] prompt: system={len(system)} chars, user={len(user)} chars")

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    chat = ChatOllama(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
        temperature=0.0,
        num_ctx=128000,
    )

    t0 = time.perf_counter()
    resp = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    elapsed = time.perf_counter() - t0
    raw = resp.content if isinstance(resp.content, str) else str(resp.content)
    usage_md = getattr(resp, "usage_metadata", None) or {}
    usage = {
        "input_tokens": int(usage_md.get("input_tokens", 0) or 0),
        "output_tokens": int(usage_md.get("output_tokens", 0) or 0),
    }

    raw_path = OUT_DIR / f"{spec_key}_{model_slug}_raw.md"
    raw_path.write_text(raw, encoding="utf-8")

    from aegis_phase1.prompts_v2.markdown_parser import (
        P1CLLM01Parser,
        P1CLLM02Parser,
        P1CLLM03Parser,
    )
    parser_cls = {"p1c01": P1CLLM01Parser, "p1c02": P1CLLM02Parser, "p1c03": P1CLLM03Parser}[spec_key]
    parser = parser_cls()
    model_obj, parse_err = parser.parse(raw)

    result = {
        "model": model_name,
        "spec": spec_key,
        "latency_s": round(elapsed, 2),
        "raw_len": len(raw),
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "parser_success": model_obj is not None,
    }
    if model_obj is not None:
        # Different output schemas per spec — store minimal structured summary
        result["status"] = getattr(model_obj.status, "value", None)
        if hasattr(model_obj, "confidence"):
            result["confidence"] = getattr(model_obj.confidence, "value", None)
        for attr in (
            "sub_domain_activations",
            "compound_events",
            "strategic_synthesis",
            "notes",
        ):
            if hasattr(model_obj, attr):
                val = getattr(model_obj, attr)
                if isinstance(val, list):
                    result[f"{attr}_count"] = len(val)
                elif isinstance(val, str):
                    result[f"{attr}_len"] = len(val)
    else:
        result["parse_error"] = str(parse_err)[:400]

    result_path = OUT_DIR / f"{spec_key}_{model_slug}_parse_result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"[{model_name}/{spec_key}] elapsed={elapsed:.2f}s tok_in={usage['input_tokens']} tok_out={usage['output_tokens']}")
    print(f"  PARSER {'OK' if model_obj else 'FAILED'}: {result.get('parse_error', '')[:200] if model_obj is None else 'structured fields captured'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())