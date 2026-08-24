#!/usr/bin/env python3
"""Single M3 call for P1C-LLM-01-OVERLAP-CLASSIFICATION, lane=D-01, case1-tinytask."""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("MINIMAX_MIN_INTERVAL", "0")

from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.llm.chat_minimax import ChatMinimax
from aegis_phase1.prompts_v2.markdown_parser import P1CLLM01Parser

SPEC_ID = "P1C-LLM-01-OVERLAP-CLASSIFICATION"
DOMAIN = "D-01"
CASE = "case1-tinytask"
OUT_DIR = Path("/tmp/corr074-propagation")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def build_inputs():
    return {
        "case_id": CASE,
        "lane_id": DOMAIN,
        "domain_id": DOMAIN,
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
            "products": ["Main SaaS Application (python/django/react on AWS eu-west-1)"],
            "data_categories": ["non_personal_data", "personal_data"],
            "roles": ["controller for admin data, processor for customer data"],
        },
        "layer0_subdomain_files": {
            "D-01.1": "SubDomains/D-01_Data-Protection/D-01.1.md",
            "D-01.2": "SubDomains/D-01_Data-Protection/D-01.2.md",
        },
        "layer0_annotation": "annotations/D-01.yaml",
        "layer0_overlap_predicates": "catalogs/scope_overlap_predicates.yaml",
    }


def main():
    if not os.environ.get("MINIMAX_API_KEY"):
        print("ERROR: MINIMAX_API_KEY not set", file=sys.stderr)
        return 2

    loader = PromptLoader()
    inputs = build_inputs()
    prompt = loader.render(SPEC_ID, inputs)
    system, user = prompt["system"], prompt["user"]
    (OUT_DIR / "p1c01_system.txt").write_text(system, encoding="utf-8")
    (OUT_DIR / "p1c01_user.txt").write_text(user, encoding="utf-8")
    print(f"prompt: system={len(system)} chars, user={len(user)} chars")

    chat = ChatMinimax(model="MiniMax-M3", max_tokens=4096, timeout=120)
    from langchain_core.messages import HumanMessage, SystemMessage
    t0 = time.perf_counter()
    result = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    elapsed = time.perf_counter() - t0

    text = result.content if isinstance(result.content, str) else str(result.content)
    (OUT_DIR / "p1c01_raw.txt").write_text(text, encoding="utf-8")

    usage = getattr(result, "usage_metadata", None) or {}
    in_tok = int(usage.get("input_tokens", 0) or 0)
    out_tok = int(usage.get("output_tokens", 0) or 0)
    print(f"M3 done in {elapsed:.2f}s | in={in_tok} out={out_tok} | raw={len(text)} chars")
    print(f"starts: {text[:80]!r}")

    parser = P1CLLM01Parser()
    model, err = parser.parse(text)

    result_dict = {
        "latency_s": elapsed,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "raw_len": len(text),
    }

    if model is None:
        result_dict["parser_success"] = False
        result_dict["parser_error"] = err
        print(f"\nPARSER FAILED: {err!r}")
    else:
        result_dict["parser_success"] = True
        result_dict["status"] = model.status.value
        result_dict["confidence"] = model.confidence.value
        result_dict["domain_summary"] = {
            "total": model.domain_summary.total_sub_domains,
            "active": model.domain_summary.active_sub_domains,
            "pairwise": model.domain_summary.pairwise_relationships,
        }
        result_dict["activations_count"] = len(model.sub_domain_activations)
        result_dict["notes_len"] = len(model.notes or "")
        print(f"\nPARSER OK")
        print(f"  status={model.status.value} confidence={model.confidence.value}")
        print(f"  domain_summary={result_dict['domain_summary']}")
        print(f"  activations={len(model.sub_domain_activations)}")
        for act in model.sub_domain_activations:
            print(f"    - {act.sub_domain_id} applicable={act.applicable} "
                  f"scope={act.scope_overlap.value} pairs={len(act.verified_relationship_per_pair)}")
            for pair in act.verified_relationship_per_pair:
                print(f"        {pair.reg_a} \u2194 {pair.reg_b} \u2192 "
                      f"l0={pair.layer0_relationship.value} verdict={pair.company_scope_verdict.value}")
        print(f"  notes_len={len(model.notes)}")

    (OUT_DIR / "p1c01_parse_result.json").write_text(json.dumps(result_dict, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
