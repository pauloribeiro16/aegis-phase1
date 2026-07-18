"""CORR-023: every domain D-01..D-10 has a ``_DOMAIN_CLAUSE_FILTER`` entry
so the ambiguity loader never falls through to the unfiltered all-cards
mode (~280 cards / >160 KB, which would blow the prompt budget). See
``ambiguity_loader.py`` docstring for the fall-through warning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aegis_phase1.v2.loader.ambiguity_loader import (
    _DOMAIN_CLAUSE_FILTER,
    load_ambiguities_for_regs,
)

PREPROCESSING = Path(
    "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/" "00_METHODOLOGY/PREPROCESSING"
)

DOMAINS = [f"D-{i:02d}" for i in range(1, 11)]


@pytest.mark.parametrize("domain_id", DOMAINS, ids=lambda d: d)
def test_every_domain_has_clause_filter_entry(domain_id: str) -> None:
    """Each domain must register at least one rule in _DOMAIN_CLAUSE_FILTER
    so the ``_entry_matches_domain`` fall-through cannot trigger."""
    rules = _DOMAIN_CLAUSE_FILTER.get(domain_id)
    assert rules, (
        f"{domain_id} has no _DOMAIN_CLAUSE_FILTER entry — ambiguity loader "
        f"will fall through to the unfiltered all-cards mode (~280 cards)."
    )


@pytest.mark.parametrize("domain_id", DOMAINS, ids=lambda d: d)
def test_filtered_card_count_under_budget(domain_id: str) -> None:
    """The filtered ambiguity section for each domain (GDPR + CRA, the
    TinyTask applicable regs) must stay well under the all-cards count.
    The all-cards mode returns 54 GDPR + 63 CRA = 117 cards; a per-domain
    filter that returns close to that is effectively a no-op."""
    entries = load_ambiguities_for_regs(["GDPR", "CRA"], PREPROCESSING, domain_id=domain_id)
    # Loose ceiling: the largest legitimate per-domain count (D-09) is ~40
    # cards. Anything approaching 117 means the filter isn't filtering.
    assert len(entries) <= 60, (
        f"{domain_id}: {len(entries)} ambiguity cards loaded — filter may be "
        f"too permissive (all-cards baseline is 117)."
    )


def test_d10_filter_unchanged_from_corr022() -> None:
    """D-10 was curated in CORR-022 and validated by the 9/9-gate run.
    Regression guard: CORR-023 must not silently alter its rules."""
    d10_rules = _DOMAIN_CLAUSE_FILTER["D-10"]
    gdpr_ids = sorted({prefix for reg, prefix, _, _ in d10_rules if reg == "GDPR" and prefix})
    cra_ids = sorted({prefix for reg, prefix, _, _ in d10_rules if reg == "CRA" and prefix})
    # Spot-check the canonical entries
    assert "GDPR-CP12" in gdpr_ids, "D-10 GDPR must retain GDPR-CP12 (Art. 30 RoPA)"
    assert "CRA-CL141" in cra_ids, "D-10 CRA must retain CRA-CL141 (Annex I (2)(l) logging)"


def test_no_domain_returns_zero_cards_for_applicable_regs() -> None:
    """For TinyTask (GDPR + CRA), each domain must return at least 1 card.
    A 0 result means the filter is too strict (no article tokens match)."""
    for domain_id in DOMAINS:
        entries = load_ambiguities_for_regs(
            ["GDPR", "CRA"], PREPROCESSING, domain_id=domain_id
        )
        assert entries, (
            f"{domain_id}: filtered ambiguities empty — §6 KNOWN AMBIGUITIES "
            f"will be blank, which is a CORR-023 regression."
        )
