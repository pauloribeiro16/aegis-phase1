#!/usr/bin/env python3
"""Single M3 call for P1B-LLM-02-RATIONALE, lane=CRA, case1-tinytask."""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("MINIMAX_MIN_INTERVAL", "0")

from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.llm.chat_minimax import ChatMinimax
from aegis_phase1.prompts_v2.markdown_parser import P1BLLM02Parser

SPEC_ID = "P1B-LLM-02-RATIONALE"
LANE = "CRA"
CASE = "case1-tinytask"
OUT_DIR = Path("/tmp/corr074-propagation")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def build_inputs():
    return {
        "case_id": CASE,
        "lane_id": LANE,
        "applicable_regs": [LANE],
        "classification": {"role": "manufacturer", "tier": "LOW", "classification_basis": "Doc 04 §5"},
        "company_facts": {
            "architecture_ref": "DOC04:ARCH-SYS-01",
            "data_categories": ["non_personal_data"],
            "products": ["Main SaaS Application (python/django/react on AWS eu-west-1)"],
            "role_obligations": ["manufacturer for CRA-regulated digital product"],
        },
        "layer0_catalog": {
            "tipo2": "methodology-main:/00_METHODOLOGY/PROMPTS/catalogs/tipo2_interpretations.yaml",
            "tipo3": "methodology-main:/00_METHODOLOGY/PROMPTS/catalogs/tipo3_derogations.yaml",
        },
        "layer0_subdomain_refs": [
            {"sub_domain_id": "D-02.3", "title": "Coordinated Vulnerability Disclosure",
             "domain_id": "D-02", "participating_regulations": ["CRA"],
             "hso_hl_objective": "Vulnerabilities in the placed product are handled and disclosed.",
             "hso_per_reg": [{"regulation": "CRA", "objective": "Annex I Part II §(7) + §(8)"}],
             "security_requirements": [], "pairs": [], "anchors": ["Annex I Part II §(7)"], "csf": []},
            {"sub_domain_id": "D-07.1", "title": "Secure Development Lifecycle",
             "domain_id": "D-07", "participating_regulations": ["CRA"],
             "hso_hl_objective": "Product developed under a secure-development lifecycle.",
             "hso_per_reg": [{"regulation": "CRA", "objective": "Annex I Part I §(2)"}],
             "security_requirements": [], "pairs": [], "anchors": ["Annex I Part I §(2)"], "csf": []},
        ],
        "p1b_llm_01_outputs": {
            "interpretations": [{"entry_id": "TIPO2-CRA-ART14-DUAL-FLOW", "applicable": "YES"}],
            "derogations": [],
        },
        "coverage_matrix_row": {
            "sub_domains_covered": ["D-02.3", "D-07.1"],
            "sub_domains_partial": [],
            "sub_domains_not_addressed": [],
        },
    }


def main():
    if not os.environ.get("MINIMAX_API_KEY"):
        print("ERROR: MINIMAX_API_KEY not set", file=sys.stderr)
        return 2

    loader = PromptLoader()
    inputs = build_inputs()
    prompt = loader.render(SPEC_ID, inputs)
    system, user = prompt["system"], prompt["user"]
    (OUT_DIR / "p1b02_system.txt").write_text(system, encoding="utf-8")
    (OUT_DIR / "p1b02_user.txt").write_text(user, encoding="utf-8")
    print(f"prompt: system={len(system)} chars, user={len(user)} chars")

    chat = ChatMinimax(model="MiniMax-M3", max_tokens=4096, timeout=120)
    from langchain_core.messages import HumanMessage, SystemMessage
    t0 = time.perf_counter()
    result = chat.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    elapsed = time.perf_counter() - t0

    text = result.content if isinstance(result.content, str) else str(result.content)
    (OUT_DIR / "p1b02_raw.txt").write_text(text, encoding="utf-8")

    usage = getattr(result, "usage_metadata", None) or {}
    in_tok = int(usage.get("input_tokens", 0) or 0)
    out_tok = int(usage.get("output_tokens", 0) or 0)
    print(f"M3 done in {elapsed:.2f}s | in={in_tok} out={out_tok} | raw={len(text)} chars")
    print(f"starts: {text[:80]!r}")

    parser = P1BLLM02Parser()
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
        result_dict["rationale_len"] = len(model.rationale)
        result_dict["implications_count"] = len(model.implications)
        result_dict["gaps_count"] = len(model.gaps)
        result_dict["notes_len"] = len(model.notes or "")
        print(f"\nPARSER OK")
        print(f"  status={model.status.value} confidence={model.confidence.value}")
        print(f"  rationale_len={len(model.rationale)}")
        print(f"  implications={len(model.implications)}")
        for imp in model.implications:
            print(f"    - {imp.id} effort={imp.effort_estimate.value}")
        print(f"  gaps={len(model.gaps)}")
        for gap in model.gaps:
            print(f"    - {gap.gap_id} coverage={gap.coverage_level.value} priority={gap.priority.value}")
        print(f"  notes_len={len(model.notes)}")

    (OUT_DIR / "p1b02_parse_result.json").write_text(json.dumps(result_dict, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
