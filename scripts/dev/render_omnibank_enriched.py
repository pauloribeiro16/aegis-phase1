"""Render Doc 04, 04a, 04b, 04c, 04d, 05 for case 3 (OmniBank) with the
newly-enriched YAML inputs.

Usage:
    PYTHONPATH=src python3 scripts/dev/render_omnibank_enriched.py \
        --output-dir output/case3-omnibank/enriched-YYYYMMDD-HHMMSS

Approach (mirrors the previous validate_corr072.py validation):
    1. Build a Phase1Orchestrator with a MockInvoker (deterministic, no LLM).
    2. Call orch.load() to populate v2 state (subdomains, ontology, profile).
    3. Call cmd_run_applicability() to render 04 + 05 + (via render_doc_04)
       04b + 04c + 04d (deterministic half only — no MAP/REDUCE).
    4. Manually invoke render_doc_04a() with the same state to add 04a to
       the bundle (cmd_run_applicability doesn't include 04a by default).
    5. Copy logs into the run dir + regenerate MANIFEST.md via
       scripts/dev/collect-output.py.

Exit code is 0 on success.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import warnings
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_case_path(case_arg: str | None) -> Path:
    if case_arg:
        return Path(case_arg).resolve()
    return (REPO_ROOT / "cases" / "case3-omnibank").resolve()


def _resolve_prep_path(prep_arg: str | None) -> Path:
    if prep_arg:
        return Path(prep_arg).resolve()
    default = REPO_ROOT / "preproc_out"
    return default.resolve()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--case", default=None, help="Case directory (default: cases/case3-omnibank)")
    p.add_argument(
        "--preprocessing",
        default=None,
        help="Regulatory Baseline path (default: preproc_out)",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="Output run directory (default: output/case3-omnibank/enriched-TS)",
    )
    p.add_argument(
        "--mock-llm",
        action="store_true",
        default=True,
        help="Always-on; deterministic fallback (default: True)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    os.environ.setdefault("MOCK_LLM", "true")
    os.environ.setdefault("AEGIS_LOG_DIR", str(REPO_ROOT / "logs" / "phase1" / "_enriched_render"))

    # CORR-013: MOCK_LLM env var must be set BEFORE build_llm_invoker() runs
    # (the factory reads it in import-time logic). Set both module-level and
    # os.environ to be safe across sub-process invocations.
    os.environ["MOCK_LLM"] = "true"

    case_path = _resolve_case_path(args.case)
    prep_path = _resolve_prep_path(args.preprocessing)
    if args.output_dir:
        out_dir = Path(args.output_dir).resolve()
    else:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        out_dir = (REPO_ROOT / "output" / "case3-omnibank" / f"enriched-{ts}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[render-enriched] case_path = {case_path}")
    print(f"[render-enriched] prep_path = {prep_path}")
    print(f"[render-enriched] output_dir = {out_dir}")

    # Build orchestrator with mock invoker.
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.llm import build_llm_invoker
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    preproc_catalog = PreprocCatalogLoader(preproc_root=str(prep_path))
    case_profile_loader = CaseProfileLoader(case_path)
    catalog_loader = CatalogLoader(root=get_prompts_root() / "catalogs")
    llm_invoker = build_llm_invoker(model="mock:enriched", provider="auto")
    orch = Phase1Orchestrator(
        llm_invoker=llm_invoker,
        preproc_catalog=preproc_catalog,
        case_profile_loader=case_profile_loader,
        catalog_loader=catalog_loader,
        run_id="enriched-render",
    )

    # LOAD stage
    orch.load(str(case_path), str(prep_path))

    # CORR-072 follow-up: orchestrator builds state["architecture_inventory"]
    # with N.1..N.6 keys, but doc_04a/doc_04c expect flat keys
    # (systems/cloud_services/auth_systems/data_flows/data_stores/data_subjects).
    # Remap at render time so the renderers see the canonical shape.
    inv = orch.state.get("architecture_inventory") or {}
    if inv and "N.1_systems" in inv and "systems" not in inv:
        remapped = {
            "systems": list(inv.get("N.1_systems") or []),
            "auth_systems": list(inv.get("N.2_auth") or []),
            "cloud_services": list(inv.get("N.3_cloud") or []),
            "data_flows": list(inv.get("N.4_data_flows") or []),
            "data_stores": list(inv.get("N.5_data_stores") or []),
            "data_subjects": list(inv.get("data_subjects") or []),
        }
        orch.state["architecture_inventory"] = remapped
        print(
            f"[render-enriched] remapped architecture_inventory: "
            f"systems={len(remapped['systems'])} cloud={len(remapped['cloud_services'])} "
            f"flows={len(remapped['data_flows'])} stores={len(remapped['data_stores'])} "
            f"auth={len(remapped['auth_systems'])} subjects={len(remapped['data_subjects'])}"
        )

    # Render Doc 04 + Doc 05 (composite 04 = 04 + 04b + 04c + 04d via render_doc_04)
    from aegis_phase1.v2.output.doc_04 import render_doc_04
    from aegis_phase1.v2.output.doc_04a import render_doc_04a
    from aegis_phase1.v2.output.doc_05 import render_doc_05

    paths: dict[str, str] = {}
    paths.update(render_doc_04(orch.state, str(out_dir), llm_invoker=None))
    paths.update(render_doc_05(orch.state, str(out_dir), llm_invoker=None))
    # Add Doc 04a explicitly (cmd_run_applicability does NOT include it; the
    # validate_corr072 baseline separately rendered it).
    paths.update(render_doc_04a(orch.state, str(out_dir), llm_invoker=None))

    print("[render-enriched] wrote artefacts:")
    for label, p in sorted(paths.items()):
        size = Path(p).stat().st_size if Path(p).exists() else 0
        lines = sum(1 for _ in Path(p).read_text(encoding="utf-8").splitlines())
        print(f"  {label:14s} -> {p}  ({size} bytes, {lines} lines)")

    # Persist state + collect logs (best-effort).
    try:
        orch.state["output_paths"] = dict(orch.state.get("output_paths", {}), **paths)
        orch._persist_state()
    except Exception as exc:
        warnings.warn(f"persist_state failed: {exc}", stacklevel=2)

    log_src = REPO_ROOT / "logs" / "phase1" / "_enriched_render"
    if log_src.exists():
        log_dst = out_dir / "logs"
        for child in log_src.rglob("*"):
            if child.is_file():
                rel = child.relative_to(log_src)
                dest = log_dst / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, dest)
        print(f"[render-enriched] copied logs from {log_src} to {log_dst}")

    # Regenerate MANIFEST.md
    import subprocess

    manifest_script = REPO_ROOT / "scripts" / "dev" / "generate-manifest.py"
    rc = subprocess.call(
        [sys.executable, str(manifest_script), "--run-dir", str(out_dir)],
        cwd=str(REPO_ROOT),
    )
    if rc != 0:
        warnings.warn(f"generate-manifest exited {rc}", stacklevel=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())