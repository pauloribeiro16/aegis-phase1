"""Tests for CORR-OBJ-Phase4: contract-driven check_gate scorecard.

OBJECTIVES_CONTRACT §2 defines 14 objectives with [G]/[J]/[H] mechanism
markers. The contract-driven scorecard is the **single entry point**
for the no-regression rule (§5).

What we verify here:

1. The contract parser extracts 14 objectives from the canonical
   ``docs/OBJECTIVES_CONTRACT.md`` (or a representative fixture).
2. A missing gate (no cell registered) is reported as ``MISSING_GATE`` /
   ``JUDGE_NOT_WIRED`` and does NOT fail the run in non-strict mode.
3. In ``--strict`` mode, a [G] failure exits non-zero.
4. A regression against a captured baseline (any status more severe)
   exits with code 2 in strict mode.
5. ``--capture-baseline`` saves the JSON and returns 0.
6. The scorecard round-trips through ``to_dict`` / ``from_dict``.
7. ``--baseline`` and ``--capture-baseline`` are mutually exclusive.
8. The full CLI is exercisable end-to-end against a synthetic run-dir.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve()
for p in REPO.parents:
    if (p / "src" / "aegis_phase1").is_dir() and (p / "scripts" / "eval").is_dir():
        REPO = p
        break
# Make scripts.eval importable.
sys.path.insert(0, str(REPO))


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


# A representative subset of the OBJECTIVES_CONTRACT.md table — 3
# rows that cover the [G], [J], and [G+J] markers. Used by tests that
# want a fast, hermetic contract fixture.
MINI_CONTRACT_MARKDOWN = """# Test contract

## 2. The objectives

| ID | Objective | Measured by | Mechanism | Status |
|----|-----------|-------------|-----------|--------|
| OBJ-01 | Company grounding | citations | [G] | MISSING |
| OBJ-05 | Proportionality | tier matrix | [G+J] | EXISTS |
| OBJ-14 | Reproducibility | metadata | [H] | PARTIAL |
"""


@pytest.fixture
def mini_contract(tmp_path: Path) -> Path:
    p = tmp_path / "CONTRACT.md"
    p.write_text(MINI_CONTRACT_MARKDOWN, encoding="utf-8")
    return p


@pytest.fixture
def objectives_module():
    return importlib.import_module("scripts.eval.objectives_contract")


@pytest.fixture
def check_gate_module():
    return importlib.import_module("scripts.eval.check_gate")


@pytest.fixture
def sample_run_dir(tmp_path: Path) -> Path:
    """A run-dir with a valid Doc 04 + state.json that scores well."""
    run = tmp_path / "run"
    run.mkdir()
    # State with Enterprise context for OBJ-05.
    state = {
        "case_id": "case-test",
        "v2_company_context": {
            "scale": "MICRO",
            "complexity_tier": "LOW",
            "company_name": "TestCo",
        },
    }
    (run / "work").mkdir()
    (run / "work" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    # Doc 04 with proportional narrative: MICRO/LOW expects 20-80 words
    # per section. We write ~50 words per subdomain so the score is 5.
    body = " ".join(["word"] * 50)
    doc04 = f"""# Company Context Assessment

### D-01.1 Asset Inventory

{body}

### D-01.4 Data Protection

{body}

