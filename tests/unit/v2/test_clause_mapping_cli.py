"""CORR-039-T6 Block 5: CLI flag smoke tests for --run-clauses + --run-phase-1b.

Verifies the new CLI flags produce the expected artefacts via the
public cmd_run_clauses / cmd_run_phase_1b functions.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


def test_run_clauses_produces_doc_06_with_content() -> None:
    """cmd_run_clauses writes 06_Clause_Mapping_Matrix.md with content."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator
    from aegis_phase1.v2.runner import cmd_run_clauses

    with tempfile.TemporaryDirectory() as work:
        with tempfile.TemporaryDirectory() as out:
            o = Phase1Orchestrator(
                work_dir=work,
                preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
            )
            paths = cmd_run_clauses(
                orch=o,
                case_path="cases/case1-tinytask",
                prep_path="",  # not used by load() with v2 loaders
                output_path=out,
            )
            # Assert inside the `with` block — the tempdir is cleaned up on exit.
            assert "AEGIS-P1-06" in paths
            p = Path(paths["AEGIS-P1-06"])
            assert p.exists(), f"Doc 06 not written at {p}"
            body = p.read_text(encoding="utf-8")
            assert "Clause Mapping Matrix" in body
            assert "GDPR" in body
            assert "CRA" in body
            assert len(body) > 5000


def test_run_phase_1b_invokes_path_with_mock_llm() -> None:
    """cmd_run_phase_1b runs the Phase 1B path and re-renders Doc 05.

    With MOCK_LLM=true the executor is skipped (by design — see
    _get_phase1_executor), but the function still:
      - calls orch.load()
      - calls orch.run_phase_1b() (which logs the MOCK_LLM skip)
      - re-renders Doc 05 with the rationale_by_reg data
    """
    import os

    os.environ["MOCK_LLM"] = "true"
    try:
        from aegis_phase1.prompts_v2.catalog import CatalogLoader
        from aegis_phase1.prompts_v2.factory import get_prompts_root
        from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
        from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
        from aegis_phase1.v2.orchestrator import Phase1Orchestrator
        from aegis_phase1.v2.runner import cmd_run_phase_1b

        with tempfile.TemporaryDirectory() as work:
            with tempfile.TemporaryDirectory() as out:
                o = Phase1Orchestrator(
                    work_dir=work,
                    preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                    case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                    catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
                )
                paths = cmd_run_phase_1b(
                    orch=o,
                    case_path="cases/case1-tinytask",
                    prep_path="",
                    output_path=out,
                )
                # Assert inside the `with` block.
                assert "AEGIS-P1-05" in paths
                p = Path(paths["AEGIS-P1-05"])
                assert p.exists(), f"Doc 05 not written at {p}"
                body = p.read_text(encoding="utf-8")
                # Doc 05 should still be rendered (with PENDING REVIEW marker for §6.1b
                # since MOCK_LLM caused the executor to be None)
                assert "Regulatory Applicability" in body
    finally:
        del os.environ["MOCK_LLM"]


def test_run_clauses_and_run_phase_1b_are_independent() -> None:
    """--run-clauses and --run-phase-1b don't depend on each other."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator
    from aegis_phase1.v2.runner import cmd_run_clauses

    with tempfile.TemporaryDirectory() as work:
        with tempfile.TemporaryDirectory() as out:
            o = Phase1Orchestrator(
                work_dir=work,
                preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
                case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
                catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
            )
            # Just call run_clauses — verifies it works without needing run_phase_1b
            paths = cmd_run_clauses(
                orch=o,
                case_path="cases/case1-tinytask",
                prep_path="",
                output_path=out,
            )
            assert "AEGIS-P1-06" in paths
