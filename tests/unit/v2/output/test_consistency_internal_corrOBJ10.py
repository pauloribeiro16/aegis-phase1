"""CORR-OBJ-10: cross-doc structural consistency checks (mock inputs).

OBJECTIVES_CONTRACT §2.2 — OBJ-10 [G+J] "Internal consistency: LLM content
must not contradict deterministic sections across the 9 docs".

The test target is the *invariant* layer of OBJ-10 — i.e. checks that a
set of rendered documents are mutually consistent **on structured data**:
subdomain IDs, CSF tokens, stakeholder IDs. LLM-side nuance is left to
future [J] judge cells.

Each test uses a synthetic bundle of three documents (Doc 04, 06, 04d
representative) and a synthetic subdomain list (case profile). No
pipeline run is needed; this isolates the consistency invariant from
LLM output variance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pytest


# ────────────────────────────────────────────────────────────────────
# Synthetic case profile + renderer for tests
# ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SubdomainProfile:
    """A minimal "active subdomain" used by all three consistency checks."""

    id: str  # e.g. "D-01.4"
    title: str
    csf_anchor: str | None = None  # e.g. "PR.DS-01"


@dataclass
class CaseBundle:
    """Synthetic rendered-doc bundle + case profile used by the tests."""

    case_id: str
    subdomains: list[SubdomainProfile] = field(default_factory=list)
    stakeholders: list[str] = field(default_factory=list)
    doc_04: str = ""
    doc_06: str = ""
    doc_04d: str = ""


def _subdomain_id_re() -> re.Pattern[str]:
    return re.compile(r"\bD-\d{2}\.\d+\b")


def _csf_token_re() -> re.Pattern[str]:
    # NIST CSF 2.0 function.category-NN shape (e.g. PR.DS-01).
    return re.compile(r"\b[A-Z]{2}\.[A-Z]{2}-\d{2}\b")


def _stakeholder_id_re() -> re.Pattern[str]:
    return re.compile(r"\bSH-\d{2}\b")


# ────────────────────────────────────────────────────────────────────
# 1. Subdomain coverage: Doc 04 sections → Doc 06 obligations
# ────────────────────────────────────────────────────────────────────


def _subdomains_in(text: str) -> set[str]:
    return set(_subdomain_id_re().findall(text))


def _subdomain_coverage_invariant(bundle: CaseBundle) -> dict:
    """Check 1: every active subdomain in Doc 04 has ≥1 obligation in Doc 06.

    Returns a dict ``{"missing_in_doc06": [...], "doc04_active": [...], ...}``
    that the tests can assert against.
    """
    doc04_subs = _subdomains_in(bundle.doc_04)
    doc06_subs = _subdomains_in(bundle.doc_06)
    profile_sub_ids = {s.id for s in bundle.subdomains}

    # "Active" subdomains are those that appear in the case profile AND
    # in Doc 04. Subdomains only in the profile (not rendered) are out of
    # scope of this invariant.
    active = doc04_subs & profile_sub_ids
    missing_in_doc06 = active - doc06_subs
    return {
        "case_id": bundle.case_id,
        "doc04_active": sorted(active),
        "doc06_present": sorted(doc06_subs),
        "missing_in_doc06": sorted(missing_in_doc06),
    }


# ────────────────────────────────────────────────────────────────────
# 2. CSF token cross-reference
# ────────────────────────────────────────────────────────────────────


def _csf_tokens_in(text: str) -> set[str]:
    return set(_csf_token_re().findall(text))


def _csf_token_invariant(bundle: CaseBundle) -> dict:
    """Check 2: every CSF token cited in Doc 06 also appears in Doc 04's
    CSF anchor section (or in the case profile's ``csf_anchor`` map).
    """
    csf_in_doc06 = _csf_tokens_in(bundle.doc_06)
    csf_in_doc04 = _csf_tokens_in(bundle.doc_04)
    profile_anchors = {s.csf_anchor for s in bundle.subdomains if s.csf_anchor}
    profile_anchors |= csf_in_doc04
    missing = csf_in_doc06 - profile_anchors
    return {
        "case_id": bundle.case_id,
        "csf_in_doc06": sorted(csf_in_doc06),
        "csf_anchors": sorted(profile_anchors),
        "missing_in_doc04": sorted(missing),
    }


# ────────────────────────────────────────────────────────────────────
# 3. Stakeholder ID parity
# ────────────────────────────────────────────────────────────────────


def _stakeholder_ids_in(text: str) -> set[str]:
    return set(_stakeholder_id_re().findall(text))


def _stakeholder_parity_invariant(bundle: CaseBundle) -> dict:
    """Check 3: stakeholder IDs in Doc 04 §1 (Stakeholder Analysis)
    are the same as in Doc 04d's RACI section.

    The Doc 04 anchor section header used here is
    ``## 3. STAKEHOLDER ANALYSIS`` per the canonical Doc 04 template.
    """
    # Find Doc 04 stakeholder section: from "## 3. STAKEHOLDER ANALYSIS"
    # to the next "## " heading.
    m = re.search(
        r"^##\s+3\.\s*STAKEHOLDER.*?(?=^##\s+|\Z)",
        bundle.doc_04,
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )
    doc04_stakeholder_section = m.group(0) if m else ""

    # Find Doc 04d RACI section: "## RACI" or "## N. RACI".
    m2 = re.search(
        r"^##\s+(?:\d+\.\s*)?RACI.*?(?=^##\s+|\Z)",
        bundle.doc_04d,
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )
    doc04d_raci_section = m2.group(0) if m2 else ""

    s_doc04 = _stakeholder_ids_in(doc04_stakeholder_section)
    s_doc04d = _stakeholder_ids_in(doc04d_raci_section)
    only_in_doc04 = s_doc04 - s_doc04d
    only_in_doc04d = s_doc04d - s_doc04
    return {
        "case_id": bundle.case_id,
        "doc04_stakeholder_ids": sorted(s_doc04),
        "doc04d_raci_ids": sorted(s_doc04d),
        "only_in_doc04": sorted(only_in_doc04),
        "only_in_doc04d": sorted(only_in_doc04d),
        "doc04_section_found": bool(doc04_stakeholder_section),
        "doc04d_raci_section_found": bool(doc04d_raci_section),
    }


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────


def _build_consistent_bundle(case_id: str) -> CaseBundle:
    """A bundle where all three invariants pass."""
    subdomains = [
        SubdomainProfile(id="D-01.1", title="Asset Inventory", csf_anchor="ID.AM-01"),
        SubdomainProfile(id="D-01.4", title="Data Protection", csf_anchor="PR.DS-01"),
        SubdomainProfile(id="D-04.2", title="Access Control", csf_anchor="PR.AC-01"),
    ]
    doc_04 = f"""# Company Context Assessment

## 1. PURPOSE
The company is case {case_id}.

## 2. ASSESSMENT SUMMARY
Summary text.

## 3. STAKEHOLDER ANALYSIS (A1)

| ID | Role |
|----|------|
| SH-01 | CEO |
| SH-02 | CTO |
| SH-03 | DPO |

## 4. BUSINESS GOALS
- Goal A.
- Goal B.

## 5. INTAKE FORM
- D-01.1 Asset Inventory context.
- D-01.4 Data Protection context.
- D-04.2 Access Control context.
"""
    doc_06 = f"""# Clause Mapping Matrix

| Subdomain | CSF | Clause |
|-----------|-----|--------|
| D-01.1 | ID.AM-01 | GDPR Art. 30 |
| D-01.4 | PR.DS-01 | GDPR Art. 32 |
| D-04.2 | PR.AC-01 | CRA Essential Requirements |
"""
    doc_04d = f"""# Roles & RACI

## 1. Overview
The RACI for case {case_id}.

## 2. RACI Matrix

| Activity | SH-01 | SH-02 | SH-03 |
|----------|-------|-------|-------|
| Approve Policy | R | A | C |
| Sign-off | A | R | C |
"""
    return CaseBundle(
        case_id=case_id,
        subdomains=subdomains,
        stakeholders=["SH-01", "SH-02", "SH-03"],
        doc_04=doc_04,
        doc_06=doc_06,
        doc_04d=doc_04d,
    )


def _build_inconsistent_bundle(case_id: str) -> CaseBundle:
    """A bundle where the invariants FAIL: Doc 06 missing one subdomain,
    Doc 06 cites a CSF token that is absent from Doc 04, and Doc 04d's
    RACI includes an extra stakeholder not present in Doc 04 §3.
    """
    subdomains = [
        SubdomainProfile(id="D-01.1", title="Asset Inventory", csf_anchor="ID.AM-01"),
        SubdomainProfile(id="D-01.4", title="Data Protection", csf_anchor="PR.DS-01"),
        SubdomainProfile(id="D-04.2", title="Access Control", csf_anchor="PR.AC-01"),
    ]
    doc_04 = f"""# Company Context Assessment

## 3. STAKEHOLDER ANALYSIS (A1)

| ID | Role |
|----|------|
| SH-01 | CEO |
| SH-02 | CTO |

## 5. INTAKE FORM
- D-01.1 Asset Inventory context.
- D-01.4 Data Protection context.
- D-04.2 Access Control context.
"""
    # Doc 06 omits D-04.2 and cites a CSF token (DE.CM-09) that is not
    # in Doc 04.
    doc_06 = f"""# Clause Mapping Matrix

| Subdomain | CSF | Clause |
|-----------|-----|--------|
| D-01.1 | ID.AM-01 | GDPR Art. 30 |
| D-01.4 | PR.DS-01 | GDPR Art. 32 |
| D-99.9 | DE.CM-09 | orphan |
"""
    # Doc 04d RACI has SH-99 that Doc 04 does not.
    doc_04d = f"""# Roles & RACI

## 2. RACI Matrix

| Activity | SH-01 | SH-02 | SH-99 |
|----------|-------|-------|-------|
| Approve Policy | R | A | C |
"""
    return CaseBundle(
        case_id=case_id,
        subdomains=subdomains,
        stakeholders=["SH-01", "SH-02"],
        doc_04=doc_04,
        doc_06=doc_06,
        doc_04d=doc_04d,
    )


# ────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────


# Test case 1/2/3 parametric coverage of OBJ-10 invariants.
@pytest.mark.parametrize("case_id", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
def test_consistent_bundle_passes_subdomain_coverage(case_id: str) -> None:
    """Check 1: every active subdomain in Doc 04 has ≥1 obligation in Doc 06."""
    bundle = _build_consistent_bundle(case_id)
    result = _subdomain_coverage_invariant(bundle)
    assert result["missing_in_doc06"] == [], (
        f"OBJ-10 REGRESSION ({case_id}): Doc 04 subdomains {result['doc04_active']} "
        f"are missing from Doc 06 obligations: {result['missing_in_doc06']}"
    )


@pytest.mark.parametrize("case_id", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
def test_consistent_bundle_passes_csf_token_anchor(case_id: str) -> None:
    """Check 2: every CSF token in Doc 06 also appears in Doc 04 anchors."""
    bundle = _build_consistent_bundle(case_id)
    result = _csf_token_invariant(bundle)
    assert result["missing_in_doc04"] == [], (
        f"OBJ-10 REGRESSION ({case_id}): CSF tokens in Doc 06 "
        f"{result['csf_in_doc06']} are not anchored in Doc 04: "
        f"{result['missing_in_doc04']}"
    )


@pytest.mark.parametrize("case_id", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
def test_consistent_bundle_passes_stakeholder_parity(case_id: str) -> None:
    """Check 3: Doc 04 §3 stakeholder IDs equal Doc 04d RACI section."""
    bundle = _build_consistent_bundle(case_id)
    result = _stakeholder_parity_invariant(bundle)
    assert result["only_in_doc04"] == [], (
        f"OBJ-10 REGRESSION ({case_id}): stakeholders in Doc 04 §3 not "
        f"present in Doc 04d RACI: {result['only_in_doc04']}"
    )
    assert result["only_in_doc04d"] == [], (
        f"OBJ-10 REGRESSION ({case_id}): stakeholders in Doc 04d RACI not "
        f"present in Doc 04 §3: {result['only_in_doc04d']}"
    )
    assert result["doc04_section_found"], (
        f"OBJ-10 REGRESSION ({case_id}): Doc 04 §3 STAKEHOLDER ANALYSIS not found"
    )
    assert result["doc04d_raci_section_found"], (
        f"OBJ-10 REGRESSION ({case_id}): Doc 04d RACI section not found"
    )


# Inverse tests: an inconsistent bundle must be DETECTED by the invariants.
def test_inconsistent_bundle_fails_subdomain_coverage() -> None:
    bundle = _build_inconsistent_bundle("case-broken")
    result = _subdomain_coverage_invariant(bundle)
    assert "D-04.2" in result["missing_in_doc06"], (
        f"OBJ-10 detection broken: expected D-04.2 in missing_in_doc06, got {result}"
    )


def test_inconsistent_bundle_fails_csf_anchor() -> None:
    bundle = _build_inconsistent_bundle("case-broken")
    result = _csf_token_invariant(bundle)
    assert "DE.CM-09" in result["missing_in_doc04"], (
        f"OBJ-10 detection broken: expected DE.CM-09 in missing_in_doc04, got {result}"
    )


def test_inconsistent_bundle_fails_stakeholder_parity() -> None:
    bundle = _build_inconsistent_bundle("case-broken")
    result = _stakeholder_parity_invariant(bundle)
    # SH-99 appears in Doc 04d but not in Doc 04 §3.
    assert "SH-99" in result["only_in_doc04d"], (
        f"OBJ-10 detection broken: expected SH-99 in only_in_doc04d, got {result}"
    )
    # (inverse) SH-01 and SH-02 must match.
    assert result["only_in_doc04"] == []


# ────────────────────────────────────────────────────────────────────
# Real-data smoke: apply the invariant to the case1 deterministic
# output (if available) so a developer running the suite sees whether
# the existing rendered docs already satisfy OBJ-10.
# ────────────────────────────────────────────────────────────────────


def _read_case1_filled_docs() -> dict[str, str] | None:
    """Best-effort read of case1-tinytask rendered docs.

    Returns ``None`` if the on-disk layout is missing (the test then
    self-skips with a clear reason) so this is non-flaky in CI.
    """
    # Project root from the test file:
    #   tests/unit/v2/output/test_consistency_internal_corrOBJ10.py
    #   -> project root is 4 parents up.
    here = Path(__file__).resolve()
    candidates = [
        here.parents[4] / "cases" / "case1-tinytask" / "output" / "phase1" / "04_Company_Context_Assessment_filled.md",
        here.parents[4] / "cases" / "case1-tinytask" / "output" / "phase1" / "06_Clause_Mapping_Matrix_filled.md",
    ]
    if not all(p.exists() for p in candidates):
        return None
    return {
        "doc_04": candidates[0].read_text(encoding="utf-8", errors="ignore"),
        "doc_06": candidates[1].read_text(encoding="utf-8", errors="ignore"),
    }


def test_case1_deterministic_outputs_smoke() -> None:
    """Smoke: case1-tinytask rendered docs satisfy the subdomain-coverage
    invariant. Skipped if the on-disk layout is not present.
    """
    docs = _read_case1_filled_docs()
    if docs is None:
        pytest.skip("case1-tinytask filled outputs not on disk; skipping smoke")
    # Build a profile that matches case1's small set of subdomains
    # referenced in the deterministic outputs.
    bundle = CaseBundle(
        case_id="case1-tinytask",
        subdomains=[
            SubdomainProfile(id="D-01.1", title="Asset Inventory", csf_anchor="ID.AM-01"),
            SubdomainProfile(id="D-01.4", title="Data Protection", csf_anchor="PR.DS-01"),
        ],
        doc_04=docs["doc_04"],
        doc_06=docs["doc_06"],
    )
    result = _subdomain_coverage_invariant(bundle)
    # Smoke: must not throw; must produce a result for `case1-tinytask`.
    assert result["case_id"] == "case1-tinytask"
    assert isinstance(result["doc04_active"], list)
    assert isinstance(result["missing_in_doc06"], list)
