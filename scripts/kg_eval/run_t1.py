"""T1 task runner — KG reasoning A/B harness (CORR-113 Commit 3).

Loads a task from ``scripts/kg_eval/tasks.yaml``, generates (or skips) the
context packet depending on the arm, builds a prompt that mirrors what the
pipeline's MAP would receive, and invokes the model via the existing project
provider abstraction (``src.aegis_phase1.v2.llm.MockInvoker`` for tests, or
``UnifiedInvoker`` for real runs).

Public API:
    load_tasks(tasks_yaml_path) -> list[dict]
    select_task(tasks, task_id) -> dict
    run_task(task, case_path, preproc_root, *, with_kg, ...) -> dict (env record)

CLI:
    python -m scripts.kg_eval.run_t1 \
        --case cases/case1-tinytask --task-family T1.1 --with-kg
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from scripts.kg_eval.generate_context_packets import (
    generate_packet,
    packet_sha256,
)

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent

logger = logging.getLogger(__name__)

# Family descriptions for the prompt-system block. Short — the per-task
# question carries the substance; the system block only sets role + rules.
_FAMILY_SYSTEM_BLOCK: dict[str, str] = {
    "T1.1": (
        "You are an AEGIS-KG Phase 1 regulatory analyst. Given a context "
        "packet and a system, list every regulatory obligation that binds "
        "it. Cite ONLY identifiers present in the packet. Use the documented "
        "markdown shape (## Affected systems / ## Legal clauses / ## CSF "
        "anchors / ## In-scope rule)."
    ),
    "T1.2": (
        "You are an AEGIS-KG Phase 1 regulatory analyst. Given a context "
        "packet and a cross-regulation conflict, emit the structured "
        "resolution block (### Tension Resolution: REG_A vs REG_B — TYPE) "
        "with Friction / Resolution adopted / Severity / Source reference. "
        "Cite only verbatim text from the packet."
    ),
    "T1.3": (
        "You are an AEGIS-KG Phase 1 regulatory analyst. Given a CONDITIONAL "
        "regulatory pair, choose the applicable reading for this company, "
        "state the disposition in {RESOLVED_BY_FACT, RESOLVED_BY_TIER, "
        "NEEDS_HUMAN}, and the anchors (article IDs, tier, asset IDs, "
        "business goal IDs) that support the call. If the pair is NOT "
        "CONDITIONAL, say so explicitly and explain why no disposition is "
        "required."
    ),
    "T1.4": (
        "You are an AEGIS-KG Phase 1 regulatory analyst. Given a subdomain "
        "at a known enterprise tier, state the evidence depth the "
        "methodology requires, the example controls, the verification "
        "method, and who owns the evidence."
    ),
    "T1.5": (
        "You are an AEGIS-KG Phase 1 regulatory analyst. Synthesise the "
        "integrated regulatory posture for a system: regulations, activated "
        "subdomains, the most rigorous proportionality requirement, open "
        "tensions, unresolved ambiguities. Cite regulation IDs and CSF "
        "subcategories for every claim."
    ),
}

# NO-KG case context: a 3-sentence case context (company name, sector, tier)
# — the bare minimum to anchor the question. Per protocol §3, no packet,
# no closed lists, no per-section anchors.
_NO_KG_CASE_CONTEXT_TEMPLATE = (
    "Case context (no KG): company={company_name}, sector={sector}, "
    "scale={scale}, applicable_regulations={applicable_regs}."
)


# ─── Task loading ────────────────────────────────────────────────────


def load_tasks(tasks_yaml_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the T1 task catalogue from YAML.

    Returns the list under the ``tasks`` key. Raises on missing/empty
    catalogue. Tolerates missing optional fields (``asset_id``,
    ``expected_structure``, ``scoring_criteria``).
    """
    if tasks_yaml_path is None:
        tasks_yaml_path = _PROJECT_ROOT / "scripts" / "kg_eval" / "tasks.yaml"
    tasks_yaml_path = Path(tasks_yaml_path)
    if not tasks_yaml_path.exists():
        raise FileNotFoundError(f"tasks.yaml not found: {tasks_yaml_path}")
    with tasks_yaml_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    tasks = raw.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(
            f"tasks.yaml at {tasks_yaml_path} has no 'tasks' list or it is empty"
        )
    return tasks


