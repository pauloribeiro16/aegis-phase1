"""Unit test for ``Phase1Orchestrator._load_clause_mappings_from_case``.

Verifies that the gold-style per-article clause table authored in
``cases/<case>/context/phase1_ontology.yaml:clause_mappings`` lands in
``state['raw_clause_mappings']`` after ``load()`` runs.

Std-lib only. Uses the same Phase1Orchestrator instantiation pattern as
``tests/unit/v2/test_domain_activation.py`` so any future loader change
that breaks Phase1Orchestrator wiring surfaces in both test files.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from aegis_phase1.v2.orchestrator import Phase1Orchestrator


def _make_orchestrator(work_dir: str) -> Phase1Orchestrator:
    """Construct a Phase1Orchestrator with the loaders the runner uses."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.llm import MockInvoker
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader

    return Phase1Orchestrator(
        work_dir=work_dir,
        llm_invoker=MockInvoker(),
        preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
        case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
        catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
    )


def test_load_populates_raw_clause_mappings_from_case_ontology() -> None:
    """End-to-end LOAD: the 54 gold-style rows appear under raw_clause_mappings."""
    # MOCK_LLM true so the executor never reaches a real model.
    os.environ["MOCK_LLM"] = "true"
    try:
        with tempfile.TemporaryDirectory() as work:
            orch = _make_orchestrator(work)
            # Regulatory baseline location (matches runner.py defaults).
            reg_baseline = (
                "Methodology-main/00_METHODOLOGY/PREPROCESSING"
                if os.path.isdir("Methodology-main/00_METHODOLOGY/PREPROCESSING")
                else "../Methodology-main/00_METHODOLOGY/PREPROCESSING"
            )
            orch.load("cases/case1-tinytask", reg_baseline)

            raw = orch.state.get("raw_clause_mappings")
            assert isinstance(
                raw, list
            ), f"raw_clause_mappings must be a list, got {type(raw).__name__}"
            # The case YAML carries all 54 gold rows; the full 54 are loaded
            assert len(raw) == 54, f"expected 54 gold rows, got {len(raw)}"

            # Spot-check a known row (GDPR-C01 = Art. 1 / Lawfulness of processing)
            sample = raw[0]
            assert sample["clause_id"] == "GDPR-C01"
            assert sample["regulation_id"] == "REG-GDPR"
            assert sample["article"] == "Art. 1"
            assert "Lawfulness" in sample["description"]
            assert sample["maps_to_subdomain"] == "D-05.1"

            # And at least 20 CRA rows exist
            cra_rows = [r for r in raw if r["regulation_id"] == "REG-CRA"]
            assert len(cra_rows) >= 20, f"CRA should have ~26 rows, got {len(cra_rows)}"

            # Legacy v1 consumers reading state['ontology'] also see
            # the gold-style rows because orchestrator.load() refreshes
            # the shim after _load_clause_mappings_from_case writes the
            # parallel key.
            ont = orch.state.get("ontology") or {}
            shim = ont.get("raw_clause_mappings") if isinstance(ont, dict) else None
            assert isinstance(shim, list)
            assert len(shim) == 54
    finally:
        del os.environ["MOCK_LLM"]


def test_load_handles_missing_clause_mappings_key_gracefully() -> None:
    """When the YAML exists but lacks clause_mappings, raw list is empty."""
    os.environ["MOCK_LLM"] = "true"
    try:
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as tmp_case:
            os.makedirs(os.path.join(tmp_case, "context"))
            with open(
                os.path.join(tmp_case, "context", "phase1_ontology.yaml"),
                "w",
            ) as f:
                f.write("company:\n  name: TestCase\n")
            # The wiring helper auto-discovers candidate paths
            # including the case's own context/ dir. Invoke directly
            # on the orchestrator instance — bypass loaders that point
            # at the real case1 directory.
            from aegis_phase1.v2.orchestrator import Phase1Orchestrator

            orch = Phase1Orchestrator(work_dir=work)
            orch._load_clause_mappings_from_case(tmp_case)

            raw = orch.state.get("raw_clause_mappings")
            assert isinstance(raw, list)
            assert raw == []
    finally:
        del os.environ["MOCK_LLM"]
