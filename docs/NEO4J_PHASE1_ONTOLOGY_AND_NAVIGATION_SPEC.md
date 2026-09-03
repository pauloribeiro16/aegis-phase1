# AEGIS-KG Phase 1 — Neo4j Ontology & LLM Navigation Specification

**Document ID:** `AEGIS-DOC-NEO4J-ONTOLOGY-001`  
**Status:** DRAFT / PENDING PEER MODEL REVIEW  
**Author:** Antigravity (Pair Programming Session)  
**Date:** 2026-09-03  
**Target Graph Database:** Neo4j (Bolt: `bolt://localhost:7688`, HTTP: `http://localhost:7475`)  
**Target Repository:** `aegis-phase1`  
**Audience:** Peer LLMs (Autonomous Graph Navigation Agents), Knowledge Engineers, Evaluators.

---

## 1. Scope & Objective

This document defines the **formal Labeled Property Graph (LPG) Ontology in Neo4j** for Phase 1 of AEGIS-KG, together with a **precise, step-by-step Navigation Playbook for LLM Agents**.

The goal is two-fold:
1. **Exhaustive Data Modeling:** Capture 100% of Phase 1 entities (regulations, articles, 331 clauses, 38 subdomains, 106 NIST CSF 2.0 subcategories, company context, IT systems, datastores, dataflows, authentication mechanisms, and regulatory tensions).
2. **Deterministic Agent Navigation:** Provide unambiguous graph query templates (Cypher) and traversal paths so that an LLM agent never has to "guess" how to query the graph, completely eliminating hallucinations and generic compliance outputs.

---

## 2. Neo4j Graph Metamodel (Ontology Schema)

### 2.1 Node Labels & Properties

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         NODE TAXONOMY (14 LABELS)                                       │
├───────────────────────────────┬─────────────────────────────────────────┬───────────────────────────────┤
│ 1. Legal / Regulatory Core    │ 2. Taxonomy / Controls                  │ 3. Enterprise Architecture    │
│   • :Regulation               │   • :MacroDomain                        │   • :Enterprise               │
│   • :Article                  │   • :SubDomain                          │   • :System                   │
│   • :Clause                   │   • :CSFSubcategory                     │   • :DataStore                │
│   • :LegalRole                │                                         │   • :DataFlow                 │
│                               │                                         │   • :AuthSystem               │
│                               │                                         │   • :ThirdPartyService        │
├───────────────────────────────┴─────────────────────────────────────────┴───────────────────────────────┤
│ 4. Evaluative / Friction State                                                                          │
│   • :RegulatoryTension                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Detailed Node Property Specifications:

1. **`:Enterprise`** (Company Context Root)
   - `case_id` (String, PK): e.g. `"case1-tinytask"`, `"case2-secureborder"`, `"case3-omnibank"`
   - `name` (String): e.g. `"OmniBank Financial Systems S.A."`
   - `sector` (String): e.g. `"Banking & Financial Services"`
   - `scale` (String, Enum): `MICRO` | `SMALL` | `MEDIUM` | `LARGE`
   - `employees` (Integer): e.g. `5000`
   - `revenue_eur` (Float): e.g. `1500000000.0`
   - `security_fte` (Float): e.g. `100.0`
   - `tier` (String, Enum): `LOW` | `MEDIUM` | `HIGH`
   - `jurisdiction` (String): e.g. `"Germany"`

2. **`:Regulation`** (EU Legal Instrument)
   - `id` (String, PK): Canonical token: `GDPR` | `CRA` | `NIS2` | `DORA` | `AI_Act`
   - `title` (String): Official EU journal title
   - `effective_date` (String, ISO-8601): e.g. `"2025-01-17"`
   - `celex_id` (String): EU legal registry ID

3. **`:Article`** (Regulatory Chapter / Section)
   - `id` (String, PK): e.g. `"DORA_Art. 9"`, `"AI_Act_Art. 14"`
   - `regulation_id` (String, FK): e.g. `"DORA"`
   - `article_number` (String): e.g. `"9"`
   - `title` (String): e.g. `"Protection and Prevention"`

4. **`:Clause`** (Atomic Prescriptive Obligation — 331 in Catalog)
   - `id` (String, PK): e.g. `"DORA-CL14"`, `"GDPR-CL06"`, `"AI_Act-CL014"`
   - `regulation_id` (String, FK): e.g. `"DORA"`
   - `article_id` (String, FK): e.g. `"DORA_Art. 9"`
   - `text` (String): Normalized clause wording
   - `mandatory_level` (String, Enum): `SHALL` | `MUST` | `SHOULD`
   - `normative_strength` (Float): `0.5` (partial) to `1.0` (substantive)
   - `activation_predicate` (String): e.g. `"processes_personal_data == true"`

