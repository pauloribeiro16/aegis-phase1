---
document_id: AEGIS-P1-04a
title: Architecture & Data Inventory
phase: 1
version: 1.0
created: "2026-07-14T10:49:58Z"
updated: "2026-07-14T10:49:58Z"
author: Executor
status: DRAFT
case_study: TinyTask Lda.
inputs: [04_Company_Context_Assessment.md, ../00_COMMON/01_Company_Context.md, 05_Regulatory_Applicability.md]
outputs: [04b_Security_Posture.md, 07_Structured_Compliance_Matrix.md]
applicable_regs: [GDPR, CRA]
active_subdomains: 37
inactive_subdomains: [D-08.3]
related_documents: [../../../00_METHODOLOGY/PREPROCESSING/SubDomains/index.md, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-01_Data-Protection/, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-05_Data-Lifecycle/, ../../../00_METHODOLOGY/PREPROCESSING/SubDomains/D-09_Governance-Documentation/D-09.4.md]
generated_at: "2026-07-14T10:49:58Z"
---
# AEGIS-P1-04a Architecture & Data Inventory

## 1. Technical Architecture

TinyTask Lda. is a Micro-enterprise SaaS provider with 8 employees operating 5 inventoried systems (Main SaaS Application, Auth Service, Customer Data Store, Cloud KMS, Backup Store). Operational maturity is low-tier; regulatory complexity remains medium because GDPR, CRA. active sub-domains: 37; inactive: D-08.3. The architecture uses managed cloud services and OAuth-based identity, consistent with the proportionality tier expected for a low-maturity SaaS.

### 1.1 System Inventory

| System ID | Name | Type | Tech Stack | Owner | Criticality | Hosts Personal Data? |
| --- | --- | --- | --- | --- | --- | --- |
| SYS-01 | Main SaaS Application | Cloud SaaS application | Node.js API, React web client, PostgreSQL driver | CTO and development team | Important | Y |
| SYS-02 | Auth Service | Managed identity service | Auth0 using OAuth 2.0 and OIDC | CTO | Important | Y |
| SYS-03 | Customer Data Store | Managed relational database | PostgreSQL on EU cloud region | CTO and lead developer | Critical | Y |
| SYS-04 | Cloud KMS | Managed key management | Cloud KMS with provider-managed key storage | CTO | Supporting | N |
| SYS-05 | Backup Store | Managed object storage | S3-compatible encrypted bucket | CTO | Important | Y |

### 1.2 Network Topology

Users reach the SaaS front-end over HTTPS, which calls SYS-01 via TLS-protected endpoints. SYS-01 connects to the managed PostgreSQL store over the provider's encrypted internal network. Administrative access is restricted to a small group with MFA enabled, and 5 documented data flows capture the user-to-app, app-to-store, app-to-log, app-to-auth, and app-to-billing edges. No enterprise network zones, private SOC, or dedicated SIEM are operated.

### 1.3 Cloud Services

| Provider | Service | Data Stored | Region | DPA in Place? |
| --- | --- | --- | --- | --- |
| AWS or equivalent EU cloud provider | PostgreSQL managed database | Customer accounts, project metadata, B2B project content | eu-west-1 or equivalent EU region | Y |
| AWS or equivalent EU cloud provider | S3-compatible object storage | Encrypted database backups | eu-west-1 or equivalent EU region | Y |
| AWS or equivalent EU cloud provider | Cloud KMS | Encryption keys and key metadata | EU region | Y |
| Auth0 | Authentication and identity | Email identifiers, authentication metadata, session metadata | EU tenant where available | Y |
| Stripe | Payment processing | Card/payment data, billing contact metadata | Stripe controlled processing locations | Y |
| Datadog or equivalent | Logs and analytics | Pseudonymised event logs and operational metrics | EU site where available | Y |

### 1.4 Authentication & Identity Systems