def select_task(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    """Select one task by ID; raise on ambiguous or missing IDs."""
    matches = [t for t in tasks if t.get("id") == task_id]
    if not matches:
        available = [t.get("id") for t in tasks]
        raise ValueError(
            f"Task {task_id!r} not found. Available: {available[:5]}…"
        )
    if len(matches) > 1:
        raise ValueError(f"Task {task_id!r} is not unique; got {len(matches)} matches")
    return matches[0]


def _git_commit_sha() -> str:
    """Return the current HEAD SHA, or ``"unknown"`` if git is unavailable."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8").strip()
    except Exception:  # pragma: no cover — defensive
        return "unknown"


# ─── Prompt construction ────────────────────────────────────────────


def _build_no_kg_case_context(case_path: Path) -> str:
    """Build the 3-sentence NO-KG case context for the prompt.

    Reads only ``cases/<case>/input/company/classification.yaml`` +
    ``cases/<case>/input/regulatory/applicability.yaml`` — the bare-minimum
    sources any LLM could plausibly read without the KG. No closed lists,
    no per-section anchors.
    """
    classification_path = case_path / "input" / "company" / "classification.yaml"
    applicability_path = case_path / "input" / "regulatory" / "applicability.yaml"
    company_name = ""
    sector = ""
    scale = "MICRO"
    if classification_path.exists():
        try:
            data = yaml.safe_load(classification_path.read_text(encoding="utf-8")) or {}
            company = data.get("company") or {}
            company_name = company.get("name") or ""
            sector = company.get("sector") or ""
            scale = company.get("scale") or "MICRO"
        except Exception:  # pragma: no cover — defensive
            pass
    applicable_regs: list[str] = []
    if applicability_path.exists():
        try:
            data = yaml.safe_load(applicability_path.read_text(encoding="utf-8")) or {}
            applicable_regs = list(data.get("applicable_regulations") or [])
        except Exception:  # pragma: no cover — defensive
            pass
    return _NO_KG_CASE_CONTEXT_TEMPLATE.format(
        company_name=company_name,
        sector=sector,
        scale=scale,
        applicable_regs=applicable_regs,
    )


def _build_prompt(
    task: dict[str, Any],
    case_context: str,
    packet: dict[str, Any] | None,
    with_kg: bool,
) -> dict[str, str]:
    """Build the {system, user} prompt pair for one task.

    The shape mirrors what the pipeline's MAP would receive
    (``prompts/MAP-DOMAIN-ADAPT.md``) — the system block is the family-
    specific role, the user block carries the question + (packet or
    bare case context). This is intentionally inline: no spec-version
    pin, so the harness can iterate on prompt shape without bumping the
    canonical Methodology-main specs.

    Args:
        task: Task dict from tasks.yaml.
        case_context: The 3-sentence no-KG case context (always built).
        packet: Generated packet (None for no-KG arm).
        with_kg: True if the packet is included; False for the bare arm.

    Returns:
        Dict with ``system`` and ``user`` strings.
    """
    family = str(task.get("family") or "").strip()
    system = _FAMILY_SYSTEM_BLOCK.get(family) or (
        "You are an AEGIS-KG Phase 1 regulatory analyst. "
        "Cite only identifiers present in the inputs."
    )
    if not with_kg:
        user = (
            f"{case_context}\n\n"
            f"# TASK ({family})\n\n"
            f"{str(task.get('question') or '').strip()}\n\n"
            f"# EXPECTED STRUCTURE\n\n"
            f"```\n{task.get('expected_structure') or ''}\n```\n\n"
            f"# OUTPUT\n\nReturn ONLY the markdown response. "
            f"Do NOT invent identifiers — if you do not know, say so."
        )
    else:
        # WITH-KG arm — render the packet as a JSON block in the user message
        packet_blob = json.dumps(packet, indent=2, ensure_ascii=False)
        user = (
            f"{case_context}\n\n"
            f"# TASK ({family})\n\n"
            f"{str(task.get('question') or '').strip()}\n\n"
            f"# EXPECTED STRUCTURE\n\n"
            f"```\n{task.get('expected_structure') or ''}\n```\n\n"
            f"# CONTEXT PACKET (CLOSE LIST — cite ONLY these IDs)\n\n"
            f"```json\n{packet_blob}\n```\n\n"
            f"# OUTPUT\n\nReturn ONLY the markdown response. "
            f"Cite ONLY identifiers present in the packet. Anything not "
            f"present is a violation."
        )
    return {"system": system, "user": user}


# ─── LLM invocation ─────────────────────────────────────────────────


def _invoker_from_env() -> Any:
    """Build the LLM invoker for the current run.

    Honours ``MOCK_LLM=true`` (returns ``MockInvoker``). Otherwise returns
    ``UnifiedInvoker`` via the project's factory
    (``aegis_phase1.v2.llm.build_llm_invoker``); caller can pass
    ``--provider`` to override.
    """
    if os.environ.get("MOCK_LLM", "").strip().lower() in {"1", "true", "yes", "on"}:
        from aegis_phase1.v2.llm import MockInvoker

        return MockInvoker()
    try:
        from aegis_phase1.v2.llm import build_llm_invoker

        return build_llm_invoker()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("build_llm_invoker failed (%s); falling back to MockInvoker", exc)
        from aegis_phase1.v2.llm import MockInvoker

        return MockInvoker()


def invoke_llm(invoker: Any, system: str, user: str, script: list[dict] | None = None) -> dict:
    """Invoke the model and return its raw response.

    If ``invoker`` is a ``MockInvoker`` and ``script`` is provided, swap the
    script (for deterministic tests). Returns the invoker's dict unchanged.
    """
    if script is not None:
        try:
            invoker.script = list(script)
            invoker.call_count = 0
        except Exception:  # pragma: no cover — defensive
            pass
    prompt = f"{system}\n\n{user}"
    response = invoker.invoke(prompt)
    return response


# ─── Run orchestration ───────────────────────────────────────────────


def run_task(
    task: dict[str, Any],
    case_path: Path | str,
    preproc_root: Path | str | None = None,
    *,
    with_kg: bool,
    invoker: Any | None = None,
    script: list[dict] | None = None,
    model: str = "mock-or-configured",
) -> dict[str, Any]:
    """Run one task in one arm. Returns the env record (per protocol §6).

    Side effect: writes the run artefacts to
    ``output/kg_eval/<task_id>_<arm>_<ts>/`` — ``raw_response.md`` (the LLM
    output) and ``env.json`` (the env record).

    The function NEVER raises on LLM errors — it captures the failure in
    ``raw_response.md`` and marks the run ``status="FAILED_AFTER_RETRIES"``
    in ``env.json`` so the scorer can flag the family as degraded (OBJ-12
    fail-loud pattern, mirrored from the pipeline).
    """
    case_path = Path(case_path).resolve()
    if preproc_root is None:
        preproc_root = _PROJECT_ROOT / "preproc_out"
    preproc_root = Path(preproc_root).resolve()

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    arm = "with_kg" if with_kg else "no_kg"
    safe_task_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(task.get("id") or "task"))
    out_dir = _PROJECT_ROOT / "output" / "kg_eval" / f"{safe_task_id}_{arm}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build prompts — always build case_context; packet only on with-kg.
    case_context = _build_no_kg_case_context(case_path)
    packet: dict[str, Any] | None = None
    digest: str | None = None
    if with_kg:
        packet = generate_packet(case_path, str(task.get("subdomain_id")), preproc_root)
        digest = packet_sha256(packet)
        (out_dir / "packet.json").write_text(
            json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if digest:
            (out_dir / "packet.sha256").write_text(digest + "\n", encoding="utf-8")

    prompt = _build_prompt(task, case_context, packet, with_kg)
    inv = invoker or _invoker_from_env()
    response = invoke_llm(inv, prompt["system"], prompt["user"], script=script)

    raw = ""
    status = "OK"
    if isinstance(response, dict):
        raw = str(response.get("raw") or "")
        status = str(response.get("status") or "OK")
    else:
        raw = str(response or "")

    (out_dir / "raw_response.md").write_text(raw, encoding="utf-8")
    (out_dir / "prompt_system.txt").write_text(prompt["system"], encoding="utf-8")
    (out_dir / "prompt_user.txt").write_text(prompt["user"], encoding="utf-8")

    env_record = {
        "task_id": task.get("id"),
        "case_id": case_path.name,
        "subdomain_id": task.get("subdomain_id"),
        "family": task.get("family"),
        "arm": arm,
        "model": model,
        "provider": "mock" if os.environ.get("MOCK_LLM", "").lower() in {"1", "true", "yes", "on"} else "ollama",
        "quantization": os.environ.get("KG_EVAL_QUANT") or None,
        "temperature": float(os.environ.get("KG_EVAL_TEMP") or 0.1),
        "seed": None,
        "packet_sha256": digest,
        "case_context_sha256": None,  # populated by the caller if needed
        "commit_sha": _git_commit_sha(),
        "timestamp_utc": timestamp,
        "task_yaml_path": "scripts/kg_eval/tasks.yaml",
        "prompt_spec_version": "v0 (built inline; see scripts/kg_eval/run_t1.py)",
        "spec_versions": {},
        "status": status,
        "output_dir": str(out_dir.relative_to(_PROJECT_ROOT)),
    }
    (out_dir / "env.json").write_text(
        json.dumps(env_record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return env_record


# ─── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: pick a task, run with-KG or no-KG, write artefacts."""
    parser = argparse.ArgumentParser(
        description="Run one T1 task in one arm (with-KG or no-KG).",
    )
    parser.add_argument("--case", required=True, type=Path, help="Case directory.")
    parser.add_argument(
        "--task-family",
        required=True,
        choices=["T1.1", "T1.2", "T1.3", "T1.4", "T1.5"],
        help="Task family (filters tasks.yaml).",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="Specific task ID. If omitted, the first matching family is run.",
    )
    parser.add_argument(
        "--arm",
        required=True,
        choices=["with-kg", "no-kg"],
        help="WITH-KG arm uses the generated packet; NO-KG uses bare case context.",
    )
    parser.add_argument(
        "--tasks-yaml",
        type=Path,
        default=_PROJECT_ROOT / "scripts" / "kg_eval" / "tasks.yaml",
        help="Path to the tasks YAML.",
    )
    parser.add_argument(
        "--preproc-root",
        type=Path,
        default=_PROJECT_ROOT / "preproc_out",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress INFO logs."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    tasks = load_tasks(args.tasks_yaml)
    family_tasks = [t for t in tasks if t.get("family") == args.task_family]
    if not family_tasks:
        logger.error("No tasks for family %s", args.task_family)
        return 1
    task = select_task(tasks, args.task_id) if args.task_id else family_tasks[0]

    env_record = run_task(
        task,
        args.case,
        args.preproc_root,
        with_kg=(args.arm == "with-kg"),
    )
    logger.info(
        "Wrote artefacts to %s (status=%s, packet_sha=%s)",
        env_record["output_dir"],
        env_record["status"],
        (env_record.get("packet_sha256") or "")[:12],
    )
    print(json.dumps(env_record, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
