# AEGIS-KG Phase 1 — Neo4j Unified Ontology & LLM Navigation Specification

**Document ID:** `AEGIS-DOC-NEO4J-ONTOLOGY-002`
**Status:** DRAFT / PENDING PEER MODEL REVIEW
**Author:** Antigravity (Pair Programming Session)
**Date:** 2026-09-03 (v2 — merged with canonical Phase 1 class model v1.1)
**Source of Truth:** `methodology-00/diagrams/Class_Models/phase1_contextual_definition.md` (v1.1, 2026-07-13)
**Target Graph Database:** Neo4j (Bolt: `bolt://localhost:7688`, HTTP: `http://localhost:7475`)
**Repository:** `aegis-phase1`
**Audience:** Peer LLMs, Knowledge Engineers, ETL Authors, Academic Reviewers.

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
│  DomainCoverageEntry · DomainElaborationEntry · ImplementationMapping ·        │
│  SecurityObjective · HierarchicalSecurityObjective · SubSecurityObjective ·    │
│  SubDomainPipeline · SecurityRule · RegulatoryApplicabilityResult ·            │
│  DeclarationGap · BlockTrigger · ConditionalExtension · RegulatoryInteraction ·│
│  SubDomainActivation · ProportionalityProfile · ProportionalityEntry ·         │
│  Gate · GateP · Gate1A · Gate1B · Gate1C · NativeCompliance · InheritedCompl. │
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
processes_personal_data      Boolean        true
places_digital_products_eu   Boolean        true
dora_financial_entity        Boolean        true
nis2_sector                  String         "banking"
aiact_high_risk_system       Boolean        true
assessment_date              String         "2026-09-03"
```

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
obligated_party         String[]       ["CONTROLLER","PROCESSOR"]  (ObligatedPartyType enum values)
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

#### `(:RegulatoryObligation)` — Derived Compliance Obligation
```
id                      String  PK     "OBL-D-01.1-GDPR-001"
description             String
category                String         "Technical" | "Organisational" | "Legal"
target_sub_domain       String  FK→SubDomain
obligation_type         String  Enum   CONTINUOUS | PERIODIC | TRIGGERED | ONE_TIME
obligated_party         String[]       ["CONTROLLER"]
normative_intensity     Float          0.5 to 1.0
```

#### `(:StrategicImplication)` — Business-Level Impact Statement
```
id                String  PK     "SI-DORA-001"
description       String
business_impact   String         Operational or financial consequence
compliance_risk   String         Regulatory risk if ignored
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
normative_intensity   Float          3.8
proportionality_tier  String  Enum   MINIMAL | LIGHTWEIGHT | STANDARD | RIGOROUS | DEFERRED
```

#### `(:RegulatoryInteraction)` — Cross-Regulation Friction (from interactions.yaml)
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

#### `(:ImplementationMapping)` — NIST CSF grounding for a subdomain
```
id                  String  PK     "IM-D-01.1-PR.DS-01"
sub_domain_id       String  FK→SubDomain
primary_framework   String         "NIST CSF 2.0"
framework_reference String         "PR.DS-01"
rationale           String
confidence_level    String  Enum   HIGH | MEDIUM | LOW
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
criticality         String  Enum   low | medium | high | critical
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
Source: `cases/*/input/architecture/data_flows.yaml`

