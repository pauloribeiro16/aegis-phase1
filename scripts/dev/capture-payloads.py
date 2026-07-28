"""Capture post-CORR-071 payloads for cases 1, 2, 3.

Uses the REAL Phase1Executor.run_phase_1b and run_phase_1c_map (which
contain the CORR-071 per-reg filter and CORR-045 per-domain filter).
The invoker is mocked to capture (spec_id, inputs, rendered prompt)
and return a fake response — no LLM calls.

Output: /tmp/payload_capture_corr071/<case>/<spec>__<lane>.json
Plus a summary table printed to stdout.

Applicable regs per case (from orchestrator's LOAD stage):
  case1-tinytask:      GDPR, CRA                 (2 regs)
  case2-secureborder:  GDPR, CRA, NIS2, AI_Act   (4 regs)
  case3-omnibank:      GDPR, CRA, NIS2, DORA, AI_Act (5 regs)
"""
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

logging.basicConfig(level=logging.ERROR)

PROMPTS_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS")
PREPROC_ROOT = Path("preproc_out")
OUT_DIR = Path("/tmp/payload_capture_corr071")
OUT_DIR.mkdir(parents=True, exist_ok=True)

from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

catalog_loader = CatalogLoader(root=PROMPTS_ROOT / "catalogs")
preproc_loader = PreprocCatalogLoader(preproc_root=str(PREPROC_ROOT))
prompt_loader = PromptLoader(root=PROMPTS_ROOT)

tipo2_all = catalog_loader.load("tipo2_interpretations")
tipo3_all = catalog_loader.load("tipo3_derogations")
all_subdomains = preproc_loader.load_subdomains()


def build_layer0_refs(subdomain_ids):
    """Mimic orchestrator's _build_layer0_subdomain_refs."""
    by_id = {s.id: s for s in all_subdomains}
    refs = []
    for sid in subdomain_ids:
        sd = by_id.get(sid)
        if sd is None:
            continue
        anchors = []
        for sr in (sd.security_requirements or []):
            anchors.extend(sr.anchors or [])
        objective = sd.hso_hl.objective if sd.hso_hl else None
        refs.append({
            "sub_domain_id": sd.id,
            "domain_id": sd.domain_id,
            "title": sd.title,
            "participating_regulations": list(sd.participating_regulations or []),
            "hso_hl_objective": objective,
            "objective": objective,
            "pairs": [p.model_dump() if hasattr(p, "model_dump") else p for p in (sd.pairs or [])],
            "anchors": sorted(set(anchors)),
            "csf": list(sd.csf_hint or []),
        })
    return refs


captured = []


class MockInvoker:
    """Capture (spec_id, inputs) and render to disk; never call LLM."""

    def __init__(self, out_dir):
        self.out_dir = out_dir

    def invoke(self, spec_id, inputs, **kwargs):
        prompt = prompt_loader.render(spec_id, inputs)
        out_file = self.out_dir / f"{spec_id}__{inputs['lane_id']}.json"
        out_file.write_text(json.dumps({
            "case": inputs.get("case_id"),
            "spec": spec_id,
            "lane": inputs.get("lane_id"),
            "system": prompt["system"],
            "user": prompt["user"],
            "inputs": inputs,
        }, indent=2, default=str))
        captured.append({
            "spec_id": spec_id,
            "lane": inputs.get("lane_id"),
            "system_len": len(prompt["system"]),
            "user_len": len(prompt["user"]),
            "n_refs": len(inputs.get("layer0_subdomain_refs") or []),
            "ref_ids": [r.get("sub_domain_id") for r in (inputs.get("layer0_subdomain_refs") or [])],
        })
        return {
            "status": "OK",
            "parsed_output": {"placeholder": True, "spec_id": spec_id},
            "retry_count": 0,
            "invocation_pattern": "captured",
        }


executor = Phase1Executor(
    invoker=MockInvoker(OUT_DIR),  # placeholder, replaced per case below
    catalog_loader=catalog_loader,
    prompt_loader=prompt_loader,
    validator=MagicMock(),
    llm_logger=MagicMock(),
    format_logger=MagicMock(),
)


CASES = {
    "case1-tinytask": ["GDPR", "CRA"],
    "case2-secureborder": ["GDPR", "CRA", "NIS2", "AI_Act"],
    "case3-omnibank": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
}