5. **`:LegalRole`** (Jurisdictional Persona)
   - `id` (String, PK): e.g. `"financial_entity"`, `"controller"`, `"manufacturer"`, `"deployer"`, `"essential_entity"`
   - `description` (String): Statutory definition

6. **`:MacroDomain`** (Top-level taxonomy — 10 Domains)
   - `id` (String, PK): `"D-01"` through `"D-10"`
   - `name` (String): e.g. `"Data Protection & Cryptography"`

7. **`:SubDomain`** (Atomic Control Subdomain — 38 Subdomains)
   - `id` (String, PK): e.g. `"D-01.1"`, `"D-04.3"`, `"D-09.4"`
   - `macro_id` (String, FK): e.g. `"D-01"`
   - `name` (String): e.g. `"Data Encryption at Rest"`
   - `description` (String): Technical scope description

8. **`:CSFSubcategory`** (NIST CSF 2.0 Anchor — Exactly 106 active)
   - `id` (String, PK): e.g. `"PR.DS-01"`, `"GV.OC-01"`, `"DE.CM-01"`
   - `function` (String): `GV` | `ID` | `PR` | `DE` | `RS` | `RC`
   - `category` (String): e.g. `"PR.DS"`
   - `text` (String): NIST CSF official outcome statement

9. **`:System`** (Software Application / Hardware Infrastructure)
   - `id` (String, PK): Scoped ID, e.g. `"case3:SYS-CBS"`, `"case3:SYS-CREDITAI"`
   - `case_id` (String, FK): e.g. `"case3-omnibank"`
   - `name` (String): e.g. `"Core Banking System (Temenos T24)"`
   - `type` (String): e.g. `"core_banking_mainframe"`, `"ai_ml_platform"`
   - `tech_stack` (String): e.g. `"IBM z/OS, DB2, COBOL"`
   - `criticality` (String, Enum): `low` | `medium` | `high` | `critical`
   - `hosts_personal_data` (Boolean): `true` | `false`

10. **`:DataStore`** (Data Repositories & Storage Systems)
    - `id` (String, PK): e.g. `"case3:STORE-DB2"`, `"case3:STORE-KAFKA"`
    - `case_id` (String, FK): `"case3-omnibank"`
    - `name` (String): e.g. `"Mainframe DB2 Accounts Ledger"`
    - `storage_type` (String): `"relational_db"` | `"event_stream"` | `"worm_archive"`
    - `contains_pii` (Boolean): `true` | `false`
    - `contains_financial` (Boolean): `true` | `false`
    - `encryption_at_rest` (Boolean): `true` | `false`

11. **`:DataFlow`** (Network & Payload Transits)
    - `id` (String, PK): e.g. `"case3:FLOW-01"`
    - `case_id` (String, FK): `"case3-omnibank"`
    - `name` (String): e.g. `"Core to Payment Gateway Transaction Flow"`
    - `source_system_id` (String, FK): `"case3:SYS-CBS"`
    - `dest_system_id` (String, FK): `"case3:SYS-PAYMENTS"`
    - `protocol` (String): e.g. `"mTLS / gRPC"`
    - `is_cross_border` (Boolean): `false`

12. **`:AuthSystem`** (Identity, Token & Cryptographic Hardware)
    - `id` (String, PK): e.g. `"case3:AS-HSM"`, `"case3:AS-MFA"`
    - `case_id` (String, FK): `"case3-omnibank"`
    - `name` (String): e.g. `"Thales payShield 10K HSM"`
    - `auth_type` (String): `"hardware_security_module"` | `"fido2_webauthn"`
    - `fips_level` (String): e.g. `"140-2 Level 3"`

13. **`:ThirdPartyService`** (SaaS / Cloud / External Gateways)
    - `id` (String, PK): e.g. `"case3:CS-AWS"`, `"case3:CS-SWIFT"`
    - `case_id` (String, FK): `"case3-omnibank"`
    - `provider` (String): e.g. `"Amazon Web Services"`, `"SWIFT SCRL"`
    - `jurisdiction` (String): e.g. `"EU (Frankfurt)"`, `"Belgium"`
    - `critical_third_party_dora` (Boolean): `true` | `false`

