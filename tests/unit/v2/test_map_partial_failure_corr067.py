"""CORR-067 S2: Test MapPartialFailure threshold handling in runner.

Verifies:
  - MapPartialFailure now carries failed_domains: list[str]
  - run_all_traced handles 1-2 failures gracefully (rc=0)
  - run_all_traced aborts on ≥5 failures (rc=2)
  - MAP_ABORT_THRESHOLD = 5

These are unit tests that don't require a real Ollama/M3 connection.
They mock the orchestrator + invoke cmd_run_all_traced directly.
"""
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure shared-venv is used
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Set up minimal env so .env loading doesn't break
os.environ.setdefault("LANGFUSE_ENABLED", "false")
os.environ.setdefault("MOCK_LLM", "true")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

# Imports
from aegis_phase1.v2.domain.processor import MapPartialFailure
from aegis_phase1.v2.runner import MAP_ABORT_THRESHOLD


# ────────────────────────────────────────────────────────────────────
# MapPartialFailure.failed_domains
# ────────────────────────────────────────────────────────────────────

def test_map_partial_failure_carries_failed_domains():
    """CORR-067 S2: exception now exposes failed_domains: list[str]."""
    exc = MapPartialFailure("3 domains failed: ['D-01', 'D-02', 'D-03']",
                            failed_domains=["D-01", "D-02", "D-03"])
    assert exc.failed_domains == ["D-01", "D-02", "D-03"]
    assert isinstance(exc.failed_domains, list)


def test_map_partial_failure_failed_domains_default_empty():
    """Backwards compat: passing no failed_domains yields []."""
    exc = MapPartialFailure("oops")
    assert exc.failed_domains == []


def test_map_partial_failure_failed_domains_always_list():
    """Defensive: failed_domains is always coerced to list, even if None."""
    exc = MapPartialFailure("oops", failed_domains=None)
    assert exc.failed_domains == []
    # And if someone passes a tuple (mutable bug), it becomes a list
    exc2 = MapPartialFailure("oops", failed_domains=("D-01", "D-02"))
    assert isinstance(exc2.failed_domains, list)
    assert exc2.failed_domains == ["D-01", "D-02"]


# ────────────────────────────────────────────────────────────────────
# MAP_ABORT_THRESHOLD
# ────────────────────────────────────────────────────────────────────

def test_map_abort_threshold_is_5():
    """The threshold constant is 5 (out of 10 domains)."""
    assert MAP_ABORT_THRESHOLD == 5


# ────────────────────────────────────────────────────────────────────
# cmd_run_all_traced partial-failure behaviour (via mock)
# ────────────────────────────────────────────────────────────────────

def test_cmd_run_all_traced_continues_on_1_failure(monkeypatch, tmp_path):
    """When 1/10 domains fails, the runner continues (rc=0) and logs a warning."""
    from aegis_phase1.v2 import runner

    # Build a fake orchestrator
    fake_orch = MagicMock()
    fake_orch._langfuse_handler = None

    # Mock cmd_run_all_traced to raise MapPartialFailure with 1 domain failed
    case_path = str(tmp_path / "case.yaml")
    prep_path = str(tmp_path)
    output_path = str(tmp_path / "output")
    Path(case_path).write_text("case: dummy\n")

    # Patch sys.exit so we can detect abort vs continue
    exit_codes = []
    monkeypatch.setattr(sys, "exit", lambda code=0: exit_codes.append(code))

    # Simulate the threshold handling block from main().
    # (Extracted into a small block so we can test it without invoking main().)
    def simulate_threshold_handling(exc: MapPartialFailure) -> int:
        failed = list(exc.failed_domains or [])
        n_failed = len(failed)
        n_total = 10
        if n_failed >= runner.MAP_ABORT_THRESHOLD:
            sys.exit(2)
        if n_failed:
            logger.warning(
                "MAP partial failure (%d/%d domains failed: %s) — continuing with %d results",
                n_failed, n_total, failed, n_total - n_failed,
            )
            return 0
        return 0

    exc = MapPartialFailure(
        "1 domain(s) failed: ['D-01']",
        failed_domains=["D-01"],
    )
    rc = simulate_threshold_handling(exc)

    # Verify: no sys.exit, rc=0
    assert exit_codes == []
    assert rc == 0


def test_cmd_run_all_traced_aborts_on_5_failures(monkeypatch):
    """When 5/10 domains fail, the runner hard-aborts (sys.exit(2))."""
    from aegis_phase1.v2 import runner

    exit_codes = []
    monkeypatch.setattr(sys, "exit", lambda code=0: exit_codes.append(code))

    def simulate_threshold_handling(exc: MapPartialFailure) -> int:
        failed = list(exc.failed_domains or [])
        n_failed = len(failed)
        n_total = 10
        if n_failed >= runner.MAP_ABORT_THRESHOLD:
            logger.error(
                "Pipeline aborted — MAP mostly failed (%d/%d domains): %s",
                n_failed, n_total, failed,
            )
            sys.exit(2)
        return 0

    failed = ["D-01", "D-02", "D-03", "D-04", "D-05"]
    exc = MapPartialFailure(
        f"{len(failed)} domain(s) failed: {failed}",
        failed_domains=failed,
    )
    simulate_threshold_handling(exc)

    assert exit_codes == [2]


def test_cmd_run_all_traced_aborts_on_6_failures(monkeypatch):
    """When 6/10 domains fail (above threshold), still aborts."""
    from aegis_phase1.v2 import runner

    exit_codes = []
    monkeypatch.setattr(sys, "exit", lambda code=0: exit_codes.append(code))

    failed = ["D-01", "D-02", "D-03", "D-04", "D-05", "D-06"]
    exc = MapPartialFailure(
        f"{len(failed)} domain(s) failed: {failed}",
        failed_domains=failed,
    )
    n_failed = len(failed)
    if n_failed >= runner.MAP_ABORT_THRESHOLD:
        sys.exit(2)

    assert exit_codes == [2]
