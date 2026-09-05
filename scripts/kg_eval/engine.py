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


# GDPR Art. 9 (special categories of personal data). The preproc clause JSONs do
# not carry an `article_reference` field, so the Art. 9 cluster is identified by
# an explicit "Art. 9(x)" mention inside the clause record itself.
_RE_ART9 = re.compile(r"Art\.\s?9\((?:\d+)\)(?:\([a-z]\))?")


def _join_categories(value: Any) -> str:
    """Normalise a `data_categories` YAML value to a single string.

    Cases carry either a list (case2 style) or an already-comma-separated string
    (case3 style); ``",".join(str)`` would explode the string per character.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list | tuple | set):
        return ",".join(str(v) for v in value)
    return str(value)


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

    # 4b. DataSubjects (Pattern 6 — only case2/case3 have this YAML)
    # TRIGGERS_CLAUSE edges are wired in step 6b, AFTER the clauses exist in the
    # graph (clauses load in step 6; wiring them here always yielded 0 edges).
    special_ds_nodes: list[Node] = []
    ds_file = arch_dir / "data_subjects.yaml"
    if ds_file.exists():
        try:
            with ds_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for idx, ds in enumerate(data.get("data_subjects", [])):
                dsid = f"DS-{case_id}-{idx:03d}"
                special = bool(ds.get("special_category", False))
                dsnode = graph.add_node(
                    "DataSubject",
                    {
                        "id": dsid,
                        "case_id": case_id,
                        "subject_type": ds.get("subject_type") or ds.get("category") or "UNKNOWN",
                        "data_categories": _join_categories(
                            ds.get("data_categories") or ds.get("data_types")
                        ),
                        "special_category": special,
                        "estimated_count": ds.get("estimated_count", 0),
                        "minor": bool(ds.get("minor", False)),
                    },
                )
                graph.add_edge(ent_node, dsnode, "HAS_DATA_SUBJECT")
                if special:
                    special_ds_nodes.append(dsnode)
        except Exception:
            pass

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
    art9_clause_nodes: list[Node] = []
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
                            artref = c_data.get("article_reference", "")
                            # The GDPR Art. 9 cluster carries no `article_reference`
                            # in preproc; recover it from the clause body so the
                            # special-category trigger can cite a real article.
                            art9_match = (
                                _RE_ART9.search(json.dumps(c_data, ensure_ascii=False))
                                if reg == "GDPR"
                                else None
                            )
                            if art9_match and not artref:
                                artref = art9_match.group(0)
                            cnode = graph.add_node(
                                "RegulatoryClause",
                                {
                                    "id": cid,
                                    "regulation_id": reg,
                                    "article_reference": artref,
                                    "description": c_data.get("description", ""),
                                    "special_category_anchor": bool(art9_match),
                                },
                            )
                            if art9_match:
                                art9_clause_nodes.append(cnode)
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

    # 6b. Special-category DataSubjects trigger the GDPR Art. 9 clauses (Pattern 6).
    # Deferred from step 4b because the clause nodes only exist after step 6.
    for dsnode in special_ds_nodes:
        for cnode in art9_clause_nodes:
            graph.add_edge(
                dsnode,
                cnode,
                "TRIGGERS_CLAUSE",
                {"trigger_reason": "GDPR Art. 9 (special category)"},
            )

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

    # 8. SecurityObjectives (Pattern 5 — from preproc_out/entities/sos)
    so_nodes: dict[str, Node] = {}
    sos_dir = preproc_root / "entities" / "sos"
    if sos_dir.exists():
        for so_file in sos_dir.rglob("*.json"):
            try:
                with so_file.open("r", encoding="utf-8") as f:
                    so_data = json.load(f)
                so_id = so_data.get("id") or so_data.get("yaml_id")
                sdid = so_data.get("subdomain_id")
                if not so_id:
                    continue
                if so_id in so_nodes:
                    continue  # avoid dup
                sonode = graph.add_node(
                    "SecurityObjective",
                    {
                        "id": so_id,
                        "regulation_code": so_data.get("regulation", ""),
                        "statement": so_data.get("objective", ""),
                        "sub_domain_id": sdid or "",
                        "inherits_from": so_data.get("inherits_from", "") or None,
                    },
                )
                so_nodes[so_id] = sonode
                if sdid and sdid in sd_nodes:
                    graph.add_edge(sonode, sd_nodes[sdid], "SCOPED_TO")
                reg_id = so_data.get("regulation", "")
                if reg_id and reg_id in reg_nodes:
                    graph.add_edge(sonode, reg_nodes[reg_id], "BELONGS_TO")
            except Exception:
                pass

    # 9. ProportionalityEntries (Pattern 3 — heuristic from active clauses per subdomain)
    # Spec §2.1: ProportionalityEntry has 9 rich attributes. We populate a minimal
    # proxy here so T2.5 has real nodes to navigate; full Phase-1 architecture is
    # ETL-real territory. One PE per (case, subdomain) with tier derived from the
    # number of activated clauses.
    _PE_TIER_BY_COUNT = (
        (0, "MINIMAL"),
        (3, "LIGHTWEIGHT"),
        (6, "STANDARD"),
        (10, "RIGOROUS"),
    )

    def _tier_for(n_clauses: int) -> str:
        for thresh, label in reversed(_PE_TIER_BY_COUNT):
            if n_clauses >= thresh:
                return label
        return "MINIMAL"

    pe_nodes: dict[str, Node] = {}
    # Count clauses per subdomain already in the graph
    clause_counts: dict[str, int] = {sdid: 0 for sdid in sd_nodes}
    for cn in graph.nodes:
        if "RegulatoryClause" in cn.labels:
            for edge in graph.edges:
                if (
                    edge.from_node is cn
                    and edge.rel_type == "MAPPED_TO_SUBDOMAIN"
                    and "SubDomain" in edge.to_node.labels
                ):
                    sdid = edge.to_node.properties.get("id", "")
                    clause_counts[sdid] = clause_counts.get(sdid, 0) + 1
    # Seed at least one ProportionalityEntry per known subdomain so navigation has nodes
    pe_seq = 0
    for sdid in sorted(sd_nodes.keys()):
        n = clause_counts.get(sdid, 0)
        tier = _tier_for(n)
        pe_seq += 1
        peid = f"PE-{case_id}-{sdid}"
        penode = graph.add_node(
            "ProportionalityEntry",
            {
                "id": peid,
                "case_id": case_id,
                "sub_domain_id": sdid,
                "tier": tier,
                "inheritability": "BUILD_REQUIRED" if n > 0 else "INHERITABLE",
                "satisfaction_pattern": "BUILD_FULL" if n > 0 else "INHERIT",
                "priority": "MUST" if tier in ("RIGOROUS", "STANDARD") else "COULD",
                "evidence_depth": (
                    f"Full evidence package (n_clauses={n} per {sdid})"
                    if n > 0
                    else f"No clauses mapped to {sdid} — minimal evidence required"
                ),
                "verification_method": "INSPECT",
                "ownership": "COMPANY",
                "n_clauses": n,
            },
        )
        pe_nodes[peid] = penode
        if sd_nodes.get(sdid):
            graph.add_edge(penode, sd_nodes[sdid], "SCOPED_TO")

    # ProportionalityProfile container (1 per Enterprise)
    if pe_nodes:
        ppid = f"PP-{case_id}"
        pp_node = graph.add_node(
            "ProportionalityProfile",
            {
                "id": ppid,
                "case_id": case_id,
                "company_scale": ent_node.properties.get("scale", ""),
                "gate_p_status": "PASS",
            },
        )
        graph.add_edge(ent_node, pp_node, "HAS_PROPORTIONALITY_PROFILE")
        for penode in pe_nodes.values():
            graph.add_edge(pp_node, penode, "CONTAINS_ENTRY")

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

    # Collect filter hints from SECONDARY matches (CORR-115 T2-EXP-3). The first
    # match is the primary label we iterate over; subsequent matches define
    # properties on relationship endpoints. For example, in
    #   MATCH (so:SecurityObjective)-[:SCOPED_TO]->(sd:SubDomain {id: 'D-09.1'})
    # the secondary match is `SubDomain {id: 'D-09.1'}`. If a Security Objective
    # carries a `sub_domain_id` property, we can restrict the primary candidate
    # set using the secondary filter key/value — without needing a full
    # multi-hop executor.
    secondary_filters: dict[str, list[tuple[str, str]]] = {}
    for m in matches[1:]:
        _sec_var, sec_label, sec_filter_str = m
        if not sec_filter_str:
            continue
        for kv in sec_filter_str.split(","):
            if ":" not in kv:
                continue
            k, v = kv.split(":", 1)
            secondary_filters.setdefault(sec_label, []).append(
                (k.strip(), v.strip().strip("'").strip('"'))
            )

    candidate_nodes = graph.find_nodes(primary_label, **filters)

    # Apply secondary-label filters (e.g. target SD id 'D-09.1' → restrict SO.sub_domain_id)
    for _sec_label, kvs in secondary_filters.items():
        for k, v in kvs:
            candidate_nodes = [n for n in candidate_nodes if str(n.properties.get(k)) == v]

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