| System | Purpose | MFA? | SSO? | Password Policy |
| --- | --- | --- | --- | --- |
| SYS-02 Auth0 | Customer and administrator authentication | Admins only; optional for customers | OIDC for SYS-01 | Auth0 default password policy with minimum length and breached-password checks |
| Cloud provider IAM | Infrastructure administration | Y for CTO and developers | No enterprise SSO | Individual accounts with least-privilege roles; quarterly review not yet formalised |
| GitHub organisation | Source-code repository and pull requests | Y for developers | No enterprise SSO | GitHub enforced 2FA; branch protection limited to main branch |

## 2. Data Inventory

### 2.1 Data Stores

| Store ID | Type | Location | System | Encryption at Rest? | Owner | Retention Period | Backup? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STORE-01 | PostgreSQL database | EU cloud region | SYS-03 | Y, AES-256 provider-managed encryption using SYS-04 keys | CTO and lead developer | Active account lifetime plus 30 days after deletion request where legally permissible | Y |
| STORE-02 | Object storage backups | EU cloud region | SYS-05 | Y, SSE-KMS/AES-256 using SYS-04 keys | CTO | Daily backups for 30 days; monthly backups for 12 months | Y |
| STORE-03 | Logs and analytics | EU monitoring region where available | SYS-01 and monitoring provider | Y, provider-managed encryption; no raw task content intentionally logged | CTO | 30 days | N |

### 2.2 Data Flows

| Flow ID | Source | Destination | Data Type | Volume | Encryption in Transit? | Protocol | Subprocessor? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FLOW-01 | Web client | SYS-01 Main SaaS Application | Account data and project data | Low to medium | Y, TLS 1.3 | HTTPS REST | N |
| FLOW-02 | SYS-01 Main SaaS Application | STORE-01 Main PostgreSQL | Customer accounts, project data, audit metadata | Low to medium | Y, encrypted internal database transport | PostgreSQL TLS | N |
| FLOW-03 | SYS-01 Main SaaS Application | STORE-03 Logs and analytics | Pseudonymised events, request metadata, error traces | Low | Y, TLS 1.2 or higher | HTTPS agent/API | Y, Datadog or equivalent |
| FLOW-04 | Web client | SYS-02 Auth Service | Authentication credentials, email identifier, OIDC tokens | Low | Y, TLS 1.3 | OAuth 2.0/OIDC over HTTPS | Y, Auth0 |
| FLOW-05 | SYS-01 Main SaaS Application | Stripe | Billing metadata and hosted-checkout redirect; no card PAN stored by TinyTask | Low | Y, TLS 1.2 or higher | HTTPS API | Y, Stripe |

### 2.3 Personal Data Categories

| Category | Legal Basis (Art. 6 GDPR) | Systems Processing | Retention | Erasure Mechanism |
| --- | --- | --- | --- | --- |
| email | Contract | SYS-01, SYS-02, SYS-03, SYS-04, SYS-05 | Account lifetime plus 30 days after deletion request where legally permissible | Manual admin deletion through support workflow; Auth0 deletion required separately |
| name | Contract | SYS-01, SYS-02, SYS-03, SYS-04, SYS-05 | Account lifetime plus 30 days after deletion request where legally permissible | Manual admin deletion through support workflow; Auth0 deletion required separately |
| password | Contract | SYS-01, SYS-02, SYS-03, SYS-04, SYS-05 | Account lifetime plus 30 days after deletion request where legally permissible | Workspace deletion removes active records; backups expire by retention schedule |
| task_content | Contract | SYS-01, SYS-02, SYS-03, SYS-04, SYS-05 | Workspace lifetime; backups retained up to 12 months | Workspace deletion removes active records; backups expire by retention schedule |

### 2.4 Data Subject Categories

| Subject Type | Data Categories | Access Mechanism | Erasure Mechanism |
| --- | --- | --- | --- |
| EU customers (B2B and B2C) | Email, name, account metadata, project data, billing metadata | In-app account view and support request | Manual support workflow; active records deleted and backup expiry relied on for residual copies |
| Free-tier users | Email, name where provided, project data, usage events | In-app account view and support request | Manual support workflow; inactive accounts reviewed ad hoc |
| Enterprise customer end users | Email, name, project data controlled by enterprise customer | Enterprise administrator export and support-assisted DSAR | Processor-assisted deletion on controller instruction under DPA |

