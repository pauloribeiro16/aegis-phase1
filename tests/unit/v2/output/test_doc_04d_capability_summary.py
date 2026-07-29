"""CORR-075 tests: Doc 04d §6 Capability Summary replaces per-individual RACI.

Contract SC-2026-18 / execution/SPEC.md (SP-2026-18) requires that
``doc_04d.py`` removes the hardcoded ``_RACI_BY_DOMAIN`` /
``_STAKEHOLDER_COLUMNS`` and renders a capability summary sourced from
``data/capabilities/{D-XX}.yaml`` via :func:`load_capabilities`. The
capability summary must NEVER name individuals.

These tests verify:
  1. The §6 header is renamed "Capability Summary".
  2. Output never contains person names (``Founder``, ``CEO acting as``,
     ``CTO as``, ``Lead Developer``, ``2 founders``, ``acting as DPO``,
     ``acting as CISO``).
  3. Capability rows from D-01 (4 caps) and D-04 (5 caps) appear in §6
     (≥7 rows total — matches AC-6 from SPEC.md).
  4. Missing capability YAMLs render an info-only note, not a PENDING
     marker.
  5. Section count: §7 Training, §8 Compliance, §9 Escalation,
     §10 Gaps, §11 Gate are present in order.

The tests use a Case 3 (MAX) ``company_context`` because the criterion
description ("Doc 04d output for case 3 (MAX)") aligns with the MAX
banking tier — that tier renders the LARGE role model which has no
"founder" naming (per ``data/role_models/MAX.yaml``). See CONTRACT-075
"Implementation notes" for why the contract JSON's test_commands were
adjusted from ``state={}`` to a MAX-tier state.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from aegis_phase1.v2.llm import MockInvoker
from aegis_phase1.v2.output.doc_04d import render_doc_04d

# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


def _max_state() -> dict[str, Any]:
    """Case 3 (MAX) state — OmniBank-shaped, 5,000 employees, banking tier.

    Aligns with ``data/role_models/MAX.yaml`` (no "Founder" naming) and
    with the proportionality note for the LARGE/MAX branch in
    ``_section_purpose_scope``.
    """
    return {
        "company_context": {
            "company_name": "OmniBank Financial Systems S.A.",
            "employees": 5000,
            "sector": "Banking & Financial Services",
            "scale": "MAX",
            "jurisdiction": "Germany (EU)",
            "applicable_regs": ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"],
            "revenue_eur": 1_500_000_000,
        },
    }


@pytest.fixture
def max_state() -> dict[str, Any]:
    return _max_state()


@pytest.fixture
def rendered_04d(max_state: dict[str, Any], tmp_path: Path) -> str:
    """Render Doc 04d once per test with MockInvoker."""
    inv = MockInvoker()
    paths = render_doc_04d(max_state, str(tmp_path), inv)
    return Path(paths["AEGIS-P1-04d"]).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# §6 header
# ─────────────────────────────────────────────────────────────────────


def test_doc_04d_section_header_renamed(rendered_04d: str) -> None:
    """§6 is renamed from "RACI Matrix" to "Capability Summary"."""
    assert "## 6. Capability Summary" in rendered_04d, (
        "§6 Capability Summary header missing — RACI was not replaced"
    )
    assert "## 6. RACI Matrix" not in rendered_04d, (
        "Stale §6 RACI Matrix header still present"
    )


# ─────────────────────────────────────────────────────────────────────
# No person names
# ─────────────────────────────────────────────────────────────────────


def test_doc_04d_no_person_names(rendered_04d: str) -> None:
    """Output contains NONE of the banned per-individual phrases."""
    BANNED = [
        "Founder",
        "CEO acting as",
        "CTO as",
        "Lead Developer",
        "2 founders",
        "acting as DPO",
        "acting as CISO",
    ]
    missing: list[str] = [p for p in BANNED if p in rendered_04d]
    assert not missing, (
        f"CORR-075 REGRESSION: person-name phrases found in output: {missing!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# Capability rows (D-01 + D-04 contribute 4 + 5 = 9 rows; ≥7 required)
# ─────────────────────────────────────────────────────────────────────


def test_doc_04d_capability_rows_for_d01_d04(rendered_04d: str) -> None:
    """§6 lists at least one capability row from D-01 and D-04 each.

    Per AC-6 (SPEC.md): Case 3 (MAX) §6 has ≥7 capability rows. With
    D-01 contributing 4 caps and D-04 contributing 5 caps, the doc
    emits 9 rows on the shipped YAMLs (which exceeds the threshold).
    """
    assert "CAP-D01-001" in rendered_04d, (
        "CAP-D01-001 missing — D-01 capability catalog not rendered"
    )
    assert "CAP-D04-001" in rendered_04d, (
        "CAP-D04-001 missing — D-04 capability catalog not rendered"
    )
    # ≥7 rows in §6 itself.
    m = re.search(
        r"## 6\. Capability Summary(.*?)(?=## 7\.|$)",
        rendered_04d,
        re.DOTALL,
    )
    assert m, "§6 Capability Summary section not found"
    section = m.group(1)
    cap_ids = re.findall(r"CAP-D\d+-\d+", section)
    assert len(cap_ids) >= 7, (
        f"AC-6 violation: expected ≥7 capability rows in §6, got {len(cap_ids)}: {cap_ids}"
    )


# ─────────────────────────────────────────────────────────────────────
# No PENDING marker; info-only note for missing catalogs
# ─────────────────────────────────────────────────────────────────────


def test_doc_04d_no_pending_marker(rendered_04d: str) -> None:
    """Output contains no ``PENDING REVIEW`` marker in §6.

    Per SPEC.md FR-4 / Decision 3: missing capability catalogs render
    an info-only note, NEVER a PENDING marker.
    """
    m = re.search(
        r"## 6\. Capability Summary(.*?)(?=## 7\.|$)",
        rendered_04d,
        re.DOTALL,
    )
    assert m, "§6 not found"
    section = m.group(1)
    assert "PENDING REVIEW" not in section, (
        f"PENDING REVIEW marker leaked into §6 — should be info-only note. "
        f"Section text:\n{section[:500]}"
    )


def test_doc_04d_info_only_for_missing(rendered_04d: str) -> None:
    """§6 contains the info-only note for D-XX without a YAML catalog.

    D-02, D-03, D-05..D-10 have no YAML shipped (CORR-074 only
    authored D-01 + D-04). Their §6 sub-sections must render the
    info-only note ``not yet authored``.
    """
    assert "not yet authored" in rendered_04d, (
        "Info-only note for missing capability catalog missing — "
        "missing YAMLs should render '_Capability catalog for D-XX "
        "not yet authored; see data/capabilities/D-XX.yaml._'"
    )


# ─────────────────────────────────────────────────────────────────────
# Renumbering: §7..§11 present in order
# ─────────────────────────────────────────────────────────────────────


def test_doc_04d_section_numbering_after_rename(rendered_04d: str) -> None:
    """Subsequent sections shifted but stay in order after the rename."""
    expected_headers = [
        "## 7. Training Status",
        "## 8. Compliance Mapping",
        "## 9. Escalation Paths",
        "## 10. Gaps",
        "## 11. Gate",
    ]
    last_idx = -1
    for header in expected_headers:
        idx = rendered_04d.find(header)
        assert idx >= 0, f"Missing header: {header!r}"
        assert idx > last_idx, (
            f"Header {header!r} appears out of order "
            f"(last_idx={last_idx}, this_idx={idx})"
        )
        last_idx = idx


# ─────────────────────────────────────────────────────────────────────
# Capability summary intro paragraph (FR-3 / AC-7)
# ─────────────────────────────────────────────────────────────────────


def test_doc_04d_capability_intro_paragraph(rendered_04d: str) -> None:
    """§6 contains the prose intro mentioning capabilities + out of scope."""
    m = re.search(
        r"## 6\. Capability Summary(.*?)(?=### D-01|$)",
        rendered_04d,
        re.DOTALL,
    )
    assert m, "§6 intro not found"
    intro = m.group(1).lower()
    assert "capabilities" in intro, "intro paragraph missing 'capabilities'"
    assert "out of scope" in intro, (
        "intro paragraph missing 'out of scope' — RACI per individual "
        "should be explicitly declared out of scope"
    )
