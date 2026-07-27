"""Capture all LLM payloads (system + user prompts) for the 5 Phase 1 LLM specs,
for all 3 cases, without making any actual API calls to MiniMax.

Strategy: call PromptLoader.render(spec_id, inputs) directly with the inputs
that Phase1Executor would have built. Save each rendered prompt to disk.

For each (case, spec, seq) we have a (system, user) prompt pair that represents
what would be POST'd to https://api.minimax.io/anthropic/v1/messages.
"""
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.ERROR)

PROMPTS_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS")
PREPROC_ROOT = PROMPTS_ROOT.parent / "PREPROCESSING"
OUT_DIR = Path("/tmp/payload_capture2")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Pre-load the case profiles
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.prompts_v2.loader import PromptLoader

CASES = {
    "case1-tinytask": {"applicable_regs": ["GDPR", "CRA"]},
    "case2-secureborder": {"applicable_regs": ["GDPR", "CRA", "NIS2", "AI_Act"]},
    "case3-omnibank": {"applicable_regs": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"]},
}

prompt_loader = PromptLoader(root=PROMPTS_ROOT)

# Load layer-0 sub-domain refs once (CORR-045: per-lane filter)
def load_layer0_refs():
    """Load all 38 sub-domain refs from preproc_out/SubDomains."""
    import json
    refs = []
    preproc_subdomains = Path("/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1/preproc_out/SubDomains")
    if not preproc_subdomains.exists():
        return refs
    for f in preproc_subdomains.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            sub_id = d.get("id") or d.get("subDomainId") or f.stem
            domain_id = sub_id.split(".")[0] if "." in sub_id else sub_id
            refs.append({
                "sub_domain_id": sub_id,
                "domain_id": domain_id,
                "name": d.get("name", sub_id),
                "description": (d.get("description", "") or "")[:200],
                "hso_hl": d.get("hso_hl", "") or "",
                "source_regs": d.get("source_regs", []) or d.get("applicable_regs", []) or [],
            })
        except Exception:
            pass
    return refs

layer0_refs = load_layer0_refs()
print(f"Loaded {len(layer0_refs)} layer-0 sub-domain refs")

# Capture results
all_captures = []

for case_name, case_meta in CASES.items():
    applicable_regs = case_meta["applicable_regs"]
    case_dir = OUT_DIR / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    profile = CaseProfileLoader(Path(f"cases/{case_name}")).load()

    # ========== P1C-LLM-01-OVERLAP-CLASSIFICATION: 10 calls (one per D-XX) ==========
    for d_num in range(1, 11):
        domain_id = f"D-{d_num:02d}"
        # Per-lane filter (CORR-045)
        lane_refs = [r for r in layer0_refs if r["sub_domain_id"].startswith(f"{domain_id}.")]

        inputs = {
            "case_id": case_name,
            "domain_id": domain_id,
            "lane_id": domain_id,
            "applicable_regs": applicable_regs,
            "company_facts": {
                "name": profile.company.name,
                "sector": profile.company.sector,
                "jurisdiction": profile.company.jurisdiction,
                "scale": profile.company.scale,
                "employees": profile.company.employees,
            },
            "layer0_subdomain_refs": lane_refs,
        }

        result = prompt_loader.render("P1C-LLM-01-OVERLAP-CLASSIFICATION", inputs)
        all_captures.append({
            "case": case_name,
            "spec": "P1C-LLM-01-OVERLAP-CLASSIFICATION",
            "seq": d_num,
            "lane": domain_id,
            "system_len": len(result["system"]),
            "user_len": len(result["user"]),
            "input_keys": list(inputs.keys()),
            "input_field_sizes": {k: (len(str(v)) if isinstance(v, (str, list, dict)) else 1) for k, v in inputs.items()},
        })
        with (case_dir / f"P1C-LLM-01-OVERLAP-CLIFICATION__{domain_id}.json").open("w") as f:
            json.dump({
                "case": case_name,
                "spec": "P1C-LLM-01-OVERLAP-CLASSIFICATION",
                "lane": domain_id,
                "system": result["system"],
                "user": result["user"],
                "inputs": {k: (v if not isinstance(v, (str, list, dict)) else (str(v) if isinstance(v, str) else v)) for k, v in inputs.items()},
            }, f, indent=2, default=str)

    # ========== P1B-LLM-01-INTERPRETATION: 1 call per applicable reg ==========
    for reg in applicable_regs:
        inputs = {
            "case_id": case_name,
            "lane_id": reg,
            "applicable_regs": [reg],
            "company_facts": {
                "name": profile.company.name,
                "sector": profile.company.sector,
                "jurisdiction": profile.company.jurisdiction,
            },
            "layer0_catalog": {"tipo2": []},
            "layer0_subdomain_refs": [r for r in layer0_refs if reg in r.get("source_regs", [])][:10],
        }
        try:
            result = prompt_loader.render("P1B-LLM-01-INTERPRETATION", inputs)
            all_captures.append({
                "case": case_name,
                "spec": "P1B-LLM-01-INTERPRETATION",
                "seq": applicable_regs.index(reg) + 1,
                "lane": reg,
                "system_len": len(result["system"]),
                "user_len": len(result["user"]),
            })
            with (case_dir / f"P1B-LLM-01-INTERPRETATION__{reg}.json").open("w") as f:
                json.dump({"case": case_name, "spec": "P1B-LLM-01-INTERPRETATION", "lane": reg, "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
        except Exception as e:
            print(f"  P1B-LLM-01 for {reg}: {e}")

    # ========== P1B-LLM-02-RATIONALE: 1 call per applicable reg ==========
    for reg in applicable_regs:
        inputs = {
            "case_id": case_name,
            "lane_id": reg,
            "applicable_regs": [reg],
        }
        try:
            result = prompt_loader.render("P1B-LLM-02-RATIONALE", inputs)
            all_captures.append({
                "case": case_name,
                "spec": "P1B-LLM-02-RATIONALE",
                "seq": applicable_regs.index(reg) + 1,
                "lane": reg,
                "system_len": len(result["system"]),
                "user_len": len(result["user"]),
            })
            with (case_dir / f"P1B-LLM-02-RATIONALE__{reg}.json").open("w") as f:
                json.dump({"case": case_name, "spec": "P1B-LLM-02-RATIONALE", "lane": reg, "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
        except Exception as e:
            print(f"  P1B-LLM-02 for {reg}: {e}")

    # ========== P1C-LLM-03-STRATEGIC-SYNTHESIS: 1 global call ==========
    inputs = {
        "case_id": case_name,
        "lane_id": "global",
        "applicable_regs": applicable_regs,
        "aggregated_activations": [],  # mock empty (we're just capturing the prompt structure)
        "doc07b_profile": {},
    }
    try:
        result = prompt_loader.render("P1C-LLM-03-STRATEGIC-SYNTHESIS", inputs)
        all_captures.append({
            "case": case_name,
            "spec": "P1C-LLM-03-STRATEGIC-SYNTHESIS",
            "seq": 1,
            "lane": "global",
            "system_len": len(result["system"]),
            "user_len": len(result["user"]),
        })
        with (case_dir / "P1C-LLM-03-STRATEGIC-SYNTHESIS__global.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1C-LLM-03-STRATEGIC-SYNTHESIS", "lane": "global", "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
    except Exception as e:
        print(f"  P1C-LLM-03: {e}")

    # ========== P1C-LLM-02-COMPOUND-EVENT: 1 global call ==========
    inputs = {
        "case_id": case_name,
        "lane_id": "global",
        "applicable_regs": applicable_regs,
        "aggregated_activations": [],
        "c03_strategic_synthesis": {"placeholder": True},
        "sync_conflicts": [],
    }
    try:
        result = prompt_loader.render("P1C-LLM-02-COMPOUND-EVENT", inputs)
        all_captures.append({
            "case": case_name,
            "spec": "P1C-LLM-02-COMPOUND-EVENT",
            "seq": 1,
            "lane": "global",
            "system_len": len(result["system"]),
            "user_len": len(result["user"]),
        })
        with (case_dir / "P1C-LLM-02-COMPOUND-EVENT__global.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1C-LLM-02-COMPOUND-EVENT", "lane": "global", "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
    except Exception as e:
        print(f"  P1C-LLM-02: {e}")

    print(f"  {case_name}: captured {sum(1 for c in all_captures if c['case'] == case_name)} payloads")

# Save summary
with (OUT_DIR / "_summary.json").open("w") as f:
    json.dump(all_captures, f, indent=2, default=str)

print(f"\n=== Total: {len(all_captures)} payloads captured ===")
print(f"Output: {OUT_DIR}")
print(f"Summary: {OUT_DIR / '_summary.json'}")
