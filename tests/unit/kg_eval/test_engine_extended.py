"""Unit tests for the 3 new ontology patterns added to build_graph_for_case.

Verifies that:
  * Pattern 3 (ProportionalityEntry) is instantiated with a valid tier and a
    real subdomain id.
  * Pattern 5 (SecurityObjective) is instantiated with a real subdomain id and
    a non-empty regulation_code.
  * Pattern 6 (DataSubject) is instantiated for case3 (which has
    data_subjects.yaml), and is absent for case1 (which has no such YAML).

These tests exercise the bug fix where `cn.label == "RegulatoryClause"` was
the wrong API for a `Node` (which uses `labels: set[str]`).
"""

from __future__ import annotations

from pathlib import Path

from scripts.kg_eval.engine import build_graph_for_case

REPO_ROOT = Path(__file__).resolve().parents[3]
PREPROC_ROOT = REPO_ROOT / "preproc_out"
CASE3_PATH = REPO_ROOT / "cases" / "case3-omnibank"
CASE1_PATH = REPO_ROOT / "cases" / "case1-tinytask"

VALID_PE_TIERS = {"MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS"}


def _real_subdomain_ids(graph) -> set[str]:
    """Collect the `id` property of every SubDomain node currently in the graph."""
    return {
        n.properties.get("id", "")
        for n in graph.nodes
        if "SubDomain" in n.labels and n.properties.get("id")
    }


def test_proportionality_entry_instantiated() -> None:
    """Pattern 3: at least one ProportionalityEntry exists with a valid tier and
    a `sub_domain_id` matching a real SubDomain id."""
    graph = build_graph_for_case(CASE3_PATH, PREPROC_ROOT)

    pe_nodes = [n for n in graph.nodes if "ProportionalityEntry" in n.labels]
    assert len(pe_nodes) > 0, "Expected ProportionalityEntry nodes to be instantiated"

    real_sd_ids = _real_subdomain_ids(graph)
    assert real_sd_ids, "Pre-condition: graph must contain at least one SubDomain"

    pe_with_valid_tier = [pe for pe in pe_nodes if pe.properties.get("tier") in VALID_PE_TIERS]
    assert (
        len(pe_with_valid_tier) > 0
    ), f"Expected at least one PE with tier in {VALID_PE_TIERS}; got tiers { {pe.properties.get('tier') for pe in pe_nodes} }"

    pe_with_real_sd = [pe for pe in pe_nodes if pe.properties.get("sub_domain_id") in real_sd_ids]
    assert pe_with_real_sd, (
        "Expected at least one ProportionalityEntry whose sub_domain_id matches a "
        f"real SubDomain id (real ids sample: {sorted(real_sd_ids)[:5]})"
    )


def test_security_objective_instantiated() -> None:
    """Pattern 5: SecurityObjective nodes are instantiated; at least one has a
    real `sub_domain_id` and a non-empty `regulation_code`."""
    graph = build_graph_for_case(CASE3_PATH, PREPROC_ROOT)

    so_nodes = [n for n in graph.nodes if "SecurityObjective" in n.labels]
    assert len(so_nodes) > 0, "Expected SecurityObjective nodes to be instantiated"

    real_sd_ids = _real_subdomain_ids(graph)

    so_with_real_sd = [so for so in so_nodes if so.properties.get("sub_domain_id") in real_sd_ids]
    assert so_with_real_sd, "Expected at least one SO with sub_domain_id matching a real SubDomain"

    so_with_reg = [so for so in so_nodes if so.properties.get("regulation_code")]
    assert so_with_reg, "Expected at least one SO with non-empty regulation_code"


def test_data_subject_instantiated_case3_with_art9_trigger() -> None:
    """Pattern 6: case3 has data_subjects.yaml, so DataSubject nodes are created.

    Since T2-EXP-1 case3 carries one `special_category: true` subject (health
    insurance claimants), TRIGGERS_CLAUSE edges to the GDPR Art. 9 clauses must
    be emitted, and the target clauses must expose an `Art. 9...` article
    reference so T2.6 can cite it.
    """
    graph = build_graph_for_case(CASE3_PATH, PREPROC_ROOT)

    ds_nodes = [n for n in graph.nodes if "DataSubject" in n.labels]
    assert ds_nodes, "Expected DataSubject nodes for case3 (has data_subjects.yaml)"

    special = [ds for ds in ds_nodes if ds.properties.get("special_category")]
    assert special, "Expected at least one special_category=true DataSubject in case3"

    triggers = [e for e in graph.edges if e.rel_type == "TRIGGERS_CLAUSE"]
    assert triggers, (
        "Expected at least one TRIGGERS_CLAUSE edge because at least one "
        "DataSubject has special_category=true"
    )

    art9_clauses = [
        n
        for n in graph.nodes
        if "RegulatoryClause" in n.labels
        and "Art. 9" in str(n.properties.get("article_reference", ""))
    ]
    assert art9_clauses, "Expected GDPR Art. 9 clauses to carry an article_reference"


def test_data_subject_categories_not_exploded_per_character() -> None:
    """A string `data_categories` (case3 style) must not be joined per character."""
    graph = build_graph_for_case(CASE3_PATH, PREPROC_ROOT)

    ds_nodes = [n for n in graph.nodes if "DataSubject" in n.labels]
    for ds in ds_nodes:
        cats = ds.properties.get("data_categories", "")
        assert ",a," not in cats and ",e," not in cats, f"data_categories exploded: {cats[:60]}"


def test_data_subject_absent_case1() -> None:
    """Pattern 6: case1 has no data_subjects.yaml, so DataSubject nodes must NOT
    be created."""
    graph = build_graph_for_case(CASE1_PATH, PREPROC_ROOT)

    ds_nodes = [n for n in graph.nodes if "DataSubject" in n.labels]
    assert (
        ds_nodes == []
    ), f"Expected 0 DataSubject nodes for case1 (no data_subjects.yaml); got {len(ds_nodes)}"
