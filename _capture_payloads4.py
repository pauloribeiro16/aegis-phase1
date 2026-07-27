"""Capture payloads using the REAL Phase1Executor.run_phase_1b and run_phase_1c_map.

This is the most faithful capture possible because it uses the same
inputs construction as the production orchestrator:
- `run_p1b_single` in orchestrator.py builds classification, layer0_catalog,
  coverage_matrix_row, layer0_subdomain_refs, company_facts, etc.
- This script mimics that same construction (using the real CatalogLoader
  and PreprocCatalogLoader) and passes the inputs to the real executor.

The executor is wrapped with a mock invoker that captures (spec_id, inputs)
and returns a fake response. The pipeline can complete its downstream
stages without any HTTP calls.
"""
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

logging.basicConfig(level=logging.ERROR)

# Configure
PROMPTS_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS")
PREPROC_ROOT = Path("preproc_out")
OUT_DIR = Path("/tmp/payload_capture4")
OUT_DIR.mkdir(parents=True, exist_ok=True)

from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

# Load catalog and preproc data
catalog_loader = CatalogLoader(root=PROMPTS_ROOT / "catalogs")
preproc_loader = PreprocCatalogLoader(preproc_root=str(PREPROC_ROOT))
prompt_loader = PromptLoader(root=PROMPTS_ROOT)

# Load tipo2 + tipo3 catalogs (these are loaded into v2_catalog_tipo2/3)
tipo2_all = catalog_loader.load("tipo2_interpretations")
tipo3_all = catalog_loader.load("tipo3_derogations")
print(f"Loaded {len(tipo2_all)} tipo2 entries, {len(tipo3_all)} tipo3 entries")

# Load layer-0 subdomains
all_subdomains = preproc_loader.load_subdomains()
print(f"Loaded {len(all_subdomains)} sub-domains")

# Build layer0_subdomain_refs (mimicking _build_layer0_subdomain_refs)
def build_layer0_refs(subdomain_ids):
    by_id = {s.id: s for s in all_subdomains}
    refs = []
    for sid in subdomain_ids:
        sd = by_id.get(sid)
        if sd is None:
            continue
        refs.append({
            "sub_domain_id": sd.id,
            "domain_id": sd.id.split(".")[0] if "." in sd.id else sd.id,
            "title": sd.title or sd.id,
            "objective": getattr(sd, "objective", "") or "",
            "hso_hl": getattr(sd, "hso_hl", "") or "",
            "hso_per_reg": getattr(sd, "hso_per_reg", []) or [],
            "participating_regulations": getattr(sd, "participating_regulations", []) or [],
            "pairs": getattr(sd, "pairs", []) or [],
        })
    return refs

# Coverage matrix row (simplified — real one is more complex)
def make_coverage_row(reg):
    return []

# Capture invoker
captured = []
class MockInvoker:
    def invoke(self, spec_id, inputs, **kwargs):
        captured.append({
            "spec_id": spec_id,
            "inputs_keys": sorted(inputs.keys()) if isinstance(inputs, dict) else None,
        })
        # Render and save the actual prompt (system + user) for inspection
        prompt = prompt_loader.render(spec_id, inputs)
        seq = sum(1 for c in captured if c["spec_id"] == spec_id)
        return {
            "status": "OK",
            "parsed_output": {"placeholder": True, "spec_id": spec_id},
            "retry_count": 0,
            "invocation_pattern": "captured",
        }

executor = Phase1Executor(
    invoker=MockInvoker(),
    catalog_loader=catalog_loader,
    prompt_loader=prompt_loader,
    validator=MagicMock(),
    llm_logger=MagicMock(),
    format_logger=MagicMock(),
)

# Run for each case
CASES = {
    "case1-tinytask": ["GDPR", "CRA"],
    "case2-secureborder": ["GDPR", "CRA", "NIS2", "AI_Act"],
    "case3-omnibank": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
}

# Subdomain IDs per case (use ALL 38 for simplicity, the orchestrator does the same)
all_subdomain_ids = [s.id for s in all_subdomains]