```
id                        String  PK     "case3:FLOW-01"
case_id                   String  FK→Enterprise
name                      String         "Core to Payment Gateway Transaction Flow"
source_system_id          String  FK→System
dest_system_id            String  FK→System
protocol                  String         "mTLS / gRPC" | "TLS 1.3 / HTTPS"
is_cross_border           Boolean        false
origin_jurisdiction       String         "DE"
destination_jurisdiction  String         "DE"
transfer_mechanism        String         "None" | "SCCs" | "Adequacy" | "BCR"
carries_pii               Boolean        true
carries_financial         Boolean        true
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
type                String  Enum   customer | employee | minor | counter_party | applicant
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
| `(:Enterprise)-[:SUBJECT_TO]->(:Regulation)` | `role: String, rationale: String, applicable: Boolean` |
| `(:Enterprise)-[:HAS_APPLICABILITY_RESULT]->(:RegulatoryApplicabilityResult)` | — |
| `(:Enterprise)-[:HAS_DECLARATION_GAP]->(:DeclarationGap)` | — |
| `(:Enterprise)-[:HAS_PROPORTIONALITY_PROFILE]->(:ProportionalityProfile)` | — |
| `(:Enterprise)-[:TRIGGERS_EXTENSION]->(:ConditionalExtension)` | `active: Boolean` |
| `(:Enterprise)-[:HAS_REGULATORY_INTERACTION]->(:RegulatoryInteraction)` | — |
| `(:Regulation)-[:HAS_ARTICLE]->(:Article)` | — |
| `(:Article)-[:CONTAINS_CLAUSE]->(:RegulatoryClause)` | — |
| `(:RegulatoryClause)-[:MAPPED_TO_SUBDOMAIN]->(:SubDomain)` | `confidence: String, normative_strength: Float` |
| `(:RegulatoryClause)-[:GENERATES_OBLIGATION]->(:RegulatoryObligation)` | — |
| `(:RegulatoryObligation)-[:IMPLIES]->(:StrategicImplication)` | — |
| `(:SecurityControlDomain)-[:HAS_SUBDOMAIN]->(:SubDomain)` | — |
| `(:SubDomain)-[:ANCHORED_TO_CSF]->(:CSFSubcategory)` | `mapping_type: "DIRECT"\|"PARTIAL"` |
| `(:SubDomain)-[:HAS_ACTIVATION]->(:SubDomainActivation)` | scoped by case_id on activation node |
| `(:SubDomainActivation)-[:GOVERNED_BY_PROPORTIONALITY]->(:ProportionalityEntry)` | — |
| `(:ProportionalityProfile)-[:CONTAINS_ENTRY]->(:ProportionalityEntry)` | — |
| `(:ProportionalityEntry)-[:SCOPED_TO]->(:SubDomain)` | — |
| `(:SecurityObjective)-[:BELONGS_TO]->(:Regulation)` | — |
| `(:SecurityObjective)-[:SCOPED_TO]->(:SubDomain)` | — |
| `(:HierarchicalSecurityObjective)-[:DERIVES_FROM]->(:SecurityObjective)` | — |
| `(:SubSecurityObjective)-[:AGGREGATED_BY]->(:HierarchicalSecurityObjective)` | — |
| `(:SecurityRule)-[:REFINES]->(:SecurityObjective)` | — |
| `(:SecurityRule)-[:ANCHORED_TO_CSF]->(:CSFSubcategory)` | — |
| `(:RegulatoryClause)-[:IN_TENSION_WITH]->(:RegulatoryClause)` | `tension_id: String, interaction_type: String` |
| `(:Gate)-[:VALIDATES_RESULT]->(:RegulatoryApplicabilityResult)` | Gate1A |
| `(:Gate)-[:VALIDATES_ACTIVATION]->(:SubDomainActivation)` | Gate1B |
| `(:GateP)-[:VALIDATES_PROFILE]->(:ProportionalityProfile)` | GateP |
| `(:Stakeholder)-[:DEFINES]->(:BusinessGoal)` | — |
| `(:BusinessGoal)-[:RESTRICTS_SHAPE_OF]->(:StrategicImplication)` | — |

### 3.2 Enterprise Architecture Relationships

| Source → Edge → Target | Properties |
|---|---|
| `(:Enterprise)-[:OPERATES_SYSTEM]->(:System)` | `owner: String` |
| `(:Enterprise)-[:HAS_DATA_SUBJECT]->(:DataSubject)` | — |
| `(:System)-[:STORES_DATA_IN]->(:DataStore)` | `access_type: String` |
| `(:System)-[:SENDS_DATA_TO]->(:System)` | `dataflow_id: String, protocol: String` |
| `(:System)-[:AUTHENTICATED_BY]->(:AuthSystem)` | `enforced: Boolean` |
| `(:System)-[:OUTSOURCED_TO]->(:ThirdPartyService)` | `critical_dora: Boolean` |
| `(:System)-[:IN_SCOPE_OF]->(:SubDomain)` | `proportionality_tier: String` |
| `(:DataFlow)-[:INVOLVES_DATA_OF]->(:DataSubject)` | — |
| `(:DataSubject)-[:TRIGGERS_CLAUSE]->(:RegulatoryClause)` | `trigger_reason: String` |

### 3.3 Cross-Tier Bridge Relationships

| Source → Edge → Target | Semantic Meaning |
|---|---|
| `(:RegulatoryInteraction)-[:INVOLVES_REGULATION]->(:Regulation)` | Multi-reg conflict scope |
| `(:RegulatoryInteraction)-[:SCOPED_TO_SUBDOMAIN]->(:SubDomain)` | Conflict subdomain scope |
| `(:ComplementarityAnalysis)-[:COMPARES]->(:Regulation)` | `regulation_position: "A"\|"B"` |
| `(:ComplementarityAnalysis)-[:SCOPED_TO]->(:SubDomain)` | Subdomain scope |
| `(:ImplementationMapping)-[:ANCHORS]->(:CSFSubcategory)` | CSF grounding |
| `(:ImplementationMapping)-[:APPLIED_TO]->(:SubDomain)` | Subdomain coverage |

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
CREATE CONSTRAINT csf_fn_pk          IF NOT EXISTS FOR (n:CSFFunction)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_cat_pk         IF NOT EXISTS FOR (n:CSFCategory)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_sub_pk         IF NOT EXISTS FOR (n:CSFSubcategory)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT system_pk          IF NOT EXISTS FOR (n:System)                   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT datastore_pk       IF NOT EXISTS FOR (n:DataStore)                REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dataflow_pk        IF NOT EXISTS FOR (n:DataFlow)                 REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT authsys_pk         IF NOT EXISTS FOR (n:AuthSystem)               REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT thirdparty_pk      IF NOT EXISTS FOR (n:ThirdPartyService)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT datasubject_pk     IF NOT EXISTS FOR (n:DataSubject)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sda_pk             IF NOT EXISTS FOR (n:SubDomainActivation)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ri_pk              IF NOT EXISTS FOR (n:RegulatoryInteraction)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pe_pk              IF NOT EXISTS FOR (n:ProportionalityEntry)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT gap_pk             IF NOT EXISTS FOR (n:DeclarationGap)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT rar_pk             IF NOT EXISTS FOR (n:RegulatoryApplicabilityResult) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pp_pk              IF NOT EXISTS FOR (n:ProportionalityProfile)   REQUIRE n.id IS UNIQUE;

// ── Lookup Indexes ───────────────────────────────────────────────────────────
CREATE INDEX system_case             IF NOT EXISTS FOR (n:System)                   ON (n.case_id);
CREATE INDEX datastore_case          IF NOT EXISTS FOR (n:DataStore)                ON (n.case_id);
CREATE INDEX dataflow_case           IF NOT EXISTS FOR (n:DataFlow)                 ON (n.case_id);
CREATE INDEX sda_case_subdomain      IF NOT EXISTS FOR (n:SubDomainActivation)      ON (n.case_id, n.sub_domain_id);
CREATE INDEX pe_case_subdomain       IF NOT EXISTS FOR (n:ProportionalityEntry)     ON (n.case_id, n.sub_domain_id);
CREATE INDEX ri_case_type            IF NOT EXISTS FOR (n:RegulatoryInteraction)    ON (n.case_id, n.interaction_type);
CREATE INDEX clause_reg              IF NOT EXISTS FOR (n:RegulatoryClause)         ON (n.regulation_id);
CREATE INDEX so_reg                  IF NOT EXISTS FOR (n:SecurityObjective)        ON (n.regulation_code);
CREATE INDEX subdomain_macro         IF NOT EXISTS FOR (n:SubDomain)                ON (n.macro_id);
CREATE INDEX gap_case_severity       IF NOT EXISTS FOR (n:DeclarationGap)           ON (n.case_id, n.severity);
```

