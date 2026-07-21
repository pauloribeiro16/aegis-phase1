"""Unit tests for scripts.audit.audit_da_outputs (CORR-035 commit 1).

Tests are organized by severity:
  - CRITICAL/HIGH detection (5 tests)
  - MEDIUM detection (4 tests)
  - index.json audit (2 tests)
  - regression parametrized over 38 DA files (2 tests)
  - end-to-end CLI (1 test)

Total: 14+ named tests + parametrized expansion = 30+ test cases.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
DA_DIR = REPO_ROOT / "preproc_out" / "crossregulation" / "DomainAnalysis"
SCRIPTS_DIR = REPO_ROOT / "scripts" / "audit"
sys.path.insert(0, str(SRC_DIR))

from scripts.audit.audit_da_outputs import (  # noqa: E402
    Finding,
    VALID_REGS,
    VALID_CLASSIFICATIONS,
    VALID_VERDICTS,
    audit_da_file,
    audit_index,
)

# Helper to run the audit script as a subprocess (end-to-end)
PY = sys.executable


def _run_audit(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, "-m", "scripts.audit.audit_da_outputs", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC_DIR), "PATH": "/usr/bin:/bin"},
    )


# ─── CRITICAL/HIGH: envelope + parse + invariants ─────────────────────


def test_envelope_missing_field_is_critical(tmp_path: Path) -> None:
    """CRITICAL: missing envelope field detected."""
    bad = {"schema_version": "1.0", "doc_id": "X"}  # 25 missing fields
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    findings = audit_da_file(p)
    critical = [f for f in findings if f.severity == "CRITICAL" and f.code == "ENVELOPE_MISSING"]
    assert len(critical) >= 20  # at least 20 of the 25 envelope fields are missing


def test_pair_count_mismatch_is_critical(tmp_path: Path) -> None:
    """CRITICAL: pair_count != len(pairs)."""
    data = {
        "schema_version": "1.0",
        "doc_id": "X",
        "sub_kind": "domain_analysis",
        "macro_domain": "D-04 Incident Response",
        "sub_domain": "D-04.1",
        "title": "t",
        "status": "DRAFT",
        "frontmatter": {},
        "title_h3": "t",
        "participants_meta": [],
        "participants_table": [],
        "participant_count": 0,
        "participants": [],
        "participants_absent": [],
        "participants_note": "",
        "pairs": [{"reg_a": "GDPR", "reg_b": "NIS2", "classification": "Contradictory"}],
        "pair_count": 5,  # WRONG
        "classification_distribution": {},
        "downstream_implication_top": "",
        "sr_cross_validation": "",
        "emergent_tensions": [],
        "sr_cross_references": [],
        "sr_cross_reference_count": 0,
        "raw_md": "",
        "raw_md_kept_reason": "x",
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    codes = [f.code for f in findings]
    assert "PAIR_COUNT_MISMATCH" in codes


def test_invalid_classification_is_high(tmp_path: Path) -> None:
    """HIGH: classification outside enum."""
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "doc_id": "X",
        "sub_kind": "domain_analysis",
        "macro_domain": "D-04",
        "sub_domain": "D-04.1",
        "title": "t",
        "status": "DRAFT",
        "frontmatter": {},
        "title_h3": "t",
        "participants_meta": [],
        "participants_table": [],
        "participant_count": 0,
        "participants": [],
        "participants_absent": [],
        "participants_note": "",
        "pairs": [
            {
                "reg_a": "GDPR",
                "reg_b": "NIS2",
                "classification": "NotARealClass",  # WRONG
                "why": "x",
                "why_qualifier": "",
                "why_note": "x",
                "oj_quotes": [],
                "oj_quotes_verbatim": [],
                "comparison_sections": [],
                "scope_disjoint_test": {"verdict": "Y", "note": ""},
                "downstream_implication": "",
                "p0_notes": [],
                "sr_ids_per_pair": [],
                "table_block_raw": "",
                "block_text_raw": "",
            }
        ],
        "pair_count": 1,
        "classification_distribution": {"NotARealClass": 1},
        "downstream_implication_top": "",
        "sr_cross_validation": "",
        "emergent_tensions": [],
        "sr_cross_references": [],
        "sr_cross_reference_count": 0,
        "raw_md": "",
        "raw_md_kept_reason": "x",
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    assert any(
        f.severity == "HIGH" and f.code == "INVALID_CLASSIFICATION" for f in findings
    )


def test_hr_leak_in_downstream_implication(tmp_path: Path) -> None:
    """HIGH: downstream_implication_top ends with leaked '---'."""
    data = _minimal_da(
        di_top="Some text about phase 2.\n\n---",
        pairs=[],
    )
    p = tmp_path / "leak.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    assert any(
        f.severity == "HIGH" and f.code == "DOWNSTREAM_IMPLICATION_TOP_HR_LEAK"
        for f in findings
    )


def test_h2_leak_in_downstream_implication(tmp_path: Path) -> None:
    """HIGH: downstream_implication_top ends with leaked next-section H2."""
    data = _minimal_da(
        di_top="Some text about phase 2.\n\n---\n\n## D-02 Vulnerability Management",
        pairs=[],
    )
    p = tmp_path / "leak.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    assert any(
        f.severity == "HIGH" and f.code == "DOWNSTREAM_IMPLICATION_TOP_H2_LEAK"
        for f in findings
    )


# ─── MEDIUM detection ─────────────────────────────────────────────────


def test_why_equals_note_is_medium(tmp_path: Path) -> None:
    """MEDIUM: why == why_note (the bug-B pattern)."""
    data = _minimal_da(
        pairs=[
            {
                "reg_a": "GDPR",
                "reg_b": "NIS2",
                "classification": "Contradictory",
                "why": "Same text",
                "why_qualifier": "mild",
                "why_note": "Same text",  # same as why
                "oj_quotes": [],
                "oj_quotes_verbatim": [],
                "comparison_sections": [],
                "scope_disjoint_test": {"verdict": "Conditional", "note": "mild"},
                "downstream_implication": "",
                "p0_notes": [],
                "sr_ids_per_pair": [],
                "table_block_raw": "",
                "block_text_raw": "",
            }
        ],
    )
    p = tmp_path / "x.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    assert any(f.code == "WHY_EQUALS_NOTE" for f in findings)


def test_scope_axis_populated_is_medium(tmp_path: Path) -> None:
    """MEDIUM: scope axis unexpectedly populated."""
    data = _minimal_da(
        pairs=[
            {
                "reg_a": "GDPR",
                "reg_b": "NIS2",
                "classification": "Contradictory",
                "why": "x",
                "why_qualifier": "",
                "why_note": "y",
                "oj_quotes": [],
                "oj_quotes_verbatim": [],
                "comparison_sections": [
                    {"axis": "obligation", "reg_a_value": "a", "reg_b_value": "b"},
                    {"axis": "scope", "reg_a_value": "SHOULD BE EMPTY", "reg_b_value": ""},
                ],
                "scope_disjoint_test": {"verdict": "Conditional", "note": ""},
                "downstream_implication": "",
                "p0_notes": [],
                "sr_ids_per_pair": [],
                "table_block_raw": "",
                "block_text_raw": "",
            }
        ],
    )
    p = tmp_path / "x.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    assert any(f.code == "SCOPE_AXIS_POPULATED" for f in findings)


def test_macro_sub_mismatch_is_medium(tmp_path: Path) -> None:
    """MEDIUM: macro_domain != prefix of sub_domain."""
    data = _minimal_da(
        macro_domain="D-09 Governance & Documentation",
        sub_domain="D-10.1 Continuous Security Monitoring",
    )
    p = tmp_path / "x.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    assert any(f.code == "MACRO_SUB_MISMATCH" for f in findings)


def test_sr_ids_empty_for_known_class_is_medium(tmp_path: Path) -> None:
    """MEDIUM: sr_ids_per_pair empty but classification is known."""
    data = _minimal_da(
        pairs=[
            {
                "reg_a": "GDPR",
                "reg_b": "NIS2",
                "classification": "Contradictory",
                "why": "x",
                "why_qualifier": "",
                "why_note": "y",
                "oj_quotes": [],
                "oj_quotes_verbatim": [],
                "comparison_sections": [],
                "scope_disjoint_test": {"verdict": "Conditional", "note": ""},
                "downstream_implication": "",
                "p0_notes": [],
                "sr_ids_per_pair": [],  # empty
                "table_block_raw": "",
                "block_text_raw": "",
            }
        ],
    )
    p = tmp_path / "x.json"
    p.write_text(json.dumps(data))
    findings = audit_da_file(p)
    assert any(f.code == "SR_IDS_EMPTY_FOR_KNOWN_CLASS" for f in findings)


# ─── index.json audit ────────────────────────────────────────────────


def test_index_missing_entry_detected(tmp_path: Path) -> None:
    """MEDIUM: file exists on disk but not listed in index.json."""
    # Create a file under tmp_path
    sub = tmp_path / "D-01_Test"
    sub.mkdir()
    (sub / "D-01.1.json").write_text("{}")
    # Create a minimal index.json that does NOT list D-01.1
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps({"domains": [{"path": "D-01_Test/D-01.99.json"}]}))
    findings = audit_index(idx)
    assert any(f.code == "INDEX_MISSING_ENTRY" for f in findings)


def test_index_extra_entry_detected(tmp_path: Path) -> None:
    """LOW: index.json lists a file that doesn't exist on disk."""
    idx = tmp_path / "index.json"
    idx.write_text(
        json.dumps({"domains": [{"path": "D-01_Test/D-01.99.json"}]})
    )
    findings = audit_index(idx)
    assert any(f.code == "INDEX_EXTRA_ENTRY" for f in findings)