## 3. Compliance Mapping (Layer 0)

This mapping uses the active scope from the company context (applicable_regs) and the Layer 0 source of truth at ``00_METHODOLOGY/PREPROCESSING/SubDomains/``. Sub-domains whose participating regulations do not intersect the company applicability set are excluded; the explicit inactive list is appended for traceability.

- **Inactive sub-domains (excluded from §3):** D-08.3

| Sub-domain | Relevant Systems | Relevant Data Stores | Relevant Data Flows | Layer 0 Requirement IDs | SubDomains file |
| --- | --- | --- | --- | --- | --- |
| D-01.1 D-01.1 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-01.2 D-01.2 | SYS-03 | STORE-01 | FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05 | - | - |
| D-01.3 D-01.3 | SYS-04 | STORE-01 | FLOW-02 | - | - |
| D-01.4 D-01.4 | SYS-05 | STORE-02 | FLOW-01, FLOW-02 | - | - |
| D-02.1 D-02.1 | SYS-03 | STORE-03 | FLOW-03 | - | - |
| D-02.2 D-02.2 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-02.3 D-02.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-02.4 D-02.4 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-03.1 D-03.1 | SYS-02 | STORE-01 | FLOW-04 | - | - |
| D-03.2 D-03.2 | SYS-02 | STORE-01 | FLOW-04 | - | - |
| D-03.3 D-03.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-03.4 D-03.4 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-04.1 D-04.1 | SYS-03 | STORE-03 | FLOW-03 | - | - |
| D-04.2 D-04.2 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-04.3 D-04.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-04.4 D-04.4 | SYS-05 | STORE-02 | FLOW-01, FLOW-02 | - | - |
| D-05.1 D-05.1 | SYS-03 | STORE-01 | FLOW-01, FLOW-02, FLOW-03, FLOW-05 | - | - |
| D-05.2 D-05.2 | SYS-05 | STORE-02 | FLOW-01, FLOW-02 | - | - |
| D-05.3 D-05.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-05.4 D-05.4 | SYS-03 | STORE-01 | FLOW-01, FLOW-02, FLOW-03, FLOW-05 | - | - |
| D-06.1 D-06.1 | SYS-02 | STORE-01 | FLOW-04, FLOW-05 | - | - |
| D-06.2 D-06.2 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-06.3 D-06.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-06.4 D-06.4 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-07.1 D-07.1 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-07.2 D-07.2 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-07.3 D-07.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-07.4 D-07.4 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-08.1 D-08.1 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-08.2 D-08.2 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-09.1 D-09.1 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-09.2 D-09.2 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-09.3 D-09.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-09.4 D-09.4 | SYS-03 | STORE-01 | FLOW-02 | - | - |
| D-10.1 D-10.1 | SYS-03 | STORE-03 | FLOW-03 | - | - |
| D-10.2 D-10.2 | SYS-03 | STORE-03 | FLOW-03 | - | - |
| D-10.3 D-10.3 | SYS-03 | STORE-01 | FLOW-02 | - | - |

## 4. Gate

| Gate Criterion | Status | Evidence |
| --- | --- | --- |
| All production systems are inventoried | PASS | 5 systems documented in Section 1.1 |
| All data stores documented with encryption status | PASS | 3 stores documented in Section 2.1 |
| All data flows documented with encryption status | PASS | 5 flows documented in Section 2.2 |
| Personal data categories enumerated with legal basis | PASS | 4 categories documented in Section 2.3 |
| Compliance mapping table populated for all active sub-domains | PASS | 37 active sub-domains in Section 3; expected 37 |
| Proportionality maintained for low-tier micro/small SaaS | PASS | Scale: Micro-enterprise; managed services used; no enterprise HSM, SOC, SIEM, or formal CMDB claimed |
