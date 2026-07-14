---
document_id: AEGIS-COMMON-01
title: AEGIS Intake Form — Company Context Assessment (AUTO-GENERATED)
version: 3.0
author: AEGIS Pipeline (auto-generated from YAML input)
status: AUTO-GENERATED
case_study: case1-tinytask
---

# AEGIS Intake Form — Company Context Assessment

> **AUTO-GENERATED** from `input/*.yaml`. Edit the YAML files; re-run the generator.

## 2. Company Profile

```yaml
# AEGIS Phase 1 — Company Classification (Case 01 — TinyTask SaaS)
# This file is the canonical source for company facts.
# The 01_Company_Context.md is auto-generated FROM this file.
company:
  name: TinyTask Lda.
  legal_structure: Private Limited Company (Lda.)
  sector: Technology/Software
  jurisdiction: Portugal (EU)
  employees: 8
  revenue_eur: 2000000
  scale: MICRO
  security_fte: 0.85
  criticality_level: non-critical
tech_stack:
  - AWS
  - Firebase
  - GitHub Actions
applicable_regulations:
  - id: REG-GDPR
    abbreviation: GDPR
    applicable: true
    obligated_party: controller
    reason: processes_personal_data = true
  - id: REG-CRA
    abbreviation: CRA
    applicable: true
    obligated_party: manufacturer
    reason: places_digital_products_eu = true
  - id: REG-NIS2
    abbreviation: NIS2
    applicable: false
    reason: below_threshold (8 employees < 50)
  - id: REG-DORA
    abbreviation: DORA
    applicable: false
    reason: not_financial_entity
  - id: REG-AI_Act
    abbreviation: AI_Act
    applicable: false
    reason: no_high_risk_ai_system
```

## 3. Business Goals

```yaml
# Business Goals (BG-01..BG-05)
goals:
  - id: BG-01
    description: GDPR-compliant data processing
    priority: HIGH
  - id: BG-02
    description: CRA-conformant product
    priority: HIGH
  - id: BG-03
    description: Customer trust through security transparency
    priority: MEDIUM
  - id: BG-04
    description: Operational efficiency via managed services
    priority: MEDIUM
  - id: BG-05
    description: EU market expansion readiness
    priority: LOW
```

## 4. Stakeholders

```yaml
# Stakeholders (SH-01..SH-07)
stakeholders:
  - id: SH-01
    role: Chief Executive Officer (CEO)
    responsibilities: [executive_sponsor, accountability]
  - id: SH-02
    role: Chief Technology Officer (CTO)
    responsibilities: [engineering_lead, security_champion, incident_lead]
  - id: SH-03
    role: Data Protection Officer (DPO)
    responsibilities: [gdpr_compliance, privacy_oversight]
  - id: SH-04
    role: Compliance Lead
    responsibilities: [regulatory_compliance, documentation]
  - id: SH-05
    role: Engineering Team
    responsibilities: [implementation, secure_development]
  - id: SH-06
    role: Customer Support
    responsibilities: [user_data_handling]
  - id: SH-07
    role: External Auditor
    responsibilities: [annual_review, certification]
```

## 5. Architecture

### 5.1 Systems

```yaml
# System Inventory (SYS-01..SYS-05)
systems:
  - id: SYS-01
    name: Main SaaS Application
    type: web_application
    stack: [python, django, react]
    hosting: AWS eu-west-1
    criticality: HIGH
  - id: SYS-02
    name: Identity Service
    type: identity_provider
    stack: [Auth0]
    hosting: Auth0 (managed)
    criticality: HIGH
  - id: SYS-03
    name: Cloud Infrastructure
    type: infrastructure
    stack: [AWS]
    hosting: AWS eu-west-1
    criticality: HIGH
  - id: SYS-04
    name: Key Management Service
    type: kms
    stack: [AWS KMS]
    hosting: AWS
    criticality: HIGH
  - id: SYS-05
    name: Monitoring & Logging
    type: observability
    stack: [Datadog]
    hosting: Datadog (managed)
    criticality: MEDIUM
```

### 5.2 Data Stores

```yaml
# Data Stores (STORE-01..STORE-03)
stores:
  - id: STORE-01
    name: Primary Database
    type: postgres
    location: AWS RDS eu-west-1
    personal_data: true
    encryption_at_rest: AES-256 (provider-managed)
    retention_days: 2555
  - id: STORE-02
    name: Backup Storage
    type: s3
    location: AWS S3 eu-west-1
    personal_data: true
    encryption_at_rest: AES-256 (provider-managed)
    retention_days: 90
  - id: STORE-03
    name: Application Logs
    type: s3
    location: AWS S3 eu-west-1
    personal_data: false
    encryption_at_rest: AES-256 (provider-managed)
    retention_days: 30
```

### 5.3 Data Flows

```yaml
# Data Flows (FLOW-01..FLOW-05)
flows:
  - id: FLOW-01
    name: Customer Registration
    source: SYS-01
    destination: STORE-01
    data_types: [email, name, password]
    encryption_in_transit: TLS 1.3
  - id: FLOW-02
    name: Customer Authentication
    source: SYS-01
    destination: SYS-02
    data_types: [email, password]
    encryption_in_transit: TLS 1.2+
  - id: FLOW-03
    name: Payment Processing
    source: SYS-01
    destination: Stripe
    data_types: [payment_metadata]
    encryption_in_transit: TLS 1.2+
  - id: FLOW-04
    name: Monitoring Telemetry
    source: SYS-01
    destination: SYS-05
    data_types: [telemetry]
    encryption_in_transit: TLS 1.2+
  - id: FLOW-05
    name: Backup Operations
    source: STORE-01
    destination: STORE-02
    data_types: [full_dataset]
    encryption_in_transit: TLS 1.2+
```

---
_Generated by `generate_context_md()` from `input/*.yaml`_
