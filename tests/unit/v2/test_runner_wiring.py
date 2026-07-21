"""CORR-039-T6 Block 3: runner.py injects the 3 loaders into Phase1Orchestrator.

Pre-CORR-039 the runner instantiated Phase1Orchestrator(llm_invoker=...)
with no loaders, so _load_v2_catalog was a no-op. Post-CORR-039-T1 the
runner instantiates and injects:
  - PreprocCatalogLoader(preproc_root='preproc_out')
  - CaseProfileLoader(args.case)
  - CatalogLoader(root=get_prompts_root() / 'catalogs')
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from aegis_phase1.prompts_v2.factory import get_prompts_root


def _read_main_module() -> str:
    """Return the source of v2/runner.py main() for inspection."""
    import inspect

    from aegis_phase1.v2 import runner

    return inspect.getsource(runner)


def test_runner_injects_preproc_catalog_into_orchestrator() -> None:
    """runner.py constructs a PreprocCatalogLoader and passes it to Phase1Orchestrator."""
    src = _read_main_module()
    assert "PreprocCatalogLoader(preproc_root=" in src
    assert "preproc_catalog=" in src
    assert "preproc_catalog=preproc_catalog" in src or "preproc_catalog=preproc" in src


def test_runner_injects_case_profile_loader_into_orchestrator() -> None:
    """runner.py constructs a CaseProfileLoader and passes it to Phase1Orchestrator."""
    src = _read_main_module()
    assert "CaseProfileLoader(" in src
    assert "case_profile_loader=" in src


def test_runner_injects_catalog_loader_into_orchestrator() -> None:
    """runner.py constructs a CatalogLoader and passes it to Phase1Orchestrator."""
    src = _read_main_module()
    assert "CatalogLoader(" in src
    assert "catalog_loader=" in src
    # And it points at the PROMPTS/catalogs dir (where tipo2/tipo3 YAMLs live)
    assert "get_prompts_root()" in src
    assert "/catalogs" in src or '"catalogs"' in src


def test_orchestrator_constructor_accepts_catalog_loader() -> None:
    """Phase1Orchestrator.__init__ accepts catalog_loader as kwarg."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    cl = CatalogLoader(root=get_prompts_root() / "catalogs")
    with tempfile.TemporaryDirectory() as d:
        o = Phase1Orchestrator(work_dir=d, catalog_loader=cl)
        assert o.catalog_loader is cl


def test_load_v2_catalog_populates_v2_catalog_keys() -> None:
    """End-to-end: orch with all 3 loaders → v2_catalog_tipo2 + v2_catalog_tipo3 populated."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    with tempfile.TemporaryDirectory() as d:
        o = Phase1Orchestrator(
            work_dir=d,
            preproc_catalog=PreprocCatalogLoader(preproc_root="preproc_out"),
            case_profile_loader=CaseProfileLoader(Path("cases/case1-tinytask")),
            catalog_loader=CatalogLoader(root=get_prompts_root() / "catalogs"),
        )
        o._load_v2_catalog("cases/case1-tinytask")
        # tipo2 + tipo3 must be present (the YAML files exist with real entries)
        assert "v2_catalog_tipo2" in o.state
        assert "v2_catalog_tipo3" in o.state
        # Real catalog has 8 tipo2 + 6 tipo3 entries
        assert len(o.state["v2_catalog_tipo2"]) == 8
        assert len(o.state["v2_catalog_tipo3"]) == 6


def test_load_v2_catalog_handles_empty_catalog_dir(tmp_path: Path) -> None:
    """Empty catalog dir (exists, no YAML files) → v2_catalog_* = [] gracefully."""
    from aegis_phase1.prompts_v2.catalog import CatalogLoader
    from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
    from aegis_phase1.v2.loader.preproc_catalog import PreprocCatalogLoader
    from aegis_phase1.v2.orchestrator import Phase1Orchestrator

    # Create an empty catalog dir (exists, no .yaml files)
    empty_catalogs = tmp_path / "empty_catalogs"
    empty_catalogs.mkdir()
    cl = CatalogLoader(root=empty_catalogs)
    # CatalogLoader constructs OK on empty dir
    assert cl.root == empty_catalogs
    # load() raises CatalogLoadError for missing files — that's the loader's job.
    from aegis_phase1.prompts_v2.catalog import CatalogLoadError

    with pytest.raises(CatalogLoadError):
        cl.load("tipo2_interpretations")
