"""orchestrator — Phase 1 v2 pipeline state machine.

Orchestrates the 4-stage pipeline: LOAD → MAP → REDUCE → OUTPUT.
Each stage updates V2State and persists to work/state.json.

MAP stage (Sprint MAP-3):
    - Sequential processing (per-domain, one at a time).
    - Ollama network failures propagate as ``OllamaUnreachable``.
    - Per-domain parse failures accumulate; ``MapPartialFailure`` is
      raised at the end if any domain is still ``FAILED``.
    - ``retry_failed()`` re-processes a chosen subset of failed domains.

Note (CORR-005): ``layer0_subdomain_refs`` kwargs forwarded to
``executor.run_phase_1b`` / ``run_phase_1c_reduce`` are WIRE-PROTOCOL
names. They land in the inputs dict serialised into the PROMPTS
template substitution performed by the sibling Methodology-main repo
(out of this contract's scope). The PROMPTS-side rename will land in a
follow-up contract; this file is the consumer-side mirror and must
keep the wire name for now.

Note (CORR-037-T3 scaffolding): The orchestrator now accepts optional
``preproc_catalog`` and ``case_profile_loader`` constructor args (typed
Pydantic loaders from CORR-037-T1/T2). They are NOT yet wired into
``load()`` — that wiring is deferred to a follow-up session (T3 full
refactor). When provided, they are stored on self and exposed for
downstream use; ``load()`` still uses the legacy loaders
(CommonLoader, PreprocessingLoader) for backwards compatibility.
Existing tests pass; new code can opt-in via constructor injection.
"""

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from aegis_phase1.v2.state import V2State

if TYPE_CHECKING:
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.phase1_executor import Phase1Executor
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

logger = logging.getLogger(__name__)


