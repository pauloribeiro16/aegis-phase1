"""Tests for CORR-OBJ-02: zero-omission subdomain coverage in check_gate.

The coverage check is the minimal viable substrate:
  * every subdomain ID (D-XX.Y) that exists in the preproc catalogue
    must appear in at least one rendered Doc 04-07b,
  * it is a light check (no clause-level granularity) — full
    clause-level coverage is a separate, bigger task.

These tests mock the preproc catalogue via monkeypatching
``check_subdomain_coverage``'s internal helper so we don't depend on
the real preproc_out/ layout.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve()
for p in REPO.parents:
    if (p / "src" / "aegis_phase1").is_dir():
        REPO = p
        break
sys.path.insert(0, str(REPO / "src"))


@pytest.fixture
def check_gate_mod(monkeypatch):
    """Import check_gate fresh and stub out the preproc loader so we
    don't depend on the real preproc_out/ tree.
    """
    # Ensure the module is importable via the scripts package.
    sys.path.insert(0, str(REPO))
    if "scripts.eval.check_gate" in sys.modules:
        del sys.modules["scripts.eval.check_gate"]
    mod = importlib.import_module("scripts.eval.check_gate")
    return mod


def _write_doc(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_check_subdomain_coverage_all_present(check_gate_mod, tmp_path: Path, monkeypatch) -> None:
    """100% coverage when every subdomain ID is mentioned somewhere."""
    _write_doc(tmp_path / "04_Company_Context.md", "Covered: D-01.1 D-01.2 D-02.1")
    _write_doc(tmp_path / "07_Structured_Compliance.md", "Also: D-03.1 D-04.2")

    # Stub the preproc loader to return 5 subdomains; all are covered.
    def fake_load(self, preproc_root: Path | None = None) -> set[str]:
        return {"D-01.1", "D-01.2", "D-02.1", "D-03.1", "D-04.2"}

    monkeypatch.setattr(check_gate_mod, "_applicable_subdomains", fake_load)

    covered, total, _cov_set, missing = check_gate_mod.check_subdomain_coverage(
        tmp_path, preproc_root=Path("/tmp/whatever")
    )
    assert total == 5
    assert covered == 5
    assert missing == set()


def test_check_subdomain_coverage_partial(check_gate_mod, tmp_path: Path, monkeypatch) -> None:
    """Reports missing subdomains and exits non-zero when below threshold."""
    _write_doc(tmp_path / "04_Company_Context.md", "Covered: D-01.1")
    _write_doc(tmp_path / "05_Regulatory_Applicability.md", "D-02.1 mentioned")

    def fake_load(self, preproc_root: Path | None = None) -> set[str]:
        return {"D-01.1", "D-02.1", "D-03.1", "D-04.2", "D-05.5"}

    monkeypatch.setattr(check_gate_mod, "_applicable_subdomains", fake_load)

    covered, total, _cov_set, missing = check_gate_mod.check_subdomain_coverage(
        tmp_path, preproc_root=Path("/tmp/whatever")
    )
    assert total == 5
    assert covered == 2
    assert missing == {"D-03.1", "D-04.2", "D-05.5"}


def test_check_subdomain_coverage_skipped_on_empty_run(check_gate_mod, tmp_path: Path) -> None:
    """No rendered docs → skip the check (return zeros, don't fail)."""
    covered, total, _cov_set, missing = check_gate_mod.check_subdomain_coverage(
        tmp_path, preproc_root=Path("/tmp/whatever")
    )
    assert covered == 0
    assert total == 0
    assert missing == set()


def test_check_subdomain_coverage_skipped_when_catalogue_unavailable(
    check_gate_mod, tmp_path: Path, monkeypatch
) -> None:
    """If the preproc catalogue can't be loaded, skip rather than fail."""
    _write_doc(tmp_path / "04_Company_Context.md", "D-01.1 mentioned")

    def fake_load(self, preproc_root: Path | None = None) -> set[str]:
        return set()

    monkeypatch.setattr(check_gate_mod, "_applicable_subdomains", fake_load)

    covered, total, _cov_set, missing = check_gate_mod.check_subdomain_coverage(
        tmp_path, preproc_root=Path("/tmp/nonexistent")
    )
    assert total == 0
    assert missing == set()


def test_check_run_includes_coverage_check_by_default(
    check_gate_mod, tmp_path: Path, monkeypatch, capsys
) -> None:
    """`check_run` should run the coverage check unless --no-check-coverage."""
    _write_doc(tmp_path / "04_Company_Context.md", "D-01.1, D-01.2")
    # Add a fake state.json so the PENDING scan is happy
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")

    def fake_load(self, preproc_root: Path | None = None) -> set[str]:
        return {"D-01.1", "D-01.2"}

    monkeypatch.setattr(check_gate_mod, "_applicable_subdomains", fake_load)

    code = check_gate_mod.check_run(
        tmp_path,
        check_coverage=True,
        preproc_root=Path("/tmp/whatever"),
        coverage_min_pct=100.0,
    )
    out = capsys.readouterr().out
    assert "Zero-omission subdomain coverage" in out
    assert code == 0


def test_check_run_no_check_coverage_flag(check_gate_mod, tmp_path: Path, monkeypatch, capsys) -> None:
    """--no-check-coverage must skip the coverage check entirely."""
    _write_doc(tmp_path / "04_Company_Context.md", "no subdomain ids here")
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")

    def fake_load(self, preproc_root: Path | None = None) -> set[str]:
        return {"D-01.1"}

    monkeypatch.setattr(check_gate_mod, "_applicable_subdomains", fake_load)

    code = check_gate_mod.check_run(
        tmp_path,
        check_coverage=False,
        preproc_root=Path("/tmp/whatever"),
        coverage_min_pct=100.0,
    )
    out = capsys.readouterr().out
    assert "Zero-omission subdomain coverage" not in out
    assert code == 0
