"""Regenerate pipeline-inputs golden fixtures.

This is the **regen script** for the pipeline-inputs contract
(documented in `tests/fixtures/pipeline_inputs_golden/_schema.json`).
Run it whenever:

1. A new spec is added to PROMPTS/ and the contract gains a new entry
2. The pipeline gains/loses an applicable regulation
3. A new test case is added to `cases/`
4. The orchestrator's `run_p1b_single` / `run_phase_1c_map` input
   construction changes (intentionally, with justification)

The script:
1. Loads the schema (required fields per spec)
2. Replays `PromptLoader.render(spec, inputs)` with the same input
   construction as the orchestrator (mimicking `run_p1b_single` and
   `run_phase_1c_map` line-by-line)
3. Writes one JSON per (case, spec, lane) into
   `tests/fixtures/pipeline_inputs_golden/<case>/`
4. Records only the **inputs dict** + **size metadata** — NOT the full
   rendered prompt text (which is too large to commit, 570K each).
   The full rendered text is regenerated at test time.

Usage:
    python _regenerate_pipeline_inputs_golden.py

Output:
    tests/fixtures/pipeline_inputs_golden/
    ├── _schema.json
    ├── case1-tinytask/      (16 files)
    ├── case2-secureborder/  (20 files)
    └── case3-omnibank/      (22 files)
"""
import json
import logging
import shutil
from pathlib import Path
from unittest.mock import MagicMock

logging.basicConfig(level=logging.ERROR)

# ── Configure ──────────────────────────────────────────────────────────
PROMPTS_ROOT = Path(
    "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/00_METHODOLOGY/PROMPTS"
)
PREPROC_ROOT = Path("preproc_out")
GOLDEN_ROOT = Path("tests/fixtures/pipeline_inputs_golden")
SCHEMA_PATH = GOLDEN_ROOT / "_schema.json"

# Ensure the golden root exists
GOLDEN_ROOT.mkdir(parents=True, exist_ok=True)

from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

# ── Load data ──────────────────────────────────────────────────────────
catalog_loader = CatalogLoader(root=PROMPTS_ROOT / "catalogs")
preproc_loader = PreprocCatalogLoader(preproc_root=str(PREPROC_ROOT))
prompt_loader = PromptLoader(root=PROMPTS_ROOT)

tipo2_all = catalog_loader.load("tipo2_interpretations")
tipo3_all = catalog_loader.load("tipo3_derogations")
all_subdomains = preproc_loader.load_subdomains()
print(f"Loaded {len(tipo2_all)} tipo2, {len(tipo3_all)} tipo3, {len(all_subdomains)} sub-domains")


# ── Helpers (mirror orchestrator) ──────────────────────────────────────
def build_layer0_refs(subdomain_ids):
    """Mirror orchestrator._build_layer0_subdomain_refs exactly.

    The previous implementation included the full ``hso_hl`` and
    ``hso_per_reg`` Pydantic repr strings (~15K per ref). The
    orchestrator only carries ``hso_hl_objective`` (extracted string),
    which produces ~3K per ref and brings the post-filter payload
    under the CORR-049 512KB cap.
    """
    by_id = {s.id: s for s in all_subdomains}
    refs = []
    for sid in subdomain_ids:
        sd = by_id.get(sid)
        if sd is None:
            continue
        anchors: list[str] = []
        for sr in (getattr(sd, "security_requirements", None) or []):
            anchors.extend(getattr(sr, "anchors", None) or [])
        objective = sd.hso_hl.objective if getattr(sd, "hso_hl", None) else None
        pairs = [
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in (getattr(sd, "pairs", None) or [])
        ]
        refs.append({
            "sub_domain_id": sd.id,
            "title": getattr(sd, "title", None) or sd.id,
            "domain_id": getattr(sd, "domain_id", None) or sd.id.split(".")[0],
            "participating_regulations": list(
                getattr(sd, "participating_regulations", None) or []
            ),
            "hso_hl_objective": objective,
            "objective": objective,
            "pairs": pairs,
            "anchors": sorted(set(anchors)),
            "csf": list(getattr(sd, "csf_hint", None) or []),
        })
    return refs


def make_coverage_row(reg):
    """Empty coverage matrix row (matches orchestrator's degraded path)."""
    return []


# ── Case definitions (kept in sync with the schema) ───────────────────
CASES = {
    "case1-tinytask": ["GDPR", "CRA"],
    "case2-secureborder": ["GDPR", "CRA", "NIS2", "AI_Act"],
    "case3-omnibank": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
}

all_subdomain_ids = [s.id for s in all_subdomains]


