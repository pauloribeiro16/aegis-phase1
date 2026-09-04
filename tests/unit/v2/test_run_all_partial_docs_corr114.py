"""CORR-114: Even when MAP raises MapPartialFailure, ``run_all`` must
continue to ``reduce()`` + ``generate_outputs()`` so the deterministic
documents (Doc 04/05/06/07/04a-04d/07b + xlsx) are always written to
disk — and re-raise after OUTPUT so the runner's ``MAP_ABORT_THRESHOLD``
gate still produces exit-code-2 on ≥5 failed domains.

These tests don't require an Ollama connection. They mock the four
steps (``run_phase_1b``, ``map_domains``, ``reduce``, ``generate_outputs``)
on a real ``Phase1Orchestrator`` and inject a ``MapPartialFailure`` from
``map_domains``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aegis_phase1.v2.domain.processor import MapPartialFailure
from aegis_phase1.v2.orchestrator import Phase1Orchestrator

logger = logging.getLogger(__name__)


def _orchestrator_for_test(monkeypatch):
    """Construct a Phase1Orchestrator that can be controlled without
    touching the network. ``_load_v2_catalog`` is patched to a no-op so
    the constructor doesn't try to read preproc_out.
    """
    monkeypatch.setattr(
        "aegis_phase1.v2.orchestrator.Phase1Orchestrator._load_v2_catalog",
        lambda self: None,
    )
    orch = Phase1Orchestrator(work_dir="/tmp/corr-114-test")
    # Stub out the methods we'll observe so we don't hit the network.
    return orch


def test_map_failure_still_writes_outputs(monkeypatch, tmp_path):
    """``map_domains`` raises MapPartialFailure → ``generate_outputs``
    is still called and the call sequence is load → 1B → MAP (raises)
    → REDUCE → OUTPUT.
    """
    orch = _orchestrator_for_test(monkeypatch)
    calls: list[str] = []

    def fake_load(self, case_path, regulatory_baseline_path, *, preprocessing_path=None):
        calls.append("load")

    def fake_phase_1b(self):
        calls.append("run_phase_1b")

    def fake_map(self):
        calls.append("map_domains")
        raise MapPartialFailure(
            "10 domains failed: ['D-01'..'D-10']",
            failed_domains=[f"D-{i:02d}" for i in range(1, 11)],
        )

    def fake_reduce(self):
        calls.append("reduce")

    def fake_outputs(self, output_dir):
        calls.append(f"generate_outputs:{output_dir}")
        # Simulate the doc files being written.
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "05_Regulatory_Applicability.md").write_text("# mock\n")
        (out / "Case_01_Phase1.xlsx").write_bytes(b"xlsx-mock")

    monkeypatch.setattr(Phase1Orchestrator, "load", fake_load)
    monkeypatch.setattr(Phase1Orchestrator, "run_phase_1b", fake_phase_1b)
    monkeypatch.setattr(Phase1Orchestrator, "map_domains", fake_map)
    monkeypatch.setattr(Phase1Orchestrator, "reduce", fake_reduce)
    monkeypatch.setattr(Phase1Orchestrator, "generate_outputs", fake_outputs)

    out_dir = str(tmp_path / "out")

    raised: list[MapPartialFailure] = []
    try:
        orch.run_all("cases/case1-tinytask", "/tmp/fake-baseline", output_dir=out_dir)
    except MapPartialFailure as exc:
        raised.append(exc)

    # Behaviour 1: the exception is re-raised after OUTPUT (so the
    # runner's exit-code-2 gate stays intact).
    assert len(raised) == 1, "MapPartialFailure should be re-raised"
    assert len(raised[0].failed_domains) == 10

    # Behaviour 2: REDUCE and OUTPUT both ran (this is the fix in P5/P6).
    assert "load" in calls
    assert "run_phase_1b" in calls
    assert "map_domains" in calls  # even though it raises
    assert "reduce" in calls, "reduce must run after MAP fails"
    assert f"generate_outputs:{out_dir}" in calls, (
        "generate_outputs must run after MAP fails so docs are written"
    )

    # Behaviour 3: docs were actually written.
    assert (Path(out_dir) / "05_Regulatory_Applicability.md").exists()
    assert (Path(out_dir) / "Case_01_Phase1.xlsx").exists()


def test_map_no_failure_follows_happy_path(monkeypatch, tmp_path):
    """When MAP succeeds, the control flow is unchanged: no re-raise,
    call order is load → 1B → MAP → REDUCE → OUTPUT.
    """
    orch = _orchestrator_for_test(monkeypatch)
    calls: list[str] = []

    def fake_load(self, *a, **k):
        calls.append("load")

    def fake_phase_1b(self):
        calls.append("run_phase_1b")

    def fake_map(self):
        calls.append("map_domains")

    def fake_reduce(self):
        calls.append("reduce")

    def fake_outputs(self, output_dir):
        calls.append(f"generate_outputs:{output_dir}")

    monkeypatch.setattr(Phase1Orchestrator, "load", fake_load)
    monkeypatch.setattr(Phase1Orchestrator, "run_phase_1b", fake_phase_1b)
    monkeypatch.setattr(Phase1Orchestrator, "map_domains", fake_map)
    monkeypatch.setattr(Phase1Orchestrator, "reduce", fake_reduce)
    monkeypatch.setattr(Phase1Orchestrator, "generate_outputs", fake_outputs)

    out_dir = str(tmp_path / "out")

    raised: list[Exception] = []
    try:
        orch.run_all("cases/case1-tinytask", "/tmp/fake-baseline", output_dir=out_dir)
    except Exception as exc:
        raised.append(exc)

    assert raised == [], "happy path must not raise"
    assert calls == [
        "load",
        "run_phase_1b",
        "map_domains",
        "reduce",
        f"generate_outputs:{out_dir}",
    ]


def test_map_failure_with_few_domains_does_not_re_raise(monkeypatch, tmp_path):
    """Even with 1-2 failed domains (below the threshold), OUTPUT
    still runs. Note this is handled in the runner, not the
    orchestrator — the orchestrator always re-raises whatever
    map_domains raised.
    """
    orch = _orchestrator_for_test(monkeypatch)

    def fake_load(self, *a, **k):
        pass

    def fake_phase_1b(self):
        pass

    def fake_map(self):
        raise MapPartialFailure("1 failed", failed_domains=["D-01"])

    def fake_reduce(self):
        pass

    def fake_outputs(self, output_dir):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "doc.md").write_text("# partial\n")

    monkeypatch.setattr(Phase1Orchestrator, "load", fake_load)
    monkeypatch.setattr(Phase1Orchestrator, "run_phase_1b", fake_phase_1b)
    monkeypatch.setattr(Phase1Orchestrator, "map_domains", fake_map)
    monkeypatch.setattr(Phase1Orchestrator, "reduce", fake_reduce)
    monkeypatch.setattr(Phase1Orchestrator, "generate_outputs", fake_outputs)

    out_dir = str(tmp_path / "out")

    raised = None
    try:
        orch.run_all("cases/case1-tinytask", "/tmp/fake", output_dir=out_dir)
    except MapPartialFailure as exc:
        raised = exc

    assert raised is not None  # orchestrator always re-raises
    # The runner's threshold decision is made in _main_ (separate code),
    # but the orchestrator guarantees OUTPUT ran.
    assert (Path(out_dir) / "doc.md").exists()