# ─── Regression: real DA files baseline ─────────────────────────────


def test_baseline_38_da_files_scanned() -> None:
    """Sanity: the script scans exactly 38 D-*.json files."""
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    json_files = list(DA_DIR.glob("**/D-*.json"))
    assert len(json_files) == 38


def test_baseline_has_known_high_findings() -> None:
    """Sanity: at baseline, the script reports >= 37 HIGH findings.

    After CORR-035 commits 2-6 are applied, this should drop to 0.
    This test pins the baseline for regression detection.
    """
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    proc = _run_audit("--json")
    if proc.returncode not in (0, 1):
        pytest.fail(f"audit script failed: {proc.stderr}")
    payload = json.loads(proc.stdout)
    # Pre-fix: at least 37 HIGH (the h4 leak). This is the baseline.
    assert payload["by_severity"].get("HIGH", 0) >= 37


# ─── End-to-end CLI ─────────────────────────────────────────────────


def test_cli_runs_and_returns_json() -> None:
    """End-to-end: the CLI runs and returns a JSON payload."""
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    proc = _run_audit("--json")
    assert proc.returncode in (0, 1)  # 0 = no findings, 1 = findings present
    payload = json.loads(proc.stdout)
    assert "files_scanned" in payload
    assert payload["files_scanned"] == 38
    assert "findings" in payload
    assert "by_severity" in payload


