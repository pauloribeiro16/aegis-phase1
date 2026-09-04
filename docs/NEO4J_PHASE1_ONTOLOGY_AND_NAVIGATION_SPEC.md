# AEGIS-KG Phase 1 — Neo4j Unified Ontology & LLM Navigation Specification

**Document ID:** `AEGIS-DOC-NEO4J-ONTOLOGY-002`
**Status:** DRAFT v3 — review conflicts resolved (see Change Note)
**Author:** Antigravity (Pair Programming Session) + ZCode review (2026-09-03)
**Date:** 2026-09-03 (v3 — review-driven refinements)
**Source of Truth:** `methodology-00/diagrams/Class_Models/phase1_contextual_definition.md` (v1.1, 2026-07-13)
**Target Graph Database:** Neo4j (Bolt: `bolt://localhost:7688`, HTTP: `http://localhost:7475`)
**Repository:** `aegis-phase1`
**Audience:** Peer LLMs, Knowledge Engineers, ETL Authors, Academic Reviewers.

> **v3 Change Note:** Supersedes v2. Review findings (ZCode 2026-09-03) resolved:
> (1) ghost entities `RegulatoryObligation`, `StrategicImplication`, `ImplementationMapping` removed (Phase 2 scope, moved to §7); (2) **ambiguity gap closed** — `(:RegulatoryPair)` Tier 1 + run-scoped `(:PairActivation)` + `(:AmbiguityDisposition)` matching the [`OBJECTIVES_CONTRACT.md`](OBJECTIVES_CONTRACT.md) §4 mechanism; (3) party roles generalised (`(:RegulatoryRole)` + `ACTS_AS {context}`); (4) DataFlow endpoints generalised + `(:ExternalParty)` + properties added to match real `cases/*/input/architecture/data_flows.yaml` fields; (5) SO hierarchy edge direction corrected (`AGGREGATES`, not `AGGREGATED_BY`); array-vs-edge duplications removed; (6) **run dimension** added (`(:Run)`) so multi-model / multi-spec runs do not collide on PKs and LLM-vs-deterministic provenance is captured per node; (7) `(:ControlEvidence)` mirrors the real `data/control_evidence/D-XX.yaml` shape; (8) `IN_SCOPE_OF` derivation now deterministic + versioned + testable (one rule, one test); (9) integration position (§1.3) declared: KG is the **derived view** layer; pipeline stays autonomous at runtime on the cluster; (10) ETL PHASE 4 VERIFY block added (counts, orphans, isolation, MERGE collisions, fingerprint); (11) DDL fills the ~10 missing constraints and adds run-scoped composite indices; (12) minor fixes (System.criticality UPPER, DataSubject.minor as attribute, Gate/GateP unified, step count).
>
> **v2 Change Note:** This revision fundamentally supersedes v1 (AEGIS-DOC-NEO4J-ONTOLOGY-001).
> The prior version was drafted without reading the canonical Phase 1 class model
> (`phase1_contextual_definition.md` v1.1) and was therefore missing 14 critical entities:
> `SecurityObjective`, `HierarchicalSecurityObjective`, `SubSecurityObjective`,
> `SubDomainActivation`, `ProportionalityProfile`, `ProportionalityEntry`,
> `Gate`/`GateP`/`Gate1A/B/C`, `DeclarationGap`, `RegulatoryApplicabilityResult`,
> `RegulatoryInteraction` (with 4-enum InteractionType), `BlockTrigger`,
> `NativeCompliance`/`InheritedCompliance`, and `ConditionalExtension`.
> All are now included and grounded in their canonical definitions.

---

## 1. Design Principles

### 1.1 Dual-Ontology Architecture