14. **`:RegulatoryTension`** (Identified Frictions between Regs)
    - `id` (String, PK): e.g. `"case3:TENS-D04.3-GDPR-DORA"`
    - `case_id` (String, FK): `"case3-omnibank"`
    - `subdomain_id` (String, FK): `"D-04.3"`
    - `regulation_a` (String): `"GDPR"`
    - `regulation_b` (String): `"DORA"`
    - `friction_summary` (String): Right to erasure vs mandatory operational forensic log retention
    - `severity` (String, Enum): `HIGH` | `MEDIUM` | `LOW`

---

### 2.2 Relationship Types (Edges)

| Source Label | Edge Type | Target Label | Properties |
|---|---|---|---|
| `(:Enterprise)` | **`[:SUBJECT_TO]`** | `(:Regulation)` | `applicable: true`, `role: String`, `rationale: String` |
| `(:Enterprise)` | **`[:ASSUMES_ROLE]`** | `(:LegalRole)` | `justification: String` |
| `(:Regulation)` | **`[:HAS_ARTICLE]`** | `(:Article)` | — |
| `(:Article)` | **`[:CONTAINS_CLAUSE]`** | `(:Clause)` | — |
| `(:Clause)` | **`[:MAPPED_TO_SUBDOMAIN]`** | `(:SubDomain)` | `confidence: "HIGH"`, `normative_strength: Float` |
| `(:SubDomain)` | **`[:ANCHORED_TO_CSF]`** | `(:CSFSubcategory)` | `mapping_type: "DIRECT"` |
| `(:Enterprise)` | **`[:OPERATES_SYSTEM]`** | `(:System)` | `owner: String` |
| `(:System)` | **`[:STORES_DATA_IN]`** | `(:DataStore)` | `access_type: "READ_WRITE"` |
| `(:System)` | **`[:SENDS_DATA_TO]`** | `(:System)` | `dataflow_id: String`, `protocol: String` |
| `(:System)` | **`[:AUTHENTICATED_BY]`** | `(:AuthSystem)` | `enforced: true` |
| `(:System)` | **`[:OUTSOURCED_TO]`** | `(:ThirdPartyService)` | `sla_hours: Integer` |
| `(:System)` | **`[:IN_SCOPE_OF]`** | `(:SubDomain)` | `proportionality_tier: "RIGOROUS"` |
| `(:Clause)` | **`[:IN_TENSION_WITH]`** | `(:Clause)` | `tension_id: String`, `contradiction_type: String` |

---

## 3. LLM Agent Navigation Playbook (Instructions for Models)

When an autonomous LLM agent is tasked with evaluating compliance, finding gaps, or resolving tensions, it **MUST** navigate the graph following these strict query patterns.

### 3.1 Rule of Case Isolation (No Multi-Case Leakage)
> **Mandatory Rule:** Every traversal starting from an architectural entity must filter by `case_id`. Never execute an unbound `MATCH (s:System)`. Always scope: `MATCH (e:Enterprise {case_id: $case_id})-[:OPERATES_SYSTEM]->(s:System)`.

---

### 3.2 Traversal Pattern 1: Determine Applicable Scope & Legal Mandates
**Agent Goal:** Find which regulations apply to the company, under which statutory roles, and how many active clauses each imposes.

```cypher
MATCH (e:Enterprise {case_id: $case_id})-[st:SUBJECT_TO]->(r:Regulation)
MATCH (r)-[:HAS_ARTICLE]->(a:Article)-[:CONTAINS_CLAUSE]->(c:Clause)
RETURN r.id AS regulation,
       st.role AS legal_role,
       count(DISTINCT a) AS article_count,
       count(DISTINCT c) AS clause_count
ORDER BY clause_count DESC;
```
*Agent Action:* Read the `legal_role`. If evaluating `DORA`, the role must be `financial_entity`. If evaluating `CRA`, it must be `manufacturer`.

---

### 3.3 Traversal Pattern 2: Asset-to-Clause Compliance Grounding
**Agent Goal:** When writing about a specific subdomain (e.g. `D-01.1` Encryption at Rest), discover which real systems of the company fall under that subdomain, which datastores they use, and which exact legal clauses apply.

```cypher
MATCH (sd:SubDomain {id: $subdomain_id})
MATCH (c:Clause)-[:MAPPED_TO_SUBDOMAIN]->(sd)
MATCH (c)<-[:CONTAINS_CLAUSE]-(a:Article)<-[:HAS_ARTICLE]-(r:Regulation)
MATCH (e:Enterprise {case_id: $case_id})-[:OPERATES_SYSTEM]->(s:System)-[:IN_SCOPE_OF]->(sd)
OPTIONAL MATCH (s)-[:STORES_DATA_IN]->(ds:DataStore)
RETURN sd.name AS subdomain,
       collect(DISTINCT r.id + ': ' + c.id + ' (' + a.id + ')') AS legal_clauses,
       collect(DISTINCT s.id + ' [' + s.name + ' - ' + s.criticality + ']') AS affected_systems,
       collect(DISTINCT ds.id + ' [' + ds.storage_type + ']') AS affected_stores;
```
*Agent Action:* When drafting the evaluation prose, the agent **MUST** explicitly cite the IDs returned in `affected_systems` and `affected_stores`. Any output lacking these exact tokens violates Quality Gate A.

