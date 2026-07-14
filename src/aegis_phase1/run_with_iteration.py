"""Iteration orchestrator for Phase 1 doc production.

Workflow:
  Run 1: Sequential fill of all 4 docs (using DocumentProducer)
  Run 2: Evaluate each doc, patch sections with high+medium severity issues
  Run 3: Same, but only patch residual HIGH issues
  Stop: When 0 issues or max_runs reached

State is passed through phase1_state.json to avoid re-running the full pipeline.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from aegis_phase1.doc_evaluator import (
    Issue,
    evaluate_filled_doc,
    group_issues_by_section,
)
from aegis_phase1.logging_config import get_logger
from aegis_phase1.section_refill import refill_section

logger = get_logger(__name__)


PHASE1_DOCS = [
    "04_Company_Context_Assessment",
    "05_Regulatory_Applicability",
    "06_Clause_Mapping_Matrix",
    "07_Structured_Compliance_Matrix",
]


@dataclass
class IterationResult:
    doc_name: str
    final_path: Path
    runs: int
    final_issues: int
    history: list[dict]


def _save_state(state: dict, case_path: str) -> Path:
    """Serialize phase1 state to JSON for reuse across iterations."""
    state_path = Path(case_path) / ".phase1_state.json"

    serializable = {}
    for k, v in state.items():
        try:
            json.dumps(v)
            serializable[k] = v
        except (TypeError, ValueError):
            serializable[k] = str(v)[:500]

    state_path.write_text(json.dumps(serializable, indent=2, default=str), encoding="utf-8")
    logger.info("[iter] saved state to %s (%d keys)", state_path, len(serializable))
    return state_path


def _load_state(case_path: str) -> dict:
    """Load previously saved phase1 state."""
    state_path = Path(case_path) / ".phase1_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"No state file at {state_path}")
    return dict(json.loads(state_path.read_text(encoding="utf-8")))


def _initial_fill(case_path: str, state: dict) -> dict[str, Path]:
    """Run 1: fill all 4 docs sequentially using the standard DocumentProducer.

    Returns: {doc_name: v1_filled_path}
    """
    from aegis_phase1.shared.document_producer import (
        PHASE1_TEMPLATES,
        DocumentProducer,
        resolve_output_path,
        resolve_template_path,
    )

    logger.info("[iter] Run 1: initial fill of %d docs", len(PHASE1_TEMPLATES))

    llm_config = state.get("llm_config", {}) or {}
    producer = DocumentProducer(case_path, llm_config, phase=1)

    base_data = {
        "coverage_matrix": state.get("coverage_matrix", {}),
        "coverage_summary": state.get("coverage_summary", {}),
        "clause_mappings": state.get("clause_mappings", []),
        "applicable_regulations": state.get("applicable_regulations", []),
        "company_context": state.get("company_context", {}),
        "complementarity_analysis": state.get("complementarity_analysis", {}),
        "stakeholders": state.get("stakeholders", []),
        "business_goals": state.get("business_goals", []),
        "applicability_matrix": state.get("applicability_matrix", {}),
        "strategic_implications": state.get("strategic_implications", []),
        "regulatory_gaps": state.get("regulatory_gaps", []),
        "phase": "Phase 1 - Regulatory Foundations",
        "stakeholder_rationale": state.get("stakeholder_rationale", ""),
        "business_goal_rationale": state.get("business_goal_rationale", ""),
        "context_assessment_rationale": state.get("context_assessment_rationale", ""),
        "applicability_evidence": state.get("applicability_evidence", ""),
        "applicability_rationale": state.get("applicability_rationale", ""),
        "mapping_rationale": state.get("mapping_rationale", ""),
        "coverage_rationale": state.get("coverage_rationale", ""),
        "complementarity_rationale": state.get("complementarity_rationale", ""),
        "evidence_sources": state.get("evidence_sources", ""),
    }

    results: dict[str, Path] = {}

    for template in PHASE1_TEMPLATES:
        template_path = resolve_template_path(case_path, template, phase=1)
        if not template_path.exists():
            logger.warning("[iter] template not found: %s", template_path)
            continue

        try:
            content = producer.read_template(template)
            filled = producer.fill_template(content, base_data, phase=1)

            producer.write_output(template, filled, version=1)
            canonical_filled = resolve_output_path(
                case_path,
                template.replace(".md", "_filled.md"),
                phase=1,
            )

            results[template.replace(".md", "")] = canonical_filled
            logger.info("[iter] v1 produced: %s (%d chars)", canonical_filled.name, len(filled))
        except Exception as e:
            logger.error("[iter] failed to fill %s: %s", template, e, exc_info=True)

    return results


def _next_version_path(current_path: Path, next_version: int) -> Path:
    """Compute the next version path (v1 -> v2, v2 -> v3) in same directory."""
    parent = current_path.parent
    stem = current_path.stem
    suffix = current_path.suffix
    base = stem.replace("_filled", "") if "_filled" in stem else stem
    return parent / f"{base}_v{next_version}{suffix}"


def _evaluate_and_decide(
    filled_path: Path,
    template_name: str,
    case_path: str,
    state: dict,
    run: int,
) -> tuple[list[Issue], bool]:
    """Evaluate a filled doc and decide if iteration should continue.

    Returns: (issues, should_continue)
    """
    from aegis_phase1.shared.document_producer import resolve_template_path

    template_path = resolve_template_path(case_path, f"{template_name}.md", phase=1)
    if not template_path.exists():
        logger.warning("[iter] template missing: %s", template_path)
        return [], False

    issues = evaluate_filled_doc(
        filled_path=filled_path,
        template_path=template_path,
        state=state,
        use_llm=(run == 2),
    )

    if not issues:
        logger.info("[iter] %s: 0 issues, done", filled_path.name)
        return issues, False

    patchable = [i for i in issues if i.severity in ("high", "medium")]
    if run == 3:
        patchable = [i for i in issues if i.severity == "high"]

    if not patchable:
        logger.info(
            "[iter] %s: %d issues but none patchable in run %d (low severity)",
            filled_path.name,
            len(issues),
            run,
        )
        return issues, False

    return issues, True


def _patch_issues(
    filled_path: Path,
    template_name: str,
    issues: list[Issue],
    case_path: str,
    state: dict,
    next_version: int,
) -> Path:
    """Patch a doc by refilling each section with issues.

    Returns: path to the new version
    """
    from aegis_phase1.shared.document_producer import resolve_template_path

    template_path = resolve_template_path(case_path, f"{template_name}.md", phase=1)
    current_path = filled_path

    grouped = group_issues_by_section(issues)

    for section, section_issues in grouped.items():
        description = "; ".join(
            f"[{i.severity}] {i.issue_type}: {i.description}" for i in section_issues
        )

        next_path = _next_version_path(current_path, next_version)
        current_path = refill_section(
            filled_path=current_path,
            section_name=section,
            template_path=template_path,
            state=state,
            issue_description=description,
            output_path=next_path,
        )

    if current_path != filled_path:
        from aegis_phase1.shared.document_producer import resolve_output_path

        canonical = resolve_output_path(case_path, f"{template_name}_filled.md", phase=1)
        shutil.copy2(current_path, canonical)
        logger.info(
            "[iter] promoted %s -> canonical %s",
            current_path.name,
            canonical.name,
        )
        return canonical

    return filled_path


def run_with_iteration(
    case_path: str,
    state: dict | None = None,
    max_runs: int = 3,
    docs_to_produce: list[str] | None = None,
    use_llm_evaluator: bool = True,
) -> dict[str, IterationResult]:
    """Run Phase 1 doc production with auto-evaluation and patch iteration.

    Args:
        case_path: Path to case directory (e.g., 'cases/case1-aegis-tinytask')
        state: Pre-computed phase1 state (if None, must be provided via .phase1_state.json)
        max_runs: Max iterations (1=initial fill only, 2=initial+1 patch, 3=initial+2 patches)
        docs_to_produce: List of doc names (without .md). Defaults to all 4.
        use_llm_evaluator: Use LLM in evaluator (more thorough but slower)

    Returns:
        Dict of {doc_name: IterationResult}
    """
    case_path_obj = Path(case_path)
    if not case_path_obj.exists():
        raise FileNotFoundError(f"Case path not found: {case_path}")

    if docs_to_produce is None:
        docs_to_produce = PHASE1_DOCS

    if state is None:
        state = _load_state(case_path)

    logger.info(
        "[iter] starting run_with_iteration: case=%s, max_runs=%d, docs=%d",
        case_path,
        max_runs,
        len(docs_to_produce),
    )

    _save_state(state, case_path)

    current_paths = _initial_fill(case_path, state)
    logger.info("[iter] Run 1 complete: %d docs produced", len(current_paths))

    results: dict[str, IterationResult] = {}

    for doc_name in docs_to_produce:
        if doc_name not in current_paths:
            logger.warning("[iter] doc %s not in initial fill results, skipping", doc_name)
            continue

        results[doc_name] = IterationResult(
            doc_name=doc_name,
            final_path=current_paths[doc_name],
            runs=1,
            final_issues=0,
            history=[{"run": 1, "action": "initial_fill", "path": str(current_paths[doc_name])}],
        )

    for run in range(2, max_runs + 1):
        logger.info("[iter] === Run %d ===", run)
        all_resolved = True

        for doc_name in docs_to_produce:
            if doc_name not in results:
                continue

            filled_path = results[doc_name].final_path
            if not filled_path.exists():
                logger.warning("[iter] %s: filled path missing, skipping", filled_path)
                continue

            issues, should_continue = _evaluate_and_decide(
                filled_path=filled_path,
                template_name=doc_name,
                case_path=case_path,
                state=state,
                run=run,
            )

            if not should_continue:
                results[doc_name].final_issues = len(issues)
                results[doc_name].history.append(
                    {
                        "run": run,
                        "action": "stop",
                        "reason": "0 patchable issues" if not issues else "low severity only",
                        "issues_remaining": len(issues),
                    }
                )
                continue

            all_resolved = False
            new_path = _patch_issues(
                filled_path=filled_path,
                template_name=doc_name,
                issues=issues,
                case_path=case_path,
                state=state,
                next_version=run,
            )
            results[doc_name].final_path = new_path
            results[doc_name].runs = run
            results[doc_name].history.append(
                {
                    "run": run,
                    "action": "patched",
                    "issues_found": len(issues),
                    "sections_patched": len({i.section for i in issues}),
                    "new_path": str(new_path),
                }
            )

        if all_resolved:
            logger.info("[iter] all docs resolved at run %d, stopping", run)
            break

    from aegis_phase1.shared.document_producer import resolve_template_path

    for doc_name, result in results.items():
        filled_path = result.final_path
        if filled_path.exists():
            template_path = resolve_template_path(case_path, f"{doc_name}.md", phase=1)
            if template_path.exists():
                final_issues = evaluate_filled_doc(
                    filled_path=filled_path,
                    template_path=template_path,
                    state=state,
                    use_llm=False,
                )
                result.final_issues = len(final_issues)

    logger.info(
        "[iter] complete: %d docs, %d iterations max",
        len(results),
        max_runs,
    )

    return results