all_subdomain_ids = [s.id for s in all_subdomains]


for case_name, applicable_regs in CASES.items():
    case_dir = OUT_DIR / case_name
    # Wipe case dir to avoid stale files from prior runs (esp. case1)
    if case_dir.exists():
        for old in case_dir.iterdir():
            old.unlink()
    case_dir.mkdir(parents=True, exist_ok=True)
    # Update the executor's invoker to write into this case's dir
    executor.invoker = MockInvoker(case_dir)
    profile = CaseProfileLoader(Path(f"cases/{case_name}")).load()

    company_facts = {
        "name": profile.company.name,
        "sector": profile.company.sector,
        "jurisdiction": profile.company.jurisdiction,
        "scale": profile.company.scale,
        "employees": profile.company.employees,
        "role": "controller",
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
    coverage_rows = []

    # ========== Phase 1B (per regulation) via REAL run_phase_1b ==========
    layer0_subdomain_refs = build_layer0_refs(all_subdomain_ids)

    aggregated_activations = []
    for d_num in range(1, 11):
        for j in range(1, 5):
            sub_id = f"D-{d_num:02d}.{j}"
            aggregated_activations.append({
                "sub_domain_id": sub_id,
                "reg_pair": applicable_regs[:2] if len(applicable_regs) >= 2 else applicable_regs,
                "company_scope_verdict": "IN_SCOPE",
                "regulatory_baseline_relationship": "EXTENDS",
            })

    # Filter catalogs once per reg (mimic orchestrator's _load_filtered_catalogs_for_reg)
    for reg in applicable_regs:
        tipo2_filtered = catalog_loader.filter_applicable(tipo2_all, regulation=reg, tier=company_facts["complexity_tier"])
        tipo3_filtered = catalog_loader.filter_applicable(tipo3_all, regulation=reg, tier=company_facts["complexity_tier"])
        try:
            tipo3_evaluated = catalog_loader.evaluate_predicates(tipo3_filtered, company_facts)
            tipo3_enriched = [{**e, "predicate_verdict": v} for e, v in tipo3_evaluated]
        except Exception:
            tipo3_enriched = tipo3_filtered
        layer0_catalog = {"tipo2": tipo2_filtered, "tipo3": tipo3_enriched}

        # Call the REAL run_phase_1b (CORR-071 filter applies here)
        result = executor.run_phase_1b(
            case_id=case_name,
            applicable_regs=[reg],
            company_facts=company_facts,
            classification=classification,
            coverage_matrix_row=coverage_rows,
            aggregated_activations=aggregated_activations,
            layer0_catalog=layer0_catalog,
            layer0_subdomain_refs=layer0_subdomain_refs,
            config=None,
            state=None,
        )

    # ========== Phase 1C Map (per domain) via REAL run_phase_1c_map ==========
    executor.run_phase_1c_map(
        case_id=case_name,
        applicable_regs=applicable_regs,
        state=None,
        company_facts=company_facts,
        classification=classification,
        aggregated_activations=aggregated_activations,
        layer0_subdomain_refs=layer0_subdomain_refs,
    )

print()
print(f"=== POST-CORR-071 PAYLOAD CAPTURE (mock invoker, no LLM calls) ===")
print(f"Cases: {list(CASES.keys())}")
print(f"Output: {OUT_DIR}/<case>/<spec>__<lane>.json (rendered prompt + inputs)")
print()

print(f"{'Spec':<35} {'Lane':<10} {'#refs':>6} {'user_bytes':>11} {'sys_bytes':>10}")
print(f"{'-'*35} {'-'*10} {'-'*6:>6} {'-'*11:>11} {'-'*10:>10}")
for c in captured:
    print(f"{c['spec_id']:<35} {c['lane']:<10} {c['n_refs']:>6} {c['user_len']:>11} {c['system_len']:>10}")

print()
print("=== Reference: pre-CORR-071 sizes (575K cap = 524288 bytes) ===")
print(f"{'P1B-01/02 pre-CORR-071':<35} {'all regs':<10} {38:>6} {575000:>11} {'above cap':>10}")
print(f"{'P1C-01 pre-CORR-071':<35} {'all D-XX':<10} {38:>6} {575000:>11} {'above cap':>10}")