"""
    (run / "04_Company_Context_Assessment.md").write_text(doc04, encoding="utf-8")
    # Add a tag to satisfy OBJ-08.
    tagged = "# Tagged doc\n\nThis is [deterministic].\n"
    (run / "07_Structured_Compliance_Matrix.md").write_text(tagged, encoding="utf-8")
    return run


# ────────────────────────────────────────────────────────────────────
# 1. Parser extracts 14 objectives from the real contract
# ────────────────────────────────────────────────────────────────────


def test_parse_objectives_contract_extracts_14_from_real_doc():
    """The real OBJECTIVES_CONTRACT.md must yield 14 objectives.

    The contract is the single source of truth (OBJECTIVES_CONTRACT §1).
    If this test fails, the contract has been edited and the parser
    must be updated to match.
    """
    from scripts.eval.objectives_contract import (
        EXPECTED_OBJECTIVE_COUNT,
        parse_objectives_contract,
    )

    contract = REPO / "docs" / "OBJECTIVES_CONTRACT.md"
    if not contract.exists():
        pytest.skip("OBJECTIVES_CONTRACT.md not on disk; skipping real-doc parse test")
    objs = parse_objectives_contract(contract)
    assert len(objs) == EXPECTED_OBJECTIVE_COUNT, (
        f"expected {EXPECTED_OBJECTIVE_COUNT} objectives, got {len(objs)}: "
        f"{[o.id for o in objs]}"
    )


def test_parse_objectives_contract_extracts_ids_from_mini(objectives_module, mini_contract: Path):
    objs = objectives_module.parse_objectives_contract(mini_contract)
    ids = [o.id for o in objs]
    assert ids == ["OBJ-01", "OBJ-05", "OBJ-14"]


def test_parse_objectives_contract_mechanism_assignment(objectives_module, mini_contract: Path):
    """[G] -> GATE, [J] -> JUDGE, [H] -> HUMAN, [G+J] -> GATE (default)."""
    objs = objectives_module.parse_objectives_contract(mini_contract)
    by_id = {o.id: o for o in objs}
    assert by_id["OBJ-01"].mechanism == objectives_module.Mechanism.GATE
    assert by_id["OBJ-05"].mechanism == objectives_module.Mechanism.GATE  # G+J defaults to G
    assert by_id["OBJ-14"].mechanism == objectives_module.Mechanism.HUMAN


def test_parse_objectives_contract_missing_file(objectives_module, tmp_path: Path):
    objs = objectives_module.parse_objectives_contract(tmp_path / "no_such.md")
    assert objs == []


# ────────────────────────────────────────────────────────────────────
# 2. Missing gate: warn but do not fail in non-strict mode
# ────────────────────────────────────────────────────────────────────


def test_missing_gate_warns_but_does_not_fail_in_non_strict(
    check_gate_module, mini_contract: Path, sample_run_dir: Path, capsys
):
    """OBJ-01 has no cell → MISSING_GATE; non-strict mode should still exit 0."""
    exit_code = check_gate_module.run_scorecard_check(
        sample_run_dir,
        contract_path=mini_contract,
        strict=False,
    )
    out = capsys.readouterr().out
    assert "MISSING_GATE" in out or "MISSING" in out
    # No [G] failure → exit 0 (OBJ-05 might pass; OBJ-01 is missing but
    # missing gates do not fail in non-strict).
    assert exit_code == 0, f"expected exit 0 in non-strict, got {exit_code}"


# ────────────────────────────────────────────────────────────────────
# 3. Strict mode: [G] failure exits non-zero
# ────────────────────────────────────────────────────────────────────


def test_strict_mode_fails_on_g_failure(
    check_gate_module, mini_contract: Path, tmp_path: Path, capsys
):
    """A run-dir with an invented statistic → OBJ-09 FAIL → strict exit 1."""
    run = tmp_path / "run-bad"
    run.mkdir()
    (run / "04_Company_Context_Assessment.md").write_text(
        "# Doc\n\nWe reduced risk by 75%.\n",
        encoding="utf-8",
    )
    # Use a contract that has OBJ-09 [G] so the fabrication check fires.
    contract_text = MINI_CONTRACT_MARKDOWN + "\n| OBJ-09 | No fabrication | ref gate | [G] | PARTIAL |\n"
    contract = tmp_path / "CONTRACT.md"
    contract.write_text(contract_text, encoding="utf-8")

    exit_code = check_gate_module.run_scorecard_check(
        run,
        contract_path=contract,
        strict=True,
    )
    out = capsys.readouterr().out
    assert "FAIL" in out or exit_code != 0
    assert exit_code == 1, f"expected exit 1 for [G] failure in strict, got {exit_code}"


# ────────────────────────────────────────────────────────────────────
# 4. Regression against baseline → exit 2
# ────────────────────────────────────────────────────────────────────


def test_regression_against_baseline_triggers_exit_2(
    check_gate_module, objectives_module, mini_contract: Path, sample_run_dir: Path, capsys
):
    """Baseline says PASS for OBJ-05; current run has FAIL → exit 2 in strict."""
    # Build a baseline where OBJ-05 PASSes.
    baseline = objectives_module.Scorecard(
        contract_path=str(mini_contract),
        case_id="case-baseline",
        run_id="baseline-run",
    )
    # OBJ-05 in the mini contract is [G+J]; we manufacture a PASS result.
    baseline.results = [
        objectives_module.ObjectiveResult(
            objective_id="OBJ-01",
            title="Company grounding",
            mechanism=objectives_module.Mechanism.GATE,
            status=objectives_module.CellStatus.MISSING_GATE,
        ),
        objectives_module.ObjectiveResult(
            objective_id="OBJ-05",
            title="Proportionality",
            mechanism=objectives_module.Mechanism.GATE,
            status=objectives_module.CellStatus.PASS,
        ),
        objectives_module.ObjectiveResult(
            objective_id="OBJ-14",
            title="Reproducibility",
            mechanism=objectives_module.Mechanism.HUMAN,
            status=objectives_module.CellStatus.SKIPPED,
        ),
    ]
    baseline_path = sample_run_dir.parent / "baseline.json"
    objectives_module.save_baseline(baseline, baseline_path)

    # Now run a degraded version: tiny narrative that scores 1 → FAIL.
    sample_run_dir.joinpath("04_Company_Context_Assessment.md").write_text(
        "# Tiny doc\n\nNothing.\n",
        encoding="utf-8",
    )

    exit_code = check_gate_module.run_scorecard_check(
        sample_run_dir,
        contract_path=mini_contract,
        strict=True,
        baseline_path=baseline_path,
    )
    out = capsys.readouterr().out
    assert "regression" in out.lower(), f"expected regression notice in output, got:\n{out}"
    assert exit_code == 2, f"expected exit 2 for regression, got {exit_code}"


def test_no_regression_when_status_matches_or_improves(
    check_gate_module, objectives_module, mini_contract: Path, sample_run_dir: Path, capsys
):
    """If current run matches or improves the baseline, no regression is reported."""
    baseline = objectives_module.Scorecard(
        contract_path=str(mini_contract),
        case_id="case-baseline",
    )
    baseline.results = [
        objectives_module.ObjectiveResult(
            objective_id="OBJ-01",
            title="Company grounding",
            mechanism=objectives_module.Mechanism.GATE,
            status=objectives_module.CellStatus.MISSING_GATE,
        ),
        objectives_module.ObjectiveResult(
            objective_id="OBJ-05",
            title="Proportionality",
            mechanism=objectives_module.Mechanism.GATE,
            status=objectives_module.CellStatus.FAIL,  # baseline FAIL
        ),
        objectives_module.ObjectiveResult(
            objective_id="OBJ-14",
            title="Reproducibility",
            mechanism=objectives_module.Mechanism.HUMAN,
            status=objectives_module.CellStatus.SKIPPED,
        ),
    ]
    baseline_path = sample_run_dir.parent / "baseline.json"
    objectives_module.save_baseline(baseline, baseline_path)

    # Current run improves OBJ-05 to PASS — not a regression.
    # Use the same proportional doc as the good sample_run_dir.
    sample_run_dir.joinpath("04_Company_Context_Assessment.md").write_text(
        """# Doc

