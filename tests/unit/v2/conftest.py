"""Shared pytest fixtures for v2 tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
from aegis_phase1.v2.orchestrator import Phase1Orchestrator


@pytest.fixture(scope="session")
def case_root() -> Path:
    return Path("cases/case1-tinytask")


@pytest.fixture(scope="session")
def case_profile_loader(case_root: Path) -> CaseProfileLoader:
    return CaseProfileLoader(case_root)


@pytest.fixture(scope="session")
def case1_v2_state(
    case_root: Path, case_profile_loader: CaseProfileLoader, tmp_path_factory: pytest.TempPathFactory
) -> dict:
    """Real case1 v2 state: orchestrator with v2 loaders applied, no LLM calls."""
    work = tmp_path_factory.mktemp("case1_v2")
    o = Phase1Orchestrator(work_dir=str(work), case_profile_loader=case_profile_loader)
    o._load_v2_catalog(str(case_root))
    return dict(o.state)
