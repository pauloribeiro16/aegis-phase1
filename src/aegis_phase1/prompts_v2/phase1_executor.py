"""Phase1Executor — Map/Reduce executor for Phase 1 v1.2.

Map stage:   10 lanes (D-01..D-10), each running P1C-LLM-01-OVERLAP-CLASSIFICATION.
Sync stage:  Detect cross-lane conflicts (mark INDETERMINATE per contract).
Reduce stage: P1C-LLM-03-STRATEGIC-SYNTHESIS (1st) → P1C-LLM-02-COMPOUND-EVENT (2nd).

Also wraps Phase 1B per-regulation calls for P1B-LLM-01 + P1B-LLM-02.

This class is the single orchestration entry point for the 5 Phase 1 LLMs.
It composes Phase1LLMInvoker, PromptLoader, CatalogLoader, Phase1Validator
and JSONLLogger — but itself does not call Ollama directly. All LLM I/O is
delegated to the underlying invoker.

Usage:
    from aegis_phase1.prompts_v2.factory import get_invoker
    invoker = get_invoker()
    executor = invoker_to_executor(invoker)
    result = executor.run("Case_01", applicable_regs=["GDPR", "CRA"])
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
from aegis_phase1.prompts_v2.track_b import TrackB
from aegis_phase1.prompts_v2.validator import Phase1Validator

logger = logging.getLogger(__name__)

# The 10 sub-domain lanes of Phase 1 v1.2. Source of truth:
# 00_METHODOLOGY/PREPROCESSING/SubDomains/{D-XX_Folder}/D-XX.Y.md
DOMAINS: list[str] = [f"D-{i:02d}" for i in range(1, 11)]  # D-01..D-10

# The 5 canonical Phase 1 LLM spec_ids (see llm_inventory.py).
SPEC_INTERPRETATION = "P1B-LLM-01-INTERPRETATION"
SPEC_RATIONALE = "P1B-LLM-02-RATIONALE"
SPEC_OVERLAP = "P1C-LLM-01-OVERLAP-CLASSIFICATION"
SPEC_COMPOUND = "P1C-LLM-02-COMPOUND-EVENT"
SPEC_STRATEGIC = "P1C-LLM-03-STRATEGIC-SYNTHESIS"


def _aggregated_status(statuses: list[str]) -> str:
    """Roll up per-call statuses into a single aggregate status.

    Returns:
        "OK" if every status is "OK"
        "FAILED" if every status is "FAILED_AFTER_RETRIES"/"FAILED"/"PARSE_ERROR"/"SCHEMA_ERROR"
        "MIXED" otherwise (mix of OK and error statuses)
    """
    statuses = [s for s in statuses if s is not None]
    if not statuses:
        return "OK"
    error_statuses = {
        "FAILED_AFTER_RETRIES",
        "FAILED",
        "PARSE_ERROR",
        "SCHEMA_ERROR",
        "PYTHON_ERROR",
    }
    if all(s == "OK" for s in statuses):
        return "OK"
    if all(s in error_statuses for s in statuses):
        return "FAILED"
    return "MIXED"


class Phase1Executor:
    """Orchestrates the 5 Phase 1 LLMs in a Map/Reduce pattern."""

    def __init__(
        self,
        prompt_loader: PromptLoader,
        catalog_loader: CatalogLoader,
        validator: Phase1Validator,
        llm_logger: JSONLLogger,
        format_logger: JSONLLogger,
        invoker: Phase1LLMInvoker | None = None,
        track_b: TrackB | None = None,
    ) -> None:
        """Construct a Phase1Executor with all dependencies wired up.

        All five parameters (prompt_loader, catalog_loader, validator,
        llm_logger, format_logger) are required because Phase1Executor needs
        to be able to construct its own Phase1LLMInvoker if none is provided.

        Args:
            prompt_loader: Loads + renders PROMPTS/*.md
            catalog_loader: Loads + filters YAML catalogs
            validator: Post-generation deterministic validator
            llm_logger: JSONLLogger for llm-calls.jsonl
            format_logger: JSONLLogger for format-errors.jsonl
            invoker: Optional pre-built invoker (uses its prompt_loader etc.
                if provided; otherwise a new invoker is built from the five
                loaders/loggers above).
            track_b: Optional TrackB instance. If None, a default TrackB()
                is constructed (deterministic, stateless). Pass a custom
                instance only if you need to override behaviour in tests.
        """
        self.prompts = prompt_loader
        self.catalogs = catalog_loader
        self.validator = validator
        self.llm_logger = llm_logger
        self.format_logger = format_logger
        self.track_b = track_b if track_b is not None else TrackB()
        if invoker is None:
            self.invoker = Phase1LLMInvoker(
                prompt_loader=prompt_loader,
                catalog_loader=catalog_loader,
                validator=validator,
                llm_logger=llm_logger,
                format_logger=format_logger,
            )
        else:
            self.invoker = invoker

    # ─── Track B (deterministic proportionality) ────────────────────────

    def run_track_b(
        self,
        scale: str,
        fte: float,
        per_subdomain_input: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        """Run deterministic tier assignment per proportionality_model.md section 5.

        Wraps self.track_b.assign_all(...) and returns the full profile
        (per-sub-domain tier + 5 attributes) plus the summary statistics.
        This is a synchronous, deterministic step; it makes no LLM calls.

        Args:
            scale: company scale (MICRO | SMALL | MEDIUM | LARGE | MAX).
            fte: security_FTE used for the section 5.2 MICRO + low-FTE
                DEFERRED path.
            per_subdomain_input: mapping sub_domain_id -> {inheritability,
                priority}.

        Returns:
            Dict with keys:
                profile: per-subdomain dict {sd_id: {tier, ...attrs}}
                summary: {total_sub_domains, tier_distribution,
                          active_sub_domains, deferred_count}
        """
        profile = self.track_b.assign_all(
            scale=scale,
            fte=fte,
            per_subdomain_input=per_subdomain_input,
        )
        summary = self.track_b.summarize(profile)
        return {"profile": profile, "summary": summary}

    # ─── Phase 1B: per-regulation ─────────────────────────────────────

    def run_phase_1b(
        self,
        case_id: str,
        applicable_regs: list[str],
        *,
        config: dict[str, Any] | None = None,
        **inputs: Any,
    ) -> dict[str, Any]:
        """For each applicable regulation, call P1B-LLM-01 then P1B-LLM-02.

        Sequential per-reg (v1.2 MVP). Parallelism per lane is a follow-up.

        Returns dict with:
            per_reg: {reg: {"P1B-LLM-01": out, "P1B-LLM-02": out}}
            aggregated_interpretations: list of all Tipo 2 interpretations
            aggregated_derogations: list of all Tipo 3 derogations
            aggregated_synthesis: {reg: synthesis_dict}
            status: "OK" | "MIXED" | "FAILED"
        """
        per_reg: dict[str, dict[str, Any]] = {}
        all_interp: list[dict[str, Any]] = []
        all_derog: list[dict[str, Any]] = []
        all_synth: dict[str, dict[str, Any]] = {}
        statuses: list[str] = []

        for reg in applicable_regs:
            out_01 = self.invoker.invoke(
                SPEC_INTERPRETATION,
                {
                    **inputs,
                    "case_id": case_id,
                    "lane_id": reg,
                    "applicable_regs": [reg],
                },
                config=config,
            )
            out_02 = self.invoker.invoke(
                SPEC_RATIONALE,
                {
                    **inputs,
                    "case_id": case_id,
                    "lane_id": reg,
                    "applicable_regs": [reg],
                },
                config=config,
            )

            per_reg[reg] = {SPEC_INTERPRETATION: out_01, SPEC_RATIONALE: out_02}
            statuses.append(out_01.get("status"))
            statuses.append(out_02.get("status"))

            parsed_01 = out_01.get("parsed_output") or {}
            if isinstance(parsed_01, dict):
                interp = parsed_01.get("interpretations") or []
                derog = parsed_01.get("derogations") or []
                if isinstance(interp, list):
                    all_interp.extend(interp)
                if isinstance(derog, list):
                    all_derog.extend(derog)

            parsed_02 = out_02.get("parsed_output") or {}
            if isinstance(parsed_02, dict):
                synth = parsed_02.get("synthesis")
                if isinstance(synth, dict):
                    all_synth[reg] = synth

        return {
            "per_reg": per_reg,
            "aggregated_interpretations": all_interp,
            "aggregated_derogations": all_derog,
            "aggregated_synthesis": all_synth,
            "status": _aggregated_status(statuses),
        }

    # ─── Phase 1C Map: per-domain lane ────────────────────────────────

    def run_phase_1c_map(
        self,
        case_id: str,
        applicable_regs: list[str],
        **inputs: Any,
    ) -> list[dict[str, Any]]:
        """For each domain D-01..D-10, call P1C-LLM-01-OVERLAP-CLASSIFICATION.

        Sequential (v1.2 MVP). True parallelism requires switching to
        asyncio.gather() or multiprocessing.Pool — see roadmap.

        Returns list of 10 lane outputs (one per domain):
            {"lane_id": "D-XX", "status": ..., "sub_domain_activations": [...], ...}
        """
        lane_outputs: list[dict[str, Any]] = []
        for domain_id in DOMAINS:
            out = self.invoker.invoke(
                SPEC_OVERLAP,
                {
                    **inputs,
                    "case_id": case_id,
                    "domain_id": domain_id,
                    "lane_id": domain_id,
                    "applicable_regs": list(applicable_regs),
                },
            )
            parsed = out.get("parsed_output") or {}
            sd_activations = (
                parsed.get("sub_domain_activations", []) if isinstance(parsed, dict) else []
            )
            lane_outputs.append(
                {
                    "lane_id": domain_id,
                    "status": out.get("status"),
                    "sub_domain_activations": sd_activations
                    if isinstance(sd_activations, list)
                    else [],
                    "latency_ms": out.get("total_latency_ms", 0) or 0,
                    "retry_count": out.get("retry_count", 0) or 0,
                    "parsed_output": parsed,
                }
            )
        return lane_outputs

    # ─── Sync: cross-lane conflict detection ──────────────────────────

    def run_sync(self, lane_outputs: list[dict[str, Any]]) -> dict[str, Any]:
        """Detect cross-lane conflicts. Build scope_overlap matrix.

        For each (sub_domain, reg_pair) key, gather all
        ``company_scope_verdict`` values contributed by every lane. If more
        than one distinct verdict appears, the entry is flagged INDETERMINATE
        and queued for human review in Phase 2.

        Returns dict with:
            matrix: {(sub_domain, reg_pair): [{"lane_id", "verdict", "relationship"}, ...]}
            conflicts: [{sub_domain, reg_pair, verdicts, lanes, severity, action}]
            status: "OK" | "CONFLICTS_DETECTED"
        """
        # matrix[(sub_domain, reg_pair_tuple)] -> list of entries
        matrix: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
        for lane in lane_outputs:
            lane_id = lane.get("lane_id", "?")
            for sd in lane.get("sub_domain_activations", []) or []:
                if not isinstance(sd, dict):
                    continue
                sd_id = sd.get("sub_domain_id", "")
                for pair in sd.get("verified_relationship_per_pair", []) or []:
                    if not isinstance(pair, dict):
                        continue
                    reg_pair_list = pair.get("reg_pair") or []
                    if not isinstance(reg_pair_list, list) or len(reg_pair_list) < 2:
                        continue
                    reg_pair = tuple(sorted(reg_pair_list))
                    key = (sd_id, reg_pair)
                    matrix.setdefault(key, []).append(
                        {
                            "lane_id": lane_id,
                            "verdict": pair.get("company_scope_verdict"),
                            "relationship": pair.get("regulatory_baseline_relationship"),
                        }
                    )

        conflicts: list[dict[str, Any]] = []
        for key, entries in matrix.items():
            verdicts = {e["verdict"] for e in entries if e["verdict"] is not None}
            if len(verdicts) > 1:
                conflicts.append(
                    {
                        "sub_domain": key[0],
                        "reg_pair": list(key[1]),
                        "verdicts": sorted(verdicts),
                        "lanes": [e["lane_id"] for e in entries],
                        "severity": "INDETERMINATE",
                        "action": "Flag for Phase 2 / human review",
                    }
                )

        return {
            "matrix": matrix,
            "conflicts": conflicts,
            "status": "CONFLICTS_DETECTED" if conflicts else "OK",
        }

    # ─── Phase 1C Reduce ──────────────────────────────────────────────

    def run_phase_1c_reduce(
        self,
        case_id: str,
        lane_outputs: list[dict[str, Any]],
        sync_result: dict[str, Any],
        track_b_profile: dict[str, Any] | None = None,
        *,
        config: dict[str, Any] | None = None,
        **inputs: Any,
    ) -> dict[str, Any]:
        """Reduce stage: P1C-LLM-03 first, then P1C-LLM-02 (per contract).

        LLM-03 (strategic synthesis) consumes Doc 07b (deterministic Track B
        constraint). LLM-02 (compound event) consumes the strategic synthesis
        produced by LLM-03.

        Returns dict with:
            "P1C-LLM-03": out_03
            "P1C-LLM-02": out_02
            "status": "OK" | "MIXED" | "FAILED"
            "aggregated_activations": flat list of sub_domain_activations
            "conflicts_count": number of cross-lane conflicts surfaced
        """
        # Flatten all sub_domain_activations across the 10 lanes.
        aggregated_activations: list[dict[str, Any]] = []
        for lane in lane_outputs:
            sds = lane.get("sub_domain_activations") or []
            if isinstance(sds, list):
                aggregated_activations.extend(sds)

        # LLM-03 (STRATEGIC SYNTHESIS) runs FIRST.
        out_03 = self.invoker.invoke(
            SPEC_STRATEGIC,
            {
                **inputs,
                "case_id": case_id,
                "lane_id": "global",
                "applicable_regs": [],
                "aggregated_activations": aggregated_activations,
                "doc07b_profile": track_b_profile or {},
                "sync_conflicts": (sync_result or {}).get("conflicts", []),
            },
            config=config,
        )

        # LLM-02 (COMPOUND EVENT) runs SECOND, consuming LLM-03 output.
        out_02 = self.invoker.invoke(
            SPEC_COMPOUND,
            {
                **inputs,
                "case_id": case_id,
                "lane_id": "global",
                "applicable_regs": [],
                "aggregated_activations": aggregated_activations,
                "c03_strategic_synthesis": (out_03.get("parsed_output") or {}),
                "sync_conflicts": (sync_result or {}).get("conflicts", []),
            },
            config=config,
        )

        statuses = [out_03.get("status"), out_02.get("status")]
        return {
            SPEC_STRATEGIC: out_03,
            SPEC_COMPOUND: out_02,
            "status": _aggregated_status(statuses),
            "aggregated_activations": aggregated_activations,
            "conflicts_count": len((sync_result or {}).get("conflicts", [])),
        }

    # ─── End-to-end ───────────────────────────────────────────────────

    def run(
        self,
        case_id: str,
        applicable_regs: list[str],
        track_b_profile: dict[str, Any] | None = None,
        track_b_scale: str | None = None,
        track_b_fte: float | None = None,
        track_b_per_subdomain: dict[str, dict[str, str]] | None = None,
        **inputs: Any,
    ) -> dict[str, Any]:
        """End-to-end Map/Reduce. Returns the full Phase 1 result dict.

        Returns dict with keys:
            case_id, phase_1b, phase_1c_map, sync, phase_1c_reduce
        """
        # If the caller supplied (scale, fte, per_subdomain) AND no
        # precomputed track_b_profile, compute it deterministically here.
        track_b_result: dict[str, Any] | None = None
        if (
            track_b_profile is None
            and track_b_scale is not None
            and track_b_fte is not None
            and track_b_per_subdomain is not None
        ):
            track_b_result = self.run_track_b(
                track_b_scale,
                track_b_fte,
                track_b_per_subdomain,
            )
            track_b_profile = track_b_result["profile"]

        phase_1b = self.run_phase_1b(case_id, applicable_regs, **inputs)
        phase_1c_map = self.run_phase_1c_map(case_id, applicable_regs, **inputs)
        sync = self.run_sync(phase_1c_map)
        phase_1c_reduce = self.run_phase_1c_reduce(
            case_id,
            phase_1c_map,
            sync,
            track_b_profile=track_b_profile,
            **inputs,
        )
        result: dict[str, Any] = {
            "case_id": case_id,
            "phase_1b": phase_1b,
            "phase_1c_map": phase_1c_map,
            "sync": sync,
            "phase_1c_reduce": phase_1c_reduce,
        }
        if track_b_result is not None:
            result["track_b"] = track_b_result
        return result


def invoker_to_executor(invoker: Phase1LLMInvoker) -> Phase1Executor:
    """Build a Phase1Executor from an existing Phase1LLMInvoker.

    Convenience function for callers that already have a fully-wired invoker
    (typically from ``prompts_v2.factory.get_invoker()``). Uses the loaders
    and loggers carried by the invoker instance.

    Raises:
        ValueError: if any of the required dependencies is missing.
    """
    prompts = getattr(invoker, "prompts", None)
    catalogs = getattr(invoker, "catalogs", None)
    validator = getattr(invoker, "validator", None)
    llm_logger = getattr(invoker, "llm_logger", None)
    format_logger = getattr(invoker, "format_logger", None)
    missing = [
        name
        for name, val in (
            ("prompt_loader", prompts),
            ("catalog_loader", catalogs),
            ("validator", validator),
            ("llm_logger", llm_logger),
            ("format_logger", format_logger),
        )
        if val is None
    ]
    if missing:
        raise ValueError(f"Invoker is missing required dependencies for Phase1Executor: {missing}")

    return Phase1Executor(
        prompt_loader=prompts,  # type: ignore[arg-type]
        catalog_loader=catalogs,  # type: ignore[arg-type]
        validator=validator,  # type: ignore[arg-type]
        llm_logger=llm_logger,  # type: ignore[arg-type]
        format_logger=format_logger,  # type: ignore[arg-type]
        invoker=invoker,
    )
