"""Capture all LLM payloads using the real PreprocCatalogLoader."""
import json
import logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.ERROR)

PROMPTS_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS")
OUT_DIR = Path("/tmp/payload_capture3")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Use the real loader to get layer-0 sub-domain refs
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
from aegis_phase1.prompts_v2.loader import PromptLoader

preproc = PreprocCatalogLoader(preproc_root="preproc_out")
all_subdomains = preproc.load_subdomains()
print(f"Loaded {len(all_subdomains)} sub-domains from preproc_out")

# Build layer0_subdomain_refs per D-XX
layer0_by_domain = defaultdict(list)
for sd in all_subdomains:
    domain = sd.id.split(".")[0] if "." in sd.id else sd.id
    layer0_by_domain[domain].append({
        "sub_domain_id": sd.id,
        "title": sd.title or sd.id,
        "objective": getattr(sd, "objective", "") or "",
        "hso_hl": getattr(sd, "hso_hl", "") or "",
        "participating_regulations": getattr(sd, "participating_regulations", []) or [],
        "pairs": getattr(sd, "pairs", []) or [],
    })

CASES = {
    "case1-tinytask": {"applicable_regs": ["GDPR", "CRA"]},
    "case2-secureborder": {"applicable_regs": ["GDPR", "CRA", "NIS2", "AI_Act"]},
    "case3-omnibank": {"applicable_regs": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"]},
}

prompt_loader = PromptLoader(root=PROMPTS_ROOT)

all_captures = []

for case_name, case_meta in CASES.items():
    applicable_regs = case_meta["applicable_regs"]
    case_dir = OUT_DIR / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    profile = CaseProfileLoader(Path(f"cases/{case_name}")).load()

    # P1C-LLM-01: 10 calls (one per D-XX)
    for d_num in range(1, 11):
        domain_id = f"D-{d_num:02d}"
        lane_refs = layer0_by_domain.get(domain_id, [])

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
            "case": case_name, "spec": "P1C-LLM-01-OVERLAP-CLASSIFICATION", "seq": d_num,
            "lane": domain_id, "system_len": len(result["system"]), "user_len": len(result["user"]),
            "layer0_count": len(lane_refs),
        })
        with (case_dir / f"P1C-LLM-01__{domain_id}.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1C-LLM-01-OVERLAP-CLASSIFICATION", "lane": domain_id,
                       "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)

    # P1B-LLM-01: 1 call per reg
    for reg in applicable_regs:
        inputs = {
            "case_id": case_name, "lane_id": reg, "applicable_regs": [reg],
            "company_facts": {"name": profile.company.name, "sector": profile.company.sector, "jurisdiction": profile.company.jurisdiction},
            "layer0_catalog": {"tipo2": []},
            "layer0_subdomain_refs": [r for r in all_subdomains if reg in (getattr(r, "participating_regulations", []) or [])][:5],
        }
        try:
            result = prompt_loader.render("P1B-LLM-01-INTERPRETATION", inputs)
            all_captures.append({"case": case_name, "spec": "P1B-LLM-01-INTERPRETATION", "seq": applicable_regs.index(reg)+1,
                                 "lane": reg, "system_len": len(result["system"]), "user_len": len(result["user"])})
            with (case_dir / f"P1B-LLM-01__{reg}.json").open("w") as f:
                json.dump({"case": case_name, "spec": "P1B-LLM-01-INTERPRETATION", "lane": reg, "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
        except Exception as e:
            print(f"  P1B-01 {reg}: {e}")

    # P1B-LLM-02: 1 call per reg
    for reg in applicable_regs:
        inputs = {"case_id": case_name, "lane_id": reg, "applicable_regs": [reg]}
        try:
            result = prompt_loader.render("P1B-LLM-02-RATIONALE", inputs)
            all_captures.append({"case": case_name, "spec": "P1B-LLM-02-RATIONALE", "seq": applicable_regs.index(reg)+1,
                                 "lane": reg, "system_len": len(result["system"]), "user_len": len(result["user"])})
            with (case_dir / f"P1B-LLM-02__{reg}.json").open("w") as f:
                json.dump({"case": case_name, "spec": "P1B-LLM-02-RATIONALE", "lane": reg, "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
        except Exception as e:
            print(f"  P1B-02 {reg}: {e}")

    # P1C-LLM-03: 1 global
    inputs = {"case_id": case_name, "lane_id": "global", "applicable_regs": applicable_regs,
              "aggregated_activations": [{"sub_domain_id": f"D-0{i}.{j}", "reg_pair": applicable_regs[:2]} for i in range(1, 6) for j in range(1, 5)],
              "doc07b_profile": {f"D-0{i}.{j}": {"tier": "STANDARD"} for i in range(1, 6) for j in range(1, 5)}}
    try:
        result = prompt_loader.render("P1C-LLM-03-STRATEGIC-SYNTHESIS", inputs)
        all_captures.append({"case": case_name, "spec": "P1C-LLM-03-STRATEGIC-SYNTHESIS", "seq": 1, "lane": "global",
                             "system_len": len(result["system"]), "user_len": len(result["user"])})
        with (case_dir / "P1C-LLM-03__global.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1C-LLM-03-STRATEGIC-SYNTHESIS", "lane": "global", "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
    except Exception as e:
        print(f"  P1C-03: {e}")

    # P1C-LLM-02: 1 global
    inputs = {"case_id": case_name, "lane_id": "global", "applicable_regs": applicable_regs,
              "aggregated_activations": [{"sub_domain_id": f"D-0{i}.{j}", "reg_pair": applicable_regs[:2]} for i in range(1, 6) for j in range(1, 5)],
              "c03_strategic_synthesis": {"placeholder": True}, "sync_conflicts": []}
    try:
        result = prompt_loader.render("P1C-LLM-02-COMPOUND-EVENT", inputs)
        all_captures.append({"case": case_name, "spec": "P1C-LLM-02-COMPOUND-EVENT", "seq": 1, "lane": "global",
                             "system_len": len(result["system"]), "user_len": len(result["user"])})
        with (case_dir / "P1C-LLM-02__global.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1C-LLM-02-COMPOUND-EVENT", "lane": "global", "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)
    except Exception as e:
        print(f"  P1C-02: {e}")

    print(f"  {case_name}: {sum(1 for c in all_captures if c['case'] == case_name)} payloads")

with (OUT_DIR / "_summary.json").open("w") as f:
    json.dump(all_captures, f, indent=2, default=str)

print(f"\n=== Total: {len(all_captures)} payloads ===")
print(f"Output: {OUT_DIR}")
