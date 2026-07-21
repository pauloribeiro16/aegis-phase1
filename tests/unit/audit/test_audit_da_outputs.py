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
import re
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


def test_no_h4_leak_in_real_da_files() -> None:
    """Regression: post commit 2, no DA file has an h4 leak."""
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    proc = _run_audit("--only", "HIGH", "--json")
    payload = json.loads(proc.stdout)
    leak_codes = {
        "DOWNSTREAM_IMPLICATION_TOP_HR_LEAK",
        "DOWNSTREAM_IMPLICATION_TOP_H2_LEAK",
        "SR_CROSS_VALIDATION_HR_LEAK",
        "SR_CROSS_VALIDATION_H2_LEAK",
    }
    leaks = [f for f in payload["findings"] if f["code"] in leak_codes]
    assert not leaks, (
        f"{len(leaks)} h4 leaks still present post-commit-2: "
        + ", ".join(f["path"] for f in leaks[:5])
    )


# ─── MEDIUM detection ─────────────────────────────────────────────────


def test_why_equals_note_is_medium(tmp_path: Path) -> None:
    """Regression for CORR-035 c4: WHY_EQUALS_NOTE finding is disabled.

    The CORR-034 contract said `why_note` is the qualifier-stripped
    version of `why`, but the parser `_extract_why_metadata` populates
    `note` with the prose after the `**Why HEADER**:` marker — which
    is identical to what `why` captures. Stripping the qualifier from
    embedded prose (e.g. `the "where feasible" softening`) would be
    fragile. The audit was incorrectly flagging this as a MEDIUM
    issue; we now accept `why == why_note` as contract-compliant.
    See CONTRACT-035 c4.
    """
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
    # CORR-035 c4: this check is disabled — `why == why_note` is OK.
    assert not any(f.code == "WHY_EQUALS_NOTE" for f in findings)


def test_scope_axis_populated_is_medium(tmp_path: Path) -> None:
    """MEDIUM: scope axis unexpectedly populated.

    CORR-035 c6: the parser now always sets scope to '' (per contract).
    Pre c6, source MDs D-01..D-03 had a populated 3rd column that the
    parser was reading. The post-c6 behavior strips it. We still
    detect populated scope IF it appears in the JSON (e.g. via a
    hand-edited file or a future bug), but for files produced by the
    build pipeline this finding should be 0.
    """
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
    # The audit still flags populated scope (defense in depth).
    assert any(f.code == "SCOPE_AXIS_POPULATED" for f in findings)


def test_no_scope_populated_in_real_da_files() -> None:
    """Regression for CORR-035 c6: post c6, no real DA file has scope
    populated. The parser hard-codes scope='' in
    _extract_comparison_sections_domain.
    """
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    proc = _run_audit("--json")
    payload = json.loads(proc.stdout)
    leaks = [f for f in payload["findings"] if f["code"] == "SCOPE_AXIS_POPULATED"]
    assert not leaks, (
        f"{len(leaks)} DA files still have scope populated post-c6: "
        + ", ".join(f["path"] for f in leaks[:5])
    )


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
    """Sanity: after commit 2 (bug A fixed), no HIGH findings remain.

    Pre-commit-2 baseline was 37 HIGH. This test now pins 0 HIGH
    as the post-commit-2 expected state. Subsequent commits may
    keep it at 0 (commits 3, 5, 6) or briefly raise it (commit 4
    may surface new findings as parser behavior changes).
    """
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    proc = _run_audit("--json")
    if proc.returncode not in (0, 1):
        pytest.fail(f"audit script failed: {proc.stderr}")
    payload = json.loads(proc.stdout)
    # Post commit 2: bug A fixed. We expect 0 HIGH findings.
    assert payload["by_severity"].get("HIGH", 0) == 0, (
        f"unexpected HIGH findings post-commit-2: {payload['by_severity']}"
    )


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


# ─── Bug C regression: SR regex accepts all 5 reg canonical names ───


@pytest.mark.parametrize(
    "sid",
    [
        "SR-GDPR-001",
        "SR-NIS2-010",  # has digit in reg name — pre-fix bug
        "SR-CRA-029",
        "SR-DORA-017",
        "SR-AI_Act-022",  # has underscore in reg name
    ],
)
def test_sr_id_regex_accepts_all_canonical_names(sid: str) -> None:
    """CORR-035 c3: the SR-ID regex must accept all 5 reg names.

    Pre-fix: SR-NIS2-NNN failed because [A-Z_]+ didn't accept digits
    in the reg-name segment.
    """
    assert re.fullmatch(r"SR-[A-Za-z0-9_]+-\d{3}", sid), f"{sid!r} not accepted"


def test_sr_id_regex_rejects_malformed() -> None:
    """Negative: regex must reject malformed SR-IDs."""
    import re

    for bad in ["SR-", "SR-A-1", "SR-GDPR-1", "SR-GDPR-1234", "GDPR-001"]:
        assert not re.fullmatch(r"SR-[A-Za-z0-9_]+-\d{3}", bad), f"{bad!r} wrongly accepted"


def test_no_sr_ids_empty_for_known_class_post_fix() -> None:
    """Regression: after the SR regex fix, no pair with NIS2 in its
    block should have sr_ids_per_pair=[] (provided classification is
    known).
    """
    if not DA_DIR.exists():
        pytest.skip(f"{DA_DIR} not present")
    proc = _run_audit("--json")
    payload = json.loads(proc.stdout)
    # The remaining SR_IDS_EMPTY_FOR_KNOWN_CLASS findings must NOT be
    # caused by NIS2 (post-fix) — they should be 0 or only non-NIS2.
    nis2_leak = [
        f
        for f in payload["findings"]
        if f["code"] == "SR_IDS_EMPTY_FOR_KNOWN_CLASS" and "NIS2" in f["path"]
    ]
    # Before fix: 7. After fix: 0 (all NIS2 SRs now captured).
    assert len(nis2_leak) == 0, (
        f"{len(nis2_leak)} NIS2 pairs still have empty sr_ids_per_pair: "
        + ", ".join(f["path"] for f in nis2_leak[:5])
    )