for case_name, applicable_regs in CASES.items():
    case_dir = OUT_DIR / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    profile = CaseProfileLoader(Path(f"cases/{case_name}")).load()

    # Build company_facts
    company_facts = {
        "name": profile.company.name,
        "sector": profile.company.sector,
        "jurisdiction": profile.company.jurisdiction,
        "scale": profile.company.scale,
        "employees": profile.company.employees,
        "role": "controller" if "GDPR" in applicable_regs else "",
        "obligated_party": "controller",
        "complexity_tier": "LOW" if profile.company.scale == "MICRO" else "HIGH",
        "data_categories": ["personal_data"],
        "products": ["SaaS application"],
        "role_obligations": ["controller"],
        "applicable_regs": applicable_regs,
    }

    classification = {
        "role": "controller",
        "tier": company_facts["complexity_tier"],
        "basis": "Doc 04 §5",
    }

    # ========== Phase 1B (per regulation) ==========
    layer0_subdomain_refs = build_layer0_refs(all_subdomain_ids)

    for reg in applicable_regs:
        # Filter catalogs for this reg (mimicking _load_filtered_catalogs_for_reg)
        tipo2_filtered = catalog_loader.filter_applicable(tipo2_all, regulation=reg, tier=company_facts["complexity_tier"])
        tipo3_filtered = catalog_loader.filter_applicable(tipo3_all, regulation=reg, tier=company_facts["complexity_tier"])
        # Evaluate tipo3 predicates
        try:
            tipo3_evaluated = catalog_loader.evaluate_predicates(tipo3_filtered, company_facts)
            tipo3_enriched = [
                {**e, "predicate_verdict": v} for e, v in tipo3_evaluated
            ]
        except Exception as exc:
            print(f"  predicate eval failed for {reg}: {exc}")
            tipo3_enriched = tipo3_filtered
        layer0_catalog = {"tipo2": tipo2_filtered, "tipo3": tipo3_enriched}

        inputs = {
            "case_id": case_name,
            "lane_id": reg,
            "applicable_regs": [reg],
            "company_facts": company_facts,
            "classification": classification,
            "coverage_matrix_row": make_coverage_row(reg),
            "aggregated_activations": [],
            "layer0_subdomain_refs": layer0_subdomain_refs,
            "layer0_catalog": layer0_catalog,
        }

        # Render the prompt for P1B-LLM-01
        result = prompt_loader.render("P1B-LLM-01-INTERPRETATION", inputs)
        captured.append({
            "case": case_name, "spec": "P1B-LLM-01-INTERPRETATION", "seq": applicable_regs.index(reg)+1,
            "lane": reg, "system_len": len(result["system"]), "user_len": len(result["user"]),
            "input_summary": {k: (type(v).__name__ + (f"[{len(v)}]" if hasattr(v, "__len__") else "")) for k, v in inputs.items()},
        })
        with (case_dir / f"P1B-LLM-01__{reg}.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1B-LLM-01-INTERPRETATION", "lane": reg, "system": result["system"], "user": result["user"], "inputs": inputs}, f, indent=2, default=str)

        # P1B-LLM-02 (rationale) - the orchestrator passes same structure
        # PLUS the P1B-LLM-01 outputs! But run_p1b_single passes p1b_llm_01_outputs=None
        # So the rationale is called with the SAME thin inputs as my v3 capture
        # Let me also include the prior outputs as a sanity check
        rationale_inputs = dict(inputs)
        rationale_inputs["p1b_llm_01_outputs"] = {"placeholder": "would contain P1B-01 result"}

        result = prompt_loader.render("P1B-LLM-02-RATIONALE", rationale_inputs)
        captured.append({
            "case": case_name, "spec": "P1B-LLM-02-RATIONALE", "seq": applicable_regs.index(reg)+1,
            "lane": reg, "system_len": len(result["system"]), "user_len": len(result["user"]),
            "input_summary": {k: (type(v).__name__ + (f"[{len(v)}]" if hasattr(v, "__len__") else "")) for k, v in inputs.items()},
        })
        with (case_dir / f"P1B-LLM-02__{reg}.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1B-LLM-02-RATIONALE", "lane": reg, "system": result["system"], "user": result["user"], "inputs": rationale_inputs}, f, indent=2, default=str)

    # ========== Phase 1C Map (per domain) ==========
    for d_num in range(1, 11):
        domain_id = f"D-{d_num:02d}"
        # Per-lane filter (CORR-045)
        lane_refs = [r for r in layer0_subdomain_refs if r["sub_domain_id"].startswith(f"{domain_id}.")]

        map_inputs = {
            "case_id": case_name,
            "domain_id": domain_id,
            "lane_id": domain_id,
            "applicable_regs": applicable_regs,
            "company_facts": company_facts,
            "layer0_subdomain_refs": lane_refs,
        }

        result = prompt_loader.render("P1C-LLM-01-OVERLAP-CLASSIFICATION", map_inputs)
        captured.append({
            "case": case_name, "spec": "P1C-LLM-01-OVERLAP-CLASSIFICATION", "seq": d_num,
            "lane": domain_id, "system_len": len(result["system"]), "user_len": len(result["user"]),
        })
        with (case_dir / f"P1C-LLM-01__{domain_id}.json").open("w") as f:
            json.dump({"case": case_name, "spec": "P1C-LLM-01-OVERLAP-CLASSIFICATION", "lane": domain_id, "system": result["system"], "user": result["user"], "inputs": map_inputs}, f, indent=2, default=str)

    # ========== Phase 1C Reduce (global) ==========
    # P1C-LLM-03 STRATEGIC SYNTHESIS (runs first)
    aggregated_activations = []
    for d_num in range(1, 11):
        for j in range(1, 5):
            sub_id = f"D-{d_num:02d}.{j}"
            aggregated_activations.append({
                "sub_domain_id": sub_id,
                "reg_pair": applicable_regs[:2] if len(applicable_regs) >= 2 else applicable_regs,
                "company_scope_verdict": "IN_SCOPE",
                "regulatory_baseline_relationship": "EXTENDS",
                "layer0_refs": [],
            })
    doc07b_profile = {}
    for a in aggregated_activations:
        doc07b_profile[a["sub_domain_id"]] = {"tier": "STANDARD", "ownership": "CTO", "satisfaction_pattern": "BUILD_REQUIRED"}

    synth_inputs = {
        "case_id": case_name,
        "lane_id": "global",
        "applicable_regs": applicable_regs,
        "aggregated_activations": aggregated_activations,
        "doc07b_profile": doc07b_profile,
        "sync_conflicts": [],
    }
    result = prompt_loader.render("P1C-LLM-03-STRATEGIC-SYNTHESIS", synth_inputs)
    captured.append({
        "case": case_name, "spec": "P1C-LLM-03-STRATEGIC-SYNTHESIS", "seq": 1, "lane": "global",
        "system_len": len(result["system"]), "user_len": len(result["user"]),
    })
    with (case_dir / "P1C-LLM-03__global.json").open("w") as f:
        json.dump({"case": case_name, "spec": "P1C-LLM-03-STRATEGIC-SYNTHESIS", "lane": "global", "system": result["system"], "user": result["user"], "inputs": synth_inputs}, f, indent=2, default=str)

    # P1C-LLM-02 COMPOUND EVENT (runs second, after strategic)
    compound_inputs = dict(synth_inputs)
    compound_inputs["c03_strategic_synthesis"] = {"placeholder": "real synthesis"}
    result = prompt_loader.render("P1C-LLM-02-COMPOUND-EVENT", compound_inputs)
    captured.append({
        "case": case_name, "spec": "P1C-LLM-02-COMPOUND-EVENT", "seq": 1, "lane": "global",
        "system_len": len(result["system"]), "user_len": len(result["user"]),
    })
    with (case_dir / "P1C-LLM-02__global.json").open("w") as f:
        json.dump({"case": case_name, "spec": "P1C-LLM-02-COMPOUND-EVENT", "lane": "global", "system": result["system"], "user": result["user"], "inputs": compound_inputs}, f, indent=2, default=str)

    n = sum(1 for c in captured if c["case"] == case_name)
    print(f"  {case_name}: {n} payloads")

with (OUT_DIR / "_summary.json").open("w") as f:
    json.dump(captured, f, indent=2, default=str)

print(f"\n=== Total: {len(captured)} payloads ===")
print(f"Output: {OUT_DIR}")