### D-01.1 Asset Inventory

""" + ("word " * 50) + """

### D-01.4 Data Protection

""" + ("word " * 50) + """

""",
        encoding="utf-8",
    )

    exit_code = check_gate_module.run_scorecard_check(
        sample_run_dir,
        contract_path=mini_contract,
        strict=True,
        baseline_path=baseline_path,
    )
    out = capsys.readouterr().out
    assert "0 regressions" in out, f"expected no regressions, got:\n{out}"
    assert exit_code == 0, f"expected exit 0 (improvement, not regression), got {exit_code}"


# ────────────────────────────────────────────────────────────────────
# 5. --capture-baseline saves and returns 0
# ────────────────────────────────────────────────────────────────────


def test_capture_baseline_writes_json_and_returns_zero(
    check_gate_module, mini_contract: Path, sample_run_dir: Path, capsys
):
    baseline_path = sample_run_dir.parent / "captured_baseline.json"
    exit_code = check_gate_module.run_scorecard_check(
        sample_run_dir,
        contract_path=mini_contract,
        strict=True,  # even in strict, capture-baseline returns 0
        capture_baseline_path=baseline_path,
    )
    assert exit_code == 0, f"capture-baseline must return 0, got {exit_code}"
    assert baseline_path.exists()
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert "results" in data
    assert "timestamp" in data
    # Scorecard contains the 3 objectives from the mini contract.
    assert len(data["results"]) == 3


# ────────────────────────────────────────────────────────────────────
# 6. --baseline and --capture-baseline are mutually exclusive
# ────────────────────────────────────────────────────────────────────


def test_baseline_and_capture_baseline_mutually_exclusive(
    check_gate_module, mini_contract: Path, sample_run_dir: Path, capsys
):
    exit_code = check_gate_module.run_scorecard_check(
        sample_run_dir,
        contract_path=mini_contract,
        strict=True,
        baseline_path=sample_run_dir / "a.json",
        capture_baseline_path=sample_run_dir / "b.json",
    )
    assert exit_code == 1, f"expected exit 1 for mutual-exclusion violation, got {exit_code}"
    err = capsys.readouterr().err
    assert "mutually exclusive" in err.lower()


# ────────────────────────────────────────────────────────────────────
# 7. Scorecard round-trip
# ────────────────────────────────────────────────────────────────────


def test_scorecard_round_trip(objectives_module):
    s = objectives_module.Scorecard(
        contract_path="x.md",
        case_id="c1",
        run_id="r1",
    )
    s.results = [
        objectives_module.ObjectiveResult(
            objective_id="OBJ-01",
            title="Company grounding",
            mechanism=objectives_module.Mechanism.GATE,
            status=objectives_module.CellStatus.PASS,
            measured="10/10",
            detail="ok",
            evidence={"k": "v"},
        ),
    ]
    data = s.to_dict()
    s2 = objectives_module.Scorecard.from_dict(data)
    assert s2.contract_path == s.contract_path
    assert s2.case_id == s.case_id
    assert s2.run_id == s.run_id
    assert len(s2.results) == 1
    r = s2.results[0]
    assert r.objective_id == "OBJ-01"
    assert r.mechanism == objectives_module.Mechanism.GATE
    assert r.status == objectives_module.CellStatus.PASS
    assert r.measured == "10/10"
    assert r.evidence == {"k": "v"}


def test_scorecard_to_markdown_contains_all_objectives(objectives_module):
    s = objectives_module.Scorecard(contract_path="x.md")
    s.results = [
        objectives_module.ObjectiveResult(
            objective_id="OBJ-01",
            title="Company grounding",
            mechanism=objectives_module.Mechanism.GATE,
            status=objectives_module.CellStatus.PASS,
            measured="10/10",
        ),
        objectives_module.ObjectiveResult(
            objective_id="OBJ-05",
            title="Proportionality",
            mechanism=objectives_module.Mechanism.JUDGE,
            status=objectives_module.CellStatus.FAIL,
            measured="1/5",
        ),
    ]
    md = s.to_markdown()
    assert "# AEGIS Phase 1 Scorecard" in md
    assert "OBJ-01" in md
    assert "OBJ-05" in md
    assert "[G]" in md
    assert "[J]" in md
    assert "PASS" in md
    assert "FAIL" in md


# ────────────────────────────────────────────────────────────────────
# 8. CLI smoke: invoking check_gate.py via subprocess
# ────────────────────────────────────────────────────────────────────


def test_cli_capture_baseline_subprocess(
    mini_contract: Path, sample_run_dir: Path
):
    """The CLI must accept --capture-baseline and write the JSON."""
    baseline = sample_run_dir.parent / "cli_baseline.json"
    cmd = [
        sys.executable,
        "-m",
        "scripts.eval.check_gate",
        "--run-dir",
        str(sample_run_dir),
        "--contract",
        str(mini_contract),
        "--capture-baseline",
        str(baseline),
    ]
    env = {**__import__("os").environ, "PYTHONPATH": f"{REPO}:{REPO / 'src'}"}
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env, cwd=str(REPO),
    )
    assert result.returncode == 0, f"CLI failed: rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    assert baseline.exists()
    data = json.loads(baseline.read_text(encoding="utf-8"))
    assert "results" in data
    assert len(data["results"]) == 3  # the 3 OBJ-NN in the mini contract


def test_cli_legacy_mode_still_works(sample_run_dir: Path):
    """Without --contract, the legacy check_run path is exercised (rc 0 or 1 OK)."""
    cmd = [
        sys.executable,
        "-m",
        "scripts.eval.check_gate",
        "--run-dir",
        str(sample_run_dir),
        "--no-check-coverage",
    ]
    env = {**__import__("os").environ, "PYTHONPATH": f"{REPO}:{REPO / 'src'}"}
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env, cwd=str(REPO),
    )
    # Legacy mode emits the RefGate / state checks; we only assert it
    # runs (rc 0 or 1) and prints the expected header.
    assert result.returncode in (0, 1), (
        f"rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "Checking RefGate assertions" in result.stdout
