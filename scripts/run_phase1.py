#!/usr/bin/env python3
"""AEGIS Phase 1 v1.2 - Interactive wizard menu for Phase1Executor runs.

v1.2 redesign: replaces the original flat 6-option menu with a hub-and-spoke
top-level menu plus a step-by-step configuration wizard. Each step shows
ONE question at a time and offers a Back option to revisit the previous
step. The Confirm step summarises the pending configuration before
returning to the top menu (no auto-run).

Top-level menu:
    1) Configure   - launches the wizard
    2) Run         - shows the current config and asks for confirmation
    3) Exit

Wizard steps (in order):
    1. Case    - which AEGIS case to run
    2. Mode    - Mock (fixture-backed) or Real (Ollama)
    3. Scope   - which Phase 1 sub-pipeline to run
    4. LLM     - (only when Scope = "Single LLM") which LLM spec
    5. Confirm - review and either save the configuration or step back

Legacy ``select_*`` functions are preserved so existing tests keep working.
"""
import json
import re
import subprocess
import sys
from collections.abc import Callable
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


# === Configuration state (persists across wizard sessions until process exits) ===
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

# Used by the legacy select_llm() function (kept for backward-compat tests).
LLMS = [
    "P1B-LLM-01-INTERPRETATION",
    "P1B-LLM-02-RATIONALE",
    "P1C-LLM-01-OVERLAP-CLASSIFICATION",
    "P1C-LLM-02-COMPOUND-EVENT",
    "P1C-LLM-03-STRATEGIC-SYNTHESIS",
    "<- Back (cancel)",
]

# Used by the wizard's step_choose_llm(). Keeps the wizard UI labels
# consistent with the rest of the wizard ("Back" rather than "<- Back (cancel)").
WIZARD_LLMS = [
    "P1B-LLM-01-INTERPRETATION",
    "P1B-LLM-02-RATIONALE",
    "P1C-LLM-01-OVERLAP-CLASSIFICATION",
    "P1C-LLM-02-COMPOUND-EVENT",
    "P1C-LLM-03-STRATEGIC-SYNTHESIS",
]

BACK_LABEL = "Back"