---

## 5. LLM Agent Navigation Playbook

### Rule 0 — The Prime Directive (No Unscoped Architecture Queries)
> Every query touching Tier 2 nodes (System, DataStore, DataFlow, AuthSystem,
> ThirdPartyService, DataSubject) MUST begin with the Enterprise anchor:
> `MATCH (e:Enterprise {case_id: $case_id})-[...]`
> The query linter rejects unscoped architecture queries.

---

### Pattern 1: Regulatory Scope & Declaration Gaps
**Always the first query for any assessment.**

```cypher
MATCH (e:Enterprise {case_id: $case_id})-[st:SUBJECT_TO]->(r:Regulation)
OPTIONAL MATCH (e)-[:HAS_DECLARATION_GAP]->(gap:DeclarationGap)
RETURN e.name                    AS enterprise,
       e.scale                   AS scale,
       collect(DISTINCT {
           regulation: r.id,
           role: st.role,
           applicable: st.applicable
       })                        AS applicable_regulations,
       collect(DISTINCT {
           reg: gap.reg,
           gap_type: gap.gap_type,
           severity: gap.severity,
           hint: gap.resolution_hint
       })                        AS declaration_gaps;
```

*Agent reads:* If `declaration_gaps` non-empty → flag as outstanding risks before proceeding.

---

### Pattern 2: Asset-to-Obligation Grounding for a Subdomain
**The core pattern. Provides legal obligations + real system IDs + proportionality tier.**

