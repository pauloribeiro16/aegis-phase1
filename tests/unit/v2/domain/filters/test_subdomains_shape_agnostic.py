"""Tests for CORR-037-T3c: shape-agnostic _summarize + _normalize_subdomain_to_v1.

Verifies that the subdomains consumer accepts BOTH:
  - v1 SubDomainDef (Pydantic from state.py) — has section2_hso, section3_requirements
  - v2 Pydantic Subdomain (from preproc_catalog.py) — has hso_hl, hso_per_reg, etc.

And produces the same SubdomainSummary shape in both cases.
"""

from __future__ import annotations

from aegis_phase1.v2.domain.filters.subdomains import (
    _normalize_subdomain_to_v1,
    _summarize,
)
from aegis_phase1.v2.loader.preproc_catalog import HSOHighLevel, HSOPerReg, Subdomain
from aegis_phase1.v2.state import SubDomainDef

# --- v1 shape: pass-through -------------------------------------------------


def test_v1_dict_passthrough() -> None:
    """A v1-shaped dict passes through unchanged."""
    v1 = {
        "title": "D-01.1 Data at Rest Encryption",
        "section2_hso": {
            "hl_objective": "High-level objective text",
            "per_reg_sos": [
                {"id": "D-01.1 — Sub-SO for GDPR", "text": "GDPR text"},
            ],
        },
        "section3_requirements": [{"id": "D-01.1.1", "title": "Req 1"}],
        "section1_crda": [],
        "frontmatter": {},
    }
    out = _normalize_subdomain_to_v1(v1)
    assert out == v1
    assert out["section2_hso"]["hl_objective"] == "High-level objective text"


def test_v1_subdomaindef_passthrough() -> None:
    """A v1 SubDomainDef Pydantic is normalized via model_dump."""
    v1 = SubDomainDef(
        document_id="AEGIS-001",
        title="D-04.3 Regulatory Notification",
        section2_hso={
            "hl_objective": "Notify authorities of incidents",
            "per_reg_sos": [
                {"id": "D-04.3.1 — Sub-SO for NIS2", "text": "NIS2 24h notification"},
            ],
        },
        section3_requirements=[{"id": "D-04.3.1.1", "title": "Notify within 24h"}],
    )
    out = _normalize_subdomain_to_v1(v1)
    assert out["title"] == "D-04.3 Regulatory Notification"
    assert out["section2_hso"]["hl_objective"] == "Notify authorities of incidents"
    assert len(out["section2_hso"]["per_reg_sos"]) == 1
    assert out["section2_hso"]["per_reg_sos"][0]["id"] == "D-04.3.1 — Sub-SO for NIS2"


# --- v2 shape: Pydantic Subdomain from preproc_catalog ---------------------


def test_v2_pydantic_subdomain_normalized() -> None:
    """A v2 Pydantic Subdomain is converted to v1 dict shape."""
    v2 = Subdomain(
        id="D-01.1",
        title="D-01.1 Data at Rest Encryption",
        hso_hl=HSOHighLevel(
            id="SO-D-01.1.HL",
            objective="Data held at rest is protected against unauthorised access",
        ),
        hso_per_reg=[
            HSOPerReg(
                id="SO-D-01.1.GDPR",
                regulation="GDPR",
                objective="GDPR Art. 32(1)(b) personal data at rest",
            ),
            HSOPerReg(
                id="SO-D-01.1.NIS2",
                regulation="NIS2",
                objective="NIS2 Art. 21(2)(h) cryptography policies",
            ),
        ],
    )
    out = _normalize_subdomain_to_v1(v2)
    assert out["title"] == "D-01.1 Data at Rest Encryption"
    # v2 hso_hl.objective -> v1 section2_hso.hl_objective
    assert out["section2_hso"]["hl_objective"] == "Data held at rest is protected against unauthorised access"
    # v2 hso_per_reg -> v1 section2_hso.per_reg_sos
    assert len(out["section2_hso"]["per_reg_sos"]) == 2
    p0 = out["section2_hso"]["per_reg_sos"][0]
    assert p0["id"] == "SO-D-01.1.GDPR"
    assert p0["text"] == "GDPR Art. 32(1)(b) personal data at rest"
    assert p0["regulation"] == "GDPR"


def test_v2_pydantic_subdomain_with_security_requirements() -> None:
    """v2 security_requirements -> v1 section3_requirements."""
    from aegis_phase1.v2.loader.preproc_catalog import SubdomainSecurityRequirement

    v2 = Subdomain(
        id="D-01.1",
        title="Test",
        hso_hl=HSOHighLevel(id="SO-D-01.1.HL", objective=""),
        hso_per_reg=[],
        security_requirements=[
            SubdomainSecurityRequirement(
                id="D-01.1.1.1",
                sr_short="1.1.1",
                title="Personal data at rest",
                csf=["PR.DS-01"],
                anchors=["Art. 32(1)"],
            ),
        ],
    )
    out = _normalize_subdomain_to_v1(v2)
    assert len(out["section3_requirements"]) == 1
    sr = out["section3_requirements"][0]
    assert sr["id"] == "D-01.1.1.1"
    assert sr["title"] == "Personal data at rest"
    assert sr["csf"] == ["PR.DS-01"]