def log_history(event: str, data: dict) -> None:
    """Append a JSONL entry to menu_history.jsonl."""
    entry = {"timestamp": datetime.now(UTC).isoformat(), "event": event, **data}
    with open(MENU_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _print_current_config() -> None:
    """Pretty-print the current CONFIG (used by Confirm step and Run prompt)."""
    print("\n  Current configuration:")
    print(f"    Case:   {CONFIG['case']}")
    print(f"    Mode:   {CONFIG['mode']}")
    print(f"    Scope:  {CONFIG['scope']}")
    print(f"    LLM:    {CONFIG['llm']}")


# === Legacy single-step selectors (kept for backward-compatible tests) ===
def select_case() -> None:
    """Prompt for a case and store it in CONFIG. No Back option."""
    choice = beaupy.select(options=list(CASES.keys()), return_index=False)
    if not choice:
        return
    CONFIG["case"] = choice
    log_history("select_case", {"case": choice})
    print(f"  -> Case set to: {choice}")


def select_mode() -> None:
    choice = beaupy.select(options=MODES, return_index=False)
    if not choice:
        return
    CONFIG["mode"] = choice
    log_history("select_mode", {"mode": choice})
    print(f"  -> Mode set to: {choice}")


def select_scope() -> None:
    choice = beaupy.select(options=SCOPES, return_index=False)
    if not choice:
        return
    CONFIG["scope"] = choice
    log_history("select_scope", {"scope": choice})
    print(f"  -> Scope set to: {choice}")


def select_llm() -> None:
    choice = beaupy.select(options=LLMS, return_index=False)
    if not choice or "Back" in choice:
        return
    CONFIG["llm"] = choice
    log_history("select_llm", {"llm": choice})
    print(f"  -> LLM set to: {choice}")


# === Wizard step functions ===
# Each step returns one of:
#   "next"  - advance to the next step
#   "back"  - go back to the previous step
#   "done"  - wizard finished; return to the top menu (used by Confirm step)


def _is_back(choice: str | None) -> bool:
    """True when the user picked the Back option (or pressed Ctrl-C / Esc)."""
    if not choice:
        return True
    return "Back" in choice


def step_choose_case() -> str:
    """First wizard step: pick a case. No Back option (nothing to go back to)."""
    options = list(CASES.keys())
    choice = beaupy.select(options=options, return_index=False)
    if not choice:
        # Treat Esc/Ctrl-C as "stay on this step" - the user can try again.
        return "back"
    CONFIG["case"] = choice
    log_history("configure_step", {"step": "case", "value": choice})
    return "next"


def step_choose_mode() -> str:
    """Second wizard step: pick Mock vs Real mode."""
    options = [*MODES, BACK_LABEL]
    choice = beaupy.select(options=options, return_index=False)
    if _is_back(choice):
        return "back"
    CONFIG["mode"] = choice  # type: ignore[assignment]
    log_history("configure_step", {"step": "mode", "value": choice})
    return "next"


def step_choose_scope() -> str:
    """Third wizard step: pick the run scope. May trigger an LLM step later."""
    options = [*SCOPES, BACK_LABEL]
    choice = beaupy.select(options=options, return_index=False)
    if _is_back(choice):
        return "back"
    CONFIG["scope"] = choice  # type: ignore[assignment]
    log_history("configure_step", {"step": "scope", "value": choice})
    # If the user is NOT running a single LLM, reset the LLM field to the default
    # so the summary stays consistent (otherwise a stale LLM name would linger).
    if "Single LLM" not in choice:
        CONFIG["llm"] = "(All 5)"
    return "next"


def step_choose_llm() -> str:
    """Wizard step shown only when Scope = "Single LLM". Pick a specific LLM spec."""
    options = [*WIZARD_LLMS, BACK_LABEL]
    choice = beaupy.select(options=options, return_index=False)
    if _is_back(choice):
        return "back"
    CONFIG["llm"] = choice  # type: ignore[assignment]
    log_history("configure_step", {"step": "llm", "value": choice})
    return "next"


def step_confirm() -> str:
    """Final wizard step: review the pending configuration and either save or go back."""
    _print_current_config()
    options = ["Save and return to menu", "Back to Scope"]
    choice = beaupy.select(options=options, return_index=False)
    if _is_back(choice):
        return "back"
    log_history("configure_done", {"config": dict(CONFIG)})
    print("\n  -> Configuration saved.")
    return "done"


# === Wizard loop ===
def _build_steps() -> list[tuple[str, Callable[[], str]]]:
    """Build the ordered step list, conditional on current CONFIG.

    The LLM step only appears when Scope = "Single LLM". This function is
    re-evaluated after every step so that switching scope mid-wizard inserts
    or removes the LLM step on the fly.
    """
    steps: list[tuple[str, Callable[[], str]]] = [
        ("Case", step_choose_case),
        ("Mode", step_choose_mode),
        ("Scope", step_choose_scope),
    ]
    if "Single LLM" in (CONFIG.get("scope") or ""):
        steps.append(("LLM", step_choose_llm))
    steps.append(("Confirm", step_confirm))
    return steps


def configure_wizard() -> None:
    """Walk through the wizard steps with Back navigation.

    The user starts at step 0 (Case) and advances one question at a time.
    Choosing "Back" on any step decrements the index (clamped at 0).
    The Confirm step returns "done" to exit the wizard cleanly.
    """
    idx = 0
    while True:
        steps = _build_steps()
        if idx >= len(steps):
            # All steps confirmed; exit wizard back to top menu.
            return
        if idx < 0:
            idx = 0
        label, step_fn = steps[idx]
        action = step_fn()
        if action == "next":
            idx += 1
        elif action == "back":
            idx -= 1
        elif action == "done":
            return
        else:  # pragma: no cover - defensive
            return


# === Top-level menu ===
def top_menu() -> str:
    """Show the hub-and-spoke top-level menu. Returns one of:
    "configure" | "run" | "exit".
    """
    print("\n" + "=" * 60)
    print("  AEGIS Phase 1 v1.2")
    print("=" * 60)
    options = [
        "1) Configure    (walk through setup one step at a time)",
        "2) Run          (execute with current settings)",
        "3) Exit",
    ]
    choice = beaupy.select(options=options, return_index=False)
    if not choice:
        return "exit"
    if "Configure" in choice:
        return "configure"
    if "Run" in choice:
        return "run"
    return "exit"


# === Run dispatcher and helpers ===
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
    """Dispatch to the appropriate run function based on the current Scope."""
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


def run_action_prompt() -> None:
    """Top-level "Run" action: show current config and ask for confirmation.

    Pressing Enter (empty input) triggers ``run_action()``; any other input
    (including Ctrl-C / EOF) cancels and returns to the top menu without
    running anything.
    """
    _print_current_config()
    print("\nPress Enter to run, or any other key to cancel...")
    try:
        key = input()
    except (EOFError, KeyboardInterrupt):
        key = "cancel"
    if key == "":
        run_action()
    else:
        print("  -> Cancelled.")


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
            candidates.append(f"case_{case_num}_{lane_id.lower().replace('-', '')}_{spec_slug}_response.json")
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


def main() -> None:
    """Top-level entry point: hub-and-spoke loop with Configure / Run / Exit."""
    while True:
        action = top_menu()
        if action == "configure":
            configure_wizard()
        elif action == "run":
            run_action_prompt()
        elif action == "exit":
            log_history("exit", {})
            print("\nGoodbye.")
            break


if __name__ == "__main__":
    main()