```cypher
MATCH (sd:SubDomain {id: $subdomain_id})
MATCH (c:RegulatoryClause)-[:MAPPED_TO_SUBDOMAIN]->(sd)
MATCH (c)<-[:CONTAINS_CLAUSE]-(a:Article)<-[:HAS_ARTICLE]-(r:Regulation)
MATCH (e:Enterprise {case_id: $case_id})-[:OPERATES_SYSTEM]->(s:System)-[:IN_SCOPE_OF]->(sd)
OPTIONAL MATCH (s)-[:STORES_DATA_IN]->(ds:DataStore)
OPTIONAL MATCH (s)-[:AUTHENTICATED_BY]->(auth:AuthSystem)
OPTIONAL MATCH (sd)-[:HAS_ACTIVATION]->(sda:SubDomainActivation {case_id: $case_id})
OPTIONAL MATCH (sd)-[:ANCHORED_TO_CSF]->(csf:CSFSubcategory)
RETURN sd.name                                                          AS subdomain,
       sda.normative_intensity                                           AS normative_intensity,
       sda.proportionality_tier                                          AS tier,
       sda.applicable_regs                                              AS active_regulations,
       collect(DISTINCT r.id + ': ' + c.id
               + ' (' + a.article_reference + ') ['
               + c.normative_strength + ']')                            AS legal_clauses,
       collect(DISTINCT s.id + ' | ' + s.name
               + ' | criticality=' + s.criticality)                     AS affected_systems,
       collect(DISTINCT coalesce(ds.id,'') + ' | ' + coalesce(ds.storage_type,'')
               + ' | pii=' + toString(coalesce(ds.contains_pii,false))) AS affected_stores,
       collect(DISTINCT coalesce(auth.id,'') + ' | '
               + coalesce(auth.auth_type,''))                           AS auth_mechanisms,
       collect(DISTINCT csf.id + ': ' + csf.outcome_text)              AS csf_anchors;
```

*Agent MUST cite in prose:* All IDs in `affected_systems` and `affected_stores`.

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
Saying "the company must balance these requirements" without citing `resolution_principle` = Gate C failure.

---

### Pattern 5: Security Objectives for a Subdomain (SO hierarchy)
**When writing at the objective layer (SO-REG-NNN and SR-REG-NNN).**

```cypher
MATCH (so:SecurityObjective)-[:SCOPED_TO]->(sd:SubDomain {id: $subdomain_id})
MATCH (so)-[:BELONGS_TO]->(r:Regulation)
MATCH (e:Enterprise {case_id: $case_id})-[:SUBJECT_TO]->(r)
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
MATCH (g:Gate {case_id: $case_id})
RETURN g.gate_type AS gate, g.status AS status, g.criteria_check_result AS detail
UNION ALL
MATCH (gp:GateP {case_id: $case_id})
RETURN 'GateP' AS gate, gp.status AS status,
       'doc_exists=' + toString(gp.document_exists)
       + ' | active_rows=' + toString(gp.active_rows_complete)
       + ' | five_attrs=' + toString(gp.five_attributes_complete)
       + ' | rule11=' + toString(gp.rule_11_satisfied) AS detail;
```

---

## 6. ETL Load Order (34-Step Dependency Graph)

