"""CORR-023: every domain D-01..D-10 has at least one article mapped for at
least one applicable regulation. Guards against the D-02/03/05/06/07/08/09
empty-catalog regression that CORR-023 closed (those domains previously
returned ``[]`` from ``filter_articles`` because their ``DOMAIN_ARTICLES``
slot was an empty stub).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.v2.loader.article_loader import DOMAIN_ARTICLES

PREPROCESSING = Path(
    "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/" "00_METHODOLOGY/PREPROCESSING"
)

# TinyTask applicable regulations. These are the only regs the article
# loader will be asked to load for the case1-tinytask case.
TINYTASK_REGS = ["GDPR", "CRA"]

DOMAINS = [f"D-{i:02d}" for i in range(1, 11)]


@pytest.mark.parametrize("domain_id", DOMAINS, ids=lambda d: d)
def test_every_domain_has_at_least_one_applicable_article(domain_id: str) -> None:
    """Each domain catalogued in DOMAIN_ARTICLES must declare at least one
    article reference for at least one TinyTask-applicable regulation."""
    mapping = DOMAIN_ARTICLES.get(domain_id)
    assert mapping is not None, f"{domain_id} missing from DOMAIN_ARTICLES"

    applicable_refs = [ref for reg in TINYTASK_REGS for ref in mapping.get(reg, [])]
    assert applicable_refs, (
        f"{domain_id} has no GDPR or CRA article refs in DOMAIN_ARTICLES; "
        f"filter_articles will return [] and §3 APPLICABLE ARTICLES will be empty."
    )


def test_no_domain_uses_empty_stub_for_applicable_regs() -> None:
    """Catch the legacy anti-pattern where a domain entry was created with
    all-empty lists (``{"GDPR": [], "CRA": [], ...}``). For TinyTask's
    applicable regs at least one must be populated."""
    for domain_id in DOMAINS:
        mapping = DOMAIN_ARTICLES[domain_id]
        populated = [reg for reg in TINYTASK_REGS if mapping.get(reg)]
        assert populated, (
            f"{domain_id} has all-empty GDPR/CRA lists — this is the "
            f"pre-CORR-023 empty-stub shape that produces empty §3 output."
        )


def test_d10_catalog_unchanged_from_corr022() -> None:
    """D-10 was curated in CORR-022 and validated by the 9/9-gate PASS run.
    Regression guard: CORR-023 must not silently alter it."""
    d10 = DOMAIN_ARTICLES["D-10"]
    assert d10["GDPR"] == ["Art. 30(3)", "Art. 5(2)", "Art. 31"]
    assert "Annex VII §3" in d10["CRA"]
    assert "Annex VII §6" in d10["CRA"]
    assert "Art. 13(4)" in d10["CRA"]


def test_catalog_covers_all_ten_domains() -> None:
    """All 10 AEGIS domains must be present in the catalog (no D-XX missing)."""
    keys = set(DOMAIN_ARTICLES.keys())
    missing = {d for d in DOMAINS if d not in keys}
    assert not missing, f"DOMAIN_ARTICLES missing domains: {sorted(missing)}"