This specification merges two complementary layers:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  TIER 1 — NORMATIVE ONTOLOGY  (Source: methodology-00/Class_Models/phase1*.md) │
│  Entities defined in the canonical Phase 1 class model v1.1 (AEGIS Research)   │
│  These are FROZEN — never invented, always derived from the methodology source  │
│                                                                                 │
│  Stakeholder · BusinessGoal · CompanyContext · Regulation · Article ·           │
│  RegulatoryClause · SecurityControlDomain(=MacroDomain) · SubDomain ·          │
│  RegulatoryObligation · StrategicImplication · ComplementarityAnalysis ·       │
│  DomainCoverageEntry · DomainElaborationEntry ·                               │
│  SecurityObjective · HierarchicalSecurityObjective · SubSecurityObjective ·    │
│  SubDomainPipeline · SecurityRule · RegulatoryApplicabilityResult ·            │
│  DeclarationGap · BlockTrigger · ConditionalExtension · RegulatoryInteraction ·│
│  SubDomainActivation · ProportionalityProfile · ProportionalityEntry ·         │
│  Gate · ConditionalExtension · BlockTrigger · RegulatoryInteraction ·│
├─────────────────────────────────────────────────────────────────────────────────┤
│  TIER 2 — ENTERPRISE ARCHITECTURE ONTOLOGY  (Source: cases/*/input/*)          │
│  Entities loaded from case YAML files — unique per case, scoped by case_id     │
│                                                                                 │
│  System · DataStore · DataFlow · AuthSystem · ThirdPartyService · DataSubject  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  TIER 3 — NIST CSF 2.0 CONTROL ANCHOR  (Source: preproc_out/global/*)          │
│  106 active subcategories. NIST CSF 2.0 ONLY — no ISO, no OWASP, no CSF 1.1   │
│                                                                                 │
│  CSFFunction · CSFCategory · CSFSubcategory                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Inviolable Rules

1. **Case isolation:** Every query touching Tier 2 MUST start with `MATCH (e:Enterprise {case_id: $case_id})`.
2. **CSF 2.0 Only:** No ISO 27001, CIS, OWASP, or CSF 1.1 references in the graph.
3. **Canonical IDs:** Clause IDs: `{REG}-{SUFFIX}{NN}`. SubDomain IDs: `D-{NN}.{N}`. CSF: `{FUNC}.{CAT}-{NN}`. System IDs: `{case_prefix}:SYS-*`.
4. **Ports:** Neo4j Bolt `bolt://localhost:7688`, HTTP `http://localhost:7475`. Never 7687/7474.

### 1.3 Integration Position (binding decision for ETL authors)

The graph is a **derived view + agent/consultation layer**, not a runtime dependency of the pipeline. Specifically:

- The pipeline (`src/aegis_phase1/v2/`) reads inputs directly from `cases/*/input/architecture/*.yaml` and `preproc_out/`, builds `authoritative_ids` closed lists at MAP time (`src/aegis_phase1/v2/domain/inputs.py`), and runs autonomously on the cluster (Deucalion). **Neo4j MUST NOT be required at pipeline runtime.**
- ETL jobs ingest the *post-run* state (per `Run` node) and the static sources (YAMLs, preproc catalogue) into the graph. The graph is the substrate for human review, peer-model review, and Phase-2-style offline queries.
- Consequences:
  - Drift between the graph and the pipeline is a real risk; PHASE 4 VERIFY (§6.4) catches it via fingerprint and per-case counts.
  - The graph must be **reproducible from sources alone** (no manual edits in Neo4j).
  - Rule 0 (unscoped architecture queries are forbidden) is enforced as a convention + future linter (see §5).

---



## 2. Node Labels & Full Property Specifications

### 2.1 Tier 1 — Normative Entities (Canonical Phase 1 Class Model v1.1)

#### `(:Enterprise)` — Company Root (CompanyContext + ComplianceContext)
The root node for all case-specific data. All architecture nodes and proportionality profiles hang from here.

```
case_id                      String  PK     "case3-omnibank"
name                         String         "OmniBank Financial Systems S.A."
sector                       String         "Banking & Financial Services"
jurisdiction                 String         "Germany (BaFin + ECB)"
scale                        String  Enum   MICRO | SMALL | MEDIUM | LARGE | MAX
complexity_tier              String  Enum   LOW | MEDIUM | HIGH
employees                    Integer        5000
revenue_eur                  Float          1_500_000_000.0
security_fte                 Float          100.0
processes_personal_data      Boolean        true   INPUT (case profile)
places_digital_products_eu   Boolean        true   INPUT (case profile)
assessment_date              String         "2026-09-03"
```

**Rule:** `Enterprise` carries **intrinsic inputs only** (case profile). Derived applicability facts (`dora_financial_entity`, `nis2_sector`, `aiact_high_risk_system`) live exclusively on `(:RegulatoryApplicabilityResult)`. Re-running the filter MUST NOT overwrite intrinsic properties.

#### `(:Regulation)` — EU Legal Instrument
Exactly 5 nodes in Phase 1: GDPR, CRA, NIS2, DORA, AI_Act.

```
id                String  PK     "GDPR" | "CRA" | "NIS2" | "DORA" | "AI_Act"
name              String         "General Data Protection Regulation"
short_name        String         "GDPR"
jurisdiction      String         "EU"
celex_id          String         "32016R0679"
effective_date    String         "2018-05-25"
enforcement_date  String         "2018-05-25"
urgency_tier      String  Enum   IMMEDIATE | NEAR_TERM | STRATEGIC
```

#### `(:Article)` — Regulation Chapter / Section
```
id                String  PK     "GDPR_Art. 32" | "DORA_Art. 9" | "AI_Act_Art. 14"
regulation_id     String  FK→Regulation
article_number    String         "32"
title             String         "Security of processing"
```

#### `(:RegulatoryClause)` — Atomic Prescriptive Obligation
**331 clauses in the active catalogue.** The most important Tier 1 leaf node.

```
id                      String  PK     "GDPR-CL06" | "DORA-CL14" | "AI_Act-CL014"
regulation_id           String  FK→Regulation
article_id              String  FK→Article
article_reference       String         "Art. 32(1)(a)"
description             String         Normalized clause text (verbatim from preprocessing)
normative_strength      String  Enum   MANDATORY_UNCONDITIONAL | MANDATORY_CONDITIONAL | GUIDANCE
normative_weight        Integer        1=MAY | 2=SHOULD | 3=SHALL
obligation_type         String  Enum   CONTINUOUS | PERIODIC | TRIGGERED | ONE_TIME
obligated_party         REMOVED        Use BINDS_PARTY edges to (:RegulatoryRole); see §3.1
is_atomic               Boolean        true
parent_clause_id        String         null or "GDPR-CL05"
sanction_reference      String         "GDPR Art. 83(4) — up to €10M or 2% of turnover"
activation_predicate    String         "processes_personal_data == true"
enforcement_date        String         "2018-05-25"
```

**ObligatedPartyType enum (full):**
`CONTROLLER | PROCESSOR | MANUFACTURER | IMPORTER | DISTRIBUTOR |
 ESSENTIAL_OR_IMPORTANT_ENTITY | FINANCIAL_ENTITY | PROVIDER | DEPLOYER`

#### `(:SecurityControlDomain)` — Macro-Domain (D-01..D-10)
```
id                String  PK     "D-01" through "D-10"
name              String         "Data Protection & Cryptography"
description       String         Scope of this control domain
reference_source  String         "AEGIS Taxonomy v1.1"
```

#### `(:SubDomain)` — Atomic Security Subdomain (38 subdomains)
```
id                String  PK     "D-01.1" | "D-04.3" | "D-09.4"
macro_id          String  FK→SecurityControlDomain
name              String         "Data Encryption at Rest"
description       String         Full technical scope
reference_source  String         "AEGIS Taxonomy v1.1"
```

#### `(:SecurityObjective)` — Regulation-derived SO (SO-REG-NNN)
Frozen, read-only from the Regulatory Baseline contract.

```
id                    String  PK     "SO-GDPR-001" | "SO-CRA-014"
regulation_code       String  FK→Regulation
statement             String         Full SO statement
regulatory_source     String         "GDPR Art. 32(1)(a)"
security_rationale    String         Technical justification
sub_domain_ids        String[]       ["D-01.1", "D-01.2"]
```

#### `(:HierarchicalSecurityObjective)` — Per-Subdomain HSO (SO-D-XX.X.REG)
```
id                      String  PK     "SO-D-01.1.GDPR"
sub_domain_id           String  FK→SubDomain
suffix                  String         "GDPR"
activation_condition    String         "processes_personal_data == true"
is_active               Boolean        true
```

#### `(:SubSecurityObjective)` — High-Level Cross-Reg SSO (SO-D-XX.X.HL)
```
id                      String  PK     "SO-D-01.1.HL"
regulation_code         String         "ALL" or specific reg code
applies_to              String[]       ["GDPR", "CRA"]
inherits_from           String  FK→SecurityObjective
activation_condition    String         "applicable == true"
is_active               Boolean        true
```

#### `(:SecurityRule)` — Implementation Rule (SR-REG-NNN)
```
id                    String  PK     "SR-GDPR-014" | "SR-AI_Act-014"
regulation_code       String  FK→Regulation
statement             String         Prescriptive rule text
regulatory_source     String         "GDPR Art. 32(1)(a)"
security_rationale    String
nist_csf_mappings     String[]       ["PR.DS-01", "PR.DS-02"]
```

#### `(:RegulatoryApplicabilityResult)` — Filter 1 Output (per case × regulation)
```
id                String  PK     "RAR-case3-DORA"
case_id           String  FK→Enterprise
regulation_id     String  FK→Regulation
applicable        Boolean        true
role              String         "financial_entity"
classification    String         "MANDATORY"
threshold_met     Boolean        true
assessment_date   String         "2026-09-03"
```

#### `(:DeclarationGap)` — Missing / Undeclared Applicability Item
Loaded from `interactions.yaml > negative_analyses`.

```
id                String  PK     "GAP-case3-AI_Act-001"
case_id           String  FK→Enterprise
reg               String  FK→Regulation
gap_type          String         "FRIA_NOT_PUBLISHED" | "EXIT_STRATEGY_MISSING" | "BOARD_REVIEW_OVERDUE"
severity          String  Enum   HIGH | MEDIUM | LOW
resolution_hint   String         "Draft and publish FRIA per AI Act Art. 27"
source_id         String         "NEG-01" (from interactions.yaml)
```

#### `(:SubDomainActivation)` — Filter 2 / MAP Output (per case × subdomain)
The central output of the MAP stage. One node per `(case_id, sub_domain_id)` pair.

```
id                    String  PK     "SDA-case3-D-01.1"
case_id               String  FK→Enterprise
sub_domain_id         String  FK→SubDomain
applicable            Boolean        true
scope_overlap         String  Enum   Y | CONDITIONAL | N
priority              String  Enum   MUST | SHOULD | COULD
has_emergent_tension  Boolean        true
applicable_regs       String[]       ["GDPR", "CRA", "DORA", "NIS2"]
active_reg_count      Integer        4
normative_intensity   Float          3.8          (CANONICAL scale, weighted; see note below)
proportionality_tier  String  Enum   MINIMAL | LIGHTWEIGHT | STANDARD | RIGOROUS | DEFERRED
origin               String         "llm:P1C-LLM-01"
```

**Note on `normative_intensity`:** the canonical scale (used on `SubDomainActivation` and `DomainElaborationEntry`) is the weighted float derived from the methodology (typical range 0.0–5.0). A second variant in 0.0–1.0 is reserved for Phase 2 (normative intensity *index*) and shall be named `*_index` if introduced — never reuse the same property name with a different scale.

#### `(:ClauseActivation)` — Per-Case Per-Clause Activation (OBJ-02 zero-omission substrate)
Computed deterministically from `activation_predicate` ∧ `Enterprise` boolean properties ∧ RAR/role. Gives the pipeline an explicit, countable substrate for the "zero omissions" objective.

```
id                  String  PK     "CA-{case_id}-GDPR-CL06"
case_id             String  FK→Enterprise
clause_id           String  FK→RegulatoryClause
activation_state    String  Enum   ACTIVE | INACTIVE | CONDITIONAL_PENDING
activated_by_role   String  FK→RegulatoryRole    (when ACTIVE)
```

---
Replaces the vague `:RegulatoryTension` from v1. Uses the formal 4-enum InteractionType.

```
id                    String  PK     "RI-case3-TEMPORAL-01"
case_id               String  FK→Enterprise
interaction_type      String  Enum   TEMPORAL_CONFLICT | REQUIREMENT_CONFLICT |
                                     TRIGGER_MISMATCH | NEGATIVE_ANALYSIS
involved_regs         String[]       ["GDPR", "CRA", "DORA", "NIS2"]
sub_domains           String[]       ["D-04.3", "D-04.4"]
conflict_description  String         Verbatim from interactions.yaml (e.g. "GDPR Art. 33 = 72h; DORA = 4h initial")
resolution_principle  String         "Adopt strictest SLA (DORA 4h) as unified internal SLA"
severity              String  Enum   HIGH | MEDIUM | LOW
source_id             String         "TEMPORAL-01"
```

#### `(:ConditionalExtension)` — Activation Block for conditional question sets
```
id                  String  PK     "EXT-AIACT-ANNEXIII"
block_id            String         "B07"
block_name          String         "AI Act Annex III High-Risk Deployer"
trigger_condition   String         "aiact_high_risk_system == true"
question_ids        String[]       ["Q-AIACT-01", "Q-AIACT-02"]
is_active           Boolean        true
```

#### `(:BlockTrigger)` — Maps trigger conditions to ConditionalExtensions
```
id                  String  PK     "BT-B07"
block_id            String         "B07"
trigger_condition   String         "aiact_high_risk_system == true"
question_ids        String[]       ["Q-AIACT-01"]
is_active           Boolean        true
```

#### `(:ComplementarityAnalysis)` — Cross-Regulation Structural Comparison
```
id                        String  PK     "CA-GDPR-DORA-D01"
regulation_a              String  FK→Regulation
regulation_b              String  FK→Regulation
sub_domain_id             String  FK→SubDomain
shared_scope              Float          0.72
complementarity_index     Float          0.65
overlap_type              String  Enum   FULL | PARTIAL | MINIMAL
structural_connectedness  Float          0.80
analysis_date             String         "2026-09-03"
```

#### `(:DomainCoverageEntry)` — Coverage statistics per (Regulation × MacroDomain)
```
id                      String  PK     "DCE-DORA-D-04"
regulation_id           String  FK→Regulation
domain_id               String  FK→SecurityControlDomain
coverage_level          String  Enum   SUBSTANTIVE | PARTIAL | NOT_ADDRESSED
clause_count            Integer        12
granularity_level       String  Enum   ARTICLE | PARAGRAPH | SUB_PARAGRAPH | ATOMIC
obligated_party_dist    String         JSON: {"FINANCIAL_ENTITY": 10, "PROVIDER": 2}
obligation_type_dist    String         JSON: {"CONTINUOUS": 8, "TRIGGERED": 4}
```

#### `(:DomainElaborationEntry)` — Per-Subdomain Complementarity Detail
```
id                      String  PK     "DEE-GDPR-DORA-D-01.1"
sub_domain_id           String  FK→SubDomain
regulation_a            String  FK→Regulation
regulation_b            String  FK→Regulation
elaboration_factor      Float          0.85
dominant_regulation     String         "DORA"
relation_type           String  Enum   Overlap | CumulativeReinforcement | Conflict | Gap
normative_intensity     Float          3.8
weighted_score          Float          3.23
notes                   String         Analyst commentary
```

#### `(:ProportionalityProfile)` — Track B Output (per Enterprise)
```
id                String  PK     "PP-case3-omnibank"
case_id           String  FK→Enterprise
company_scale     String  Enum   MICRO | SMALL | MEDIUM | LARGE | MAX
security_fte      Float          100.0
gate_p_status     String  Enum   PASS | FAIL
```

#### `(:ProportionalityEntry)` — Track B Row (per Subdomain × Enterprise)
**9 rich attributes per subdomain per enterprise — the key analytical output of Phase 1.**

```
id                      String  PK     "PE-case3-D-01.1"
case_id                 String  FK→Enterprise
sub_domain_id           String  FK→SubDomain
inheritability          String  Enum   INHERITABLE | BUILD_REQUIRED
priority                String  Enum   MUST | SHOULD | COULD
tier                    String  Enum   MINIMAL | LIGHTWEIGHT | STANDARD | RIGOROUS | DEFERRED
satisfaction_pattern    String  Enum   INHERIT | BUY_MANAGED | BUILD_LIGHT | BUILD_FULL
evidence_depth          String         "Full technical evidence package: HSM audit logs, FIPS cert, key rotation proof"
verification_method     String  Enum   INSPECT | DEMONSTRATE | TEST | ANALYZE
ownership               String  Enum   SUPPLIER | SHARED | COMPANY | COMPANY_AUDITOR
example_controls        String         "Thales payShield HSM FIPS 140-2 L3, AES-256-GCM at rest on DB2 z/OS"
```

`(:ProportionalityEntry)-[:OWNED_BY]->(:Stakeholder)` is added (see §3.1) to enable DORA board-level accountability queries (resolves open question §8.2).

#### `(:Gate)` — Pipeline Validation Checkpoint
```
id                    String  PK     "GATE-1A-case3"
gate_type             String         "Gate1A" | "Gate1B" | "Gate1C" | "GateP"
case_id               String  FK→Enterprise
phase                 String         "1"
status                String  Enum   PASS | FAIL | NOT_CHECKED
criteria_check_result String
```

#### `(:GateP)` — Proportionality Profile Validator (validates Doc 07b)
```
id                        String  PK     "GATEP-case3"
case_id                   String  FK→Enterprise
document_id               String         "07b_Proportionality_Profile.md"
document_exists           Boolean        true
active_rows_complete      Boolean        true
five_attributes_complete  Boolean        true
rule_11_satisfied         Boolean        true
status                    String  Enum   PASS | FAIL
```

#### `(:Stakeholder)` — Internal or External Actor
```
id                String  PK     "SH-case3-CISO"
case_id           String  FK→Enterprise
name              String         "Chief Information Security Officer"
role              String         "CISO"
stakeholder_type  String  Enum   INTERNAL | EXTERNAL
department        String         "Information Security"  (INTERNAL only)
organization      String         null | "BaFin" | "BSI"  (EXTERNAL only)
relationship_type String         null | "REGULATOR" | "AUDITOR" | "VENDOR"
```

#### `(:BusinessGoal)` — Strategic Objective
```
id                    String  PK     "BG-case3-001"
case_id               String  FK→Enterprise
description           String
priority              String  Enum   MUST | SHOULD | COULD
strategic_alignment   String         "EU Digital Finance Strategy"
```

#### `(:RegulatoryPair)` — Cross-Regulation Pair from preproc (196 total)
Frozen classification — never modified by loader or LLM. Source: `entities/pairs/D-{XX}/D-{XX.Y}_{A}-{B}.json`.

```
id                    String  PK     "D-01.1_GDPR-CRA"
subdomain_id          String  FK→SubDomain
reg_a                 String  FK→Regulation
reg_b                 String  FK→Regulation
classification        String         "SAME" | "COMPLEMENTARY" | "CONTRADICTORY" | "SCOPE_DISJOINT" | "CONDITIONAL"
verified_relationship String         FROZEN textual relationship (Layer 0 read-only)
layer2_flag           Boolean        true if a CONDITIONAL predicate requires Layer-2 evaluation
scope_overlap         String         "Y" | "N" | "CONDITIONAL"
scope_disjoint_test   String         Predicate text
downstream_implication String
verbatim_articles     JSON           {reg: article_reference}
```

`CONDITIONAL` pairs are the **documented ambiguity surface** (multiple legitimate readings); the LLM disposition (`:AmbiguityDisposition`, run-scoped) closes this per company.

#### `(:PairActivation)` — Run-Scoped Activation of a RegulatoryPair
One node per `(run_id, pair_id)`; carries the MAP verdict. Re-keyed by Run so multi-model runs do not collide.

```
id                    String  PK     "PA-{run_id}-D-01.1_GDPR-CRA"
run_id                String  FK→Run
pair_id               String  FK→RegulatoryPair
case_id               String  FK→Enterprise
company_scope_verdict String  Enum   OVERLAP_CONFIRMED | OVERLAP_NOT_TRIGGERED |
                                     SCOPE_DISJOINT | INDETERMINATE
origin                String         "llm:P1C-LLM-01"
notes                 String
```

#### `(:AmbiguityDisposition)` — Run-Scoped Resolution of a CONDITIONAL Pair (OBJECTIVES_CONTRACT §4)
One node per `(run_id, pair_id)` where `Pair.classification = CONDITIONAL`; emit only when specs are at v1.2+. Closed disposition vocabulary.

```
id                String  PK     "AD-{run_id}-D-01.1_GDPR-CRA"
run_id            String  FK→Run
pair_id           String  FK→RegulatoryPair
case_id           String  FK→Enterprise
applicable_reading String        One of the documented readings from `verbatim_articles` (text)
anchors           String[]       Anchors from closed lists only (article IDs, tier, asset IDs, business goal IDs)
consequence       String
disposition       String  Enum   RESOLVED_BY_FACT | RESOLVED_BY_TIER | NEEDS_HUMAN
origin            String         "llm:P1C-LLM-01"  (when populated)
```

#### `(:RegulatoryRole)` — Obligated Party Enumeration
Replaces the `obligated_party: String[]` field on `RegulatoryClause` (which was non-traversable) and the single-value `SUBJECT_TO.role` (which cannot represent multi-role enterprises — OmniBank is CONTROLLER for customers, PROCESSOR for partners, PROVIDER and DEPLOYER under AI Act).

```
id           String  PK     "GDPR-CONTROLLER" | "DORA-FINANCIAL_ENTITY" |
                        "AI_Act-DEPLOYER" | "AI_Act-PROVIDER" | "GDPR-PROCESSOR" |
                        "CRA-MANUFACTURER" | "CRA-IMPORTER" | "CRA-DISTRIBUTOR" |
                        "NIS2-ESSENTIAL_OR_IMPORTANT_ENTITY"
regulation_id String FK→Regulation
role_name    String         ObligatedPartyType enum value
```

#### `(:ControlEvidence)` — Mirror of `data/control_evidence/D-XX.yaml`
Populated in Phase 1; STATUS (IMPLEMENTED/PARTIAL/PLANNED/ABSENT) is Phase 2 work (resolves open question §8.1).

```
id              String  PK     "CE-D-01-encryption-at-rest"
domain_id       String  FK→SecurityControlDomain
control         String         "Encryption at rest"
current_by_tier JSON           {"MICRO": "...", "SMALL": "...", "MEDIUM": "...", "LARGE": "...", "MAX": "..."}
evidence_refs   String[]       ["STORES", "FLOWS", "SYSTEMS"]
```

#### `(:Run)` — Pipeline Run Identity
All run-derived nodes hang from a Run. Deterministic nodes are case-scoped (no Run).

```
run_id          String  PK     "{case}-{model}-{provider}-{quant}-{ts}"
case_id         String  FK→Enterprise
model           String         "nemotron-3.5-lightning:30b" | "MiniMax-M3" | ...
provider        String         "ollama" | "transformers" | "minimax"
quantization    String         "q4_k_m" | "fp8" | "provider_default" | null
spec_versions   JSON           {"P1B-LLM-01": "1.1.0", "P1C-LLM-01": "1.1.0", ...}
gate_mode       String  Enum   "warn" | "hard"
started_at      String         ISO-8601 UTC
ended_at        String         ISO-8601 UTC | null
status          String  Enum   "running" | "completed" | "degraded" | "failed"
```

#### `(:GraphMeta)` — Catalog Fingerprint (per database)
Used by PHASE 4 VERIFY to detect drift between sources and graph.

```
key             String  PK     "preproc_fingerprint" | "etl_version" | "loaded_at"
value           String
```

---

### 2.2 Tier 2 — Enterprise Architecture Entities

#### `(:System)` — IT System / Application
Source: `cases/*/input/architecture/systems.yaml`

```
id                  String  PK     "case3:SYS-CBS"
case_id             String  FK→Enterprise
name                String         "Core Banking System (Temenos T24)"
type                String         "core_banking_mainframe" | "web_application" | "ai_ml_platform"
tech_stack          String         "Temenos T24, IBM z/OS, COBOL, DB2 z/OS"
owner               String         "Head of Operations (COO)"
criticality         String  Enum   LOW | MEDIUM | HIGH | CRITICAL  (ETL normalises YAML lowercase)
hosts_personal_data Boolean        true
ai_annex_iii        Boolean        false  (true only for e.g. SYS-CREDITAI)
notes               String
```

#### `(:DataStore)` — Data Repository
Source: `cases/*/input/architecture/data_stores.yaml`

```
id                  String  PK     "case3:STORE-DB2"
case_id             String  FK→Enterprise
name                String         "Mainframe DB2 Accounts Ledger"
storage_type        String         "relational_db" | "event_stream" | "worm_archive" | "key_vault"
contains_pii        Boolean        true
contains_financial  Boolean        true
encryption_at_rest  Boolean        true
encryption_standard String         "AES-256-GCM" | "FIPS 140-2"
retention_days      Integer        3650
```

#### `(:DataFlow)` — Data Transit
Source: `cases/*/input/architecture/data_flows.yaml`. **Endpoints are generalised** (the real YAML carries stores, customers, and regulators — not just systems): the `SENDS_DATA_TO` edge duplication from v2 is removed in favour of two directed edges `ORIGINATES_FROM` / `TERMINATES_AT` to any of {System, DataStore, ThirdPartyService, DataSubject, ExternalParty}.

```
id                        String  PK     "case3:FLOW-01"
case_id                   String  FK→Enterprise
name                      String         "Core to Payment Gateway Transaction Flow"
data_type                 String         Free text from YAML (e.g. "Customer PII + authn credentials")
volume                    String         Free text ("~2 M unique customers; ~150 M sessions/month")
protocol                  String         "mTLS / gRPC" | "TLS 1.3 / HTTPS" | ...
encryption_in_transit     String         "TLS 1.3 (FAPI 2.0 profile)" | ...
subprocessor              Boolean        true if YAML `subprocessor: Y`
subprocessor_vendor       String         Vendor name when subprocessor=true
is_cross_border           Boolean        Derived (DERIVED rule in ETL; see §6.5)
origin_jurisdiction       String         Derived from source endpoint
destination_jurisdiction  String         Derived from destination endpoint
transfer_mechanism        String         Derived (None | SCCs | Adequacy | BCR)
carries_pii               Boolean        Derived from data_type keywords (DERIVED; see §6.5)
carries_financial         Boolean        Derived from data_type keywords (DERIVED; see §6.5)
```

#### `(:ExternalParty)` — Regulators, Customer-facing Parties, Public Endpoints
Endpoints outside the company control plane that appear as flow endpoints (e.g. BaFin goAML gateway in case3, "Retail customer browser").

```
id            String  PK     "case3:EXT-BAFIN"
case_id       String  FK→Enterprise
name          String         "BaFin (FIU Germany via goAML)"
kind          String  Enum   REGULATOR | END_USER | PUBLIC_INTERNET | OTHER
jurisdiction  String         "DE"
```

#### `(:AuthSystem)` — Authentication & Cryptographic Hardware
Source: `cases/*/input/architecture/auth_systems.yaml`

```
id                String  PK     "case3:AS-HSM"
case_id           String  FK→Enterprise
name              String         "Thales payShield 10K HSM"
auth_type         String         "hardware_security_module" | "fido2_webauthn" | "pki_ca" | "mfa_totp"
fips_level        String         "140-2 Level 3" | null
coverage          String[]       ["case3:SYS-CBS", "case3:SYS-WEB"]
```

#### `(:ThirdPartyService)` — External Cloud / SaaS / Critical Vendor
Source: `cases/*/input/architecture/cloud_services.yaml`

```
id                          String  PK     "case3:CS-AWS"
case_id                     String  FK→Enterprise
provider                    String         "Amazon Web Services"
service_name                String         "AWS Frankfurt (eu-central-1)"
jurisdiction                String         "EU (Frankfurt)"
critical_third_party_dora   Boolean        true
exit_strategy_documented    Boolean        true
sla_rto_hours               Integer        4
```

#### `(:DataSubject)` — Data Subject Category
Source: `cases/*/input/architecture/data_subjects.yaml`
**Gap from v1:** Required to auto-infer GDPR Art. 8 (minors), Art. 9 (special categories), Art. 22 (automated decisions).

```
id                  String  PK     "case3:DS-CUSTOMERS"
case_id             String  FK→Enterprise
type                String  Enum   CUSTOMER | EMPLOYEE | COUNTER_PARTY | APPLICANT
is_minor            Boolean        false  (attribute, NOT a type; a customer can be minor)
special_category    Boolean        false  (true → GDPR Art. 9 mandatory; triggers extra clauses)
estimated_count     Integer        750000
description         String         "Retail and SMB banking customers"
```

---

### 2.3 Tier 3 — NIST CSF 2.0 Control Anchors

#### `(:CSFFunction)` — 6 top-level functions
```
id     String  PK     "GV" | "ID" | "PR" | "DE" | "RS" | "RC"
name   String         "GOVERN" | "IDENTIFY" | "PROTECT" | "DETECT" | "RESPOND" | "RECOVER"
```

#### `(:CSFCategory)` — 34 categories
```
id            String  PK     "PR.DS" | "GV.OC" | "DE.CM"
function_id   String  FK→CSFFunction
name          String         "Data Security"
```

#### `(:CSFSubcategory)` — 106 active subcategories (NIST CSWP 29, 2024-02-26)
```
id              String  PK     "PR.DS-01" | "GV.OC-01" | "DE.CM-01"
category_id     String  FK→CSFCategory
function_id     String  FK→CSFFunction
outcome_text    String         Full NIST CSF 2.0 outcome statement
nist_version    String         "2.0 (CSWP 29, 2024-02-26)"
```

---

## 3. Relationship Catalogue

### 3.1 Normative Layer Relationships

| Source → Edge → Target | Properties |
|---|---|
| `(:Enterprise)-[:HAS_APPLICABILITY_RESULT]->(:RegulatoryApplicabilityResult)` | — |
| `(:Enterprise)-[:HAS_DECLARATION_GAP]->(:DeclarationGap)` | — |
| `(:Enterprise)-[:HAS_PROPORTIONALITY_PROFILE]->(:ProportionalityProfile)` | — |
| `(:Enterprise)-[:TRIGGERS_EXTENSION]->(:ConditionalExtension)` | `active: Boolean` |
| `(:Enterprise)-[:HAS_REGULATORY_INTERACTION]->(:RegulatoryInteraction)` | — |
| `(:Enterprise)-[:ACTS_AS {context}]->(:RegulatoryRole)` | `context: String` (e.g. "customer_data", "ai_system_deployment") — replaces v2's single-value SUBJECT_TO.role |
| `(:RegulatoryRole)-[:BELONGS_TO_REGULATION]->(:Regulation)` | — (the FK-like association that Pattern 5 traverses via `ACTS_AS`→`RegulatoryRole`→`BELONGS_TO_REGULATION`→`Regulation`) |
| `(:Regulation)-[:HAS_ARTICLE]->(:Article)` | — |
| `(:Article)-[:CONTAINS_CLAUSE]->(:RegulatoryClause)` | — |
| `(:RegulatoryClause)-[:MAPPED_TO_SUBDOMAIN]->(:SubDomain)` | `confidence: String, mapping_type: DIRECT\|PARTIAL` (the v2 property `normative_strength: Float` is replaced by `mapping_type`; intensity lives on SubDomainActivation only) |
| `(:RegulatoryClause)-[:BINDS_PARTY]->(:RegulatoryRole)` | — (replaces `obligated_party: String[]` property) |
| `(:SecurityControlDomain)-[:HAS_SUBDOMAIN]->(:SubDomain)` | — |
| `(:SecurityControlDomain)-[:HAS_CONTROL_EVIDENCE]->(:ControlEvidence)` | — |
| `(:SubDomain)-[:ANCHORED_TO_CSF]->(:CSFSubcategory)` | `mapping_type: DIRECT\|PARTIAL, confidence_level: HIGH\|MEDIUM\|LOW, rationale: String` (the former `(:ImplementationMapping)` node is now property set on this edge) |
| `(:SubDomain)-[:HAS_ACTIVATION]->(:SubDomainActivation)` | scoped by case_id on activation node |
| `(:SubDomainActivation)-[:GOVERNED_BY_PROPORTIONALITY]->(:ProportionalityEntry)` | — |
| `(:ProportionalityProfile)-[:CONTAINS_ENTRY]->(:ProportionalityEntry)` | — |
| `(:ProportionalityEntry)-[:SCOPED_TO]->(:SubDomain)` | — |
| `(:ProportionalityEntry)-[:OWNED_BY]->(:Stakeholder)` | — (resolves open question §8.2 — board-level accountability) |
| `(:SecurityObjective)-[:BELONGS_TO]->(:Regulation)` | — |
| `(:SecurityObjective)-[:SCOPED_TO]->(:SubDomain)` | — (replaces `SecurityObjective.sub_domain_ids: String[]` array) |
| `(:HierarchicalSecurityObjective)-[:DERIVES_FROM]->(:SecurityObjective)` | — |
| `(:SubSecurityObjective)-[:AGGREGATES]->(:HierarchicalSecurityObjective)` | direction corrected in v3 (was `AGGREGATED_BY` — semantically inverted); the array `SubSecurityObjective.inherits_from` removed |
| `(:SecurityRule)-[:REFINES]->(:SecurityObjective)` | — |
| `(:SecurityRule)-[:ANCHORED_TO_CSF]->(:CSFSubcategory)` | `mapping_type: DIRECT\|PARTIAL` |
| `(:RegulatoryClause)-[:IN_TENSION_WITH]->(:RegulatoryClause)` | `tension_id: String, interaction_type: String` |
| `(:RegulatoryPair)-[:HAS_ACTIVATION]->(:PairActivation)` | scoped by run_id on activation node |
| `(:PairActivation)-[:GOVERNED_BY_PROPORTIONALITY]->(:ProportionalityEntry)` | — |
| `(:RegulatoryPair)-[:HAS_AMBIGUITY_DISPOSITION]->(:AmbiguityDisposition)` | scoped by run_id; only for CONDITIONAL pairs |
| `(:RegulatoryClause)-[:HAS_CLAUSE_ACTIVATION]->(:ClauseActivation)` | scoped by case_id |
| `(:Gate)-[:VALIDATES_RESULT]->(:RegulatoryApplicabilityResult)` | gate_type=Gate1A, run_id |
| `(:Gate)-[:VALIDATES_ACTIVATION]->(:SubDomainActivation)` | gate_type=Gate1B, run_id |
| `(:Gate)-[:VALIDATES_PROFILE]->(:ProportionalityProfile)` | gate_type=GateP (replaces v2's separate (:GateP) label), run_id |
| `(:Gate)-[:VALIDATES_PAIR]->(:PairActivation)` | gate_type=Gate1C, run_id |
| `(:Stakeholder)-[:DEFINES]->(:BusinessGoal)` | — |
| `(:Run)-[:PRODUCED]->(:SubDomainActivation)` | — |
| `(:Run)-[:PRODUCED]->(:PairActivation)` | — |
| `(:Run)-[:PRODUCED]->(:AmbiguityDisposition)` | — |
| `(:Run)-[:PRODUCED]->(:Gate)` | — |

**Provenance (`origin` property):** every run-derived node carries `origin: "deterministic" | "llm:<spec_id>"` (e.g. `llm:P1C-LLM-01`). This is the CORR-112 deterministic/LLM distinction made structurally navigable in the graph.

### 3.2 Enterprise Architecture Relationships

| Source → Edge → Target | Properties |
|---|---|
| `(:Enterprise)-[:OPERATES_SYSTEM]->(:System)` | `owner: String` |
| `(:Enterprise)-[:HAS_DATA_SUBJECT]->(:DataSubject)` | — |
| `(:System)-[:STORES_DATA_IN]->(:DataStore)` | `access_type: String` |
| `(:System)-[:AUTHENTICATED_BY]->(:AuthSystem)` | `enforced: Boolean` |
| `(:System)-[:OUTSOURCED_TO]->(:ThirdPartyService)` | `critical_dora: Boolean` |
| `(:System)-[:IN_SCOPE_OF]->(:SubDomain)` | `proportionality_tier: String, rule_id: String, basis: String` (v3: rule_id points to a deterministic rule in `data/in_scope_of_rules.yaml`; basis is the human-readable justification; no LLM in v1 derivation) |
| `(:DataFlow)-[:ORIGINATES_FROM]->(:System \| :DataStore \| :DataSubject \| :ExternalParty)` | — |
| `(:DataFlow)-[:TERMINATES_AT]->(:System \| :DataStore \| :ThirdPartyService \| :ExternalParty)` | — (replaces v2's two FK properties + redundant `SENDS_DATA_TO` edge) |
| `(:DataFlow)-[:INVOLVES_DATA_OF]->(:DataSubject)` | — |
| `(:DataSubject)-[:TRIGGERS_CLAUSE]->(:RegulatoryClause)` | `trigger_reason: String` |

### 3.3 Cross-Tier Bridge Relationships

| Source → Edge → Target | Semantic Meaning |
|---|---|
| `(:RegulatoryInteraction)-[:INVOLVES_REGULATION]->(:Regulation)` | Multi-reg conflict scope |
| `(:RegulatoryInteraction)-[:SCOPED_TO_SUBDOMAIN]->(:SubDomain)` | Conflict subdomain scope |
| `(:ComplementarityAnalysis)-[:COMPARES]->(:Regulation)` | `regulation_position: "A"\|"B"` |
| `(:ComplementarityAnalysis)-[:SCOPED_TO]->(:SubDomain)` | Subdomain scope |
| `(:CSFSubcategory)<-[:ANCHORS]-(edge between SubDomain and CSFSubcategory)` | see §3.1 — `(:ImplementationMapping)` node replaced by properties on the edge |
| `(:SubDomain)<-[:APPLIED_TO]-(edge between SubDomain and CSFSubcategory)` | see §3.1 |

---

## 4. Constraint & Index Definitions (Cypher DDL)

Execute in order on fresh database before any ETL load:

```cypher
// ── Unique Constraints ───────────────────────────────────────────────────────
CREATE CONSTRAINT enterprise_pk      IF NOT EXISTS FOR (n:Enterprise)               REQUIRE n.case_id IS UNIQUE;
CREATE CONSTRAINT regulation_pk      IF NOT EXISTS FOR (n:Regulation)               REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT article_pk         IF NOT EXISTS FOR (n:Article)                  REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT clause_pk          IF NOT EXISTS FOR (n:RegulatoryClause)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT domain_pk          IF NOT EXISTS FOR (n:SecurityControlDomain)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT subdomain_pk       IF NOT EXISTS FOR (n:SubDomain)                REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT so_pk              IF NOT EXISTS FOR (n:SecurityObjective)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT hso_pk             IF NOT EXISTS FOR (n:HierarchicalSecurityObjective) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sso_pk             IF NOT EXISTS FOR (n:SubSecurityObjective)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sr_pk              IF NOT EXISTS FOR (n:SecurityRule)             REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pair_pk            IF NOT EXISTS FOR (n:RegulatoryPair)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT role_pk            IF NOT EXISTS FOR (n:RegulatoryRole)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_fn_pk          IF NOT EXISTS FOR (n:CSFFunction)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_cat_pk         IF NOT EXISTS FOR (n:CSFCategory)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_sub_pk         IF NOT EXISTS FOR (n:CSFSubcategory)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT system_pk          IF NOT EXISTS FOR (n:System)                   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT datastore_pk       IF NOT EXISTS FOR (n:DataStore)                REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dataflow_pk        IF NOT EXISTS FOR (n:DataFlow)                 REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT authsys_pk         IF NOT EXISTS FOR (n:AuthSystem)               REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT thirdparty_pk      IF NOT EXISTS FOR (n:ThirdPartyService)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT datasubject_pk     IF NOT EXISTS FOR (n:DataSubject)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT externalparty_pk   IF NOT EXISTS FOR (n:ExternalParty)            REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT stakeholder_pk     IF NOT EXISTS FOR (n:Stakeholder)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT bizgoal_pk         IF NOT EXISTS FOR (n:BusinessGoal)             REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sda_pk             IF NOT EXISTS FOR (n:SubDomainActivation)      REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT pa_pk              IF NOT EXISTS FOR (n:PairActivation)           REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT ad_pk              IF NOT EXISTS FOR (n:AmbiguityDisposition)     REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT gate_pk            IF NOT EXISTS FOR (n:Gate)                     REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT run_pk             IF NOT EXISTS FOR (n:Run)                      REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT clauseact_pk       IF NOT EXISTS FOR (n:ClauseActivation)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ri_pk              IF NOT EXISTS FOR (n:RegulatoryInteraction)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pe_pk              IF NOT EXISTS FOR (n:ProportionalityEntry)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT gap_pk             IF NOT EXISTS FOR (n:DeclarationGap)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT rar_pk             IF NOT EXISTS FOR (n:RegulatoryApplicabilityResult) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pp_pk              IF NOT EXISTS FOR (n:ProportionalityProfile)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ce_pk              IF NOT EXISTS FOR (n:ControlEvidence)          REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ext_pk             IF NOT EXISTS FOR (n:ConditionalExtension)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT bt_pk              IF NOT EXISTS FOR (n:BlockTrigger)             REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dce_pk             IF NOT EXISTS FOR (n:DomainCoverageEntry)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dee_pk             IF NOT EXISTS FOR (n:DomainElaborationEntry)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ca_pk              IF NOT EXISTS FOR (n:ComplementarityAnalysis)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT meta_pk            IF NOT EXISTS FOR (n:GraphMeta)                REQUIRE n.key IS UNIQUE;

// ── Lookup Indexes ───────────────────────────────────────────────────────────
CREATE INDEX system_case             IF NOT EXISTS FOR (n:System)                   ON (n.case_id);
CREATE INDEX datastore_case          IF NOT EXISTS FOR (n:DataStore)                ON (n.case_id);
CREATE INDEX dataflow_case           IF NOT EXISTS FOR (n:DataFlow)                 ON (n.case_id);
CREATE INDEX authsys_case            IF NOT EXISTS FOR (n:AuthSystem)               ON (n.case_id);
CREATE INDEX thirdparty_case         IF NOT EXISTS FOR (n:ThirdPartyService)        ON (n.case_id);
CREATE INDEX externalparty_case      IF NOT EXISTS FOR (n:ExternalParty)            ON (n.case_id);
CREATE INDEX stakeholder_case        IF NOT EXISTS FOR (n:Stakeholder)              ON (n.case_id);
CREATE INDEX bizgoal_case            IF NOT EXISTS FOR (n:BusinessGoal)             ON (n.case_id);
CREATE INDEX sda_run_subdomain       IF NOT EXISTS FOR (n:SubDomainActivation)      ON (n.run_id, n.sub_domain_id);
CREATE INDEX sda_run_case            IF NOT EXISTS FOR (n:SubDomainActivation)      ON (n.run_id, n.case_id);
CREATE INDEX pa_run_pair             IF NOT EXISTS FOR (n:PairActivation)           ON (n.run_id, n.pair_id);
CREATE INDEX ad_run_pair             IF NOT EXISTS FOR (n:AmbiguityDisposition)     ON (n.run_id, n.pair_id);
CREATE INDEX gate_run_type           IF NOT EXISTS FOR (n:Gate)                     ON (n.run_id, n.gate_type);
CREATE INDEX clauseact_case_clause   IF NOT EXISTS FOR (n:ClauseActivation)         ON (n.case_id, n.clause_id);
CREATE INDEX pe_case_subdomain       IF NOT EXISTS FOR (n:ProportionalityEntry)     ON (n.case_id, n.sub_domain_id);
CREATE INDEX ri_case_type            IF NOT EXISTS FOR (n:RegulatoryInteraction)    ON (n.case_id, n.interaction_type);
CREATE INDEX clause_reg              IF NOT EXISTS FOR (n:RegulatoryClause)         ON (n.regulation_id);
CREATE INDEX so_reg                  IF NOT EXISTS FOR (n:SecurityObjective)        REQUIRE n.regulation_code IS UNIQUE;
CREATE INDEX subdomain_macro         IF NOT EXISTS FOR (n:SubDomain)                ON (n.macro_id);
CREATE INDEX gap_case_severity       IF NOT EXISTS FOR (n:DeclarationGap)           ON (n.case_id, n.severity);
CREATE INDEX ce_domain               IF NOT EXISTS FOR (n:ControlEvidence)          ON (n.domain_id);
```

> **v3 note (REQUIRED):** `Run`-derived node constraints (SDA, PairActivation, AmbiguityDisposition, Gate) are keyed on `(run_id)` — NOT `(id, case_id)` as in v2. Multi-model / multi-spec runs MUST NOT collide on PK.

---

## 5. LLM Agent Navigation Playbook

### Rule 0 — The Prime Directive (No Unscoped Architecture Queries)
> Every query touching Tier 2 nodes (System, DataStore, DataFlow, AuthSystem,
> ThirdPartyService, DataSubject, ExternalParty) MUST begin with the Enterprise anchor:
> `MATCH (e:Enterprise {case_id: $case_id})-[...]`
>
> **Status (v3):** enforced as a **convention** and reviewable in the query examples below; a real linter is on the roadmap but does not exist yet. ETL authors and reviewer agents must apply Rule 0 manually until the linter ships.

---

### Pattern 1: Regulatory Scope & Declaration Gaps
**Always the first query for any assessment.**

```cypher
MATCH (e:Enterprise {case_id: $case_id})
MATCH (e)-[:ACTS_AS {context: $context}]->(role:RegulatoryRole)
MATCH (role)-[:BELONGS_TO_REGULATION]->(r:Regulation)
OPTIONAL MATCH (rar:RegulatoryApplicabilityResult)
  WHERE rar.case_id = $case_id AND rar.regulation_id = r.id
OPTIONAL MATCH (e)-[:HAS_DECLARATION_GAP]->(gap:DeclarationGap)
RETURN e.name                    AS enterprise,
       e.scale                   AS scale,
       collect(DISTINCT {
           regulation: r.id,
           role: role.role_name,
           context: $context,
           applicable: rar.applicable
       })                        AS applicable_regulations,
       collect(DISTINCT {
           reg: gap.reg,
           gap_type: gap.gap_type,
           severity: gap.severity,
           hint: gap.resolution_hint
       })                        AS declaration_gaps;
```

*Note:* `context` (e.g. `"customer_data"`, `"ai_system_deployment"`) picks which role binding to traverse. `OPTIONAL MATCH` against `RegulatoryApplicabilityResult` keeps the applicability verdict available without imposing one role binding per query.

*Agent reads:* If `declaration_gaps` non-empty → flag as outstanding risks before proceeding.

---

### Pattern 2: Asset-to-Obligation Grounding for a Subdomain
**The core pattern. Provides legal obligations + real system IDs + proportionality tier. Scoped to a `Run` so the agent cites evidence from a specific run, not from stale graph state.**

```cypher
MATCH (run:Run {run_id: $run_id})
MATCH (e:Enterprise {case_id: $case_id})
MATCH (sd:SubDomain {id: $subdomain_id})
MATCH (c:RegulatoryClause)-[:MAPPED_TO_SUBDOMAIN]->(sd)
MATCH (c)<-[:CONTAINS_CLAUSE]-(a:Article)<-[:HAS_ARTICLE]-(r:Regulation)
MATCH (e)-[:OPERATES_SYSTEM]->(s:System)-[iso:IN_SCOPE_OF]->(sd)
OPTIONAL MATCH (s)-[:STORES_DATA_IN]->(ds:DataStore)
OPTIONAL MATCH (s)-[:AUTHENTICATED_BY]->(auth:AuthSystem)
OPTIONAL MATCH (sd)-[:HAS_ACTIVATION]->(sda:SubDomainActivation {run_id: $run_id})
OPTIONAL MATCH (sd)-[:ANCHORED_TO_CSF]->(csf:CSFSubcategory)
RETURN sd.name                                                          AS subdomain,
       sda.normative_intensity                                           AS normative_intensity,
       sda.proportionality_tier                                          AS tier,
       sda.applicable_regs                                              AS active_regulations,
       sda.origin                                                       AS activation_origin,
       iso.rule_id                                                       AS in_scope_rule_id,
       iso.basis                                                         AS in_scope_basis,
       collect(DISTINCT r.id + ': ' + c.id
               + ' (' + a.article_reference + ')')                     AS legal_clauses,
       collect(DISTINCT s.id + ' | ' + s.name
               + ' | criticality=' + s.criticality)                     AS affected_systems,
       collect(DISTINCT coalesce(ds.id,'') + ' | ' + coalesce(ds.storage_type,'')
               + ' | pii=' + toString(coalesce(ds.contains_pii,false))) AS affected_stores,
       collect(DISTINCT coalesce(auth.id,'') + ' | '
               + coalesce(auth.auth_type,''))                           AS auth_mechanisms,
       collect(DISTINCT csf.id + ': ' + csf.outcome_text)              AS csf_anchors;
```

*Agent MUST cite in prose:* All IDs in `affected_systems` and `affected_stores`. *Agent SHOULD surface* `in_scope_rule_id` and `in_scope_basis` when invoking `IN_SCOPE_OF` in claims, to make the deterministic basis auditable.

---

### Pattern 3: Proportionality Attributes for a Subdomain
**When writing about evidence depth, ownership, and implementation strategy.**

```cypher
MATCH (e:Enterprise {case_id: $case_id})-[:HAS_PROPORTIONALITY_PROFILE]->(pp:ProportionalityProfile)
MATCH (pp)-[:CONTAINS_ENTRY]->(pe:ProportionalityEntry {sub_domain_id: $subdomain_id})
RETURN pe.tier                  AS proportionality_tier,
       pe.inheritability         AS inheritability,
       pe.priority               AS priority,
       pe.satisfaction_pattern   AS satisfaction_pattern,
       pe.evidence_depth         AS evidence_depth,
       pe.verification_method    AS verification_method,
       pe.ownership              AS ownership,
       pe.example_controls       AS example_controls;
```

*Agent reads:* `tier = RIGOROUS` → full technical evidence package required.
`tier = MINIMAL` → company exempt from deep implementation at current scale.
`satisfaction_pattern = INHERIT` → inherit from cloud provider; cite `ThirdPartyService` node.

---

### Pattern 4: Regulatory Interactions (Tensions & Conflicts)
**When writing about cross-regulation frictions on a subdomain.**

```cypher
MATCH (e:Enterprise {case_id: $case_id})-[:HAS_REGULATORY_INTERACTION]->(ri:RegulatoryInteraction)
WHERE $subdomain_id IN ri.sub_domains
RETURN ri.interaction_type        AS conflict_type,
       ri.involved_regs           AS regulations,
       ri.conflict_description    AS friction_description,
       ri.resolution_principle    AS resolution,
       ri.severity                AS severity,
       ri.source_id               AS source_reference
ORDER BY
  CASE ri.severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END;
```

*Agent MUST produce for each HIGH/MEDIUM tension:*
```markdown
### Tension Resolution: [REG_A] vs [REG_B] — [conflict_type]
- Friction: [friction_description]
- Resolution adopted: [resolution_principle]
- Severity: [severity]
```
Saying "the company must balance these requirements" without citing `resolution_principle` = Gate C failure. CONDITIONAL pairs (documented ambiguities) require the structured disposition block from Pattern 8.

---

### Pattern 5: Security Objectives for a Subdomain (SO hierarchy)
**When writing at the objective layer (SO-REG-NNN and SR-REG-NNN).**

```cypher
MATCH (so:SecurityObjective)-[:SCOPED_TO]->(sd:SubDomain {id: $subdomain_id})
MATCH (so)-[:BELONGS_TO]->(r:Regulation)
MATCH (e:Enterprise {case_id: $case_id})-[:ACTS_AS]->(:RegulatoryRole)-[:BELONGS_TO_REGULATION]->(r)
OPTIONAL MATCH (sr:SecurityRule)-[:REFINES]->(so)
OPTIONAL MATCH (sr)-[:ANCHORED_TO_CSF]->(csf:CSFSubcategory)
RETURN so.id                                    AS so_id,
       r.id                                     AS regulation,
       so.statement                             AS objective_statement,
       so.regulatory_source                     AS legal_source,
       collect(DISTINCT sr.id + ': ' + sr.statement) AS rules,
       collect(DISTINCT csf.id)                 AS csf_controls;
```

---

### Pattern 6: Data Subject Clause Auto-Inference (GDPR Art. 8, 9, 22)
**When evaluating GDPR applicability with special categories.**

```cypher
MATCH (e:Enterprise {case_id: $case_id})-[:HAS_DATA_SUBJECT]->(ds:DataSubject)
OPTIONAL MATCH (ds)-[:TRIGGERS_CLAUSE]->(c:RegulatoryClause)
OPTIONAL MATCH (f:DataFlow {case_id: $case_id})-[:INVOLVES_DATA_OF]->(ds)
RETURN ds.type                                            AS subject_type,
       ds.special_category                               AS special_category_art9,
       ds.estimated_count                                AS count,
       collect(DISTINCT c.id + ' — ' + c.article_reference) AS triggered_clauses,
       collect(DISTINCT f.id + ' | ' + f.protocol)       AS flows_with_this_data;
```

---

### Pattern 7: Gate Validation Status (before emitting final document)
**Always run before producing any Phase 1 output document.**

```cypher
MATCH (run:Run {run_id: $run_id})-[:PRODUCED]->(g:Gate)
RETURN g.gate_type AS gate, g.status AS status, g.criteria_check_result AS detail
```

(`GateP` is no longer a separate label — it lives under `Gate` with `gate_type = GateP` and the same provenance pattern.)

---

### Pattern 8: Conditional Pairs & Ambiguity Dispositions
**Closes the ambiguity substrate (OBJECTIVES_CONTRACT §4). Run-scoped; only populated when specs are at v1.2+.**

```cypher
MATCH (run:Run {run_id: $run_id})
MATCH (e:Enterprise {case_id: $case_id})
MATCH (p:RegulatoryPair)
WHERE p.classification = 'CONDITIONAL'
  AND any(r IN p.reg_a + [p.reg_b] WHERE r IN
    [(e)-[:ACTS_AS]->(:RegulatoryRole)-[:BELONGS_TO_REGULATION]->(reg:Regulation) | reg.id])
MATCH (p)-[:HAS_ACTIVATION]->(pa:PairActivation {run_id: $run_id})
OPTIONAL MATCH (p)-[:HAS_AMBIGUITY_DISPOSITION]->(ad:AmbiguityDisposition {run_id: $run_id})
RETURN p.id                              AS pair,
       pa.company_scope_verdict          AS scope_verdict,
       ad.applicable_reading             AS reading,
       ad.disposition                    AS disposition,
       ad.consequence                    AS consequence,
       ad.anchors                        AS anchors;
```

*Agent MUST produce for each CONDITIONAL pair (no exceptions):*
```markdown
### Ambiguity Disposition: [REG_A] vs [REG_B] — D-XX.Y
- Reading adopted: [applicable_reading]
- Anchors: [comma-separated list, e.g. "GDPR Art. 5(1)(c), Tier=HIGH, case3:SYS-CBS, BG-case3-001"]
- Consequence: [consequence]
- Disposition: [RESOLVED_BY_FACT | RESOLVED_BY_TIER | NEEDS_HUMAN]
```

*Gate checks:* every CONDITIONAL pair in scope has exactly one `AmbiguityDisposition` node per Run (coverage); `disposition ∈ closed vocabulary`; `anchors ⊆ closed lists` (article IDs, tier, asset IDs, business goal IDs); `NEEDS_HUMAN` rows must include `consequence` non-empty.

---



## 6. ETL Load Order (41-Step Dependency Graph)

```
PHASE 0 — Foundation (once, case-agnostic — load order matters for FK integrity)
  01. CSFFunction                    (6 nodes)
  02. CSFCategory                    (34 nodes, FK→CSFFunction)
  03. CSFSubcategory                 (106 nodes, FK→CSFCategory) + ANCHORED_IN
  04. Regulation                     (5 nodes)
  05. Article                        (FK→Regulation) + HAS_ARTICLE
  06. RegulatoryClause               (331 nodes, FK→Article) + CONTAINS_CLAUSE
  07. RegulatoryRole                 (9 nodes) + BELONGS_TO_REGULATION
  08. BINDS_PARTY                    (RegulatoryClause → RegulatoryRole, bulk)
  09. SecurityControlDomain          (10 macro-domains)
  10. SubDomain                      (38, FK→SecurityControlDomain) + HAS_SUBDOMAIN
  11. MAPPED_TO_SUBDOMAIN            (Clause → SubDomain, bulk)
  12. ANCHORED_TO_CSF                (SubDomain → CSFSubcategory, bulk; carries confidence + rationale on the edge)
  13. SecurityObjective              (FK→Regulation) + BELONGS_TO, SCOPED_TO
  14. HierarchicalSecurityObjective  (FK→SecurityObjective) + DERIVES_FROM
  15. SubSecurityObjective           + AGGREGATES → HSO
  16. SecurityRule                   (FK→SO) + REFINES, ANCHORED_TO_CSF
  17. IN_TENSION_WITH                (Clause ↔ Clause, from methodology conflict catalogue)
  18. RegulatoryPair                 (196 nodes, FROZEN) — populated by `preproc_catalog.load_pairs()`

PHASE 1 — Per-Case Normative (run once per case_id)
  19. Enterprise                     (root node, intrinsic inputs only)
  20. Stakeholder                    (FK→Enterprise) + DEFINES → BusinessGoal
  21. BusinessGoal                   (FK→Enterprise)
  22. ACTS_AS                        (Enterprise → RegulatoryRole, with `context` property)
  23. RegulatoryApplicabilityResult  + HAS_APPLICABILITY_RESULT
  24. DeclarationGap                 (from negative_analyses in interactions.yaml) + HAS_DECLARATION_GAP
  25. ConditionalExtension + BlockTrigger
  26. RegulatoryInteraction          (all 4 types from interactions.yaml) + HAS_REGULATORY_INTERACTION
  27. ClauseActivation               (per case × clause, deterministic derivation) + HAS_CLAUSE_ACTIVATION
  28. ComplementarityAnalysis        + COMPARES, SCOPED_TO
  29. DomainCoverageEntry            + (Regulation→Entry, Domain→Entry)
  30. DomainElaborationEntry         + (Complementarity→Entry, Entry→SubDomain)
  31. ProportionalityProfile         + HAS_PROPORTIONALITY_PROFILE
  32. ProportionalityEntry           (38 per case) + CONTAINS_ENTRY, SCOPED_TO, OWNED_BY → Stakeholder
  33. ControlEvidence                (mirrors data/control_evidence/D-XX.yaml) + HAS_CONTROL_EVIDENCE

PHASE 2 — Per-Case Architecture (run once per case_id, after Phase 1)
  34. System                         (FK→Enterprise) + OPERATES_SYSTEM  (criticality normalised UPPER)
  35. DataStore                      + STORES_DATA_IN (System→DataStore)
  36. DataFlow                       + ORIGINATES_FROM, TERMINATES_AT (multi-target)
  37. AuthSystem                     + AUTHENTICATED_BY (System→AuthSystem)
  38. ThirdPartyService              + OUTSOURCED_TO (System→ThirdParty)
  39. ExternalParty                  (BaFin goAML, end-users, public endpoints) + (no FK until referenced)
  40. DataSubject                    + HAS_DATA_SUBJECT (Enterprise→DataSubject)

PHASE 3 — Computed / Inferred (run after Phase 2; deterministic, versioned, testable)
  41. IN_SCOPE_OF (System→SubDomain)  — via `data/in_scope_of_rules.yaml`; rule_id + basis recorded on edge
  42. TRIGGERS_CLAUSE (DataSubject→RegulatoryClause) — special_category=true → Art.9
  43. INVOLVES_DATA_OF (DataFlow→DataSubject)  — from data_flows.yaml subject refs
  44. GOVERNED_BY_PROPORTIONALITY (SubDomainActivation→ProportionalityEntry) — join
```

### 6.5 Derived properties on DataFlow (rules)
- `is_cross_border`: `origin_jurisdiction ≠ destination_jurisdiction`
- `carries_pii`: regex match against `data_type` keywords (`PII`, `name`, `email`, `address`, etc.) — kept conservative (defaults to false on no match); superset list checked into `data/dataflow_derivation_rules.yaml`
- `carries_financial`: same pattern against financial keywords
- `transfer_mechanism`: empty → "None"; populated by manual annotation only

Rules are versioned in `data/*_rules.yaml` with one rule = one test in the ETL test suite.

### 6.4 PHASE 4 — Verify (mandatory after every load)
- Counts vs. expected: CSFFunction=6, CSFCategory=34, CSFSubcategory=106, Regulation=5, RegulatoryClause=331, SecurityControlDomain=10, SubDomain=38, RegulatoryPair=196, RegulatoryRole=9. Mismatches MUST fail the load.
- Per case: system/data_store/data_flow/auth_system/third_party/data_subject counts vs YAMLs.
- Orphan check: every FK on the right side has a target.
- Isolation: `MATCH (n) WHERE (n:RegulatoryInteraction OR n:SubDomainActivation OR n:PairActivation OR n:AmbiguityDisposition OR n:Gate OR n:ClauseActivation OR n:ProportionalityEntry OR n:ProportionalityProfile OR n:ControlEvidence OR n:DeclarationGap) AND (n.case_id IS NULL OR n.run_id IS NULL)` returns zero (Run-derived nodes need `run_id`; case-derived nodes need `case_id`).
- MERGE collision report: any case where two source files would produce the same PK is a hard failure.
- Fingerprint: write `(:GraphMeta {key: 'preproc_fingerprint', value: <sha256>})` and `(:GraphMeta {key: 'etl_version', value: <semver>})`. PHASE 4 fails on mismatch against the source-of-truth fingerprint from `preproc_out/`.

---

## 7. Boundary with Phase 2 (aegis-kg ETL Phase 2)

The following entities from `phase2_elaboration_secure_design.md` are **explicitly out of scope** for Phase 1 and belong in the `aegis-kg` ETL Phase 2 scripts:

| Entity | Phase 2 Reason |
|---|---|
| `RegulatoryObligation` | Doc 08 derivation (v3: removed from Phase 1 ontology; was ghost in v2) |
| `StrategicImplication` | Doc 08 / 09 elaboration |
| `ImplementationMapping` | v3: reabsorbed into properties on `SubDomain-[:ANCHORED_TO_CSF]->CSFSubcategory` edge; listed here for traceability |
| `StrategicTension` | Requires MAP output + LLM synthesis (REDUCE stage) |
| `ConflictResolution` + `JustificationRecord` | Requires Phase 1 tensions as input |
| `ArchitecturalGoal` / `PrivacyGoal` / `SecurityGoal` | Derived from RegulatoryObligation — Phase 2 output |
| `AbstractRule` / `ComplianceRule` / `BestPracticeRule` | Phase 2 rules catalog |
| `RulesCatalog` | Aggregation of Phase 2 outputs |
| `RiskOwner` | Maps to Stakeholder from Phase 1 but requires Phase 2 context |
| `(:Control {status: IMPLEMENTED\|PARTIAL\|PLANNED\|ABSENT})` + `[:SATISFIES]->(:RegulatoryClause)` | Phase 2: evidence is in Phase 1 (ControlEvidence), STATUS is not. Open Q1 resolved. |

---

## 8. Resolved Decisions (formerly Open Questions)

1. **Control implementation status (status field):** evidence lives in Phase 1 (`:ControlEvidence`); the `status: IMPLEMENTED|PARTIAL|PLANNED|ABSENT` `(:Control)-[:SATISFIES]->(:RegulatoryClause)` lives in Phase 2 (see §7).
2. **Accountability chain:** `(:ProportionalityEntry)-[:OWNED_BY]->(:Stakeholder)` added (see §3.1); enables DORA board-level queries without changing property schemas.
3. **Source traceability:** per-node `origin` property (`"deterministic" | "llm:<spec_id>"`) + per-case `provenance` (file + line) recorded in ETL; full `(:Source)` node is overkill at this scale. `(:GraphMeta)` fingerprint catches catalog drift.
4. **Temporal deadlines:** `RegulatoryClause.enforcement_date` as a property is sufficient for Phase 1. Dedicated `(:ComplianceDeadline)` node is reserved for Phase 2 (countdown semantics).
5. **Cross-case ComplementarityAnalysis:** stays case-agnostic — it is a structural regulatory comparison by class-model definition.

---

## 9. Agent Output Quality Checklist

```
BEFORE EMITTING ANY PHASE 1 DOCUMENT:

  ✓ Ran Pattern 1 — scope and declaration gaps documented
  ✓ Ran Pattern 7 — all gates PASS or gaps acknowledged
  ✓ Every subdomain section cites ≥1 real SYS-* or STORE-* ID
  ✓ Every obligation cites specific article (e.g. "DORA Art. 9(2)")
  ✓ Every GDPR Data Subject section checks special_category flag
  ✓ Every HIGH/MEDIUM tension has a structured resolution block
  ✓ CSF anchors cited with exact ID (e.g. "PR.DS-01")
  ✓ ProportionalityEntry.tier consulted before claiming evidence depth

  ✗ REJECT: "the enterprise should implement robust access controls"
  ✗ REJECT: "according to applicable European regulations"
  ✗ REJECT: tension identified with no resolution_principle cited
  ✗ REJECT: CSF control mentioned without exact subcategory ID
  ✗ REJECT: any Architecture query not scoped to case_id
```