# ── Generation loop ───────────────────────────────────────────────────
for case_name, applicable_regs in CASES.items():
    case_dir = GOLDEN_ROOT / case_name
    # Clean before regenerating (removes stale entries)
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)

    profile = CaseProfileLoader(Path(f"cases/{case_name}")).load()
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

    # ── Phase 1B (per regulation) ────────────────────────────────
    layer0_subdomain_refs = build_layer0_refs(all_subdomain_ids)

    for reg in applicable_regs:
        tipo2_filtered = catalog_loader.filter_applicable(
            tipo2_all, regulation=reg, tier=company_facts["complexity_tier"]
        )
        tipo3_filtered = catalog_loader.filter_applicable(
            tipo3_all, regulation=reg, tier=company_facts["complexity_tier"]
        )
        try:
            tipo3_evaluated = catalog_loader.evaluate_predicates(
                tipo3_filtered, company_facts
            )
            tipo3_enriched = [
                {**e, "predicate_verdict": v} for e, v in tipo3_evaluated
            ]
        except Exception:
            tipo3_enriched = tipo3_filtered
        layer0_catalog = {"tipo2": tipo2_filtered, "tipo3": tipo3_enriched}

        # CORR-071: per-reg filter mirrors phase1_executor.run_phase_1b
        # (same predicate: ``reg in ref.participating_regulations``).
        # The executor applies this filter at runtime so the LLM
        # receives only refs where the regulation participates.
        # Goldens must reflect what the LLM actually sees.
        lane_refs = [
            r for r in layer0_subdomain_refs
            if reg in (r.get("participating_regulations") or [])
        ]

        inputs = {
            "case_id": case_name,
            "lane_id": reg,
            "applicable_regs": [reg],
            "company_facts": company_facts,
            "classification": classification,
            "coverage_matrix_row": make_coverage_row(reg),
            "aggregated_activations": [],
            "layer0_subdomain_refs": lane_refs,
            "layer0_catalog": layer0_catalog,
        }

        # Render to capture size metadata
        result = prompt_loader.render("P1B-LLM-01-INTERPRETATION", inputs)
        golden = {
            "case": case_name,
            "spec": "P1B-LLM-01-INTERPRETATION",
            "lane": reg,
            "inputs": inputs,
            "rendered": {
                "system_len": len(result["system"]),
                "user_len": len(result["user"]),
            },
        }
        with (case_dir / f"P1B-LLM-01__{reg}.json").open("w") as f:
            json.dump(golden, f, indent=2, default=str)

        # P1B-LLM-02 (rationale) — same inputs + p1b_llm_01_outputs placeholder
        rationale_inputs = dict(inputs)
        rationale_inputs["p1b_llm_01_outputs"] = {
            "placeholder": "would contain P1B-01 result in real run"
        }
        result = prompt_loader.render("P1B-LLM-02-RATIONALE", rationale_inputs)
        golden = {
            "case": case_name,
            "spec": "P1B-LLM-02-RATIONALE",
            "lane": reg,
            "inputs": rationale_inputs,
            "rendered": {
                "system_len": len(result["system"]),
                "user_len": len(result["user"]),
            },
        }
        with (case_dir / f"P1B-LLM-02__{reg}.json").open("w") as f:
            json.dump(golden, f, indent=2, default=str)

    # ── Phase 1C Map (per domain) ─────────────────────────────────
    for d_num in range(1, 11):
        domain_id = f"D-{d_num:02d}"
        lane_refs = [
            r for r in layer0_subdomain_refs
            if r["sub_domain_id"].startswith(f"{domain_id}.")
        ]
        map_inputs = {
            "case_id": case_name,
            "domain_id": domain_id,
            "lane_id": domain_id,
            "applicable_regs": applicable_regs,
            "company_facts": company_facts,
            "layer0_subdomain_refs": lane_refs,
        }
        result = prompt_loader.render(
            "P1C-LLM-01-OVERLAP-CLASSIFICATION", map_inputs
        )
        golden = {
            "case": case_name,
            "spec": "P1C-LLM-01-OVERLAP-CLASSIFICATION",
            "lane": domain_id,
            "inputs": map_inputs,
            "rendered": {
                "system_len": len(result["system"]),
                "user_len": len(result["user"]),
            },
        }
        with (case_dir / f"P1C-LLM-01__{domain_id}.json").open("w") as f:
            json.dump(golden, f, indent=2, default=str)

    # ── Phase 1C Reduce (global) ──────────────────────────────────
    aggregated_activations = []
    for d_num in range(1, 11):
        for j in range(1, 5):
            sub_id = f"D-{d_num:02d}.{j}"
            aggregated_activations.append({
                "sub_domain_id": sub_id,
                "reg_pair": (
                    applicable_regs[:2] if len(applicable_regs) >= 2
                    else applicable_regs
                ),
                "company_scope_verdict": "IN_SCOPE",
                "regulatory_baseline_relationship": "EXTENDS",
                "layer0_refs": [],
            })
    doc07b_profile = {
        a["sub_domain_id"]: {
            "tier": "STANDARD",
            "ownership": "CTO",
            "satisfaction_pattern": "BUILD_REQUIRED",
        }
        for a in aggregated_activations
    }

    synth_inputs = {
        "case_id": case_name,
        "lane_id": "global",
        "applicable_regs": applicable_regs,
        "aggregated_activations": aggregated_activations,
        "doc07b_profile": doc07b_profile,
        "sync_conflicts": [],
    }
    result = prompt_loader.render(
        "P1C-LLM-03-STRATEGIC-SYNTHESIS", synth_inputs
    )
    golden = {
        "case": case_name,
        "spec": "P1C-LLM-03-STRATEGIC-SYNTHESIS",
        "lane": "global",
        "inputs": synth_inputs,
        "rendered": {
            "system_len": len(result["system"]),
            "user_len": len(result["user"]),
        },
    }
    with (case_dir / "P1C-LLM-03__global.json").open("w") as f:
        json.dump(golden, f, indent=2, default=str)

    compound_inputs = dict(synth_inputs)
    compound_inputs["c03_strategic_synthesis"] = {
        "placeholder": "real synthesis"
    }
    result = prompt_loader.render("P1C-LLM-02-COMPOUND-EVENT", compound_inputs)
    golden = {
        "case": case_name,
        "spec": "P1C-LLM-02-COMPOUND-EVENT",
        "lane": "global",
        "inputs": compound_inputs,
        "rendered": {
            "system_len": len(result["system"]),
            "user_len": len(result["user"]),
        },
    }
    with (case_dir / "P1C-LLM-02__global.json").open("w") as f:
        json.dump(golden, f, indent=2, default=str)

    n = sum(1 for _ in case_dir.glob("*.json"))
    print(f"  {case_name}: {n} golden files")

print(f"\n=== Regenerated golden files in {GOLDEN_ROOT} ===")
print("Next step: review the diff, then commit.")