```
PHASE 0 — Foundation (once, case-agnostic — load order matters for FK integrity)
  01. CSFFunction                    (6 nodes)
  02. CSFCategory                    (34 nodes, FK→CSFFunction)
  03. CSFSubcategory                 (106 nodes, FK→CSFCategory) + ANCHORED_IN
  04. Regulation                     (5 nodes)
  05. Article                        (FK→Regulation) + HAS_ARTICLE
  06. RegulatoryClause               (331 nodes, FK→Article) + CONTAINS_CLAUSE
  07. SecurityControlDomain          (10 macro-domains)
  08. SubDomain                      (38, FK→SecurityControlDomain) + HAS_SUBDOMAIN
  09. MAPPED_TO_SUBDOMAIN            (Clause → SubDomain, bulk)
  10. ANCHORED_TO_CSF                (SubDomain → CSFSubcategory, bulk)
  11. SecurityObjective              (FK→Regulation) + BELONGS_TO, SCOPED_TO
  12. HierarchicalSecurityObjective  (FK→SecurityObjective) + DERIVES_FROM
  13. SubSecurityObjective           (FK→HSO) + AGGREGATED_BY
  14. SecurityRule                   (FK→SO) + REFINES, ANCHORED_TO_CSF
  15. IN_TENSION_WITH                (Clause ↔ Clause, from methodology conflict catalogue)

PHASE 1 — Per-Case Normative (run once per case_id)
  16. Enterprise                     (root node)
  17. Stakeholder                    (FK→Enterprise) + DEFINES → BusinessGoal
  18. BusinessGoal                   (FK→Enterprise)
  19. SUBJECT_TO                     (Enterprise → Regulation, with role property)
  20. RegulatoryApplicabilityResult  + HAS_APPLICABILITY_RESULT
  21. DeclarationGap                 (from negative_analyses in interactions.yaml) + HAS_DECLARATION_GAP
  22. ConditionalExtension + BlockTrigger
  23. RegulatoryInteraction          (all 4 types from interactions.yaml) + HAS_REGULATORY_INTERACTION
  24. SubDomainActivation            (MAP output, 38 per case) + HAS_ACTIVATION
  25. ComplementarityAnalysis        + COMPARES, SCOPED_TO
  26. DomainCoverageEntry            + (Regulation→Entry, Domain→Entry)
  27. DomainElaborationEntry         + (Complementarity→Entry, Entry→SubDomain)
  28. ProportionalityProfile         + HAS_PROPORTIONALITY_PROFILE
  29. ProportionalityEntry           (38 per case) + CONTAINS_ENTRY, SCOPED_TO
  30. Gate (1A, 1B, 1C)             + VALIDATES_* relationships
  31. GateP                          + VALIDATES_PROFILE

PHASE 2 — Per-Case Architecture (run once per case_id, after Phase 1)
  32. System                         (FK→Enterprise) + OPERATES_SYSTEM
  33. DataStore                      + STORES_DATA_IN (System→DataStore)
  34. DataFlow                       + SENDS_DATA_TO (System→System)
  35. AuthSystem                     + AUTHENTICATED_BY (System→AuthSystem)
  36. ThirdPartyService              + OUTSOURCED_TO (System→ThirdParty)
  37. DataSubject                    + HAS_DATA_SUBJECT (Enterprise→DataSubject)

PHASE 3 — Computed / Inferred (run after Phase 2)
  38. IN_SCOPE_OF (System→SubDomain)  — derived from criticality + data mapping
  39. TRIGGERS_CLAUSE (DataSubject→RegulatoryClause) — special_category=true → Art.9
  40. INVOLVES_DATA_OF (DataFlow→DataSubject)  — from data_flows.yaml subject refs
  41. GOVERNED_BY_PROPORTIONALITY (SubDomainActivation→ProportionalityEntry) — join
```

---

## 7. Boundary with Phase 2 (aegis-kg ETL Phase 2)

The following entities from `phase2_elaboration_secure_design.md` are **explicitly out of scope** for Phase 1 and belong in the `aegis-kg` ETL Phase 2 scripts:

| Entity | Phase 2 Reason |
|---|---|
| `StrategicTension` | Requires MAP output + LLM synthesis (REDUCE stage) |
| `ConflictResolution` + `JustificationRecord` | Requires Phase 1 tensions as input |
| `ArchitecturalGoal` / `PrivacyGoal` / `SecurityGoal` | Derived from RegulatoryObligation — Phase 2 output |
| `AbstractRule` / `ComplianceRule` / `BestPracticeRule` | Phase 2 rules catalog |
| `RulesCatalog` | Aggregation of Phase 2 outputs |
| `RiskOwner` | Maps to Stakeholder from Phase 1 but requires Phase 2 context |

---

## 8. Open Questions for Peer Model Review

1. **Control Implementation State:** Should a `(:Control)` node with
   `status: IMPLEMENTED|PARTIAL|PLANNED|ABSENT` and `[:SATISFIES]->(:RegulatoryClause)` live
   in Phase 1 or Phase 2? It bridges the obligation layer and operational reality —
   arguably it's Phase 1 context but populated during Phase 2.

2. **Accountability Chain in Graph:** `ProportionalityEntry.ownership` captures SUPPLIER/COMPANY/SHARED
   tiers but doesn't name the accountable Stakeholder. Should
   `(:ProportionalityEntry)-[:OWNED_BY]->(:Stakeholder)` be added to enable DORA board-level
   accountability queries?

3. **Provenance / Source Traceability:** No `(:Source)` node tracks which YAML file
   and schema version each node came from. Required for academic reproducibility and
   for CI pipeline drift detection. Should this be a full node or just properties on each node?

4. **Temporal Deadline as Node vs Property:** `RegulatoryClause.enforcement_date` exists
   as a property. Is this sufficient for agents to answer "what obligations are due in 6 months"
   or do we need a dedicated `(:ComplianceDeadline)` node with countdown semantics?

5. **Cross-Case ComplementarityAnalysis:** `ComplementarityAnalysis` currently compares
   two regulations scoped to a SubDomain. Should it also be scoped to `case_id`,
   or is it case-agnostic (purely regulatory comparison independent of which company is assessed)?

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