class Phase1Orchestrator:
    """Orchestrates the 4-stage v2 pipeline (LOAD → MAP → REDUCE → OUTPUT).

    Each stage updates the V2State, persists to work/state.json after each stage.
    """

    def __init__(
        self,
        work_dir: str = "work",
        llm_invoker: Any | None = None,
        *,
        preproc_catalog: "PreprocCatalogLoader | None" = None,
        case_profile_loader: "CaseProfileLoader | None" = None,
        catalog_loader: "CatalogLoader | None" = None,
    ):
        """Initialize the orchestrator.

        Args:
            work_dir: Where the orchestrator persists state.json
                (default: "work").
            llm_invoker: Phase1LLMInvoker for LLM calls (or None for
                deterministic-only runs).
            preproc_catalog: CORR-037-T1 typed JSON loader for preproc_out/.
                Optional. When provided, stored on self.preproc_catalog for
                downstream use (SP-B/C/D). When None, ``load()`` falls back
                to the v1 loaders (CommonLoader, legacy PreprocessingLoader).
            case_profile_loader: CORR-037-T2 typed YAML loader for case
                inputs. Optional. Same opt-in pattern as preproc_catalog.
            catalog_loader: CORR-039-T1 CatalogLoader for tipo2/tipo3 YAML
                catalogs (from ``Methodology-main/00_METHODOLOGY/PROMPTS/catalogs/``).
                Optional. When provided, ``_load_v2_catalog`` populates
                ``state["v2_catalog_tipo2"]`` and ``state["v2_catalog_tipo3"]``
                for use by P1B-LLM-01 in Phase 1B (CORR-039-T4).
        """
        self.state: V2State = self._init_state()
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.llm_invoker = llm_invoker
        # CORR-037-T3: typed loaders (opt-in). Full wiring in follow-up.
        self.preproc_catalog = preproc_catalog
        self.case_profile_loader = case_profile_loader
        # CORR-039-T1: catalog loader for tipo2/tipo3 YAMLs
        self.catalog_loader = catalog_loader
        # Stash the preproc_catalog reference in state so the T2
        # ClauseMappingContext builder can call load_clauses() lazily.
        # Set in _load_v2_catalog — see T1 branch below.
        self._skip_reduce_llms = False
        self._skip_phase_1b = False
        # CORR-060 (multi-model eval): when the runner sets AEGIS_LOG_DIR
        # to a per-model subdir (e.g. logs/phase1/gemma4_e2b), the MAP
        # per-domain jsonl files land under that model dir, not under
        # <work_dir>/logs/... . Falls back to legacy <work_dir>/logs/...
        # when AEGIS_LOG_DIR is unset.
        import os as _os
        _log_base = _os.environ.get("AEGIS_LOG_DIR")
        if _log_base:
            self.log_dir = Path(_log_base) / "v2" / "map"
        else:
            self.log_dir = self.work_dir.parent / "logs" / "phase1" / "v2" / "map"

        try:
            from aegis_phase1.llm.tracing import get_langfuse_callback

            _, self._langfuse_handler = get_langfuse_callback()
        except Exception:  # noqa: BLE001 — tracing is optional
            self._langfuse_handler = None

        if (
            self._langfuse_handler is not None
            and self.llm_invoker is not None
            and hasattr(self.llm_invoker, "_langfuse_handler")
        ):
            try:
                self.llm_invoker._langfuse_handler = self._langfuse_handler
            except Exception:  # noqa: BLE001 — handler attachment is best-effort
                logger.debug(
                    "Could not attach langfuse_handler to %s",
                    type(self.llm_invoker).__name__,
                )

    def set_skip_reduce_llms(self, skip: bool) -> None:
        """Toggle skipping of reduce-stage LLM calls. Default: False.

        Set to True via the ``--skip-reduce-llms`` CLI flag.
        """
        self._skip_reduce_llms = bool(skip)

    def _load_v2_catalog(self, case_path: str) -> None:
        """CORR-037-T3a: populate v2_* state keys from typed loaders (opt-in).

        New state keys (all Pydantic models; consumers must .field access):
          - v2_company_profile    : CompanyProfile     (case inputs summary)
          - v2_company_facts     : CompanyFacts       (canonical facts)
          - v2_applicable_regs   : list[str]          (sorted, computed)
          - v2_declared_regs     : list[str]          (from YAML)
          - v2_obligated_party   : dict[str, str]     (reg → party)
          - v2_subdomains        : list[Subdomain]    (38)
          - v2_srs               : list[SR]           (282)
          - v2_sos               : list[SO]           (328)
          - v2_pairs             : list[Pair]         (196)
          - v2_audit_both_pass   : bool               (gate)

        All keys are populated ONLY when the corresponding loader is
        injected via the constructor. When loaders are None, this method
        is a no-op and the v1 legacy state keys remain the only data.
        """
        if self.case_profile_loader is not None:
            try:
                profile = self.case_profile_loader.load()
                self.state["v2_company_profile"] = profile
                self.state["v2_company_facts"] = profile.company
                self.state["v2_applicable_regs"] = list(profile.applicable_regs)
                self.state["v2_declared_regs"] = list(profile.declared_applicable_regs)
                self.state["v2_obligated_party"] = dict(profile.regulatory.obligated_party_per_reg)
                # CORR-038-T2/T3: surface rationale + clause_count so
                # build_applicability_context can read them directly
                # without re-parsing the YAML.
                self.state["v2_regulatory_rationale"] = dict(profile.regulatory.applicability_rationale)
                self.state["v2_clause_count_per_reg"] = dict(profile.regulatory.clause_count_per_reg)
                logger.debug(
                    "T3a: case_profile loaded — %d stakeholders, %d goals, %d architecture sections",
                    len(profile.stakeholders),
                    len(profile.business_goals),
                    sum(
                        len(getattr(profile.architecture, attr))
                        for attr in (
                            "systems",
                            "auth_systems",
                            "cloud_services",
                            "data_flows",
                            "data_stores",
                        )
                    ),
                )
            except Exception as e:
                logger.warning("T3a: case_profile_loader failed (%s) — v2_* keys not set", e)

        if self.preproc_catalog is not None:
            try:
                self.state["v2_subdomains"] = self.preproc_catalog.load_subdomains()
                self.state["v2_srs"] = self.preproc_catalog.load_srs()
                self.state["v2_sos"] = self.preproc_catalog.load_sos()
                self.state["v2_pairs"] = self.preproc_catalog.load_pairs()
                audit = self.preproc_catalog.load_audit()
                self.state["v2_audit_both_pass"] = audit.both_pass
                # CORR-039-T1: stash the loader reference so the
                # ClauseMappingContext builder (T2) can call load_clauses()
                # lazily without re-instantiating the loader.
                self.state["v2_preproc_catalog_ref"] = self.preproc_catalog
                logger.debug(
                    "T3a: preproc_catalog loaded — %d subs, %d srs, %d sos, %d pairs, audit.both_pass=%s",
                    len(self.state["v2_subdomains"]),
                    len(self.state["v2_srs"]),
                    len(self.state["v2_sos"]),
                    len(self.state["v2_pairs"]),
                    audit.both_pass,
                )
            except Exception as e:
                logger.warning("T3a: preproc_catalog failed (%s) — v2_* keys not set", e)

        # CORR-039-T1: load tipo2 + tipo3 catalogs (filter for P1B-LLM-01)
        if self.catalog_loader is not None:
            try:
                self.state["v2_catalog_tipo2"] = self.catalog_loader.load(
                    "tipo2_interpretations"
                )
                self.state["v2_catalog_tipo3"] = self.catalog_loader.load(
                    "tipo3_derogations"
                )
                logger.debug(
                    "T1: catalogs loaded — tipo2=%d entries, tipo3=%d entries",
                    len(self.state["v2_catalog_tipo2"]),
                    len(self.state["v2_catalog_tipo3"]),
                )
            except Exception as e:
                # Empty catalogs (file missing) is a valid state — fall
                # back to empty lists so downstream LLM calls proceed.
                logger.info(
                    "T1: catalog_loader returned no entries (%s) — using empty lists",
                    e,
                )
                self.state["v2_catalog_tipo2"] = []
                self.state["v2_catalog_tipo3"] = []

        # CORR-037-T4b: SHIM — populate legacy v1 state keys from v2 sources
        # so the 8 output consumers (doc_04*.py, doc_05..07.py, xlsx_generator.py)
        # can read meaningful data without code changes. Future T4c contract
        # migrates consumers to read v2_* keys directly and drops the shim.
        self._populate_v1_state_keys_from_v2()

    def _populate_v1_state_keys_from_v2(self) -> None:
        """SHIM: derive legacy v1 state keys (company_context, ontology,
        architecture_inventory, business_goals, stakeholders, regulations,
        subdomains) from the v2_* keys populated by ``_load_v2_catalog``.

        Only populates a key if the v1 key is not already meaningfully
        populated (i.e. empty / None / missing). Preserves the v1 loaders'
        output when both paths coexist.
        """
        if not self._has_v2_keys():
            return

        facts = self.state.get("v2_company_facts")
        if facts is not None and not self.state.get("company_context"):
            self.state["company_context"] = self._build_company_context(facts)

        applicable = self.state.get("v2_applicable_regs", [])
        if applicable and not self.state.get("regulations"):
            self.state["regulations"] = list(applicable)

        if not self.state.get("architecture_inventory"):
            self.state["architecture_inventory"] = self._build_architecture_inventory()

        if not self.state.get("ontology"):
            self.state["ontology"] = self._build_ontology_shim()

        if not self.state.get("preprocessing"):
            self.state["preprocessing"] = self._build_preprocessing_shim()

        if not self.state.get("stakeholders"):
            profile = self.state.get("v2_company_profile")
            if profile is not None:
                self.state["stakeholders"] = [s.model_dump() for s in profile.stakeholders]

        if not self.state.get("business_goals"):
            profile = self.state.get("v2_company_profile")
            if profile is not None:
                self.state["business_goals"] = [g.model_dump() for g in profile.business_goals]

        if not self.state.get("taxonomy_entries"):
            self.state["taxonomy_entries"] = []

    def _has_v2_keys(self) -> bool:
        return any(k.startswith("v2_") for k in self.state)

    def _build_company_context(self, facts: Any) -> dict[str, Any]:
        """Build a v1-shape company_context dict from v2 CompanyFacts.

        Returns a Pydantic state.CompanyContext.model_dump() (dict). The
        v1 schema (with required complexity_tier enum + revenue float) is
        derivable from the v2 facts + a simple tier estimate based on
        scale + employees.

        CORR-049-T6: also embeds the full v2 CompanyProfile (under
        ``v2_company_profile`` key) and the 4 CORR-047 fields at the
        top level. Pre-CORR-049 the returned dict was a flat 9-key
        shape; the downstream ``_extract_corr047_fields`` helper
        tried 3 paths to find the 4 new fields but none matched the
        flat shape, so the fields were silently dropped. The bridge
        here makes Path 2 (``ctx["v2_company_profile"]``) and Path 3
        (direct top-level keys) work.
        """
        from aegis_phase1.models import ComplexityTier
        from aegis_phase1.v2.state import CompanyContext as _CC

        # Lazy tier estimate (T4b shim). The proper tier assignment comes
        # from a follow-up tier-assignment step in SP-B (CORR-038).
        employees = getattr(facts, "employees", 0) or 0
        if employees >= 250:
            tier = ComplexityTier.HIGH.value
        elif employees >= 50:
            tier = ComplexityTier.MEDIUM.value
        else:
            tier = ComplexityTier.LOW.value

        base = _CC(
            company_name=facts.name,
            sector=facts.sector,
            jurisdiction=facts.jurisdiction,
            employees=facts.employees,
            revenue=float(facts.revenue_eur),
            scale=facts.scale,
            applicable_regs=list(self.state.get("v2_applicable_regs", [])),
            complexity_tier=tier,
            security_fte=facts.security_fte or 0.0,
            tech_stack=list(facts.tech_stack or []),
        ).model_dump()

        # CORR-049-T6: attach the rich CompanyProfile (loaded by
        # CaseProfileLoader in CORR-047) so _extract_corr047_fields
        # Path 2 can find the 4 new fields. Also expose the 4 fields
        # as top-level keys (Path 3 fallback).
        profile = self.state.get("v2_company_profile")
        if profile is not None:
            base["v2_company_profile"] = profile  # Pydantic instance
            for field in (
                "implementation_readiness",
                "regulatory_classification",
                "role_matrix",
                "regulatory_interactions",
            ):
                value = getattr(profile, field, None)
                if value is not None:
                    base[field] = (
                        value.model_dump()
                        if hasattr(value, "model_dump")
                        else value
                    )

        return base

    def _build_architecture_inventory(self) -> dict[str, list[dict[str, Any]]]:
        """Build v1-shape architecture_inventory (dict[str, list[dict]])."""
        profile = self.state.get("v2_company_profile")
        if profile is None:
            return {}
        arch = profile.architecture
        return {
            "N.1_systems": list(arch.systems),
            "N.2_auth": list(arch.auth_systems),
            "N.3_cloud": list(arch.cloud_services),
            "N.4_data_flows": list(arch.data_flows),
            "N.5_data_stores": list(arch.data_stores),
            "N.6_other": [],
        }

    def _build_ontology_shim(self) -> dict[str, Any]:
        """Build v1-shape ontology from v2 pairs.

        v1 ontology had: overlaps, regulations, source_regulations, stacks.
        v2 sources give us: v2_pairs (cross-regulation pairs) and
        v2_applicable_regs.
        """
        return {
            "regulations": list(self.state.get("v2_applicable_regs", [])),
            "overlaps": [p.model_dump() for p in self.state.get("v2_pairs", [])],
            "source_regulations": {},
            "stacks": [],
        }

    def _build_preprocessing_shim(self) -> dict[str, Any]:
        """Build v1-shape preprocessing from v2 pairs + audit."""
        return {
            "cross_regulation": [p.model_dump() for p in self.state.get("v2_pairs", [])],
            "audit_both_pass": self.state.get("v2_audit_both_pass", False),
        }

    def set_skip_phase_1b(self, skip: bool) -> None:
        """Toggle skipping of Phase 1B RATIONALE LLM calls. Default: False.

        Set to True via the ``--skip-phase-1b`` CLI flag. Covers the
        per-regulation ``P1B-LLM-02 RATIONALE`` synthesis stage that
        runs between MAP and REDUCE (CORR-004 / CORR-005).
        """
        self._skip_phase_1b = bool(skip)

    def load(
        self,
        case_path: str,
        regulatory_baseline_path: str | None = None,
        *,
        preprocessing_path: str | None = None,
    ) -> V2State:
        """Stage 0: Load all inputs from 3 sources.

        1. Load 00_COMMON/ (company context, taxonomy, ontology)
        2. Load PREPROCESSING/SubDomains/ (38 sub-domain definitions)
        3. Load PREPROCESSING/CrossRegulation/ + AMBIGUITY_ANALYSIS/

        The legacy argument ``preprocessing_path`` is accepted as a
        deprecated alias for ``regulatory_baseline_path``. If neither is
        supplied, a ValueError is raised. (Phase 0 rebranding: "Layer 0"
        → "Regulatory Baseline".)
        """
        if regulatory_baseline_path is None:
            if preprocessing_path is not None:
                import warnings

                warnings.warn(
                    "Argument 'preprocessing_path' is deprecated; use "
                    "'regulatory_baseline_path' instead. (Phase 0 rebranding)",
                    DeprecationWarning,
                    stacklevel=2,
                )
                regulatory_baseline_path = preprocessing_path
            else:
                raise ValueError(
                    "Either 'regulatory_baseline_path' or the deprecated "
                    "'preprocessing_path' must be supplied."
                )

        # Local alias used throughout this method body for clarity.
        preprocessing_path = regulatory_baseline_path

        logger.info("=== STAGE 0: LOAD ===")
        start = time.time()

        # CORR-037-T4c: the v1 loaders (CommonLoader, PreprocessingLoader)
        # have been removed. v1-shape state keys (company_context,
        # architecture_inventory, stakeholders, business_goals,
        # taxonomy_entries, ontology, regulations, preprocessing,
        # subdomains) are populated exclusively by the shim in
        # ``_populate_v1_state_keys_from_v2()`` from the v2_* keys.
        # Consumers can either read v1_* (via the shim) or v2_*
        # (via the v2 typed models directly). For new code, prefer v2_*.

        # Subdomains: prefer PreprocCatalogLoader (typed Pydantic) when
        # injected. T3c made the consumer shape-agnostic, so v2 Pydantic
        # Subdomain objects (with hso_hl / hso_per_reg / security_requirements
        # / pairs) are transparently normalized to the v1 SubDomainDef
        # shape by v2.domain.filters.subdomains._summarize.
        if self.preproc_catalog is not None:
            subs_list = self.preproc_catalog.load_subdomains()
            self.state["subdomains"] = {s.id: s for s in subs_list}
        else:
            logger.warning(
                "T4: no preproc_catalog injected — state['subdomains'] is empty. "
                "Inject a PreprocCatalogLoader for the canonical 38 subdomains."
            )
            self.state["subdomains"] = {}

        # Populate v2_* state keys + v1 shim (replaces the removed
        # CommonLoader/PreprocessingLoader output).
        self._load_v2_catalog(case_path)

        self.state["current_stage"] = "LOADED"
        self.state["case_path"] = case_path
        # State key retains 'preprocessing_path' for backward compatibility
        # with persisted work/state.json files from the v2.1 era.
        self.state["preprocessing_path"] = regulatory_baseline_path
        # New canonical key added for forward-readability by tooling.
        self.state["regulatory_baseline_path"] = regulatory_baseline_path

        elapsed = time.time() - start
        logger.info(
            "LOAD complete: %d sub-domains, %d regs (%.2fs)",
            len(self.state["subdomains"]),
            len(self.state["regulations"]),
            elapsed,
        )
        self._persist_state()
        return self.state

    def map_domains(self) -> V2State:
        """Stage 1: MAP — adapt sub-domain HSOs per domain (sequential).

        LEGACY loop body (CORR-018a S1): iterates D-01..D-10 sequentially
        and delegates each iteration to :meth:`map_single_domain`. The
        pre-built ``DomainProcessor`` is constructed once and passed to
        each call. Per-domain results are stored in
        ``state["domain_results"]`` keyed by domain ID.

        CORR-040-T2: when the canonical Phase1Executor is available
        (i.e. a real LLM invoker is wired and MOCK_LLM is not set), the
        canonical 5-LLM ``run_phase_1c_map`` is invoked instead — this
        fires P1C-LLM-01-OVERLAP-CLASSIFICATION per domain with the
        full input set (case_id + applicable_regs + sub_domain refs).
        Result is translated into the same ``state["domain_results"]``
        shape so downstream consumers (Doc 07, Doc 07b, the new
        DomainActivationContext) don't change.

        Raises:
            OllamaUnreachable: Propagated from ``map_single_domain`` when
                the LLM is unreachable. The whole MAP stage aborts.
            MapPartialFailure: When ≥1 domain ends with status FAILED
                (after retries). The state is persisted before raising.
        """
        logger.info("=== STAGE 1: MAP ===")
        start = time.time()

        from aegis_phase1.v2.domain.processor import (
            DomainProcessor,
            MapPartialFailure,
            OllamaUnreachable,
        )

        # CORR-040-T2: try the canonical P1C-LLM-01 path first
        executor = self._get_phase1_executor()
        if executor is not None:
            try:
                results = self._map_domains_via_p1c_llm_01(executor)
                self.state["domain_results"] = results
                self.state["current_stage"] = "MAPPED"
                statuses: dict[str, int] = {}
                for r in results.values():
                    s = r.get("llm_status", "UNKNOWN")
                    statuses[s] = statuses.get(s, 0) + 1
                elapsed = time.time() - start
                logger.info(
                    "MAP complete (P1C-LLM-01 canonical): %d domains in %.2fs — statuses=%s",
                    len(results),
                    elapsed,
                    statuses,
                )
                self._persist_state()
                self._seed_review_after_map(results)
                failed = [d for d, r in results.items() if r.get("llm_status") == "FAILED"]
                if failed:
                    raise MapPartialFailure(
                        f"{len(failed)} domain(s) failed: {failed}"
                    )
                return self.state
            except MapPartialFailure:
                raise
            except Exception as exc:
                logger.warning(
                    "P1C-LLM-01 MAP path failed (%s) — falling back to legacy loop",
                    exc,
                )
                # Fall through to the legacy loop below.

        # LEGACY path (LLM-A via DomainProcessor)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        processor = DomainProcessor(
            llm_invoker=self.llm_invoker,
            log_dir=self.log_dir,
            langfuse_handler=self._langfuse_handler,
        )
        domain_ids = [f"D-{i:02d}" for i in range(1, 11)]

        results = dict(self.state.get("domain_results") or {})
        statuses = {}
        failed_domains: list[str] = []

        for did in domain_ids:
            try:
                result = self.map_single_domain(did, processor=processor)
            except OllamaUnreachable as exc:
                logger.error("MAP aborted — Ollama unreachable on %s: %s", did, exc)
                self.state["domain_results"] = results
                self.state["current_stage"] = "MAP_FAILED"
                self._persist_state()
                raise
            except Exception as exc:
                logger.exception("MAP raised for %s: %s", did, exc)
                result = self._failed_domain_result(did, exc)

            results[did] = result
            status = result.get("llm_status", "UNKNOWN")
            statuses[status] = statuses.get(status, 0) + 1
            if status == "FAILED":
                failed_domains.append(did)

        self.state["domain_results"] = results
        self.state["current_stage"] = "MAPPED"
        elapsed = time.time() - start
        logger.info(
            "MAP complete: %d domains in %.2fs — statuses=%s",
            len(results),
            elapsed,
            statuses,
        )
        self._persist_state()
        self._seed_review_after_map(results)

        if failed_domains:
            logger.error(
                "MAP partial failure: %d domain(s) failed: %s",
                len(failed_domains),
                failed_domains,
            )
            raise MapPartialFailure(f"{len(failed_domains)} domain(s) failed: {failed_domains}")
        return self.state

    def _map_domains_via_p1c_llm_01(
        self,
        executor: Any,
    ) -> dict[str, Any]:
        """CORR-040-T2 helper: invoke the canonical P1C-LLM-01 per domain.

        Calls ``executor.run_phase_1c_map`` once for all 10 lanes, then
        translates the per-lane result into the same ``DomainResult``
        shape produced by the legacy ``DomainProcessor.process()`` so
        downstream consumers (Doc 07, Doc 07b,
        DomainActivationContext) work unchanged.

        Returns:
            Mapping ``D-XX`` -> ``DomainResult`` (10 entries).
        """
        from aegis_phase1.v2.domain.processor import DOMAIN_NAMES

        # Extract applicable_regs
        cc_raw = self.state.get("company_context")
        if hasattr(cc_raw, "model_dump"):
            cc = cc_raw.model_dump()
        elif isinstance(cc_raw, dict):
            cc = dict(cc_raw)
        else:
            cc = {}
        applicable_regs = [
            str(r) for r in (cc.get("applicable_regs") or []) if r
        ]

        case_id = Path(self.state.get("case_path") or "case").name
        lane_outputs = executor.run_phase_1c_map(
            case_id=case_id,
            applicable_regs=applicable_regs,
            company_facts=cc,
            layer0_subdomain_refs=self._build_layer0_subdomain_refs(
                list((self.state.get("subdomains") or {}).keys())
            ),
        )
        # Translate executor output → DomainResult shape
        results: dict[str, Any] = {}
        for lane in lane_outputs:
            did = str(lane.get("lane_id") or "")
            if not did.startswith("D-"):
                continue
            status = str(lane.get("status") or "FAILED")
            sd_activations = lane.get("sub_domain_activations") or []
            # Build adapted_subdomains_v3 from sub_domain_activations
            adapted_v3 = []
            for sd in sd_activations:
                if not isinstance(sd, dict):
                    continue
                adapted_v3.append(
                    {
                        "sub_domain_id": sd.get("sub_domain_id", ""),
                        "reg_pair": sd.get("reg_pair", []),
                        "company_scope_verdict": sd.get("company_scope_verdict", ""),
                        "regulatory_baseline_relationship": sd.get(
                            "regulatory_baseline_relationship", ""
                        ),
                        "layer0_refs": sd.get("layer0_refs", []),
                    }
                )
            results[did] = {
                "domain_id": did,
                "domain_name": DOMAIN_NAMES.get(did, did),
                "subdomains": [],
                "coverage": "SUBSTANTIVE" if adapted_v3 else "NOT_ADDRESSED",
                "cross_regulation": [],
                "llm_status": "OK" if status == "OK" else "FAILED",
                "adapted_objective": "",
                "adapted_subdomains": [],
                "adapted_subdomains_v3": adapted_v3,
                "key_changes": [],
                "applicable_regs": applicable_regs,
                "confidence": "UNKNOWN",
                "latency_ms": int(lane.get("latency_ms") or 0),
            }
        # Fill missing lanes (executor may skip failed ones)
        for did in [f"D-{i:02d}" for i in range(1, 11)]:
            if did not in results:
                results[did] = self._failed_domain_result(
                    did, Exception("P1C-LLM-01 lane missing from executor output")
                )
        return results

    def map_single_domain(
        self,
        domain_id: str,
        *,
        processor: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Single-domain MAP for one D-XX.

        Granular method extracted from :meth:`map_domains` (CORR-018a S1).
        Invokes ``processor.process(domain_id, state)`` and returns the
        ``DomainResult``-shaped dict. Does NOT catch exceptions; the
        caller (legacy ``map_domains`` or a LangGraph node in S2) owns
        the try/except policy and ``OllamaUnreachable`` propagation.

        Args:
            domain_id: Domain identifier (e.g. ``"D-04"``).
            processor: Pre-built ``DomainProcessor`` for performance. When
                ``None`` (default), a fresh processor is constructed
                lazily from orchestrator state. The legacy
                :meth:`map_domains` constructs one processor and passes it
                to all 10 calls; LangGraph nodes (S2) construct per-call.
            config: Optional LangChain ``RunnableConfig`` threaded into
                the LLM invocation so the GENERATION span in Langfuse is
                named after the LangGraph node (CORR-018b C7 fix).

        Returns:
            A :class:`DomainResult` dict as returned by ``processor.process``.
        """
        if processor is None:
            from aegis_phase1.v2.domain.processor import DomainProcessor

            processor = DomainProcessor(
                llm_invoker=self.llm_invoker,
                log_dir=self.log_dir,
                langfuse_handler=self._langfuse_handler,
                config=config,
            )
        elif config is not None:
            processor.config = config
        return processor.process(domain_id, self.state)

    def _build_synthesis_context(self) -> None:
        """CORR-041-T2: build the canonical SynthesisContext from current state.

        Called from :meth:`reduce` (after reduce_synthesis + reduce_compound)
        and from :meth:`run_phase_1b` (after rationale_by_reg is populated).
        Writes ``state['v2_synthesis_context']`` for downstream consumers
        (Doc 04a-d, Doc 07 §5.2/§6.2, parity check).

        Backward-compatible: the v1 shim keys
        (``state['aggregated_data']['synthesis']`` etc.) are NOT modified;
        only the new ``v2_synthesis_context`` is added.
        """
        try:
            from aegis_phase1.v2.context.synthesis_context import (
                build_synthesis_context,
            )

            ctx = build_synthesis_context(self.state)
            self.state["v2_synthesis_context"] = ctx
            logger.debug(
                "T2: v2_synthesis_context built — status=%s, "
                "synthesis=%d chars, %d compound events, %d per-reg rationale",
                ctx.status,
                len(ctx.synthesis.prose),
                ctx.compound_event_count(),
                ctx.per_reg_count(),
            )
        except Exception as exc:
            logger.warning("T2: build_synthesis_context failed: %s", exc)

    def _failed_domain_result(self, domain_id: str, exc: Exception) -> dict[str, Any]:
        """Build the FAILED ``DomainResult`` dict for a domain whose processing raised.

        Extracted from the inline construction in the legacy
        :meth:`map_domains` loop body (CORR-018a S1). Mirrors the
        original shape exactly so callers see identical output.
        """
        from aegis_phase1.v2.domain.processor import DOMAIN_NAMES

        return {
            "domain_id": domain_id,
            "domain_name": DOMAIN_NAMES.get(domain_id, domain_id),
            "subdomains": [],
            "coverage": "NOT_ADDRESSED",
            "cross_regulation": [],
            "llm_status": "FAILED",
            "adapted_objective": "",
            "key_changes": [],
            "applicable_regs": [],
            "confidence": "LOW",
            "error_reason": str(exc),
        }

    def retry_failed(self, domain_ids: list[str]) -> V2State:
        """Re-run MAP for a chosen subset of domain IDs.

        Replaces existing entries in ``state["domain_results"]`` for the
        supplied IDs. Newly failed domains are reported via
        :class:`MapPartialFailure`.

        Args:
            domain_ids: Domain IDs to retry (e.g. ``["D-04", "D-07"]``).

        Returns:
            Updated :class:`V2State`.

        Raises:
            MapPartialFailure: When ≥1 domain ends with status FAILED
                after retries.
        """
        from aegis_phase1.v2.domain.processor import (
            DomainProcessor,
            MapPartialFailure,
        )

        if not domain_ids:
            return self.state

        normalised = [d.upper() for d in domain_ids]
        logger.info("=== RETRY FAILED: %s ===", normalised)

        self.log_dir.mkdir(parents=True, exist_ok=True)
        processor = DomainProcessor(
            llm_invoker=self.llm_invoker,
            log_dir=self.log_dir,
            langfuse_handler=self._langfuse_handler,
        )

        results: dict[str, Any] = dict(self.state.get("domain_results") or {})
        failed: list[str] = []
        statuses: dict[str, int] = {}

        for did in normalised:
            try:
                result = processor.process(did, self.state)
            except Exception as exc:
                logger.exception("retry_failed: %s raised: %s", did, exc)
                raise MapPartialFailure(f"Retry aborted for {did}: {exc}") from exc
            results[did] = result
            status = result.get("llm_status", "UNKNOWN")
            statuses[status] = statuses.get(status, 0) + 1
            if status == "FAILED":
                failed.append(did)

        self.state["domain_results"] = results
        self._persist_state()

        if failed:
            logger.error(
                "Retry partial failure: %d domain(s) still failing: %s",
                len(failed),
                failed,
            )
            raise MapPartialFailure(f"{len(failed)} domain(s) still failing after retry: {failed}")
        logger.info("Retry complete — statuses=%s", statuses)
        return self.state

    def reduce(self) -> V2State:
        """Stage 2: Reduce MAP-stage domain results into a per-sub-domain profile.

        LEGACY entry point (CORR-018a S1). Delegates the deterministic
        and LLM sub-stages to granular methods:

        1. :meth:`reduce_deterministic` — concat / merge / conflicts / proportionality.
        2. :meth:`reduce_synthesis` — P1C-LLM-03 STRATEGIC SYNTHESIS.
        3. :meth:`reduce_compound` — P1C-LLM-02 COMPOUND EVENTS.

        All four deterministic outputs are merged into
        ``state["aggregated_data"]`` (same as the pre-refactor
        behaviour); the LLM granular methods populate
        ``synthesis`` and ``compound_events`` from the executor result.
        """
        logger.info("=== STAGE 2: REDUCE ===")
        start = time.time()

        profile = self.reduce_deterministic()
        synthesis = self.reduce_synthesis()
        compound_events = self.reduce_compound()

        cached = getattr(self, "_phase_1c_reduce_cache", None)
        if isinstance(cached, dict):
            logger.info(
                "REDUCE-LLM complete: synthesis=%s, compound_events=%s, status=%s",
                "OK" if synthesis else "MISSING",
                "OK" if compound_events else "MISSING",
                cached.get("status", "?"),
            )

        elapsed = time.time() - start
        profile_data = profile if isinstance(profile, dict) else {}
        logger.info(
            "REDUCE complete: %d subdomains profiled (%.2fs)",
            len(profile_data),
            elapsed,
        )
        # CORR-041-T2: build canonical SynthesisContext (synthesis +
        # compound_events + track_b + conflicts + per_reg_rationale)
        self._build_synthesis_context()
        self._persist_state()
        return self.state

    def reduce_deterministic(self) -> dict[str, Any] | None:
        """Deterministic reduce step (concat / merge / conflicts / proportionality).

        Granular method extracted from :meth:`reduce` (CORR-018a S1).
        Runs the four deterministic reduce sub-stages and writes the
        merged outputs into ``state["aggregated_data"]``. Sets
        ``state["current_stage"] = "REDUCED"``. Does not touch the
        ``synthesis`` / ``compound_events`` keys (those remain ``None``
        until the LLM granular methods fill them in).

        Returns:
            The profile sub-dict (the value stored under
            ``aggregated_data["profile"]``), for diagnostic logging by
            the legacy :meth:`reduce` caller. Returns ``None`` only if
            the deterministic stages returned ``None`` (preserved from
            the original behaviour).
        """
        from aegis_phase1.v2.reduce import (
            apply_proportionality,
            concatenate,
            merge_requirements,
            resolve_conflicts,
        )

        concatenated = concatenate(self.state)
        merged = merge_requirements(concatenated)
        preprocessing = self.state.get("preprocessing") or {}
        ambiguities = preprocessing.get("ambiguities", []) or []
        resolved = resolve_conflicts(merged, ambiguities)
        profile = apply_proportionality(merged, self.state.get("company_context"))

        profile_data = profile.get("profile", {}) if isinstance(profile, dict) else profile
        self.state["aggregated_data"] = {
            "concatenated": concatenated,
            "merged": merged,
            "conflicts": resolved,
            "profile": profile_data,
            "synthesis": None,
            "compound_events": None,
        }
        self.state["current_stage"] = "REDUCED"
        return profile_data if isinstance(profile_data, dict) else None

    def reduce_synthesis(self, *, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """P1C-LLM-03 STRATEGIC SYNTHESIS reduce step.

        Granular method extracted from :meth:`reduce` (CORR-018a S1).
        Calls the Phase1Executor's ``run_phase_1c_reduce`` (which fires
        P1C-LLM-03 then P1C-LLM-02 internally per contract), stores the
        P1C-LLM-03 synthesis into ``state["aggregated_data"]["synthesis"]``,
        and caches the full executor result on ``self._phase_1c_reduce_cache``
        so :meth:`reduce_compound` can extract P1C-LLM-02 without a second
        executor call (avoids re-invoking ``_get_phase1_executor`` and
        preserves the LLM-02-consumes-LLM-03 chain).

        Args:
            config: Optional LangChain ``RunnableConfig`` threaded into
                the executor's invoker (CORR-018b C7 fix).

        Returns:
            The P1C-LLM-03 synthesis dict on success, ``None`` when the
            executor is unavailable, returned an unexpected type, or
            raised. On failure, appends to ``state["errors"]`` and sets
            ``current_stage = "REDUCE_INDETERMINATE"`` (identical to the
            pre-refactor fallback).
        """
        executor = self._get_phase1_executor()
        if executor is None:
            logger.info("REDUCE-LLM skipped: deterministic-only or mock mode")
            return None

        lane_outputs = [
            {
                "lane_id": lane_id,
                "sub_domain_activations": (
                    lane_result.get("subdomains") or [] if isinstance(lane_result, dict) else []
                ),
            }
            for lane_id, lane_result in (self.state.get("domain_results") or {}).items()
        ]

        raw_company_context = self.state.get("company_context")
        if isinstance(raw_company_context, dict):
            company_context = dict(raw_company_context)
        elif raw_company_context is not None:
            company_context = raw_company_context.model_dump()
        else:
            company_context = {}

        applicable_regs = [str(reg) for reg in company_context.get("applicable_regs", []) if reg]
        if not applicable_regs:
            applicability = company_context.get("applicable_regulations", [])
            if isinstance(applicability, list):
                applicable_regs = [
                    str(reg.get("abbreviation"))
                    for reg in applicability
                    if isinstance(reg, dict)
                    and reg.get("applicable", False)
                    and reg.get("abbreviation")
                ]

        try:
            case_id = Path(self.state.get("case_path") or "case").name
            run_result = executor.run_phase_1c_reduce(
                case_id=case_id,
                lane_outputs=lane_outputs,
                sync_result={"conflicts": self.state["aggregated_data"].get("conflicts", []) or []},
                track_b_profile=self.state["aggregated_data"].get("profile", {}),
                applicable_regs=applicable_regs,
                company_facts=company_context,
                layer0_subdomain_refs=self._build_layer0_subdomain_refs(
                    list((self.state.get("subdomains") or {}).keys())
                ),
                config=config,
            )
        except Exception as exc:
            logger.warning("REDUCE-LLM failed (continuing): %s", exc)
            self.state["errors"].append(f"reduce_llm: {exc}")
            self.state["current_stage"] = "REDUCE_INDETERMINATE"
            return None

        if not isinstance(run_result, dict):
            logger.warning(
                "REDUCE-LLM: unexpected return type %s",
                type(run_result).__name__,
            )
            return None

        self._phase_1c_reduce_cache = run_result
        synthesis = run_result.get(
            "P1C-LLM-03-STRATEGIC-SYNTHESIS",
            run_result.get("P1C-LLM-03"),
        )
        if synthesis is not None:
            self.state["aggregated_data"]["synthesis"] = synthesis
        return synthesis if isinstance(synthesis, dict) else None

    def reduce_compound(self, *, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """P1C-LLM-02 COMPOUND EVENTS reduce step.

        Granular method extracted from :meth:`reduce` (CORR-018a S1).
        Reads the cached executor result produced by :meth:`reduce_synthesis`
        (no new LLM call) and writes the P1C-LLM-02 payload into
        ``state["aggregated_data"]["compound_events"]``.

        Args:
            config: Reserved for forward-compat — this step currently
                reads from cache and does not invoke the LLM directly,
                but the signature mirrors :meth:`reduce_synthesis` so
                the LangGraph nodes can pass a uniform ``config``.

        Returns:
            The P1C-LLM-02 compound-events dict when a cached result is
            available, ``None`` otherwise (e.g. synthesis step was
            skipped or failed before caching).
        """
        run_result = getattr(self, "_phase_1c_reduce_cache", None)
        if not isinstance(run_result, dict):
            return None
        compound_events = run_result.get(
            "P1C-LLM-02-COMPOUND-EVENT",
            run_result.get("P1C-LLM-02"),
        )
        if compound_events is not None:
            self.state["aggregated_data"]["compound_events"] = compound_events
        return compound_events if isinstance(compound_events, dict) else None

    def _get_phase1_executor(self) -> "Phase1Executor | None":
        """Lazy-initialize the canonical five-LLM Phase1Executor.

        Returns None when no LLM invoker is configured, mock mode is active,
        or reduce-stage LLM calls were explicitly disabled.

        CORR-003 (Phase A): The model is sourced from ``self.llm_invoker``
        (when it exposes a ``.model`` attribute, as ``UnifiedInvoker``
        does) before falling back to the ``OLLAMA_MODEL`` env var. This
        makes ``--model`` propagate consistently between MAP and REDUCE
        stages. ``MOCK_LLM`` is honoured by the guard above; ``MockInvoker``
        exposes no ``.model`` so REDUCE-LLM is unreachable for it anyway
        (guarded above) but the fallback is defensive.
        """
        import os

        if self.llm_invoker is None:
            logger.info("REDUCE-LLM skipped: no llm_invoker configured")
            return None

        if self._skip_reduce_llms:
            logger.info("REDUCE-LLM skipped: --skip-reduce-llms flag set")
            return None

        if self._skip_phase_1b:
            logger.info(
                "Phase1Executor skipped: --skip-phase-1b flag set (covers "
                "Phase 1B P1B-LLM-02 RATIONALE)"
            )
            return None

        if os.environ.get("MOCK_LLM", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            logger.info("REDUCE-LLM skipped: MOCK_LLM env var set")
            return None

        cached = getattr(self, "_phase1_executor_cached", None)
        if cached is not None:
            return cast("Phase1Executor", cached)

        # CORR-003 Phase A: prefer the runner-configured llm_invoker's
        # model so --model propagates to REDUCE LLMs.
        configured_model = getattr(self.llm_invoker, "model", None)
        if not isinstance(configured_model, str) or not configured_model:
            configured_model = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
            model_source = "env"
        else:
            model_source = "llm_invoker"

        try:
            from aegis_phase1.prompts_v2.factory import get_invoker
            from aegis_phase1.prompts_v2.phase1_executor import invoker_to_executor

            p1_invoker = get_invoker(model=configured_model)
            executor = invoker_to_executor(p1_invoker)
            self._phase1_executor_cached = executor
            logger.info(
                "REDUCE-LLM Phase1Executor instantiated: model=%s (source=%s, " "invoker_type=%s)",
                configured_model,
                model_source,
                type(self.llm_invoker).__name__,
            )
            return executor
        except Exception as exc:
            logger.warning("Failed to instantiate Phase1Executor: %s", exc)
            return None

    def generate_deterministic_docs(self, output_dir: str = "output/phase1") -> V2State:
        """Stage 3a: Generate 100% deterministic docs (no MAP/REDUCE required).

        Renders the 04 body plus documents 05, 06, 07, 07b, and the
        consolidated xlsx. All of these artefacts derive exclusively
        from the LOAD-stage data (company context, taxonomy, ontology,
        regulations, sub-domains, preprocessing data) and from the
        deterministic fallback paths of the renderers — no LLM
        invoker is required.

        This stage is **always safe to run**, even after ``MAP_FAILED``,
        so the operator can inspect baseline artefacts while debugging
        a broken MAP run. Sets ``state["current_stage"]`` to
        ``"OUTPUT_DONE_DETERMINISTIC"`` and persists state.

        Errors from individual renderers are accumulated under
        ``state["errors"]`` rather than aborting the stage.

        Args:
            output_dir: Directory in which the documents are written.
                Created if missing.

        Returns:
            Updated :class:`V2State` with ``output_paths`` populated
            for the deterministic subset.
        """
        logger.info("=== STAGE 3a: OUTPUT (DETERMINISTIC) ===")
        start = time.time()

        paths: dict[str, str] = dict(self.state.get("output_paths") or {})
        for label, fn in (
            ("04_body", self.render_doc_04_body),
            ("05", self.render_doc_05),
            ("06", self.render_doc_06),
            ("07", self.render_doc_07),
            ("07b", self.render_doc_07b),
        ):
            try:
                result = fn(self.state, output_dir)
            except Exception as exc:
                logger.exception("OUTPUT (deterministic): renderer %s failed", label)
                self.state.setdefault("errors", []).append(f"output:{label}: {exc!s}")
                continue
            if isinstance(result, dict):
                paths.update(result)

        try:
            xlsx_paths = self.generate_xlsx_workbook(self.state, output_dir)
        except Exception as exc:
            logger.exception("OUTPUT (deterministic): xlsx generator failed")
            self.state.setdefault("errors", []).append(f"output:xlsx: {exc!s}")
            xlsx_paths = {}
        if isinstance(xlsx_paths, dict):
            paths.update(xlsx_paths)

        self.state["output_paths"] = paths
        # Only advance the stage marker if we haven't already completed
        # an enhanced run. This keeps the state machine monotonic.
        if self.state.get("current_stage") not in {"OUTPUT_DONE"}:
            self.state["current_stage"] = "OUTPUT_DONE_DETERMINISTIC"

        elapsed = time.time() - start
        logger.info(
            "OUTPUT (deterministic) complete: %d artefacts in %.2fs -> %s",
            len(paths),
            elapsed,
            output_dir,
        )
        self._persist_state()
        return self.state

    def generate_enhanced_docs(self, output_dir: str = "output/phase1") -> V2State:
        """Stage 3b: Generate LLM-enhanced docs (require successful MAP stage).

        Renders 04a, 04b, 04c, and 04d. These artefacts depend on
        ``state["domain_results"]`` (from MAP) — particularly 04b/04c/04d
        which embed the per-domain ``adapted_objective`` narratives — and
        benefit from an LLM invoker for §3 compliance mapping summaries
        and architecture narrative prose. Deterministic fallbacks exist
        for every section, so the documents remain valid without an
        LLM, but the **stage guard** ensures we skip the call entirely
        when MAP has already failed (to avoid producing partially
        misleading artefacts that pretend to reflect MAP output).

        Sets ``state["current_stage"]`` to ``"OUTPUT_DONE"`` and
        persists state.

        Errors from individual renderers are accumulated under
        ``state["errors"]`` rather than aborting the stage.

        Args:
            output_dir: Directory in which the documents are written.
                Created if missing.

        Returns:
            Updated :class:`V2State` with ``output_paths`` populated
            for the enhanced subset. If MAP failed, returns the state
            unchanged (after logging a warning).
        """
        if self.state.get("current_stage") == "MAP_FAILED":
            logger.warning(
                "OUTPUT (enhanced) SKIPPED — state is MAP_FAILED; "
                "deterministic docs may still be produced via "
                "generate_deterministic_docs()."
            )
            return self.state

        logger.info("=== STAGE 3b: OUTPUT (ENHANCED) ===")
        start = time.time()

        paths: dict[str, str] = dict(self.state.get("output_paths") or {})
        for label, fn in (
            ("04a", self.render_doc_04a),
            ("04b", self.render_doc_04b),
            ("04c", self.render_doc_04c),
            ("04d", self.render_doc_04d),
        ):
            try:
                result = fn(self.state, output_dir)
            except Exception as exc:
                logger.exception("OUTPUT (enhanced): renderer %s failed", label)
                self.state.setdefault("errors", []).append(f"output:{label}: {exc!s}")
                continue
            if isinstance(result, dict):
                paths.update(result)

        self.state["output_paths"] = paths
        self.state["current_stage"] = "OUTPUT_DONE"

        elapsed = time.time() - start
        logger.info(
            "OUTPUT (enhanced) complete: %d artefacts in %.2fs -> %s",
            len(paths),
            elapsed,
            output_dir,
        )
        self._persist_state()
        return self.state

    # ─── Granular render methods (CORR-018b) ────────────────────────────
    #
    # Each render_doc_XX method delegates to the underlying doc_XX module
    # function. Granular methods are the LangGraph node entry points;
    # legacy :meth:`generate_deterministic_docs` and
    # :meth:`generate_enhanced_docs` now call these in a loop so the
    # behaviour is identical to the previous direct invocation.

    def render_doc_04_body(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render the 04 body (deterministic)."""
        from aegis_phase1.v2.output.doc_04 import render_doc_04_body

        return render_doc_04_body(state, output_dir)

    def render_doc_04a(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 04a (architecture & data inventory)."""
        from aegis_phase1.v2.output.doc_04a import render_doc_04a

        return render_doc_04a(state, output_dir, self.llm_invoker, config=config)

    def render_doc_04b(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 04b (security posture)."""
        from aegis_phase1.v2.output.doc_04b import render_doc_04b

        return render_doc_04b(state, output_dir, self.llm_invoker, config=config)

    def render_doc_04c(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 04c (third-party landscape)."""
        from aegis_phase1.v2.output.doc_04c import render_doc_04c

        return render_doc_04c(state, output_dir, self.llm_invoker, config=config)

    def render_doc_04d(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 04d (roles & RACI)."""
        from aegis_phase1.v2.output.doc_04d import render_doc_04d

        return render_doc_04d(state, output_dir, self.llm_invoker, config=config)

    def render_doc_05(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 05 (regulatory applicability)."""
        from aegis_phase1.v2.output.doc_05 import render_doc_05

        return render_doc_05(state, output_dir, self.llm_invoker, config=config)

    def render_doc_06(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 06 (clause mapping matrix, deterministic)."""
        from aegis_phase1.v2.output.doc_06 import render_doc_06

        return render_doc_06(state, output_dir)

    def render_doc_07(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 07 (structured compliance matrix)."""
        from aegis_phase1.v2.output.doc_07 import render_doc_07

        return render_doc_07(state, output_dir, self.llm_invoker, config=config)

    def render_doc_07b(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render 07b (proportionality profile)."""
        from aegis_phase1.v2.output.doc_07b import render_doc_07b

        return render_doc_07b(state, output_dir, self.llm_invoker, config=config)

    def generate_xlsx_workbook(
        self,
        state: dict[str, Any],
        output_dir: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Render the consolidated xlsx workbook (deterministic)."""
        from aegis_phase1.v2.output.xlsx_generator import generate_xlsx

        return generate_xlsx(state, output_dir)

    def generate_outputs(self, output_dir: str = "output/phase1") -> V2State:
        """Legacy single-shot: generate all docs (deterministic + enhanced).

        Equivalent to calling :meth:`generate_deterministic_docs` followed
        by :meth:`generate_enhanced_docs`. Kept for backward compatibility
        with callers (and tests) that expect a single ``generate_outputs``
        method to produce every artefact.

        Stage-guard behaviour: if ``state["current_stage"]`` is
        ``"MAP_FAILED"`` at call time, the deterministic half runs but
        the enhanced half is skipped (logged warning, no exception).

        Args:
            output_dir: Directory in which the documents are written.
                Created if missing.

        Returns:
            Updated :class:`V2State` with ``output_paths`` populated for
            all generated artefacts.
        """
        logger.info("=== STAGE 3: OUTPUT (composite) ===")
        self.generate_deterministic_docs(output_dir)
        self.generate_enhanced_docs(output_dir)
        logger.info("=== PIPELINE OUTPUT COMPLETE ===")
        return self.state

    def run_all(
        self,
        case_path: str,
        regulatory_baseline_path: str | None = None,
        output_dir: str = "output/phase1",
        *,
        preprocessing_path: str | None = None,
    ) -> V2State:
        """Run all 4 stages in sequence: LOAD → MAP → REDUCE → OUTPUT.

        Both ``regulatory_baseline_path`` (canonical) and the deprecated
        ``preprocessing_path`` alias are accepted. If only the alias is
        given, a DeprecationWarning is emitted.
        """
        logger.info("=== RUN ALL STAGES ===")
        # Resolve deprecated alias before delegating to load().
        if regulatory_baseline_path is None:
            regulatory_baseline_path = preprocessing_path
            if regulatory_baseline_path is not None:
                import warnings

                warnings.warn(
                    "Argument 'preprocessing_path' is deprecated; use "
                    "'regulatory_baseline_path' instead. (Phase 0 rebranding)",
                    DeprecationWarning,
                    stacklevel=2,
                )
        if regulatory_baseline_path is None:
            regulatory_baseline_path = ""
        self.load(
            case_path,
            regulatory_baseline_path,
            preprocessing_path=preprocessing_path,
        )
        self.map_domains()
        self.run_phase_1b()
        self.reduce()
        self.generate_outputs(output_dir)
        logger.info("=== PIPELINE COMPLETE ===")
        return self.state

    def run_phase_1b(self) -> V2State:
        """Stage 1.5: Per-regulation rationale synthesis via P1B-LLM-02.

        LEGACY entry point (CORR-018a S1). Delegates each applicable
        regulation to :meth:`run_p1b_single` in a loop and aggregates
        the per-reg synthesis payloads into
        ``state["aggregated_data"]["rationale_by_reg"]`` keyed by
        regulation code (e.g. ``"GDPR"`` →
        ``{synthesis: {rationale, implications, gaps}, ...}``).

        Skipped when:

        - ``llm_invoker`` is None (deterministic-only run),
        - ``--skip-reduce-llms`` flag is set (covers Phase 1B by convention),
        - ``MOCK_LLM`` env var is truthy,
        - ``--skip-phase-1b`` flag is set (explicit skip).

        Failures are caught and logged; the pipeline continues so the
        deterministic DOC 05 / DOC 07 renderers still run with a
        PENDING-REVIEW marker instead of crashing.
        """
        logger.info("=== STAGE 1.5: PHASE 1B RATIONALE ===")

        if "aggregated_data" not in self.state or not isinstance(
            self.state["aggregated_data"], dict
        ):
            self.state["aggregated_data"] = {}

        executor = self._get_phase1_executor()
        if executor is None:
            logger.info(
                "Phase 1B RATIONALE skipped (deterministic/mock " "mode or --skip-phase-1b flag)"
            )
            self.state["aggregated_data"]["rationale_by_reg"] = None
            self._persist_state()
            return self.state

        # Extract applicable_regs (mirrors reduce() extraction pattern
        # because company_context may be a Pydantic model).
        cc_raw = self.state.get("company_context")
        if hasattr(cc_raw, "model_dump"):
            cc = cc_raw.model_dump()
        elif isinstance(cc_raw, dict):
            cc = dict(cc_raw)
        else:
            cc = {}

        regs: list[str] = []
        for candidate in cc.get("applicable_regs") or []:
            if candidate:
                regs.append(str(candidate))
        if not regs:
            appl = cc.get("applicable_regulations", [])
            if isinstance(appl, list):
                for entry in appl:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("applicable") and entry.get("abbreviation"):
                        regs.append(str(entry["abbreviation"]))

        if not regs:
            logger.warning("Phase 1B RATIONALE skipped: no applicable regulations")
            self.state["aggregated_data"]["rationale_by_reg"] = {}
            self._persist_state()
            return self.state

        synth_by_reg: dict[str, Any] = {}
        last_status: str = "?"
        for reg_id in regs:
            try:
                per_reg_synth = self.run_p1b_single("P1B-LLM-02-RATIONALE", reg_id)
            except Exception as exc:
                logger.warning(
                    "Phase 1B RATIONALE failed (continuing) for %s: %s",
                    reg_id,
                    exc,
                )
                self.state.setdefault("errors", []).append(f"phase_1b:{reg_id}: {exc}")
                continue
            if isinstance(per_reg_synth, dict) and per_reg_synth:
                synth_by_reg[reg_id] = per_reg_synth

        self.state["aggregated_data"]["rationale_by_reg"] = synth_by_reg
        logger.info(
            "Phase 1B RATIONALE complete for %d regulation(s) " "(status=%s)",
            len(synth_by_reg),
            last_status,
        )
        # CORR-041-T2: refresh the SynthesisContext with the new
        # rationale_by_reg data
        self._build_synthesis_context()
        self._persist_state()
        return self.state

    def run_p1b_single(
        self,
        spec_id: str,
        reg_id: str,
        *,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Single Phase1B call: one spec × one regulation.

        Granular method extracted from :meth:`run_phase_1b` (CORR-018a S1).
        Computes the per-call inputs from ``self.state``, invokes
        ``executor.run_phase_1b(applicable_regs=[reg_id])``, and returns
        the ``aggregated_synthesis[reg_id]`` slice for that regulation
        (i.e. the per-reg synthesis dict the executor produced).

        CORR-039-T4: enriches the inputs with the filtered tipo2 + tipo3
        catalogs (via ``self.catalog_loader``), so P1B-LLM-01 sees the
        interpretations and derogations that apply to this company
        rather than the full unfiltered catalog. Also swaps the
        coverage_matrix_row source from the empty v1 ontology
        ``clause_mappings`` to the v2 ClauseMappingContext (T2/T3).

        Args:
            spec_id: Reserved for future per-spec splitting (e.g. to call
                P1B-LLM-01 and P1B-LLM-02 independently per spec). The
                executor currently performs both sub-calls per reg in a
                single ``run_phase_1b`` invocation; ``spec_id`` is
                therefore accepted but ignored in S1.
            reg_id: One applicable regulation code (e.g. ``"GDPR"``).
            config: Optional LangChain ``RunnableConfig`` threaded into
                the executor's invoker so the GENERATION span in Langfuse
                is named after the LangGraph node (CORR-018b C7 fix).

        Returns:
            The per-reg synthesis dict (the value under
            ``aggregated_synthesis[reg_id]``) on success, ``None`` when
            the executor is unavailable or returned an unexpected type.
            The caller (legacy :meth:`run_phase_1b`) aggregates results
            and persists ``state["errors"]`` on exception.
        """
        executor = self._get_phase1_executor()
        if executor is None:
            return None

        cc_raw = self.state.get("company_context")
        if hasattr(cc_raw, "model_dump"):
            cc = cc_raw.model_dump()
        elif isinstance(cc_raw, dict):
            cc = dict(cc_raw)
        else:
            cc = {}

        aggregated_activations: list[Any] = []
        for lr in (self.state.get("domain_results") or {}).values():
            subs = lr.get("subdomains", []) if isinstance(lr, dict) else []
            if isinstance(subs, list):
                aggregated_activations.extend(subs)

        # CORR-039-T3/T4: use the v2 ClauseMappingContext for the
        # per-reg coverage_matrix_row. Pre-CORR-039 this read the empty
        # state['ontology']['clause_mappings'] and the LLM saw 0 rows.
        coverage_rows: list[Any] = []
        try:
            from aegis_phase1.v2.context.clause_mapping_context import (
                build_clause_mapping_context,
            )

            cm_ctx = build_clause_mapping_context(self.state)
            coverage_rows = [e.model_dump() for e in cm_ctx.by_regulation(reg_id)]
        except Exception as exc:
            logger.debug(
                "run_p1b_single: clause_mapping_context build failed (%s) — "
                "coverage_rows will be empty for %s",
                exc,
                reg_id,
            )

        # CORR-039-T4: filter tipo2 + tipo3 catalogs for this reg + tier
        layer0_catalog = self._load_filtered_catalogs_for_reg(reg_id, cc)

        case_id = Path(self.state.get("case_path") or "case").name
        result = executor.run_phase_1b(
            case_id=case_id,
            applicable_regs=[reg_id],
            p1b_llm_01_outputs=None,
            company_facts=cc,
            coverage_matrix_row=coverage_rows,
            aggregated_activations=aggregated_activations,
            layer0_subdomain_refs=self._build_layer0_subdomain_refs(
                list((self.state.get("subdomains") or {}).keys())
            ),
            layer0_catalog=layer0_catalog,
            classification={
                "role": cc.get("role") or cc.get("obligated_party") or "controller",
                "tier": cc.get("complexity_tier") or "LOW",
                "basis": "Doc 04 §5",
            },
            config=config,
        )

        if not isinstance(result, dict):
            logger.warning(
                "run_p1b_single(%s, %s): unexpected return type %s",
                spec_id,
                reg_id,
                type(result).__name__,
            )
            return None

        synth = result.get("aggregated_synthesis")
        if not isinstance(synth, dict):
            return None
        return synth.get(reg_id)

    def _load_filtered_catalogs_for_reg(
        self,
        reg_id: str,
        company_context: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        """CORR-039-T4: return tipo2 + tipo3 entries filtered for this reg.

        Uses ``self.catalog_loader.filter_applicable(regulation, tier)``
        on the v2_catalog_tipo2 / v2_catalog_tipo3 lists populated by
        ``_load_v2_catalog`` (T1). Falls back to empty lists when the
        catalog loader is not injected or the catalogs are empty — the
        LLM call still proceeds with an empty catalog and returns
        ``interpretations: []`` / ``derogations: []``.

        For tipo3 entries, ``evaluate_predicates`` is run against the
        company facts and the verdict is attached to each entry as
        ``predicate_verdict`` (True / False / None for
        INSUFFICIENT_EVIDENCE). This gives P1B-LLM-01 the evaluated
        activation signal alongside the catalog metadata.
        """
        out: dict[str, list[dict[str, Any]]] = {"tipo2": [], "tipo3": []}
        if self.catalog_loader is None:
            return out
        tier = str(
            company_context.get("complexity_tier")
            or company_context.get("tier")
            or "LOW"
        )
        try:
            tipo2_all = self.state.get("v2_catalog_tipo2", []) or []
            tipo3_all = self.state.get("v2_catalog_tipo3", []) or []
            out["tipo2"] = self.catalog_loader.filter_applicable(
                tipo2_all, regulation=reg_id, tier=tier
            )
            tipo3_filtered = self.catalog_loader.filter_applicable(
                tipo3_all, regulation=reg_id, tier=tier
            )
            # Enrich tipo3 with predicate verdicts (best-effort)
            try:
                evaluated = self.catalog_loader.evaluate_predicates(
                    tipo3_filtered, company_context
                )
                out["tipo3"] = [
                    {**entry, "predicate_verdict": verdict}
                    for entry, verdict in evaluated
                ]
            except Exception as exc:
                logger.debug(
                    "predicate evaluation failed for %s: %s — keeping unevaluated",
                    reg_id,
                    exc,
                )
                out["tipo3"] = list(tipo3_filtered)
            logger.debug(
                "T4: filtered catalogs for %s (tier=%s) — tipo2=%d, tipo3=%d",
                reg_id,
                tier,
                len(out["tipo2"]),
                len(out["tipo3"]),
            )
        except Exception as exc:
            logger.warning(
                "T4: catalog filter failed for %s: %s — using empty lists", reg_id, exc
            )
        return out

    def _init_state(self) -> V2State:
        return {
            "current_stage": "INIT",
            "case_path": "",
            # Legacy key — kept for backward-compat reads of work/state.json
            # from v2.1 era. New code should read regulatory_baseline_path.
            "preprocessing_path": "",
            # Canonical key introduced in Phase 0 rebranding.
            "regulatory_baseline_path": "",
            "company_context": None,
            "architecture_inventory": {},
            "stakeholders": [],
            "business_goals": [],
            "taxonomy_entries": [],
            "ontology": {},
            "regulations": [],
            "subdomains": {},
            "preprocessing": {},
            "domain_results": {},
            "aggregated_data": {},
            "output_paths": {},
            "errors": [],
        }

    def _persist_state(self) -> None:
        """Persist current state to work/state.json."""
        state_path = self.work_dir / "state.json"
        try:
            serializable = self._make_serializable(self.state)
            state_path.write_text(
                json.dumps(serializable, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            logger.debug("State persisted to %s", state_path)
        except Exception as e:
            logger.warning("Failed to persist state: %s", e)

    def _seed_review_after_map(self, results: dict[str, Any]) -> None:
        """Create the human-review YAML for adapted_objectives if missing.

        Idempotent: human edits to existing entries are preserved; only
        missing domain entries are seeded with ``status: PENDING``. A
        missing ``case_path`` or YAML failure is logged but does not
        abort MAP (the review file is a soft, human-in-the-loop
        artefact).
        """
        case_path = self.state.get("case_path", "") or ""
        if not case_path:
            logger.debug("MAP seed_review: no case_path; skipping")
            return
        try:
            from aegis_phase1.v2.review.loader import seed_review

            seeded = seed_review(case_path, results)
            logger.info(
                "MAP seed_review: %d review entries at %s/review/adapted_objectives.yaml",
                len(seeded),
                case_path,
            )
        except Exception as exc:
            logger.warning("MAP seed_review failed for %s: %s", case_path, exc)

    def _make_serializable(self, obj: Any) -> Any:
        """Convert non-serializable objects (Pydantic models) to dicts."""
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._make_serializable(v) for v in obj]
        return obj

    def _build_layer0_subdomain_refs(
        self,
        subdomain_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Build rich ``layer0_subdomain_refs`` from subdomain IDs.

        CORR-045: replaces the previous
        ``list((state["subdomains"] or {}).keys())`` pattern that passed
        bare string IDs (crashed the canonical P1C-LLM-01 path with
        ``'str' object has no attribute 'get'``). Each entry now carries
        the metadata the P1C-LLM-01 spec requires (objective, pairs,
        participating_regulations, anchors, csf).

        Args:
            subdomain_ids: list of subdomain IDs (e.g. ``["D-01.1",
                "D-01.2"]``).

        Returns:
            list[dict] with one entry per subdomain_id, ordered by ID.
            Missing subdomains are skipped (logged at DEBUG). When the
            ``preproc_catalog`` loader is missing, returns bare ID
            dicts (P1C-LLM-01 may produce thin output).
        """
        if (
            not hasattr(self, "preproc_catalog")
            or self.preproc_catalog is None
        ):
            logger.warning(
                "_build_layer0_subdomain_refs: preproc_catalog not loaded; "
                "returning bare ID dicts (P1C-LLM-01 may produce thin output)"
            )
            return [{"sub_domain_id": sid, "title": sid} for sid in subdomain_ids]

        all_subdomains = self.preproc_catalog.load_subdomains()
        by_id: dict[str, Any] = {s.id: s for s in all_subdomains}
        refs: list[dict[str, Any]] = []
        for sid in subdomain_ids:
            sd = by_id.get(sid)
            if sd is None:
                logger.debug(
                    "subdomain %s not found in preproc_catalog; skipping", sid
                )
                continue
            anchors: list[str] = []
            for sr in (sd.security_requirements or []):
                anchors.extend(sr.anchors or [])
            objective = sd.hso_hl.objective if sd.hso_hl else None
            refs.append(
                {
                    "sub_domain_id": sd.id,
                    "title": sd.title,
                    "domain_id": sd.domain_id,
                    "participating_regulations": list(
                        sd.participating_regulations or []
                    ),
                    "hso_hl_objective": objective,
                    "objective": objective,
                    "pairs": [
                        p.model_dump() if hasattr(p, "model_dump") else p
                        for p in (sd.pairs or [])
                    ],
                    "anchors": sorted(set(anchors)),
                    "csf": list(sd.csf_hint or []),
                }
            )
        return refs


__all__ = ["Phase1Orchestrator"]