def test_cli_only_filter() -> None:
    """End-to-end: --only HIGH filters out lower severities."""
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    proc = _run_audit("--only", "HIGH", "--json")
    payload = json.loads(proc.stdout)
    severities = {f["severity"] for f in payload["findings"]}
    # Only HIGH or CRITICAL should appear (CRITICAL is also shown)
    assert severities.issubset({"CRITICAL", "HIGH"})


# ─── Helpers ──────────────────────────────────────────────────────────


def _minimal_da(
    *,
    macro_domain: str = "D-04 Incident Response",
    sub_domain: str = "D-04.1",
    di_top: str = "",
    pairs: list[dict] | None = None,
) -> dict[str, Any]:
    """Build a minimal but valid DA envelope for negative tests."""
    return {
        "schema_version": "1.0",
        "source": "/tmp/test.md",
        "doc_id": f"AEGIS-PREPROC-CRDA-{sub_domain}",
        "sub_kind": "domain_analysis",
        "macro_domain": macro_domain,
        "sub_domain": sub_domain,
        "title": f"{sub_domain} — Test",
        "status": "DRAFT",
        "frontmatter": {},
        "title_h3": sub_domain,
        "participants_meta": [],
        "participants_table": [],
        "participant_count": 0,
        "participants": [],
        "participants_absent": [],
        "participants_note": "",
        "pairs": pairs or [],
        "pair_count": len(pairs or []),
        "classification_distribution": {},
        "downstream_implication_top": di_top,
        "sr_cross_validation": "",
        "emergent_tensions": [],
        "sr_cross_references": [],
        "sr_cross_reference_count": 0,
        "raw_md": "",
        "raw_md_kept_reason": "test",
    }


# Parametrized: every real DA file must parse without CRITICAL ────────


@pytest.mark.skipif(not DA_DIR.exists(), reason="DA_DIR not present")
@pytest.mark.parametrize(
    "da_file",
    sorted(DA_DIR.glob("**/D-*.json")),
    ids=lambda p: p.relative_to(DA_DIR).as_posix(),
)
def test_no_critical_in_real_da_file(da_file: Path) -> None:
    """No CRITICAL findings in any real DA file at baseline (already true)."""
    findings = audit_da_file(da_file)
    critical = [f for f in findings if f.severity == "CRITICAL"]
    assert not critical, (
        f"{da_file.name}: unexpected CRITICAL findings: "
        + ", ".join(f"{f.code}({f.msg[:60]})" for f in critical)
    )
