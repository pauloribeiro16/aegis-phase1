#!/usr/bin/env python3
"""AEGIS Phase 1 v1.2 - Interactive beaupy menu for Phase1Executor runs."""
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import beaupy
except ImportError:
    print("ERROR: beaupy not installed. Run: pip install beaupy")
    sys.exit(1)


PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs" / "phase1"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
MENU_HISTORY = LOGS_DIR / "menu_history.jsonl"


# === Configuration state ===
CONFIG = {
    "case": "Case 01 - TinyTask SaaS (2 regs: GDPR, CRA)",
    "mode": "Mock (no Ollama, fast)",
    "scope": "Full Pipeline (1B + 1C Map + 1C Reduce)",
    "llm": "(All 5)",
}

CASES = {
    "Case 01 - TinyTask SaaS (2 regs: GDPR, CRA)": {
        "case_id": "Case_01_TinyTask_SaaS",
        "applicable_regs": ["GDPR", "CRA"],
    },
    "Case 02 - SecureBorder (4 regs)": {
        "case_id": "Case_02_SecureBorder_Solutions",
        "applicable_regs": ["GDPR", "CRA", "NIS2", "AI_Act"],
    },
    "Case 03 - OmniBank (5 regs)": {
        "case_id": "Case_03_OmniBank_Financial",
        "applicable_regs": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
    },
}

MODES = [
    "Mock (no Ollama, fast, uses fixtures in data/)",
    "Real (Ollama + gemma4:e2b, slow)",
]

SCOPES = [
    "Full Pipeline (1B + 1C Map + 1C Reduce)",
    "Phase 1B only (per-regulation)",
    "Phase 1C Map only (10 lanes)",
    "Phase 1C Reduce only",
    "Single LLM (specify next)",
    "Run unit tests (pytest)",
]

LLMS = [
    "P1B-LLM-01-INTERPRETATION",
    "P1B-LLM-02-RATIONALE",
    "P1C-LLM-01-OVERLAP-CLASSIFICATION",
    "P1C-LLM-02-COMPOUND-EVENT",
    "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    "<- Back (cancel)",
]


