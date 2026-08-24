#!/usr/bin/env python3
"""Single M3 call for P1C-LLM-02-COMPOUND-EVENT (global_reduce, case1-tinytask)."""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("MINIMAX_MIN_INTERVAL", "0")

from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.llm.chat_minimax import ChatMinimax
from aegis_phase1.prompts_v2.markdown_parser import P1CLLM02Parser

SPEC_ID = "P1C-LLM-02-COMPOUND-EVENT"
CASE = "case1-tinytask"
OUT_DIR = Path("/tmp/corr074-propagation")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def build_inputs():
    return {
        "case_id": CASE,
        "lane_id": "global",
        "applicable_regs": ["GDPR", "CRA"],
        "aggregated_activations": [
            {"lane_id": "D-01", "sub_domain_activations": [
                {"sub_domain_id": "D-01.1", "applicable": True, "scope_overlap": "Y"},
            ]},
            {"lane_id": "D-04", "sub_domain_activations": [
                {"sub_domain_id": "D-04.3", "applicable": True, "scope_overlap": "Y"},
            ]},
            {"lane_id": "D-06", "sub_domain_activations": [
                {"sub_domain_id": "D-06.1", "applicable": True, "scope_overlap": "Y"},
            ]},
        ],
        "doc07b_profile": [
            {"sub_domain_id": "D-01.1", "tier": "LIGHTWEIGHT",
             "satisfaction_pattern": "BUY_MANAGED",
             "evidence_depth": "managed_service_config_plus_annual_review"},
            {"sub_domain_id": "D-04.3", "tier": "STANDARD",
             "satisfaction_pattern": "BUY_MANAGED",
             "evidence_depth": "annual_review_with_templates"},
            {"sub_domain_id": "D-06.1", "tier": "STANDARD",
             "satisfaction_pattern": "BUILD",
             "evidence_depth": "annual_review_with_templates"},
        ],
        "p1c_llm_03_output": {
            "implications": [{"id": "IMP-01", "description": "Unified incident workflow"}],
        },
        "company_facts": {
            "products": ["Main SaaS Application (python/django/react on AWS eu-west-1)"],
            "data_categories": ["non_personal_data", "personal_data"],
            "roles": ["controller for admin data, processor for customer data"],
        },
        "layer0_event_templates": "catalogs/event_templates.yaml",
    }


def main():
    if not os.environ.get("MINIMAX_API_KEY"):
        print("ERROR: MINIMAX_API_KEY not set", file=sys.stderr)
        return 2

    loader = PromptLoader()
    inputs = build_inputs()
    prompt = loader.render(SPEC_ID, inputs)
    system, user = prompt["system"], prompt["user"]
    (OUT_DIR / "p1c02_system.txt").write_text(system, encoding="utf-8")
    (OUT_DIR / "p1c02_user.txt").write_text(user, encoding="utf-8")
    print(f"prompt: system={len(system)} chars, user={len(user)} chars")

    chat = ChatMinimax(model="MiniMax-M3", max_tokens=4096, timeout=120)
    from langchain_core.messages import HumanMessage, SystemMessage
    t0 = time.perf_counter()
    result = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    elapsed = time.perf_counter() - t0

    text = result.content if isinstance(result.content, str) else str(result.content)
    (OUT_DIR / "p1c02_raw.txt").write_text(text, encoding="utf-8")

    usage = getattr(result, "usage_metadata", None) or {}
    in_tok = int(usage.get("input_tokens", 0) or 0)
    out_tok = int(usage.get("output_tokens", 0) or 0)
    print(f"M3 done in {elapsed:.2f}s | in={in_tok} out={out_tok} | raw={len(text)} chars")
    print(f"starts: {text[:80]!r}")

    parser = P1CLLM02Parser()
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
        result_dict["positive_events_count"] = len(model.positive_events)
        result_dict["negative_events_count"] = len(model.negative_events)
        result_dict["notes_len"] = len(model.notes or "")
        print(f"\nPARSER OK")
        print(f"  status={model.status.value} confidence={model.confidence.value}")
        print(f"  positive_events={len(model.positive_events)}")
        for ev in model.positive_events:
            print(f"    - {ev.event_id} subs={ev.sub_domains} regs={ev.regulations_triggered} "
                  f"tension={ev.tension_type.value} severity={ev.severity.value}")
        print(f"  negative_events={len(model.negative_events)}")
        for ev in model.negative_events:
            print(f"    - scenario={ev.scenario[:50]!r}... regs={ev.regulations_checked}")
        print(f"  notes_len={len(model.notes)}")

    (OUT_DIR / "p1c02_parse_result.json").write_text(json.dumps(result_dict, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