---

### 3.4 Traversal Pattern 3: Identifying & Resolving Regulatory Tensions
**Agent Goal:** Find conflicting regulatory requirements where two active regulations place incompatible mandates on the same subdomain.

```cypher
MATCH (sd:SubDomain {id: $subdomain_id})
MATCH (c1:Clause)-[:MAPPED_TO_SUBDOMAIN]->(sd)
MATCH (c2:Clause)-[:MAPPED_TO_SUBDOMAIN]->(sd)
MATCH (c1)-[rel:IN_TENSION_WITH]->(c2)
MATCH (c1)<-[:CONTAINS_CLAUSE]-(:Article)<-[:HAS_ARTICLE]-(r1:Regulation)
MATCH (c2)<-[:CONTAINS_CLAUSE]-(:Article)<-[:HAS_ARTICLE]-(r2:Regulation)
RETURN sd.id AS subdomain,
       r1.id + ' (' + c1.id + ')' AS regulation_source_1,
       c1.text AS text_1,
       r2.id + ' (' + c2.id + ')' AS regulation_source_2,
       c2.text AS text_2,
       rel.contradiction_type AS conflict_nature;
```
*Agent Action:* The agent must take `text_1` and `text_2` and produce the tripartite compromise control:
1. *Friction Point:* What one law demands vs what the other forbids.
2. *Operational Risk:* What breaks if either is prioritized blindly.
3. *Compromise Technical Mechanism:* The concrete engineering control (e.g. encrypted write-once audit vault with cryptographic erasure keys).

---

### 3.5 Traversal Pattern 4: NIST CSF 2.0 Control Alignment
**Agent Goal:** Retrieve the exact NIST CSF 2.0 subcategories that anchor this subdomain.

```cypher
MATCH (sd:SubDomain {id: $subdomain_id})-[:ANCHORED_TO_CSF]->(csf:CSFSubcategory)
RETURN sd.id AS subdomain,
       csf.id AS csf_code,
       csf.function AS function,
       csf.category AS category,
       csf.text AS outcome_statement;
```
*Agent Action:* Ensure the technical control recommendations align with `csf_code` (e.g. `PR.DS-01`). External frameworks (ISO, CIS) are strictly forbidden.

---

## 4. Graph Navigation Decision Flow for Autonomous Agents

```
                        [AGENT RECEIVES TASK]
                                  │
                                  ▼
                  Query 1: Scope & Applicable Roles
            (Check :Enterprise -[:SUBJECT_TO]-> :Regulation)
                                  │
                                  ▼
                  Query 2: Active Subdomains for Case
              (Filter Subdomains where Clause count >= 1)
                                  │
                                  ▼
        ┌───────────────────────────────────────────────────┐
        │ For Each Active Subdomain ($subdomain_id):        │
        ├───────────────────────────────────────────────────┤
        │ 1. Fetch Legal Clauses + NIST CSF Anchors         │
        │ 2. Fetch Company Systems (:System -[:IN_SCOPE_OF])│
        │ 3. Check for [:IN_TENSION_WITH] conflicts         │
        │ 4. Synthesize tailored assessment citing IDs      │
        └───────────────────────────────────────────────────┘
                                  │
                                  ▼
                  Query 3: Verify Grounding Gate
          (Ensure all SYS-*, STORE-*, CL-* IDs are cited)
                                  │
                                  ▼
                         [EMIT FINAL DOC]
```

---

## 5. Reviewer / Model Feedback Checklist

When other LLM models review this ontology, they should evaluate:
1. **Expressiveness:** Are there any compliance artifacts in Docs 04..07b that cannot be expressed with these 14 labels and 13 relationships?
2. **Cypher Ergonomics:** Are the traversal paths indexed properly (e.g., `INDEX ON :System(case_id)`, `INDEX ON :Clause(id)`) to ensure sub-second graph response times?
3. **Agent Clarity:** Are the 4 traversal patterns sufficient for an autonomous agent with a Cypher tool to answer all Phase 1 compliance questions without manual prompt intervention?
