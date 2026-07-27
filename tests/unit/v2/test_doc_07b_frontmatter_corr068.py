"""CORR-068 S3: Doc 07b front-matter must use _safe_attr (handles dicts), not getattr.

Pre-S3 the front-matter used:
    "case_study": getattr(ctx, "company_name", "UNKNOWN") if ctx else "UNKNOWN",

where ctx is a dict (from _build_company_context().model_dump()). getattr
on a dict always raises AttributeError, so the fallback "UNKNOWN" was
always returned, even when ctx["company_name"] was the correct name.

The _safe_attr helper (defined elsewhere in doc_07b.py) does check
isinstance(obj, Mapping) and falls back to .get() — so the same field
read via _safe_attr works correctly.

Fix: replace getattr() with _safe_attr() in the front-matter dict.

Tests parse the YAML front-matter and check the case_study field.
"""
import logging
import re

import yaml

logging.basicConfig(level=logging.WARNING)


def _parse_frontmatter(fm_str):
    """Parse the YAML front-matter from _build_frontmatter's output."""
    # Strip the '---' markers
    fm_body = re.sub(r"^---\n|---\n?$", "", fm_str, flags=re.MULTILINE)
    return yaml.safe_load(fm_body)


def test_doc_07b_frontmatter_uses_company_name_from_dict_ctx():
    """When ctx is a dict (typical case), case_study should be the dict value."""
    from aegis_phase1.v2.output.doc_07b import _build_frontmatter

    state = {
        "company_context": {
            "company_name": "SecureBorder Solutions B.V.",
            "scale": "LARGE",
            "security_fte": 25.0,
            "applicable_regs": ["GDPR", "CRA", "NIS2", "AI_Act"],
        }
    }
    fm_str = _build_frontmatter(state, applicable=["GDPR", "CRA", "NIS2", "AI_Act"])
    fm = _parse_frontmatter(fm_str)

    assert "case_study" in fm
    assert fm["case_study"] == "SecureBorder Solutions B.V.", (
        f"expected 'SecureBorder Solutions B.V.', got {fm['case_study']!r}"
    )


def test_doc_07b_frontmatter_handles_missing_ctx():
    """When ctx is missing, case_study should be 'UNKNOWN' (fallback)."""
    from aegis_phase1.v2.output.doc_07b import _build_frontmatter

    state = {}
    fm_str = _build_frontmatter(state, applicable=[])
    fm = _parse_frontmatter(fm_str)

    assert fm["case_study"] == "UNKNOWN"


def test_doc_07b_frontmatter_handles_dict_without_company_name():
    """When ctx is a dict missing company_name, case_study should be 'UNKNOWN'."""
    from aegis_phase1.v2.output.doc_07b import _build_frontmatter

    state = {"company_context": {"scale": "LARGE", "security_fte": 25.0}}
    fm_str = _build_frontmatter(state, applicable=[])
    fm = _parse_frontmatter(fm_str)

    assert fm["case_study"] == "UNKNOWN"


def test_doc_07b_frontmatter_handles_pydantic_ctx():
    """When ctx is a Pydantic model dumped to dict, case_study should also work."""
    from aegis_phase1.v2.output.doc_07b import _build_frontmatter
    from aegis_phase1.v2.state import CompanyContext

    ctx = CompanyContext(
        company_name="PydanticCo",
        sector="Software",
        jurisdiction="EU",
        employees=10,
        revenue=100000.0,
        scale="MICRO",
        applicable_regs=["GDPR"],
        complexity_tier="LOW",
        security_fte=0.5,
        tech_stack=["AWS"],
    )
    state = {"company_context": ctx.model_dump()}
    fm_str = _build_frontmatter(state, applicable=["GDPR"])
    fm = _parse_frontmatter(fm_str)

    assert fm["case_study"] == "PydanticCo"
