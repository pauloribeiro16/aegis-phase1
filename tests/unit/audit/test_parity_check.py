"""Unit tests for scripts.audit.parity_check (CORR-035 c7 pilot).

These tests pin the parity invariants:
  - 38 sub-domains exist in source MD and preproc JSON (DA + Deep)
  - For each sub-domain, raw_md is verbatim the source MD body
  - For each sub-domain, the extracted fields match the source
  - No HIGH or CRITICAL findings are tolerated
  - INFO findings are tolerated (intentional parser mitigations)

Parametrized over 38 sub-domains × 2 sides = 76 test cases.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
METH_ROOT = Path("/home/epmq-cyber/Área de Trabalho/projects/Methodology-main")
METH_CROSSREG = METH_ROOT / "00_METHODOLOGY" / "PREPROCESSING" / "CrossRegulation"
PREPROC_CROSSREG = REPO_ROOT / "preproc_out" / "2-crossregulation"

sys.path.insert(0, str(SRC_DIR))
from scripts.audit.parity_check import (  # noqa: E402
    check_strict,
    check_structural_da,
    check_structural_deep,
    Finding,
    main,
)

# All 38 sub-domains (D-01.1 .. D-10.3) from the preproc_dir
SUBDOMAINS: list[tuple[str, str]] = []
for sub_path in sorted(PREPROC_CROSSREG.glob("DomainAnalysis/*/D-*.json")):
    SUBDOMAINS.append((sub_path.stem, sub_path.parent.name))


# ── Sanity: 38 sub-domains exist ─────────────────────────────────────


def test_38_subdomains_discovered() -> None:
    """Sanity: exactly 38 sub-domains found in preproc_dir."""
    if not PREPROC_CROSSREG.exists():
        pytest.skip(f"{PREPROC_CROSSREG} not present")
    assert len(SUBDOMAINS) == 38, f"expected 38 sub-domains, got {len(SUBDOMAINS)}"


def test_source_and_preproc_have_same_subdomains() -> None:
    """Sanity: 38 source MDs (DA + Deep) match 38 preproc JSONs."""
    if not (METH_CROSSREG / "DomainAnalysis").exists():
        pytest.skip(f"{METH_CROSSREG} not present")
    da_src = sorted(
        p.stem
        for p in (METH_CROSSREG / "DomainAnalysis").glob("*/*.md")
    )
    deep_src = sorted(
        p.stem
        for p in (METH_CROSSREG / "DeepAnalysis").glob("*/*.md")
    )
    da_pre = sorted(p.stem for p in (PREPROC_CROSSREG / "DomainAnalysis").glob("*/*.json"))
    deep_pre = sorted(p.stem for p in (PREPROC_CROSSREG / "DeepAnalysis").glob("*/*.json"))
    assert da_src == da_pre, f"DA source {len(da_src)} != preproc {len(da_pre)}"
    assert deep_src == deep_pre, f"Deep source {len(deep_src)} != preproc {len(deep_pre)}"
    assert da_src == deep_src, "DA and Deep sub-domain IDs differ"


# ── Parametrized: no HIGH or CRITICAL per sub-domain per side ──────────


@pytest.mark.skipif(
    not (METH_CROSSREG / "DomainAnalysis").exists(),
    reason="source MDs not present",
)
@pytest.mark.parametrize(
    "sub,macro",
    SUBDOMAINS,
    ids=lambda v: v if isinstance(v, str) else f"{v[0]}_{v[1]}",
)
def test_no_high_or_critical_in_da(sub: str, macro: str) -> None:
    """Per sub-domain DA: no HIGH or CRITICAL findings tolerated."""
    src_md = METH_CROSSREG / "DomainAnalysis" / macro / f"{sub}.md"
    preproc = PREPROC_CROSSREG / "DomainAnalysis" / macro / f"{sub}.json"
    if not src_md.exists() or not preproc.exists():
        pytest.skip(f"missing {src_md} or {preproc}")
    findings: list[Finding] = []
    data = check_strict(f"DA/{sub}", src_md, preproc, findings)
    check_structural_da(f"DA/{sub}", src_md, data, findings)
    bad = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]
    assert not bad, (
        f"{sub} (DA): {len(bad)} HIGH/CRITICAL findings:\n"
        + "\n".join(f"  {f.code}: {f.msg[:120]}" for f in bad)
    )


@pytest.mark.skipif(
    not (METH_CROSSREG / "DeepAnalysis").exists(),
    reason="source MDs not present",
)
@pytest.mark.parametrize(
    "sub,macro",
    SUBDOMAINS,
    ids=lambda v: v if isinstance(v, str) else f"{v[0]}_{v[1]}",
)
def test_no_high_or_critical_in_deep(sub: str, macro: str) -> None:
    """Per sub-domain Deep: no HIGH or CRITICAL findings tolerated."""
    src_md = METH_CROSSREG / "DeepAnalysis" / macro / f"{sub}.md"
    preproc = PREPROC_CROSSREG / "DeepAnalysis" / macro / f"{sub}.json"
    if not src_md.exists() or not preproc.exists():
        pytest.skip(f"missing {src_md} or {preproc}")
    findings: list[Finding] = []
    data = check_strict(f"Deep/{sub}", src_md, preproc, findings)
    check_structural_deep(f"Deep/{sub}", src_md, data, findings)
    bad = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]
    assert not bad, (
        f"{sub} (Deep): {len(bad)} HIGH/CRITICAL findings:\n"
        + "\n".join(f"  {f.code}: {f.msg[:120]}" for f in bad)
    )


# ── Aggregate: full audit via subprocess returns 0 (no CRITICAL/HIGH) ─


def test_full_audit_no_critical_or_high() -> None:
    """End-to-end: full parity audit returns no CRITICAL or HIGH findings.

    INFO findings (parser auto-corrections, partial participants) are
    tolerated. This pins the contract: MD ↔ JSON parity is preserved
    across all 38 sub-domains × 2 sides, modulo documented mitigations.
    """
    if not PREPROC_CROSSREG.exists():
        pytest.skip(f"{PREPROC_CROSSREG} not present")
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.audit.parity_check", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC_DIR), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode in (0, 1), f"audit crashed: {proc.stderr}"
    payload = json.loads(proc.stdout)
    by_sev = payload.get("by_severity", {})
    assert by_sev.get("CRITICAL", 0) == 0, f"CRITICAL findings: {payload['findings']}"
    assert by_sev.get("HIGH", 0) == 0, f"HIGH findings: {payload['findings']}"
    # INFO is tolerated; record for visibility
    info_count = by_sev.get("INFO", 0)
    print(f"\n  INFO findings (tolerated): {info_count}")
