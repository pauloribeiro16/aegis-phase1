"""Ollama dry-run v2: P1B-LLM-01-INTERPRETATION with inlined tipo2/tipo3 catalog."""
import json
import sys
import time
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.markdown_parser import P1BLLM01Parser

OUT_DIR = Path("/tmp/corr074-ollama")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SPEC_ID = "P1B-LLM-01-INTERPRETATION"
LANE = "CRA"
CASE = "case1-tinytask"
OLLAMA_BASE_URL = "http://localhost:11434"
CATALOG_BASE = "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS/catalogs"


def _load_yaml_entries(name: str, reg: str) -> list[dict]:
    """Load the SECOND ```yaml code-block (entries) from the catalog file."""
    text = open(f"{CATALOG_BASE}/{name}").read()
    body = text.split("---", 2)[2] if text.startswith("---") else text
    blocks = body.split("```yaml")
    if len(blocks) < 3:
        return []
    yaml_block = blocks[2].split("```", 1)[0]
    entries = yaml.safe_load(yaml_block) or []
    return [e for e in entries if isinstance(e, dict) and reg in (e.get("applies_to") or [])]


def build_inputs():
    tipo2_entries = _load_yaml_entries("tipo2_interpretations.yaml", LANE)
    tipo3_entries = _load_yaml_entries("tipo3_derogations.yaml", LANE)
    print(f"loaded: tipo2={len(tipo2_entries)} tipo3={len(tipo3_entries)} CRA entries")
    return {
        "case_id": CASE,
        "lane_id": LANE,
        "applicable_regs": [LANE],
        "classification": {
            "role": "manufacturer",
            "tier": "LOW",
            "classification_basis": "Doc 04 §5",
        },
        "company_facts": {
            "architecture_ref": "DOC04:ARCH-SYS-01",
            "data_categories": ["non_personal_data"],
            "products": ["Main SaaS Application (python/django/react on AWS eu-west-1)"],
            "role_obligations": ["manufacturer for CRA-regulated digital product"],
            "role": "manufacturer",
            "sector": "saas_software",
        },
        "layer0_catalog": {
            "tipo2_entries": tipo2_entries,
            "tipo3_entries": tipo3_entries,
        },
        "layer0_subdomain_refs": [
            {
                "sub_domain_id": "D-02.3",
                "title": "Coordinated Vulnerability Disclosure",
                "domain_id": "D-02",
                "participating_regulations": ["CRA"],
                "hso_hl_objective": "Vulnerabilities in the placed product are handled and disclosed.",
                "hso_per_reg": [{"regulation": "CRA", "objective": "Annex I Part II §(7) + §(8)."}],
                "security_requirements": [],
                "pairs": [],
                "anchors": ["Annex I Part II §(7)", "Annex I Part II §(8)"],
                "csf": [],
            },
            {
                "sub_domain_id": "D-07.1",
                "title": "Secure Development Lifecycle",
                "domain_id": "D-07",
                "participating_regulations": ["CRA"],
                "hso_hl_objective": "Product developed under a secure-development lifecycle.",
                "hso_per_reg": [{"regulation": "CRA", "objective": "Annex I Part I §(2)."}],
                "security_requirements": [],
                "pairs": [],
                "anchors": ["Annex I Part I §(2)"],
                "csf": [],
            },
        ],
    }


def _extract_usage(resp):
    md = getattr(resp, "usage_metadata", None) or {}
    return {
        "input_tokens": int(md.get("input_tokens", 0) or 0),
        "output_tokens": int(md.get("output_tokens", 0) or 0),
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: dry_run_p1b01_v2.py <model_name>", file=sys.stderr)
        return 2
    model_name = sys.argv[1]
    model_slug = model_name.replace(":", "_")

    loader = PromptLoader()
    inputs = build_inputs()
    prompt = loader.render(SPEC_ID, inputs)
    system, user = prompt["system"], prompt["user"]
    print(f"[{model_name}] prompt: system={len(system)} chars, user={len(user)} chars")

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
    usage = _extract_usage(resp)

    raw_path = OUT_DIR / f"p1b01_{model_slug}_v2_raw.txt"
    raw_path.write_text(raw, encoding="utf-8")

    parser = P1BLLM01Parser()
    model_obj, parse_err = parser.parse(raw)

    result = {
        "model": model_name,
        "input_version": "v2_inlined_catalog",
        "latency_s": round(elapsed, 2),
        "raw_len": len(raw),
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "parser_success": model_obj is not None,
    }
    if model_obj is not None:
        result["status"] = model_obj.status.value
        result["confidence"] = model_obj.confidence.value
        result["interpretations_count"] = len(model_obj.interpretations)
        result["derogations_count"] = len(model_obj.derogations)
        result["notes_len"] = len(model_obj.notes or "")
        result["interp_entries"] = [
            {"entry_id": i.entry_id, "applicable": i.applicable.value}
            for i in model_obj.interpretations
        ]
        result["derog_entries"] = [
            {"entry_id": d.entry_id, "verdict": d.activation_verdict.value}
            for d in model_obj.derogations
        ]
    else:
        result["parse_error"] = str(parse_err)[:400]

    result_path = OUT_DIR / f"p1b01_{model_slug}_v2_result.json"
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"[{model_name}] elapsed={elapsed:.2f}s tok_in={usage['input_tokens']} tok_out={usage['output_tokens']}")
    if model_obj is not None:
        print(f"  PARSER OK: status={result.get('status')} conf={result.get('confidence')}")
        print(f"  interpretations={result.get('interpretations_count')} derogations={result.get('derogations_count')}")
        for e in result.get("interp_entries", []):
            print(f"    - {e['entry_id']} -> {e['applicable']}")
        for e in result.get("derog_entries", []):
            print(f"    - {e['entry_id']} -> {e['verdict']}")
    else:
        print(f"  PARSER FAILED: {result.get('parse_error', '')[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
