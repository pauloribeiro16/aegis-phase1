"""Unit tests for the framework policy CI gate (CORR-028).

Policy: docs/NIST_CSF_2.0_ONLY.md — NIST CSF 2.0 is the SOLE control
framework. References to other frameworks (ISO 27001, SOC 2, OWASP,
CSF 1.1, etc.) are forbidden in active code paths unless annotated
with a `CORR-028` marker within ±5 lines.

NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): The framework names mentioned
in this test file (ISO 27001, SOC 2, OWASP, CSF 1.1) appear as **test
fixtures** — strings that the test uses to assert the CI gate's
behaviour. They are NOT real control-framework references; the test
file itself is part of the framework-policy enforcement suite.

Strategy: each test creates a minimal sandbox tree (NOT a copy of the
real repo) so that policy-exemption files don't pollute the test. The
sandbox contains:
  - src/some_module.py (where the test writes the file under test)
  - a CI gate script that points to the sandbox
The test asserts the gate's pass/fail behaviour.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".hooks" / "ci-frameworks.sh"


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """Create a minimal sandbox for the CI gate to scan.

    The sandbox contains only a `src/` directory with a single file that
    doesn't trigger the gate. Policy-exemption files are NOT present so
    the test exercises the strict checking path.
    """
    sandbox = tmp_path / "sandbox"
    (sandbox / "src").mkdir(parents=True)
    # Add a single clean file so the scan has something to look at
    (sandbox / "src" / "module.py").write_text(
        "def clean():\n" '    return "only uses NIST CSF 2.0 subcategories"\n',
    )
    return sandbox


def _run_ci(sandbox: Path) -> subprocess.CompletedProcess[str]:
    """Run a sandbox-local copy of the CI gate against the sandbox tree.

    The sandbox-local copy has its SCAN_PATHS set to the sandbox's
    src/ and POLICY_FILE_PATTERNS emptied (so the test exercises the
    strict checking path).
    """
    script = sandbox / "ci-frameworks.sh"
    content = SCRIPT.read_text()
    # Replace SCAN_PATHS to use the sandbox src/
    content = content.replace(
        'SCAN_PATHS=(\n  "src/"\n  "docs/"\n  "tests/unit/"\n  "README.md"\n)',
        f'SCAN_PATHS=(\n  "{sandbox}/src"\n)',
    )
    # Empty the POLICY_FILE_PATTERNS so the test sees strict behaviour
    content = content.replace(
        'POLICY_FILE_PATTERNS=(\n  "AGENTS.md"\n  "methodology-00/MANIFESTO.md"\n  "methodology-00/REFERENCE/related_frameworks.md"\n  "docs/NIST_CSF_2.0_ONLY.md"\n  "docs/CONTRACTS.md"\n  "execution/CONTRACT-028.md"\n  "execution/CONTRACT-027.md"\n  "execution/AUDIT_D-01.1_CSF_MAPPING.md"\n)',
        "POLICY_FILE_PATTERNS=(\n)",
    )
    script.write_text(content)
    script.chmod(0o755)
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        cwd=sandbox,
    )


def test_clean_sandbox_passes(sandbox: Path) -> None:
    """A sandbox with only CSF 2.0 references passes the gate."""
    result = _run_ci(sandbox)
    assert result.returncode == 0, (
        f"CI gate should pass on clean sandbox; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_unannotated_iso_27001_fails(sandbox: Path) -> None:
    """An unannotated ISO 27001 reference fails the gate."""
    (sandbox / "src" / "module.py").write_text(
        "def f():\n" "    # No annotation\n" '    return "Use ISO 27001 as a control framework"\n',
    )
    result = _run_ci(sandbox)
    assert result.returncode == 1, "CI gate should fail on unannotated ISO 27001"
    assert "ISO 27001" in result.stdout


def test_unannotated_soc_2_fails(sandbox: Path) -> None:
    """An unannotated SOC 2 reference fails the gate."""
    (sandbox / "src" / "module.py").write_text(
        "def f():\n" '    return "Obtain SOC 2 attestation"\n',
    )
    result = _run_ci(sandbox)
    assert result.returncode == 1, "CI gate should fail on unannotated SOC 2"
    assert "SOC 2" in result.stdout


def test_unannotated_owasp_fails(sandbox: Path) -> None:
    """An unannotated OWASP reference fails the gate."""
    (sandbox / "src" / "module.py").write_text(
        "def f():\n" '    return "Apply OWASP Top 10 guidance"\n',
    )
    result = _run_ci(sandbox)
    assert result.returncode == 1, "CI gate should fail on unannotated OWASP"
    assert "OWASP" in result.stdout


def test_unannotated_csf_1_1_fails(sandbox: Path) -> None:
    """An unannotated CSF 1.1 reference fails the gate."""
    (sandbox / "src" / "module.py").write_text(
        "def f():\n" '    return "Map to CSF 1.1 PR.AC-1"\n',
    )
    result = _run_ci(sandbox)
    assert result.returncode == 1, "CI gate should fail on unannotated CSF 1.1"
    assert "CSF 1.1" in result.stdout


def test_annotated_soc_2_passes(sandbox: Path) -> None:
    """A reference annotated with CORR-028 within ±5 lines passes."""
    (sandbox / "src" / "module.py").write_text(
        "def f():\n"
        "    # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): 'SOC 2' below is\n"
        "    # a vendor attestation pattern, NOT a control framework.\n"
        '    return "Obtain SOC 2 attestation"\n',
    )
    result = _run_ci(sandbox)
    assert result.returncode == 0, (
        f"CI gate should pass on annotated SOC 2; " f"stdout={result.stdout!r}"
    )


def test_annotated_owasp_passes(sandbox: Path) -> None:
    """An OWASP reference annotated as implementation guidance passes."""
    (sandbox / "src" / "module.py").write_text(
        "def f():\n"
        "    # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): 'OWASP Top 10' below\n"
        "    # is implementation guidance, NOT a control framework.\n"
        '    return "Apply OWASP Top 10 to secure coding"\n',
    )
    result = _run_ci(sandbox)
    assert result.returncode == 0, (
        f"CI gate should pass on annotated OWASP; " f"stdout={result.stdout!r}"
    )


def test_annotated_iso_27001_passes(sandbox: Path) -> None:
    """An ISO 27001 reference annotated as attestation passes."""
    (sandbox / "src" / "module.py").write_text(
        "def f():\n"
        "    # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): 'ISO 27001' below is\n"
        "    # a vendor attestation certificate, NOT a control framework.\n"
        '    return "Check the ISO 27001 certificate expiry"\n',
    )
    result = _run_ci(sandbox)
    assert result.returncode == 0, (
        f"CI gate should pass on annotated ISO 27001; " f"stdout={result.stdout!r}"
    )


def test_annotation_outside_window_fails(sandbox: Path) -> None:
    """An annotation more than 5 lines from the reference does NOT count."""
    lines = ["def f():"]
    lines.append("    # NOTE (CORR-028, NIST_CSF_2.0_ONLY.md §2): far away")
    # 6 blank lines (annotation is at line 2, target is at line 9 — 7 away)
    for _ in range(6):
        lines.append("")
    lines.append('    return "Use ISO 27001 as a control framework"')
    (sandbox / "src" / "module.py").write_text("\n".join(lines) + "\n")
    result = _run_ci(sandbox)
    assert result.returncode == 1, (
        f"Annotation outside the ±5 window should not count; " f"stdout={result.stdout!r}"
    )