def test_v2_dict_passthrough_when_hso_keys_present() -> None:
    """A v2 model_dump() dict (has hso_hl/hso_per_reg keys) is normalized."""
    v2_dump = {
        "id": "D-01.1",
        "title": "D-01.1 Data at Rest Encryption",
        "hso_hl": {
            "id": "SO-D-01.1.HL",
            "objective": "Protect data at rest",
        },
        "hso_per_reg": [
            {
                "id": "SO-D-01.1.GDPR",
                "regulation": "GDPR",
                "objective": "GDPR text",
            },
        ],
        "security_requirements": [],
        "pairs": [],
    }
    out = _normalize_subdomain_to_v1(v2_dump)
    assert out["title"] == "D-01.1 Data at Rest Encryption"
    assert out["section2_hso"]["hl_objective"] == "Protect data at rest"
    assert len(out["section2_hso"]["per_reg_sos"]) == 1
    assert out["section2_hso"]["per_reg_sos"][0]["regulation"] == "GDPR"


# --- _summarize end-to-end with v2 input -----------------------------------


def test_summarize_with_v2_pydantic_subdomain() -> None:
    """_summarize must accept v2 Pydantic Subdomain and produce SubdomainSummary."""
    v2 = Subdomain(
        id="D-01.1",
        title="D-01.1 Data at Rest Encryption",
        hso_hl=HSOHighLevel(
            id="SO-D-01.1.HL",
            objective="Protect data at rest with encryption",
        ),
        hso_per_reg=[
            HSOPerReg(
                id="SO-D-01.1.GDPR",
                regulation="GDPR",
                objective="GDPR Art. 32(1)(b)",
            ),
            HSOPerReg(
                id="SO-D-01.1.CRA",
                regulation="CRA",
                objective="CRA Annex I Part I (2)(e)",
            ),
        ],
    )
    summary = _summarize(
        sid="D-01.1",
        sub=v2,
        source_regs_by_sub={},  # empty — use _extract_regulation fallback
    )
    assert summary["id"] == "D-01.1"
    assert summary["title"] == "D-01.1 Data at Rest Encryption"
    assert summary["hso_hl"] == "Protect data at rest with encryption"
    # 2 per_reg_sos, both kept (no applicable_regs filter)
    assert len(summary["hso_per_reg"]) == 2
    regs = {entry["regulation"] for entry in summary["hso_per_reg"]}
    assert regs == {"GDPR", "CRA"}


def test_summarize_with_v1_subdomaindef() -> None:
    """_summarize must still accept v1 SubDomainDef (backwards compat)."""
    v1 = SubDomainDef(
        document_id="AEGIS-001",
        title="D-04.3 Regulatory Notification",
        section2_hso={
            "hl_objective": "Notify authorities of incidents",
            "per_reg_sos": [
                {"id": "D-04.3.1 — Sub-SO for NIS2", "text": "NIS2 24h notification"},
            ],
        },
        section3_requirements=[],
    )
    summary = _summarize(
        sid="D-04.3",
        sub=v1,
        source_regs_by_sub={},
    )
    assert summary["id"] == "D-04.3"
    assert summary["title"] == "D-04.3 Regulatory Notification"
    assert summary["hso_hl"] == "Notify authorities of incidents"


def test_summarize_v1_vs_v2_same_hso_hl() -> None:
    """Both v1 and v2 produce the same hso_hl string (shape-agnostic)."""
    hl = "High-level objective shared by both shapes"

    v1 = SubDomainDef(
        document_id="AEGIS",
        title="Shared Title",
        section2_hso={"hl_objective": hl, "per_reg_sos": []},
        section3_requirements=[],
    )
    v2 = Subdomain(
        id="X-01.1",
        title="Shared Title",
        hso_hl=HSOHighLevel(id="SO-X.HL", objective=hl),
        hso_per_reg=[],
    )
    s1 = _summarize("X-01.1", v1, {})
    s2 = _summarize("X-01.1", v2, {})
    assert s1["hso_hl"] == s2["hso_hl"] == hl
    assert s1["title"] == s2["title"] == "Shared Title"


# --- Edge cases ------------------------------------------------------------


def test_normalize_handles_none() -> None:
    """None / missing input returns empty dict."""
    assert _normalize_subdomain_to_v1(None) == {}


def test_normalize_handles_unknown_shape() -> None:
    """An unrecognized shape (e.g. plain string) returns empty dict."""
    assert _normalize_subdomain_to_v1("not a sub") == {}
    assert _normalize_subdomain_to_v1(42) == {}


def test_normalize_v2_with_empty_hso_hl() -> None:
    """v2 with hso_hl=None returns empty hl_objective (graceful)."""
    v2 = Subdomain(
        id="D-01.1",
        title="Test",
        hso_hl=None,
        hso_per_reg=[],
    )
    out = _normalize_subdomain_to_v1(v2)
    assert out["section2_hso"]["hl_objective"] == ""
    assert out["section2_hso"]["per_reg_sos"] == []
