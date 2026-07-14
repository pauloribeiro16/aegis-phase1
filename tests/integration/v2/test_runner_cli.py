"""CLI integration tests for ``aegis_phase1.v2.runner``.

These tests spawn the runner as a subprocess against the canonical case
and preprocessing directories, verifying:

1. ``--help`` advertises the full flag surface.
2. ``--run-all --mock-llm`` runs end-to-end and produces the expected
   output artefacts (5 docs from Doc 04 + Doc 05/06/07/07b + 1 xlsx).

The tests do NOT require a live Ollama instance — they use ``--mock-llm``
(equivalent to ``MOCK_LLM=true``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_runner_help() -> None:
    """``python -m aegis_phase1.v2.runner --help`` shows all MAP-3/MAP-4 flags."""
    result = subprocess.run(
        [sys.executable, "-m", "aegis_phase1.v2.runner", "--help"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    stdout = result.stdout
    for flag in ("--mock-llm", "--retry-failed", "--model"):
        assert flag in stdout, f"Missing flag {flag} in --help output"


def test_runner_mock_llm_runs(tmp_path: Path) -> None:
    """``--run-all --mock-llm`` succeeds and produces the 10 expected artefacts."""
    env = os.environ.copy()
    env["MOCK_LLM"] = "true"

    output_dir = tmp_path / "out"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aegis_phase1.v2.runner",
            "--run-all",
            "--mock-llm",
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=180,
    )

    assert result.returncode == 0, (
        f"Runner exited with code {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    assert output_dir.exists(), f"Output directory not created: {output_dir}"

    md_files = list(output_dir.glob("*.md"))
    xlsx_files = list(output_dir.glob("*.xlsx"))
    files = md_files + xlsx_files
    # 5 from Doc 04 + Doc 05 + Doc 06 + Doc 07 + Doc 07b + xlsx = 10
    assert len(files) >= 10, (
        f"Expected ≥10 artefacts, got {len(files)}: "
        f"{sorted(p.name for p in files)}"
    )
    assert len(xlsx_files) >= 1, "Expected at least one xlsx output"


def test_runner_mock_llm_map_only_skips_outputs(tmp_path: Path) -> None:
    """``--map-only`` runs LOAD+MAP but produces no output artefacts.

    This documents the contract that ``--map-only`` is intended for
    iterative MAP-stage work; full artefacts require ``--run-all``.
    The runner does not create the output directory in this mode, so
    we only assert that no artefact files appear anywhere under tmp_path.
    """
    env = os.environ.copy()
    env["MOCK_LLM"] = "true"

    output_dir = tmp_path / "out_map_only"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aegis_phase1.v2.runner",
            "--map-only",
            "--mock-llm",
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"Runner exited with code {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    files = list(output_dir.glob("*.md")) + list(output_dir.glob("*.xlsx"))
    assert files == [], (
        f"--map-only should produce no output artefacts, got: "
        f"{sorted(p.name for p in files)}"
    )


def test_runner_deterministic_only_produces_baseline_artefacts(tmp_path: Path) -> None:
    """``--deterministic-only`` produces 5 docs + xlsx without running MAP/REDUCE.

    Sprint Phase 3 decouple: the deterministic docs (04 body, 05, 06,
    07, 07b) plus the consolidated xlsx must be writable after a
    LOAD-only run. No 04a/04b/04c/04d artefacts should appear, since
    those depend on MAP output.
    """
    env = os.environ.copy()
    env["MOCK_LLM"] = "true"

    output_dir = tmp_path / "out_det_only"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "aegis_phase1.v2.runner",
            "--deterministic-only",
            "--mock-llm",
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"Runner exited with code {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    md_files = sorted(p.name for p in output_dir.glob("*.md"))
    xlsx_files = sorted(p.name for p in output_dir.glob("*.xlsx"))

    # The 5 deterministic docs must be present.
    expected_docs = {
        "04_Company_Context_Assessment.md",
        "05_Regulatory_Applicability.md",
        "06_Clause_Mapping_Matrix.md",
        "07_Structured_Compliance_Matrix.md",
        "07b_Proportionality_Profile.md",
    }
    assert expected_docs.issubset(set(md_files)), (
        f"Missing deterministic docs. Got: {md_files}"
    )

    # 04a/04b/04c/04d must NOT be present (those require MAP).
    forbidden_docs = {
        "04a_Architecture_DataInventory.md",
        "04b_Security_Posture.md",
        "04c_ThirdParty_Landscape.md",
        "04d_Org_Roles_RACI.md",
    }
    assert not (forbidden_docs & set(md_files)), (
        f"--deterministic-only should NOT produce enhanced docs. "
        f"Got: {md_files}"
    )

    # The xlsx must be present (it aggregates everything deterministic).
    assert len(xlsx_files) == 1, f"Expected 1 xlsx, got {xlsx_files}"
