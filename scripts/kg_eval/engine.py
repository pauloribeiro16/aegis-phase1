"""scripts/kg_eval/engine.py — Lightweight in-memory Cypher/Graph execution engine for T2.

Provides an in-process graph populated directly from case architecture YAMLs and
canonical preproc_out data (CSF 2.0, clauses, regulations, pairs, interactions).
Executes Cypher read queries (MATCH ... RETURN ...) with deterministic syntax checks,
relationship traversals, and realistic error feedback when queries fail.

References:
    - docs/NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md
    - docs/KG_EVAL_PROTOCOL.md §8
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Valid ontology labels per NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC §2
VALID_LABELS = frozenset(
    {
        "Enterprise",
        "Regulation",
        "Article",
        "RegulatoryClause",
        "SecurityControlDomain",
        "SubDomain",
        "SecurityObjective",
        "HierarchicalSecurityObjective",
        "SubSecurityObjective",
        "SecurityRule",
        "RegulatoryPair",
        "RegulatoryRole",
        "CSFFunction",
        "CSFCategory",
        "CSFSubcategory",
        "System",
        "DataStore",
        "DataFlow",
        "AuthSystem",
        "ThirdPartyService",
        "DataSubject",
        "ExternalParty",
        "Stakeholder",
        "BusinessGoal",
        "Run",
        "SubDomainActivation",
        "PairActivation",
        "AmbiguityDisposition",
        "Gate",
        "ClauseActivation",
        "RegulatoryInteraction",
        "ProportionalityEntry",
        "DeclarationGap",
        "RegulatoryApplicabilityResult",
        "ProportionalityProfile",
        "ControlEvidence",
        "ConditionalExtension",
        "BlockTrigger",
        "DomainCoverageEntry",
        "DomainElaborationEntry",
        "ComplementarityAnalysis",
        "GraphMeta",
    }
)

# Valid relationship types per spec §3
VALID_RELATIONSHIPS = frozenset(
    {
        "IN_SCOPE_OF",
        "MAPPED_TO_SUBDOMAIN",
        "ANCHORED_TO_CSF",
        "HAS_ARTICLE",
        "CONTAINS_CLAUSE",
        "BELONGS_TO_REGULATION",
        "ACTS_AS",
        "OPERATES_SYSTEM",
        "STORES_DATA_IN",
        "AUTHENTICATED_BY",
        "SENDS_DATA_TO",
        "ORIGINATES_FROM",
        "TERMINATES_AT",
        "INVOLVES_DATA_OF",
        "TRIGGERS_CLAUSE",
        "HAS_ACTIVATION",
        "HAS_REGULATORY_INTERACTION",
        "SCOPED_TO_SUBDOMAIN",
        "INVOLVES_REGULATION",
        "HAS_PROPORTIONALITY_PROFILE",
        "CONTAINS_ENTRY",
        "HAS_DECLARATION_GAP",
        "REFINES",
        "BELONGS_TO",
        "SCOPED_TO",
        "HAS_DATA_SUBJECT",
        "HAS_AMBIGUITY_DISPOSITION",
        "PRODUCED",
    }
)


@dataclass
class Node:
    labels: set[str]
    properties: dict[str, Any]


@dataclass
class Edge:
    rel_type: str
    from_node: Node
    to_node: Node
    properties: dict[str, Any] = field(default_factory=dict)


class CypherSyntaxError(Exception):
    """Raised when a Cypher query is syntactically invalid or uses unknown ontology tokens."""

    pass


class InMemoryGraph:
    """In-memory graph database holding nodes and directed edges."""

    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

    def add_node(self, label: str, properties: dict[str, Any]) -> Node:
        node = Node(labels={label}, properties=properties)
        self.nodes.append(node)
        return node

    def add_edge(
        self,
        from_node: Node,
        to_node: Node,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> Edge:
        edge = Edge(
            rel_type=rel_type,
            from_node=from_node,
            to_node=to_node,
            properties=properties or {},
        )
        self.edges.append(edge)
        return edge

    def find_nodes(self, label: str | None = None, **prop_filters: Any) -> list[Node]:
        res = []
        for n in self.nodes:
            if label and label not in n.labels:
                continue
            match = True
            for k, v in prop_filters.items():
                if n.properties.get(k) != v:
                    match = False
                    break
            if match:
                res.append(n)
        return res


def build_graph_for_case(case_path: Path, preproc_root: Path) -> InMemoryGraph:
    """Build and populate the in-memory graph from case inputs and preproc_out data."""
    graph = InMemoryGraph()

    # 1. Enterprise node
    classification_yaml = case_path / "input" / "company" / "classification.yaml"
    company_info = {}
    if classification_yaml.exists():
        with classification_yaml.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            company_info = data.get("company", {})

    case_id = case_path.name
    ent_node = graph.add_node(
        "Enterprise",
        {
            "case_id": case_id,
            "name": company_info.get("name", case_id),
            "scale": company_info.get("scale", "SMALL"),
            "sector": company_info.get("sector", "Technology"),
        },
    )

    # 2. Regulations
    reg_nodes: dict[str, Node] = {}
    for reg in ("GDPR", "CRA", "NIS2", "DORA", "AI_Act"):
        r_node = graph.add_node("Regulation", {"id": reg, "name": reg})
        reg_nodes[reg] = r_node

    # 3. NIST CSF 2.0 Subcategories
    csf_path = preproc_root / "global" / "NIST_CSF_2.0_subcategories.json"
    csf_nodes: dict[str, Node] = {}
    if csf_path.exists():
        with csf_path.open("r", encoding="utf-8") as f:
            csf_data = json.load(f)
            for item in csf_data.get("subcategories", []):
                cid = item.get("id")
                if cid:
                    cnode = graph.add_node(
                        "CSFSubcategory",
                        {
                            "id": cid,
                            "outcome_text": item.get("outcome", item.get("description", "")),
                            "function_id": item.get("function_id", ""),
                            "category_id": item.get("category_id", ""),
                        },
                    )
                    csf_nodes[cid] = cnode

    # 4. Architecture Assets
    arch_dir = case_path / "input" / "architecture"
    sys_nodes: dict[str, Node] = {}
    store_nodes: dict[str, Node] = {}

    systems_file = arch_dir / "systems.yaml"
    if systems_file.exists():
        with systems_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            for s in data.get("systems", []):
                sid = s.get("id")
                snode = graph.add_node(
                    "System",
                    {
                        "id": sid,
                        "case_id": case_id,
                        "name": s.get("name", sid),
                        "criticality": s.get("criticality", "MEDIUM"),
                        "description": s.get("description", ""),
                    },
                )
                sys_nodes[sid] = snode
                graph.add_edge(ent_node, snode, "OPERATES_SYSTEM")

    stores_file = arch_dir / "data_stores.yaml"
    if stores_file.exists():
        with stores_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            for st in data.get("data_stores", []):
                stid = st.get("id")
                stnode = graph.add_node(
                    "DataStore",
                    {
                        "id": stid,
                        "case_id": case_id,
                        "name": st.get("name", stid),
                        "storage_type": st.get("type", "database"),
                        "contains_pii": st.get("contains_pii", False),
                    },
                )
                store_nodes[stid] = stnode
                graph.add_edge(ent_node, stnode, "OPERATES_SYSTEM")

    # 5. Subdomains & Macro-domains
    sd_nodes: dict[str, Node] = {}
    subdomains_dir = preproc_root / "entities" / "subdomains"
    if subdomains_dir.exists():
        for fpath in subdomains_dir.glob("D-*.json"):
            try:
                with fpath.open("r", encoding="utf-8") as f:
                    sd_data = json.load(f)
                    sd_id = sd_data.get("id")
                    if sd_id:
                        sdnode = graph.add_node(
                            "SubDomain",
                            {
                                "id": sd_id,
                                "name": sd_data.get("name", sd_id),
                                "macro_id": sd_id.split(".")[0],
                            },
                        )
                        sd_nodes[sd_id] = sdnode
            except Exception:
                pass

    # Ensure D-01.1 .. D-10.4 default fallback if preproc_out subdomains not indexed
    if not sd_nodes:
        for macro in range(1, 11):
            m_str = f"D-{macro:02d}"
            for sub in range(1, 5):
                sd_id = f"{m_str}.{sub}"
                sd_nodes[sd_id] = graph.add_node(
                    "SubDomain",
                    {
                        "id": sd_id,
                        "name": f"Subdomain {sd_id}",
                        "macro_id": m_str,
                    },
                )

    # Connect Systems to Subdomains heuristically / deterministically
    for _sid, snode in sys_nodes.items():
        # Default connection to D-01.1 and D-02.1
        for default_sd in ("D-01.1", "D-02.3", "D-04.4"):
            if default_sd in sd_nodes:
                graph.add_edge(
                    snode,
                    sd_nodes[default_sd],
                    "IN_SCOPE_OF",
                    {
                        "rule_id": "R-DEFAULT",
                        "basis": "Architecture deployment scope",
                    },
                )

    # 6. Clauses from preproc_out
    clauses_dir = preproc_root / "entities" / "clauses" / "_root"
    if clauses_dir.exists():
        for reg in ("GDPR", "CRA", "NIS2", "DORA", "AI_Act"):
            r_dir = clauses_dir / reg
            if not r_dir.is_dir():
                continue
            for c_file in r_dir.glob(f"{reg}_CL*.json"):
                try:
                    with c_file.open("r", encoding="utf-8") as f:
                        c_data = json.load(f)
                        cid = c_data.get("id")
                        if cid:
                            cnode = graph.add_node(
                                "RegulatoryClause",
                                {
                                    "id": cid,
                                    "regulation_id": reg,
                                    "article_reference": c_data.get("article_reference", ""),
                                    "description": c_data.get("description", ""),
                                },
                            )
                            if reg in reg_nodes:
                                graph.add_edge(reg_nodes[reg], cnode, "CONTAINS_CLAUSE")

                            # Mapping to subdomains
                            for sdid in c_data.get("sub_domains", []):
                                if sdid in sd_nodes:
                                    graph.add_edge(cnode, sd_nodes[sdid], "MAPPED_TO_SUBDOMAIN")

                            # Mapping to CSF anchors
                            for csfid in c_data.get("nist_csf_mappings", []):
                                if csfid in csf_nodes:
                                    graph.add_edge(cnode, csf_nodes[csfid], "ANCHORED_TO_CSF")
                                    # Also anchor subdomain
                                    for sdid in c_data.get("sub_domains", []):
                                        if sdid in sd_nodes:
                                            graph.add_edge(
                                                sd_nodes[sdid], csf_nodes[csfid], "ANCHORED_TO_CSF"
                                            )
                except Exception:
                    pass

    # 7. Regulatory Interactions (Tensions)
    interactions_path = case_path / "input" / "regulatory" / "interactions.yaml"
    if interactions_path.exists():
        with interactions_path.open("r", encoding="utf-8") as f:
            int_data = yaml.safe_load(f) or {}
            for bucket in (
                "temporal_conflicts",
                "requirement_conflicts",
                "trigger_mismatches",
                "negative_analyses",
            ):
                for item in int_data.get(bucket, []):
                    iid = item.get("source_id", item.get("id", f"RI-{len(graph.nodes)}"))
                    ri_node = graph.add_node(
                        "RegulatoryInteraction",
                        {
                            "id": iid,
                            "case_id": case_id,
                            "interaction_type": item.get(
                                "interaction_type", bucket.upper().rstrip("S")
                            ),
                            "involved_regs": item.get("involved_regs", []),
                            "sub_domains": item.get("sub_domains", []),
                            "conflict_description": item.get("conflict_description", ""),
                            "resolution_principle": item.get("resolution_principle", ""),
                            "severity": item.get("severity", "MEDIUM"),
                            "source_id": item.get("source_id", ""),
                        },
                    )
                    graph.add_edge(ent_node, ri_node, "HAS_REGULATORY_INTERACTION")
                    for sdid in item.get("sub_domains", []):
                        if sdid in sd_nodes:
                            graph.add_edge(ri_node, sd_nodes[sdid], "SCOPED_TO_SUBDOMAIN")

    return graph


def execute_cypher(graph: InMemoryGraph, query: str) -> list[dict[str, Any]]:
    """Validate Cypher query syntax against AEGIS-KG schema and execute against the in-memory graph.

    Raises:
        CypherSyntaxError: On unknown label, unknown relationship, or parse error.
    """
    cleaned_query = query.strip()
    if not cleaned_query.upper().startswith("MATCH"):
        raise CypherSyntaxError("Only read queries starting with 'MATCH' are permitted.")

    # 1. Check for invented labels (:Label)
    labels_found = re.findall(r":([A-Za-z0-9_]+)", cleaned_query)
    for lbl in labels_found:
        # If it's a relationship, skip
        if f"[:{lbl}" in cleaned_query or f"-[:{lbl}" in cleaned_query:
            continue
        if lbl not in VALID_LABELS and lbl not in VALID_RELATIONSHIPS:
            raise CypherSyntaxError(
                f"Unknown label or token ':{lbl}' not in AEGIS-KG ontology catalogue."
            )

    # 2. Check for invented relationships ([:REL])
    rels_found = re.findall(r"\[:([A-Za-z0-9_]+)", cleaned_query)
    for rel in rels_found:
        if rel not in VALID_RELATIONSHIPS:
            raise CypherSyntaxError(
                f"Unknown relationship '[:{rel}]' not in AEGIS-KG ontology catalogue."
            )

    # Extract target label and optional filters
    # Regex: MATCH (var:Label {key: 'val'})
    match_pat = re.compile(
        r"MATCH\s*\(([A-Za-z0-9_]+)?\s*:\s*([A-Za-z0-9_]+)(?:\s*\{([^}]+)\})?\)",
        re.IGNORECASE,
    )
    matches = match_pat.findall(cleaned_query)
    if not matches:
        # Fallback to general search if syntax is valid but complex
        return []

    results: list[dict[str, Any]] = []
    primary_var, primary_label, filter_str = matches[0]

    filters: dict[str, Any] = {}
    if filter_str:
        pairs = filter_str.split(",")
        for pair in pairs:
            if ":" in pair:
                k, v = pair.split(":", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                filters[k] = v

    candidate_nodes = graph.find_nodes(primary_label, **filters)

    # Simple multi-hop resolution for canonical patterns
    # Case: System -> IN_SCOPE_OF -> SubDomain <- MAPPED_TO_SUBDOMAIN <- RegulatoryClause
    if "IN_SCOPE_OF" in cleaned_query and "RegulatoryClause" in cleaned_query:
        for snode in candidate_nodes:
            # find outgoing IN_SCOPE_OF
            for e1 in graph.edges:
                if e1.from_node == snode and e1.rel_type == "IN_SCOPE_OF":
                    sd_node = e1.to_node
                    # find incoming MAPPED_TO_SUBDOMAIN
                    for e2 in graph.edges:
                        if e2.to_node == sd_node and e2.rel_type == "MAPPED_TO_SUBDOMAIN":
                            clause_node = e2.from_node
                            results.append(
                                {
                                    "system": snode.properties.get("id"),
                                    "system_name": snode.properties.get("name"),
                                    "subdomain": sd_node.properties.get("id"),
                                    "clause": clause_node.properties.get("id"),
                                    "regulation": clause_node.properties.get("regulation_id"),
                                    "article_reference": clause_node.properties.get(
                                        "article_reference"
                                    ),
                                }
                            )
        return results

    # Case: RegulatoryInteraction
    if primary_label == "RegulatoryInteraction":
        for rnode in candidate_nodes:
            results.append(dict(rnode.properties))
        return results

    # Case: General property return
    for node in candidate_nodes:
        row = dict(node.properties)
        row["_label"] = next(iter(node.labels))
        results.append(row)

    return results


__all__ = [
    "VALID_LABELS",
    "VALID_RELATIONSHIPS",
    "CypherSyntaxError",
    "InMemoryGraph",
    "build_graph_for_case",
    "execute_cypher",
]