def log_history(event: str, data: dict) -> None:
    """Append a JSONL entry to menu_history.jsonl."""
    entry = {"timestamp": datetime.now(UTC).isoformat(), "event": event, **data}
    with open(MENU_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def show_menu() -> None:
    print("\n" + "=" * 60)
    print(" AEGIS Phase 1 v1.2 - Interactive Menu (beaupy)")
    print("=" * 60)
    print("\n  Current configuration:")
    print(f"    Case:   {CONFIG['case']}")
    print(f"    Mode:   {CONFIG['mode']}")
    print(f"    Scope:  {CONFIG['scope']}")
    print(f"    LLM:    {CONFIG['llm']}")
    print("\n  Actions:")


def select_case() -> None:
    choice = beaupy.select(options=list(CASES.keys()), return_index=False)
    CONFIG["case"] = choice
    log_history("select_case", {"case": choice})
    print(f"  -> Case set to: {choice}")


def select_mode() -> None:
    choice = beaupy.select(options=MODES, return_index=False)
    CONFIG["mode"] = choice
    log_history("select_mode", {"mode": choice})
    print(f"  -> Mode set to: {choice}")


def select_scope() -> None:
    choice = beaupy.select(options=SCOPES, return_index=False)
    CONFIG["scope"] = choice
    log_history("select_scope", {"scope": choice})
    print(f"  -> Scope set to: {choice}")


def select_llm() -> None:
    choice = beaupy.select(options=LLMS, return_index=False)
    if "Back" in choice:
        return
    CONFIG["llm"] = choice
    log_history("select_llm", {"llm": choice})
    print(f"  -> LLM set to: {choice}")


def run_unit_tests() -> None:
    print("\n  Running pytest on tests/unit/ ...")
    result = subprocess.run(
        ["pytest", "tests/unit/", "-v",
         "--ignore=tests/unit/prompts_v2/test_smoke_e2e.py",
         "--ignore=tests/unit/test_phase1_e2e_ollama.py"],
        cwd=str(PROJECT_ROOT),
    )
    log_history("run_unit_tests", {"returncode": result.returncode})


def build_invoker():
    """Build the appropriate invoker (Mock or Real) for the current mode.

    Class MockPhase1LLMInvoker is defined further down; this function uses
    the module-level binding so it works whether the file is executed as
    ``python scripts/run_phase1.py`` (name == "__main__") or imported as
    ``from scripts import run_phase1`` in tests.
    """
    is_mock = "Mock" in CONFIG["mode"]
    if is_mock:
        return MockPhase1LLMInvoker(project_root=PROJECT_ROOT)
    else:
        from aegis_phase1.prompts_v2 import get_invoker
        return get_invoker()


def _build_executor(invoker):
    """Construct a Phase1Executor wired with the given invoker."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.loader import PromptLoader
    from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
    from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
    from aegis_phase1.prompts_v2.track_b import TrackB
    from aegis_phase1.prompts_v2.validator import Phase1Validator

    pl = PromptLoader()
    cl = CatalogLoader()
    val = Phase1Validator(layer0_root=pl.root.parent / "PREPROCESSING" / "SubDomains")
    ll = JSONLLogger(LOGS_DIR / "llm-calls.jsonl")
    fl = JSONLLogger(LOGS_DIR / "format-errors.jsonl")
    tb = TrackB()
    ex = Phase1Executor(pl, cl, val, ll, fl, track_b=tb)
    ex.invoker = invoker
    return ex


def run_full_pipeline() -> None:
    case_info = CASES[CONFIG["case"]]
    invoker = build_invoker()
    ex = _build_executor(invoker)
    print(f"\n  Running Full Pipeline for {case_info['case_id']} ...")
    result = ex.run(case_info["case_id"], case_info["applicable_regs"])
    p1b_status = result["phase_1b"]["status"]
    p1c_map_lanes = len(result["phase_1c_map"])
    sync_status = result["sync"]["status"]
    reduce_status = result["phase_1c_reduce"]["status"]
    print(f"  -> Status: {p1b_status}")
    print(f"  -> Phase 1C Map lanes: {p1c_map_lanes}")
    print(f"  -> Sync conflicts: {sync_status}")
    print(f"  -> Reduce: {reduce_status}")
    log_history("run_full_pipeline", {
        "case": case_info["case_id"],
        "mode": CONFIG["mode"],
        "phase_1b_status": p1b_status,
        "sync_status": sync_status,
        "reduce_status": reduce_status,
    })


def run_phase_1b() -> None:
    case_info = CASES[CONFIG["case"]]
    invoker = build_invoker()
    ex = _build_executor(invoker)
    print(f"\n  Running Phase 1B for {case_info['case_id']} ...")
    result = ex.run_phase_1b(case_info["case_id"], case_info["applicable_regs"])
    print(f"  -> Status: {result['status']}")
    print(f"  -> Per-reg: {list(result['per_reg'].keys())}")
    log_history("run_phase_1b", {"case": case_info["case_id"], "status": result["status"]})


def run_phase_1c_map() -> None:
    case_info = CASES[CONFIG["case"]]
    invoker = build_invoker()
    ex = _build_executor(invoker)
    print(f"\n  Running Phase 1C Map (10 lanes) for {case_info['case_id']} ...")
    result = ex.run_phase_1c_map(case_info["case_id"], case_info["applicable_regs"])
    print(f"  -> Lanes: {len(result)}")
    for lane in result:
        print(f"    {lane['lane_id']}: {lane['status']} ({lane['latency_ms']:.0f}ms)")
    log_history("run_phase_1c_map", {"case": case_info["case_id"], "lanes": len(result)})


def run_phase_1c_reduce() -> None:
    case_info = CASES[CONFIG["case"]]
    invoker = build_invoker()
    ex = _build_executor(invoker)
    print(f"\n  Running Phase 1C Reduce for {case_info['case_id']} ...")
    lane_outputs = []
    for i in range(10):
        lane_outputs.append({
            "lane_id": f"D-{i + 1:02d}",
            "status": "OK",
            "sub_domain_activations": [],
        })
    sync_result = ex.run_sync(lane_outputs)
    result = ex.run_phase_1c_reduce(case_info["case_id"], lane_outputs, sync_result)
    print(f"  -> LLM-03 status: {result['P1C-LLM-03']['status']}")
    print(f"  -> LLM-02 status: {result['P1C-LLM-02']['status']}")
    print(f"  -> Overall: {result['status']}")
    log_history("run_phase_1c_reduce", {"case": case_info["case_id"], "status": result["status"]})


def run_single_llm() -> None:
    case_info = CASES[CONFIG["case"]]
    spec_id = CONFIG["llm"]
    invoker = build_invoker()
    print(f"\n  Running single LLM: {spec_id} for {case_info['case_id']} ...")
    if "P1B" in spec_id:
        inputs = {
            "case_id": case_info["case_id"],
            "lane_id": case_info["applicable_regs"][0],
            "applicable_regs": [case_info["applicable_regs"][0]],
            "classification": {"role": "Controller", "tier": "LOW"},
            "company_facts": {
                "sector": "saas",
                "employees": 8,
                "is_manufacturer": False,
                "processes_eu_personal_data": True,
            },
            "layer0_catalog": {},
            "layer0_subdomain_refs": [],
        }
    else:
        inputs = {
            "case_id": case_info["case_id"],
            "lane_id": "D-01",
            "applicable_regs": case_info["applicable_regs"][:2],
            "company_facts": {"sector": "saas", "employees": 8},
            "coverage_entries": [],
            "complementarity_data": [],
        }
    result = invoker.invoke(spec_id, inputs, max_retries=1)
    print(f"  -> Status: {result.get('status')}")
    print(f"  -> Total latency: {result.get('total_latency_ms', 0):.0f}ms")
    print(f"  -> Retry count: {result.get('retry_count', 0)}")
    log_history("run_single_llm", {"spec_id": spec_id, "case": case_info["case_id"], "status": result.get("status")})


def run_action() -> None:
    scope = CONFIG["scope"]
    if "unit tests" in scope:
        run_unit_tests()
    elif "Full Pipeline" in scope:
        run_full_pipeline()
    elif "Phase 1B" in scope and "1B" in scope and "1C" not in scope:
        run_phase_1b()
    elif "Phase 1C Map" in scope:
        run_phase_1c_map()
    elif "Phase 1C Reduce" in scope:
        run_phase_1c_reduce()
    elif "Single LLM" in scope:
        run_single_llm()
    else:
        print(f"  ! Unknown scope: {scope}")


def main() -> None:
    while True:
        show_menu()
        choice = beaupy.select(
            options=[
                "1) Select Case",
                "2) Select LLM Mode (Mock / Real)",
                "3) Select Scope",
                "4) Select Specific LLM",
                "5) Run with current configuration",
                "6) Exit",
            ],
            return_index=False,
        )
        if "1)" in choice:
            select_case()
        elif "2)" in choice:
            select_mode()
        elif "3)" in choice:
            select_scope()
        elif "4)" in choice:
            if "Single LLM" not in CONFIG["scope"]:
                print("  ! Step 4 only valid if Scope = 'Single LLM'. Change scope first.")
            else:
                select_llm()
        elif "5)" in choice:
            run_action()
        elif "6)" in choice:
            log_history("exit", {})
            print("\nGoodbye.")
            break


# === Mock invoker for tests ===
class MockPhase1LLMInvoker:
    """Stub invoker that returns canned responses from data/fixtures/.

    Looks up fixtures by {case_id}_{spec_id}.json or
    {case_id}_{lane_id}_{spec_id}.json. Falls back to a generic empty
    ``OK`` response if no fixture matches. Used by ``python scripts/run_phase1.py``
    in Mock mode so the menu can be exercised without Ollama running.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.fixtures_dir = project_root / "data" / "fixtures"

    def invoke(self, spec_id: str, inputs: dict, max_retries: int = 2) -> dict:
        case_id = inputs.get("case_id", "unknown")
        lane_id = inputs.get("lane_id", "")

        # Extract case number from case_id ("Case_01_TinyTask_SaaS" -> "01")
        m = re.match(r"Case_(\d+)_", case_id)
        case_num = m.group(1) if m else "01"

        # Build short spec slug from spec_id
        # "P1B-LLM-01-INTERPRETATION" -> "p1b01"
        # "P1C-LLM-01-OVERLAP-CLASSIFICATION" -> "p1c01"
        parts = spec_id.split("-")
        spec_slug = (parts[0] + parts[2]).lower() if len(parts) >= 3 else spec_id.lower()

        # Lookup candidates: try multiple naming conventions before fallback
        candidates: list[str] = []
        # 1) Descriptive naming used by data/fixtures/
        if lane_id:
            candidates.append(f"case_{case_num}_{lane_id.lower().replace("-", "")}_{spec_slug}_response.json")
        # 2) Strict canonical: {case_id}_{spec_id}.json
        candidates.append(f"{case_id}_{spec_id}.json")
        # 3) Strict canonical with lane_id: {case_id}_{lane_id}_{spec_id}.json
        if lane_id:
            candidates.append(f"{case_id}_{lane_id}_{spec_id}.json")

        for fname in candidates:
            fpath = self.fixtures_dir / fname
            if fpath.exists():
                with open(fpath, encoding="utf-8") as f:
                    fixture = json.load(f)
                fixture["retry_count"] = 1
                fixture["total_latency_ms"] = fixture.get("total_latency_ms", 50)
                return fixture
        return {
            "status": "OK",
            "parsed_output": {},
            "total_latency_ms": 10,
            "retry_count": 1,
        }


if __name__ == "__main__":
    main()
