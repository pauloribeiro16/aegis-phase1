---
document_id: AEGIS-P1-06
title: Clause Mapping Matrix
version: 1.0
status: DRAFT
generated_at: "2026-08-24T14:42:04Z"
---
# AEGIS-P1-06 Clause Mapping Matrix

## 1. PURPOSE

Map every regulatory clause from the in-scope regulations to a security sub-domain. The mapping is the canonical input for the coverage matrix (07) and the Proportionality Profile (07b).

## 2. SUMMARY

- **Total clauses mapped:** 222
- **Clauses per regulation:** CRA=150, GDPR=72
- **Unmapped clauses (no SR link):** 41 (see §4 NOTES)

## 3. CLAUSE-TO-SUBDOMAIN MAPPINGS

| Clause ID | Regulation | Article | Description | Sub-domain | Normative Strength | Obligated Party |
| --- | --- | --- | --- | --- | --- | --- |
| CRA-CL10 | CRA | Art. 8(1) — assurance level at least `substantial` | Critical-product certification requirement | D-09.1 | 2 | obligated_party |
| CRA-CL100 | CRA | Art. 23(2) — 10-year retention of supply-chain information | 10-year retention of supply-chain information. | D-06.4 | 2 | obligated_party |
| CRA-CL101 | CRA | Art. 24(1) — OSS steward cybersecurity policy | OSS steward cybersecurity policy | D-09.1 | 2 | obligated_party |
| CRA-CL102 | CRA | Art. 24(2) — OSS steward cooperation with MSAs | OSS stewards cooperate with MSAs; provide documentation on request. | D-09.1 | 2 | obligated_party |
| CRA-CL103 | CRA | Art. 24(3) — OSS steward Art. 14 extension cross-ref to CVD | OSS steward Art. 14 extension | D-02.3 | 2 | obligated_party |
| CRA-CL108 | CRA | Art. 27(1) — presumption of conformity via harmonised standards | Products conforming to harmonised standards are presumed compliant. | D-09.1 | 2 | obligated_party |
| CRA-CL109 | CRA | Art. 27(2) — common specifications via implementing acts | Commission may adopt implementing acts establishing common specifications. | D-09.1 | 2 | obligated_party |
| CRA-CL110 | CRA | Art. 27(5) — presumption via common specifications | Products conforming to common specs are presumed compliant. | D-09.1 | 2 | obligated_party |
| CRA-CL111 | CRA | Art. 27(8) — CSA-certification presumption | Products with EU statement/certificate under CSA presumed compliant. | D-09.1 | 2 | obligated_party |
| CRA-CL112 | CRA | Art. 27(9) — delegated acts specifying CSA schemes | Commission specifies which CSA schemes demonstrate conformity. | D-09.1 | 2 | obligated_party |
| CRA-CL113 | CRA | Art. 28(1) — EU declaration content | EU declaration states fulfilment of Annex I requirements. | D-09.4 | 2 | obligated_party |
| CRA-CL114 | CRA | Art. 28(2) — declaration format per Annex V/VI | Declaration follows Annex V model; simplified follows Annex VI. | D-09.4 | 2 | obligated_party |
| CRA-CL116 | CRA | Art. 28(4) — manufacturer responsibility | By drawing up declaration, manufacturer assumes responsibility for compliance. | D-09.4 | 2 | obligated_party |
| CRA-CL117 | CRA | Art. 30(1) — CE marking affixing | CE marking affixed visibly, legibly, indelibly; for software, on declaration ... | D-09.4 | 2 | obligated_party |
| CRA-CL118 | CRA | Art. 30(3) — CE marking before placing on market | CE marking affixed before placing on market. | D-09.4 | 2 | obligated_party |
| CRA-CL119 | CRA | Art. 30(6) — implementing acts for labels/pictograms | Commission may adopt implementing acts for labels/pictograms related to secur... | D-09.4 | 2 | obligated_party |
| CRA-CL123 | CRA | Art. 32(1) — default conformity assessment | Manufacturers choose module A, B+C, H, or certification. | D-09.4 | 2 | obligated_party |
| CRA-CL124 | CRA | Art. 32(2) — Class I important products: Module B+C or H | Class I conformity assessment | D-09.4 | 2 | obligated_party |
| CRA-CL125 | CRA | Art. 32(3) — Class II important products: B+C / H / certification at substantial | Class II conformity assessment | D-09.4 | 2 | obligated_party |
| CRA-CL126 | CRA | Art. 32(4) — critical products: certification or B+C/H fallback | Critical products: certification (Art. 8(1)) or module B+C/H fallback. | D-09.4 | 2 | obligated_party |
| CRA-CL127 | CRA | Art. 32(5) — FOSS simplified CA (Module A when tech docs are public) | FOSS simplified conformity assessment | D-09.4 | 2 | obligated_party |
| CRA-CL129 | CRA | Annex I Part I (1) — chapeau | Appropriate level of cybersecurity based on risks. | D-01.1 | 2 | obligated_party |
| CRA-CL130 | CRA | Annex I Part I (2)(a) — no known exploitable vulnerabilities | No known exploitable vulnerabilities at market placement. | D-02.1 | 2 | obligated_party |
| CRA-CL131 | CRA | Annex I Part I (2)(b) — secure by default configuration | Secure default configuration; reset-to-original-state. | D-03.4 | 2 | obligated_party |
| CRA-CL132 | CRA | Annex I Part I (2)(c) — vulnerabilities addressed through security updates | Vulnerabilities addressed via security updates; auto-update default; opt-out. | D-02.2 | 2 | obligated_party |
| CRA-CL133 | CRA | Annex I Part I (2)(d) — access control | Protection from unauthorised access via authentication/IAM; report on access. | D-01.1 | 2 | obligated_party |
| CRA-CL134 | CRA | Annex I Part I (2)(e) — confidentiality + encryption | Protect confidentiality; encrypt at rest and in transit by state of the art. | D-01.1 | 2 | obligated_party |
| CRA-CL135 | CRA | Annex I Part I (2)(f) — integrity + report on corruptions | Protect integrity of data/commands/configs; report on corruptions. | D-01.4 | 2 | obligated_party |
| CRA-CL136 | CRA | Annex I Part I (2)(g) — adequate, relevant, necessary = data minimisation | Process only data adequate, relevant, necessary for intended purpose. | D-05.1 | 2 | obligated_party |
| CRA-CL137 | CRA | Annex I Part I (2)(h) — availability + resilience + DoS | Protect availability of essential functions after incident; DoS resilience. | D-04.2 | 2 | obligated_party |
| CRA-CL138 | CRA | Annex I Part I (2)(i) — minimise negative impact on services of other devices/networks | Minimise negative impact on other devices/networks. | D-04.2 | 2 | obligated_party |
| CRA-CL139 | CRA | Annex I Part I (2)(j) — limit attack surfaces incl. external interfaces | Limit attack surfaces including external interfaces. | D-01.2 | 2 | obligated_party |
| CRA-CL14 | CRA | Art. 13(1) — design/development/production duty | Design/development/production duty | D-01.1 | 2 | obligated_party |
| CRA-CL140 | CRA | Annex I Part I (2)(k) — exploitation mitigation | Reduce impact of incident via exploitation mitigation. | D-04.2 | 2 | obligated_party |
| CRA-CL141 | CRA | Annex I Part I (2)(l) — logging + monitoring | Record and monitor access/modification; opt-out for user. | D-01.4 | 2 | obligated_party |
| CRA-CL142 | CRA | Annex I Part I (2)(m) — secure and easily remove on a permanent basis all data and settings | User can securely and permanently remove all data/settings. | D-03.3 | 2 | obligated_party |
| CRA-CL143 | CRA | Annex I Part II (1) — identify and document vulnerabilities and components + SBOM | Identify/document vulnerabilities + components; SBOM in machine-readable format. | D-02.1 | 2 | obligated_party |
| CRA-CL144 | CRA | Annex I Part II (2) — address and remediate without delay | Address/remediate without delay; security updates separated from functionality. | D-02.2 | 2 | obligated_party |
| CRA-CL145 | CRA | Annex I Part II (3) — effective and regular tests and reviews | Effective and regular tests and reviews. | D-02.4 | 2 | obligated_party |
| CRA-CL146 | CRA | Annex I Part II (4) — public vulnerability disclosure with delay exception | Disclose fixed vulnerabilities; may delay if security risk outweighs benefit. | D-02.3 | 2 | obligated_party |
| CRA-CL147 | CRA | Annex I Part II (5) — CVD policy | Coordinated vulnerability disclosure policy. | D-02.3 | 2 | obligated_party |
| CRA-CL148 | CRA | Annex I Part II (6) — vulnerability sharing + contact address | Facilitate sharing of potential vulnerabilities; provide contact address. | D-02.3 | 2 | obligated_party |
| CRA-CL149 | CRA | Annex I Part II (7) — secure distribution of updates | Securely distribute updates; automatic if technically feasible. | D-02.2 | 2 | obligated_party |
| CRA-CL15 | CRA | Art. 13(2) sentence 1 — cybersecurity risk assessment | Cybersecurity risk-assessment core duty | D-07.1 | 2 | obligated_party |
| CRA-CL150 | CRA | Annex I Part II (8) — disseminate without delay, free of charge | Disseminate security updates without delay; free of charge (unless agreed). | D-02.2 | 2 | obligated_party |
| CRA-CL151 | CRA | Annex II §1 — manufacturer contact info | Name, address, email, website. | D-09.4 | 2 | obligated_party |
| CRA-CL152 | CRA | Annex II §2 — SPOC for vulnerability reporting | Single point of contact; CVD policy location. | D-02.3 | 2 | obligated_party |
| CRA-CL153 | CRA | Annex II §3 — name and type and unique identification | Name, type, unique identification. | D-03.1 | 2 | obligated_party |
| CRA-CL154 | CRA | Annex II §4 — intended purpose + security environment + security properties | Intended purpose, security environment, functionalities, security properties. | D-07.1 | 2 | obligated_party |
| CRA-CL155 | CRA | Annex II §5 — known/foreseeable circumstances that may lead to significant cybersecurity risks | Known/foreseeable circumstances leading to significant cybersecurity risks. | D-09.2 | 2 | obligated_party |
| CRA-CL156 | CRA | Annex II §6 — internet address for EU declaration | Internet address for EU declaration. | D-09.4 | 2 | obligated_party |
| CRA-CL157 | CRA | Annex II §7 — type of technical support + end-date | Technical security support type; end-date of support period. | D-02.2 | 2 | obligated_party |
| CRA-CL158 | CRA | Annex II §8(e) — how the automatic-update default setting can be turned off | Detailed instructions for secure use, data changes, updates, decommissioning,... | D-02.2 | 2 | obligated_party |
| CRA-CL159 | CRA | Annex II §9 — SBOM access location for user (if manufacturer decides) | Where SBOM can be accessed (if manufacturer decides). | D-06.2 | 2 | obligated_party |
| CRA-CL16 | CRA | Art. 13(2) sentence 1 — 6-phase lifecycle propagation | 6-phase lifecycle propagation | D-07.1 | 2 | obligated_party |
| CRA-CL160 | CRA | Annex VII §1 — general description | Product description: purpose, SW versions, hardware features, Annex II user i... | D-09.2 | 2 | obligated_party |
| CRA-CL161 | CRA | Annex VII §2(b) — SBOM in technical documentation | Design/dev/production description: architecture, vuln handling processes, SBO... | D-02.1 | 2 | obligated_party |
| CRA-CL162 | CRA | Annex VII §3 — risk-assessment documentation in technical documentation | Cybersecurity risk assessment per Art. 13; Annex I applicability mapping. | D-07.1 | 2 | obligated_party |
| CRA-CL163 | CRA | Annex VII §4 — support-period determination info | Support-period determination factors. | D-02.2 | 2 | obligated_party |
| CRA-CL164 | CRA | Annex VII §5 — standards applied + alternatives adopted | Standards applied; alternatives where not applied. | D-09.4 | 2 | obligated_party |
| CRA-CL165 | CRA | Annex VII §6 — test reports in technical documentation | Test reports for Annex I Part I + Part II compliance. | D-02.4 | 2 | obligated_party |
| CRA-CL166 | CRA | Annex VII §7 — EU declaration copy | Copy of EU declaration of conformity. | D-09.4 | 2 | obligated_party |
| CRA-CL167 | CRA | Annex VII §8 — SBOM on MSA request | SBOM provided on MSA request. | D-02.1 | 2 | obligated_party |
| CRA-CL168 | CRA | Annex VIII Part I (1) — Module A: sole responsibility | Manufacturer self-declares compliance; sole responsibility. | D-09.4 | 2 | obligated_party |
| CRA-CL17 | CRA | Art. 13(2) sentence 2 — health + safety of users | Health-and-safety of users | D-07.1 | 2 | obligated_party |
| CRA-CL170 | CRA | Annex VIII Part I (3) — manufacturer takes all measures for design/dev/production/vuln handling | Manufacturer takes all measures for design/dev/production/vuln compliance. | D-09.4 | 2 | obligated_party |
| CRA-CL171 | CRA | Annex VIII Part II (1) — Module B: EU-type examination | Notified body examines design + vuln handling; attests compliance. | D-09.4 | 2 | obligated_party |
| CRA-CL173 | CRA | Annex VIII Part II (6) — EU-type certificate issued (or refused) by notified body | Notified body issues certificate; may refuse and inform. | D-09.4 | 2 | obligated_party |
| CRA-CL174 | CRA | Annex VIII Part II (8) — Module B periodic audits of vuln handling | Periodic audits of vuln handling processes. | D-02.4 | 2 | obligated_party |
| CRA-CL175 | CRA | Annex VIII Part III (1) — Module C: internal production control | Manufacturer controls production per EU-type. | D-09.4 | 2 | obligated_party |
| CRA-CL176 | CRA | Annex VIII Part IV (1) — Module H: full quality assurance | Full quality assurance; notified body audits QMS. | D-09.4 | 2 | obligated_party |
| CRA-CL18 | CRA | Art. 13(3) sentence 1 — risk assessment documented and updated | Risk-assessment documentation | D-02.1 | 2 | obligated_party |
| CRA-CL19 | CRA | Art. 13(3) sentence 2 — intended purpose + reasonably foreseeable use | Intended purpose + reasonably foreseeable use | D-05.1 | 2 | obligated_party |
| CRA-CL20 | CRA | Art. 13(3) sentence 3 — Annex I Part I (2) applicability | Annex I Part I(2) applicability | D-07.1 | 2 | obligated_party |
| CRA-CL21 | CRA | Art. 13(4) sentence 1 — include risk assessment in technical documentation | Include risk assessment in technical documentation. | D-09.2 | 2 | obligated_party |
| CRA-CL22 | CRA | Art. 13(4) sentence 2 — AI Act carve-out for unified risk assessment | Risk assessment may be part of AI Act risk assessment. | D-09.2 | 2 | obligated_party |
| CRA-CL23a | CRA | Art. 13(5) — due diligence on third-party components | Supply-chain due diligence (the Q6=b split locus) | D-06.1 | 2 | obligated_party |
| CRA-CL24 | CRA | Art. 13(6) sentence 1 — component vulnerability address + remediate | Component-vulnerability handling | D-02.2 | 2 | obligated_party |
| CRA-CL25 | CRA | Art. 13(6) sentence 2 — share with component supplier | Share code/documentation with component supplier. | D-02.2 | 2 | obligated_party |
| CRA-CL26 | CRA | Art. 13(7) — systematically document relevant cybersecurity aspects | Systematically document cybersecurity aspects. | D-02.1 | 2 | obligated_party |
| CRA-CL27 | CRA | Art. 13(8) sentence 1 — handle vulnerabilities during support period | Vulnerability handling during support | D-02.2 | 2 | obligated_party |
| CRA-CL28 | CRA | Art. 13(8) sentence 2 — support-period determination factors | Support-period factors | D-02.2 | 2 | obligated_party |
| CRA-CL29 | CRA | Art. 13(8) sentence 3 — 5-year minimum | 5-year minimum support period | D-02.2 | 2 | obligated_party |
| CRA-CL30 | CRA | Art. 3(30) — substantial modification | Commission may specify minimum support period by category. | D-02.2 | 2 | obligated_party |
| CRA-CL32 | CRA | Art. 13(8) sentence 6 — CVD policy | Have appropriate policies including CVD. | D-02.3 | 2 | obligated_party |
| CRA-CL33 | CRA | Art. 13(9) — 10-year update availability | 10-year update availability | D-02.2 | 2 | obligated_party |
| CRA-CL34 | CRA | Art. 13(10) — substantial-modification compliance scope (last version) | May comply with Part II(2) only for last-placed version if conditions met. | D-02.2 | 2 | obligated_party |
| CRA-CL35 | CRA | Art. 13(11) — public software archives + user risk communication | Maintain public archives; inform users of risks. | D-02.2 | 2 | obligated_party |
| CRA-CL36 | CRA | Art. 13(12) sentence 1 — technical documentation + conformity assessment before placing | Draw up tech docs; carry out conformity assessment before placing on market. | D-09.4 | 2 | obligated_party |
| CRA-CL37 | CRA | Art. 13(12) sentence 2 — EU declaration + CE marking | Draw up EU declaration; affix CE marking. | D-09.4 | 2 | obligated_party |
| CRA-CL38 | CRA | Art. 13(13) — 10-year documentation retention | Keep tech docs + EU declaration for 10 years or support period. | D-09.4 | 2 | obligated_party |
| CRA-CL39 | CRA | Art. 3(39) — SBOM definition (details and supply chain relationships) | Procedures for series-production to remain in conformity. | D-02.1 | 2 | obligated_party |
| CRA-CL40 | CRA | Art. 13(15) — type/batch/serial number or other element | Type/batch/serial number or other element. | D-03.1 | 2 | obligated_party |
| CRA-CL41 | CRA | Art. 13(16) — manufacturer contact info on product | Name, trade name, address, email, website. | D-09.4 | 2 | obligated_party |
| CRA-CL42 | CRA | Art. 13(17) — single point of contact (manufacturer) | Single point of contact | D-02.3 | 2 | obligated_party |
| CRA-CL43 | CRA | Art. 13(18) — accompany with Annex II info, accessible for 10 years | Accompany with Annex II info; accessible for 10 years. | D-02.2 | 2 | obligated_party |
| CRA-CL44 | CRA | Art. 13(19) — end date at time of purchase | Display end date of support period at purchase; notify users at end. | D-02.2 | 2 | obligated_party |
| CRA-CL45 | CRA | Art. 6(2) of NIS 2 (cross-ref via CRA Art. 3(43) `incident`) — availability, authenticity, integrity, confidentiality | Provide full or simplified EU declaration. | D-04.3 | 2 | obligated_party |
| CRA-CL46 | CRA | Art. 13(21) — corrective measures on non-conformity | Corrective measures | D-04.2 | 2 | obligated_party |
| CRA-CL47 | CRA | Art. 13(22) — manufacturer cooperation with MSAs | Provide info and documentation to MSAs on request. | D-09.4 | 2 | obligated_party |
| CRA-CL48 | CRA | Art. 3(48) — free and open-source software definition | Notify MSAs and users before ceasing operations. | D-06.1 | 2 | obligated_party |
| CRA-CL49 | CRA | Art. 13(24) — Commission implementing acts on SBOM format | Commission may specify SBOM format. | D-06.2 | 2 | obligated_party |
| CRA-CL50 | CRA | Art. 13(25) — Union-wide dependency assessment by ADCO | ADCO may conduct dependency assessment on FOSS components. | D-09.4 | 2 | obligated_party |
| CRA-CL51 | CRA | Art. 14(1) sentence 1 — AEV notification to CSIRT + ENISA | AEV notification duty | D-04.3 | 2 | obligated_party |
| CRA-CL52 | CRA | Art. 14(1) sentence 2 — single reporting platform | Via single reporting platform (Art. 16). | D-04.3 | 2 | obligated_party |
| CRA-CL53 | CRA | Art. 14(2)(a) — AEV early warning 24h | Early warning 24h (AEV) | D-04.3 | 2 | obligated_party |
| CRA-CL54 | CRA | Art. 14(2)(b) — AEV vulnerability notification 72h | Vulnerability notification 72h (AEV) | D-04.3 | 2 | obligated_party |
| CRA-CL55 | CRA | Art. 14(2)(c) — AEV final report 14d + content (i)(ii)(iii) | Final report 14 days (AEV) | D-04.3 | 2 | obligated_party |
| CRA-CL56 | CRA | Art. 14(3) sentence 1 — severe-incident notification to CSIRT + ENISA | Severe-incident notification duty | D-04.3 | 2 | obligated_party |
| CRA-CL57 | CRA | Art. 14(3) sentence 2 — single platform | Via single reporting platform. | D-04.3 | 2 | obligated_party |
| CRA-CL58 | CRA | Art. 14(4)(a) — SI early warning 24h | Early warning 24h (SI) | D-04.3 | 2 | obligated_party |
| CRA-CL59 | CRA | Art. 14(4)(b) — SI incident notification 72h | 72h incident notification. | D-04.3 | 2 | obligated_party |
| CRA-CL60 | CRA | Art. 14(4)(c) — SI final report 1 month | Final report 1 month after (b). | D-04.3 | 2 | obligated_party |
| CRA-CL61 | CRA | Art. 14(5)(a) — SI test A: CIA of sensitive/important | Severe-incident test A | D-04.3 | 2 | obligated_party |
| CRA-CL62 | CRA | Art. 14(5)(b) — SI test B: malicious code | Severe-incident test B | D-04.3 | 2 | obligated_party |
| CRA-CL63 | CRA | Art. 14(6) — intermediate report on CSIRT request | Intermediate report on CSIRT request. | D-04.3 | 2 | obligated_party |
| CRA-CL64 | CRA | Art. 14(7) — routing through CSIRT of MS of main establishment | Notification via CSIRT of Member State of main establishment. | D-04.3 | 2 | obligated_party |
| CRA-CL65 | CRA | Art. 14(8) sentence 1 — user notification + machine-readable format | User notification | D-04.3 | 2 | obligated_party |
| CRA-CL66 | CRA | Art. 14(8) sentence 2 — CSIRT fallback | CSIRT may provide info to users if manufacturer fails. | D-04.3 | 2 | obligated_party |
| CRA-CL67 | CRA | Art. 14(9) — delegated acts on delay grounds | Commission specifies cybersecurity-related grounds for delaying dissemination. | D-02.3 | 2 | obligated_party |
| CRA-CL68 | CRA | Art. 14(10) — implementing acts on notification format/procedures | Commission specifies format and procedures. | D-09.4 | 2 | obligated_party |
| CRA-CL69 | CRA | Art. 15(1) — voluntary AEV reporting by any person | Any person may notify vulnerabilities voluntarily to CSIRT or ENISA. | D-04.3 | 2 | obligated_party |
| CRA-CL70 | CRA | Art. 15(2) — voluntary SI / near-miss reporting by any person | Any person may notify incidents/near misses voluntarily. | D-04.3 | 2 | obligated_party |
| CRA-CL72 | CRA | Art. 15(4) — third-party notification + CSIRT informs manufacturer | Non-manufacturer notifies AEV/severe incident → CSIRT informs manufacturer. | D-04.3 | 2 | obligated_party |
| CRA-CL74 | CRA | Art. 16(1) — ENISA single reporting platform | ENISA establishes and maintains single reporting platform. | D-04.3 | 2 | obligated_party |
| CRA-CL75 | CRA | Art. 16(2) — CSIRT dissemination with delay grounds | Dissemination with delay grounds | D-02.3 | 2 | obligated_party |
| CRA-CL76 | CRA | Art. 16(3) — CSIRT provides notification info to market-surveillance authorities | CSIRTs provide notification info to market surveillance authorities. | D-09.4 | 2 | obligated_party |
| CRA-CL77 | CRA | Art. 16(4) — ENISA platform security measures | ENISA takes appropriate and proportionate measures to secure platform. | D-09.4 | 2 | obligated_party |
| CRA-CL78 | CRA | Art. 17(1) — ENISA submits to EU-CyCLONe for large-scale incident management | ENISA may submit notifications to EU-CyCLONe for large-scale incident managem... | D-04.3 | 2 | obligated_party |
| CRA-CL79 | CRA | Art. 17(2) — public disclosure option by CSIRT | Public disclosure | D-04.3 | 2 | obligated_party |
| CRA-CL80 | CRA | Art. 17(3) — ENISA biennial report on cybersecurity risks in products | ENISA prepares biennial report on cybersecurity risks in products. | D-09.4 | 2 | obligated_party |
| CRA-CL81 | CRA | Art. 17(4) — no increased liability for mere notification | No-increased-liability shield | D-04.3 | 2 | obligated_party |
| CRA-CL82 | CRA | Art. 17(5) — EU vulnerability database | ENISA adds publicly known vulnerability to EU vuln database (Art. 12(2) NIS 2). | D-04.3 | 2 | obligated_party |
| CRA-CL83 | CRA | Art. 17(6) — CSIRT helpdesk for manufacturers on reporting obligations | CSIRTs provide helpdesk support to manufacturers on reporting obligations. | D-09.4 | 2 | obligated_party |
| CRA-CL84 | CRA | Art. 18(1) — AR appointment | Manufacturer may appoint authorised representative. | D-06.4 | 2 | obligated_party |
| CRA-CL85 | CRA | Art. 18(2) — AR carve-out of non-delegable obligations | Art. 13(1)–(11), (12) first sub, (14) not part of AR mandate. | D-06.4 | 2 | obligated_party |
| CRA-CL86 | CRA | Art. 18(3) — AR tasks | AR keeps tech docs, cooperates with MSAs. | D-06.4 | 2 | obligated_party |
| CRA-CL87 | CRA | Art. 19(1) — importer only places compliant products | Importers shall only place compliant products on market. | D-06.3 | 2 | obligated_party |
| CRA-CL88 | CRA | Art. 19(2) — importer pre-market checks | Before placing: conformity assessment, tech docs, CE marking, contact info. | D-06.3 | 2 | obligated_party |
| CRA-CL89 | CRA | Art. 19(3) — importer non-conformity + MSA notification of significant risk | Importer shall not place non-conforming product; inform MSA of significant risk. | D-04.2 | 2 | obligated_party |
| CRA-CL90 | CRA | Art. 19(5) — importer corrective measures + inform manufacturer of vulnerability | Importer immediately takes corrective measures; informs manufacturer of vulne... | D-04.2 | 2 | obligated_party |
| CRA-CL91 | CRA | Art. 19(6) — importer 10-year retention | Importer keeps EU declaration + tech docs for 10 years or support period. | D-06.3 | 2 | obligated_party |
| CRA-CL92 | CRA | Art. 20(1) — distributor due care | Distributor due care | D-06.3 | 2 | obligated_party |
| CRA-CL93 | CRA | Art. 20(2) — distributor pre-market checks | Before making available: verify CE marking + manufacturer/importer compliance. | D-06.3 | 2 | obligated_party |
| CRA-CL94 | CRA | Art. 20(3) — distributor non-conformity | Distributor shall not make non-conforming product available; inform MSA. | D-04.2 | 2 | obligated_party |
| CRA-CL95 | CRA | Art. 20(4) — distributor corrective measures + inform manufacturer | Distributor takes corrective measures; informs manufacturer of vulnerability. | D-04.2 | 2 | obligated_party |
| CRA-CL96 | CRA | Art. 21 — manufacturer-equivalent trigger (own name/trademark or substantial modification) | Manufacturer-equivalent trigger | D-04.2 | 2 | obligated_party |
| CRA-CL97 | CRA | Art. 22(1) — third-party substantial modification = manufacturer | Third-party substantial modification | D-06.4 | 2 | obligated_party |
| CRA-CL98 | CRA | Art. 22(2) — scope of obligations (affected part or whole) | Obligations apply to affected part or whole product. | D-06.4 | 2 | obligated_party |
| CRA-CL99 | CRA | Art. 23(1) — economic operator identification duty | Economic operators provide supplier/recipient info to MSAs on request. | D-06.4 | 2 | obligated_party |
| GDPR-CL01 | GDPR | Art. 4(1) — personal data definition | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-01.1 | 2 | CONTROLLER |
| GDPR-CL02 | GDPR | Art. 4(5) — pseudonymisation definition | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-01.1 | 2 | CONTROLLER |
| GDPR-CL03 | GDPR | Art. 5(1)(c) — data minimisation (cross) | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-01.4 | 2 | CONTROLLER |
| GDPR-CL04 | GDPR | Art. 5(1)(d) — accuracy | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-01.4 | 2 | CONTROLLER |
| GDPR-CL05 | GDPR | Art. 5(1)(e) — storage limitation | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL06 | GDPR | Art. 5(1)(f) | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-01.1 | 2 | CONTROLLER |
| GDPR-CL07 | GDPR | Art. 4(16) — main establishment (cross) | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-06.3 | 2 | CONTROLLER |
| GDPR-CL08 | GDPR | Art. 4(20) — BCR definition | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL09 | GDPR | Art. 4(22) — supervisory authority concerned | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-04.3 | 2 | CONTROLLER |
| GDPR-CL10 | GDPR | Art. 6(1)(c) — legal obligation | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL11 | GDPR | Art. 6(1)(d) — vital interests | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL12 | GDPR | Art. 6(1)(e) — public interest | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL13 | GDPR | Art. 6(1)(f) — legitimate interests | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL14 | GDPR | Art. 6(4) — compatibility test | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL15 | GDPR | Art. 7(1) — demonstrability | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL16 | GDPR | Art. 7(2) — bundled consent | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL17 | GDPR | Art. 7(3) — withdrawal | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL18 | GDPR | Art. 7(4) — conditional consent | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL19 | GDPR | Art. 8(1) — age threshold | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL20 | GDPR | Art. 8(2) — reasonable verification efforts | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CL21 | GDPR | Art. 9(1) — special-category prohibition | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL22 | GDPR | Art. 9(2)(a) — explicit consent | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL23 | GDPR | Art. 9(2)(g) — substantial public interest (cross) | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-05.1 | 2 | CONTROLLER |
| GDPR-CL26 | GDPR | Art. 11(2) — identification exemption | Art. 5(1)(a) — Lawfulness, fairness, transparency | D-03.1 | 2 | CONTROLLER |
| GDPR-CP01 | GDPR | Art. 24(1) — appropriate measures | Art. 24(1) — General controller responsibility | D-09.1 | 2 | CONTROLLER |
| GDPR-CP02 | GDPR | Art. 25(1) — privacy by design (cross) | Art. 24(1) — General controller responsibility | D-01.1 | 2 | CONTROLLER |
| GDPR-CP03 | GDPR | Art. 25(2) — privacy by default | Art. 24(1) — General controller responsibility | D-01.1 | 2 | CONTROLLER |
| GDPR-CP04 | GDPR | Art. 26(1) — joint-controller determination | Art. 24(1) — General controller responsibility | D-06.3 | 2 | CONTROLLER |
| GDPR-CP05 | GDPR | Art. 26(2) — arrangement essentials | Art. 24(1) — General controller responsibility | D-09.2 | 2 | CONTROLLER |
| GDPR-CP06 | GDPR | Art. 27(1) — designate in writing | Art. 24(1) — General controller responsibility | D-06.4 | 2 | NON |
| GDPR-CP07 | GDPR | Art. 28(1) — processor selection | Art. 24(1) — General controller responsibility | D-06.1 | 2 | CONTROLLER |
| GDPR-CP08 | GDPR | Art. 28(2) — sub-processor authorisation | Art. 24(1) — General controller responsibility | D-06.1 | 2 | PROCESSOR |
| GDPR-CP09 | GDPR | Art. 28(3)(a)/(b) | Art. 24(1) — General controller responsibility | D-03.3 | 2 | PROCESSOR |
| GDPR-CP10 | GDPR | Art. 28(3)(g) — delete polysemy | Art. 24(1) — General controller responsibility | D-05.3 | 2 | PROCESSOR |
| GDPR-CP11 | GDPR | Art. 29 — processing under authority | Art. 24(1) — General controller responsibility | D-03.3 | 2 | PROCESSOR |
| GDPR-CP12 | GDPR | Art. 30(1)(f) — retention time limits | Art. 24(1) — General controller responsibility | D-05.2 | 2 | CONTROLLER |
| GDPR-CP13 | GDPR | Art. 30(5) — 250-employee exception | Art. 24(1) — General controller responsibility | D-09.4 | 2 | CONTROLLER |
| GDPR-CP14 | GDPR | Art. 31 — supervisory authority cooperation | Art. 24(1) — General controller responsibility | D-09.4 | 2 | CONTROLLER |
| GDPR-CP15 | GDPR | Art. 32(1)(b) | Art. 24(1) — General controller responsibility | D-01.1 | 2 | CONTROLLER |
| GDPR-CP16 | GDPR | Art. 32(2) — risk enumeration | Art. 24(1) — General controller responsibility | D-01.1 | 2 | CONTROLLER |
| GDPR-CP17 | GDPR | Art. 33(1) — 72-hour notification trigger | Art. 24(1) — General controller responsibility | D-04.1 | 2 | CONTROLLER |
| GDPR-CP18 | GDPR | Art. 33(3)(d) — measures taken or proposed | Art. 24(1) — General controller responsibility | D-04.2 | 2 | CONTROLLER |
| GDPR-CP19 | GDPR | Art. 34(1) — high-risk breach communication to data subject | Art. 24(1) — General controller responsibility | D-01.3 | 2 | CONTROLLER |
| GDPR-CP20 | GDPR | Art. 34(3)(a) — unintelligibility exception | Art. 24(1) — General controller responsibility | D-01.3 | 2 | CONTROLLER |
| GDPR-CP21 | GDPR | Art. 35(1) — high-risk DPIA | Art. 24(1) — General controller responsibility | D-04.3 | 2 | CONTROLLER |
| GDPR-CP22 | GDPR | Art. 35(7) — DPIA content | Art. 24(1) — General controller responsibility | D-02.1 | 2 | CONTROLLER |
| GDPR-CP23 | GDPR | Art. 36(1) — prior consultation | Art. 24(1) — General controller responsibility | D-04.3 | 2 | CONTROLLER |
| GDPR-CP25 | GDPR | Art. 37(1)(a)/(b)/(c) — DPO designation triggers | Art. 24(1) — General controller responsibility | D-09.1 | 2 | CONTROLLER |
| GDPR-CP26 | GDPR | Art. 38 — DPO position | Art. 24(1) — General controller responsibility | D-09.1 | 2 | CONTROLLER |
| GDPR-CP27 | GDPR | Art. 38(6) — conflict of interests | Art. 24(1) — General controller responsibility | D-09.1 | 2 | CONTROLLER |
| GDPR-CP28 | GDPR | Art. 39(1)(b) — awareness and training | Art. 24(1) — General controller responsibility | D-08.1 | 2 | DPO |
| GDPR-RT01 | GDPR | Art. 12(1) — transparency modalities | Art. 12(1) — Transparency modalities | D-09.4 | 2 | CONTROLLER |
| GDPR-RT02 | GDPR | Art. 12(3) — 1-month response | Art. 12(1) — Transparency modalities | D-09.4 | 2 | CONTROLLER |
| GDPR-RT03 | GDPR | Art. 12(5) — manifestly unfounded or excessive | Art. 12(1) — Transparency modalities | D-09.4 | 2 | CONTROLLER |
| GDPR-RT04 | GDPR | Art. 12(6) — identity verification | Art. 12(1) — Transparency modalities | D-03.1 | 2 | CONTROLLER |
| GDPR-RT05 | GDPR | Art. 13(1) — collection-time information | Art. 12(1) — Transparency modalities | D-09.4 | 2 | CONTROLLER |
| GDPR-RT07 | GDPR | Art. 14(1)/(2) — third-party-source information | Art. 12(1) — Transparency modalities | D-09.4 | 2 | CONTROLLER |
| GDPR-RT09 | GDPR | Art. 15(1)/(3) — copy provision and format | Art. 12(1) — Transparency modalities | D-05.4 | 2 | CONTROLLER |
| GDPR-RT10 | GDPR | Art. 15(3) — commonly used electronic form | Art. 12(1) — Transparency modalities | D-05.4 | 2 | CONTROLLER |
| GDPR-RT11 | GDPR | Art. 15(4) — third-party-rights limit | Art. 12(1) — Transparency modalities | D-04.3 | 2 | CONTROLLER |
| GDPR-RT12 | GDPR | Art. 16 — rectification right | Art. 12(1) — Transparency modalities | D-01.4 | 2 | CONTROLLER |
| GDPR-RT15 | GDPR | Art. 19 — cascade notification (cross) | Art. 12(1) — Transparency modalities | D-01.4 | 2 | CONTROLLER |
| GDPR-TR01 | GDPR | Art. 44 — general transfer principle | Art. 44 — General transfer principle | D-06.3 | 2 | CONTROLLER |
| GDPR-TR02 | GDPR | Art. 45(1) — adequacy-based transfer | Art. 44 — General transfer principle | D-06.3 | 2 | CONTROLLER |
| GDPR-TR03 | GDPR | Art. 45(3) — periodic review of adequacy | Art. 44 — General transfer principle | D-06.3 | 2 | EUROPEAN |
| GDPR-TR04 | GDPR | Art. 46(1) | Art. 44 — General transfer principle | D-06.3 | 2 | CONTROLLER |
| GDPR-TR05 | GDPR | Art. 46(2)(a)–(f) — six mechanism types | Art. 44 — General transfer principle | D-06.3 | 2 | CONTROLLER |
| GDPR-TR06 | GDPR | Art. 47(2)(a)–(n) — 14 content items | Art. 44 — General transfer principle | D-06.3 | 2 | EU |
| GDPR-TR07 | GDPR | Art. 48 — third-country legal-request filter | Art. 44 — General transfer principle | D-06.3 | 2 | CONTROLLER |
| GDPR-TR08 | GDPR | Art. 49(1)(a) — explicit consent | Art. 44 — General transfer principle | D-03.1 | 2 | CONTROLLER |
| GDPR-TR09 | GDPR | Art. 49(1)(d) — important public interest | Art. 44 — General transfer principle | D-06.3 | 2 | CONTROLLER |
| GDPR-TR10 | GDPR | Art. 49(1) second subparagraph — catch-all | Art. 44 — General transfer principle | D-06.3 | 2 | CONTROLLER |

## 4. NOTES

- Normative strength is encoded 1-3 in the ontology (see ``phase1_schema.yaml`` for the mapping). Default 2 (medium) until clause-level metadata is enriched.

- Sub-domain IDs follow the ``D-XX.Y`` notation; see AEGIS-COMMON-00 (Taxonomy Reference).

- 41 clause(s) had no SR link and are excluded from the mapping table. These orphans are listed in the next contract (CORR-040) for review.


## Appendix: Source LLM Responses

Raw markdown responses captured by the S3b invoker wiring. Each subsection corresponds to one of the 5 canonical Phase 1 LLM specs. Multi-call specs (P1B-LLM-01/02 per regulation, P1C-LLM-01 per domain) are concatenated with a horizontal rule (``---``) between calls. When a spec did not run (mock mode, deterministic-only, or invoker failure) the section shows a ``(no LLM response)`` placeholder.


### P1B-LLM-01-INTERPRETATION

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-CRA-ART14-DUAL-FLOW (YES): Company is classified as a manufacturer (`role_matrix.cra.role`); CRA Art. 14(1) requires reporting to ENISA within 24h of awareness of actively exploited vulnerability; Art. 14(2) requires user notification if material impact applies.
- TIPO2-CRA-ART15-VOLUNTARY (YES): Company has active products (`v2_company_profile` lists SaaS application); CRA Art. 15 allows voluntary reporting to ENISA for vulnerabilities not yet actively exploited, applicable given the manufacturer role and product lifecycle management obligations.

## Derogations
- TIPO3-CRA-NON-PLACED (NOT_ACTIVATED): Company places digital products on EU market (`applicability_predicates.places_digital_products_eu = true`); CRA Art. 2 exclusion for non-placed products does not apply to commercial SaaS offerings distributed in the Union.
- TIPO3-CRA-OPEN-SOURCE (NOT_ACTIVATED): Company operates as a commercial entity (`revenue=2000000`, `legal_structure='Private Limited Company'`); CRA Recital 18 exclusion for non-commercial OSS does not apply to proprietary or commercially licensed software.

## Rationale
TinyTask Lda. is classified under the Cyber Resilience Act (CRA) as a manufacturer of products with digital elements (`role_matrix.cra.role = 'manufacturer'`). This classification activates mandatory incident reporting obligations under CRA Art. 14, specifically the dual-flow requirement to notify ENISA within 24 hours and users if there is material impact (`TIPO2-CRA-ART14-DUAL-FLOW`, `SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA`). Additionally, as a manufacturer with active products in the market (`v2_company_profile`), the company falls under voluntary reporting provisions for pre-exploitation vulnerabilities to support ecosystem security (`TIPO2-CRA-ART15-VOLUNTARY`, `SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO`).

Derogations were evaluated against specific exclusion criteria in the Regulatory Baseline. The non-placement derogation is not engaged because the company explicitly places digital products on the EU market (`applicability_predicates.places_digital_products_eu = true`), triggering full CRA scope under Art. 13 and Annex I requirements (`TIPO3-CRA-NON-PLACED`, `SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO`). Similarly, the open-source derogation is not applicable as TinyTask operates a commercial SaaS model with revenue generation (`revenue=2000000`), distinguishing it from non-commercial OSS projects excluded under CRA Recital 18 (`TIPO3-CRA-OPEN-SOURCE`, `SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO`). The company's LOW complexity tier does not exempt these baseline obligations, as CRA manufacturer duties are product-centric rather than entity-size dependent for core compliance tracks like vulnerability handling and conformity assessment.

---

## Status
- applicable: YES
- confidence: HIGH

## Interpretations
- TIPO2-GDPR-RTS-DEADLINES (NO): company sector is "Technology/Software", not in ['health', 'energy', 'transport', 'digital_infrastructure']; predicate fails.

## Derogations
- TIPO3-GDPR-HOUSEHOLD (NOT_ACTIVATED): company operates a commercial SaaS application, processing scope is NOT purely personal or household; GDPR Art. 2(2)(c) derogation does not apply.

## Rationale
TinyTask Lda. qualifies as a data controller under the GDPR for its admin dataset and customer data routed through its SaaS platform (DOC04:FACTS-role_matrix.gdpr.role). The company operates in the "Technology/Software" sector with 8 employees, classified as MICRO scale (DOC04:FACTS-scale).

Regarding interpretations, `TIPO2-GDPR-RTS-DEADLINES` is not applicable because its activation predicate requires the company's sector to be one of ['health', 'energy', 'transport', 'digital_infrastructure']. TinyTask's sector ("Technology/Software") does not match this list (DOC04:FACTS-sector). Therefore, while GDPR Art. 33(1) breach notification deadlines generally apply to all controllers, the specific RTS-deadline interpretation nuance for critical sectors is not triggered here.

Regarding derogations, `TIPO3-GDPR-HOUSEHOLD` evaluates whether processing falls under purely personal or household activity (GDPR Art. 2(2)(c)). TinyTask provides a commercial SaaS application with data flows involving customer registration and payment metadata (DOC04:FACTS-architecture.data_flows). This constitutes professional/commercial processing, not household activity. Consequently, the derogation is NOT_ACTIVATED, and full GDPR obligations apply without exclusion based on this clause.

All citations are drawn from the Regulatory Baseline entries provided in `layer0_catalog` (`SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA`, `SubDomains/D-09_Governance-Documentation/D-09.1.md §2 HSO`) and company facts verified against Doc 04 inputs. No article numbers were invented; legal references match the catalog entries (GDPR Art. 33(1), GDPR Art. 2(2)(c)).


### P1B-LLM-02-RATIONALE

## Status
- applicable: YES
- confidence: HIGH

## Findings
- **Implication:** IMP-D-04.3-CRA-AEV (Actively Exploited Vulnerability Reporting)
  - description: As a CRA Manufacturer of Class I products, TinyTask must notify ENISA within 24 hours of becoming aware of an actively exploited vulnerability and inform users if there is material impact. This requires distinct detection logic from GDPR breach notification (72h).
  - effort_estimate: days to weeks (requires integration with monitoring stack)
  - dependencies: D-01.3 Cryptographic Key Management, D-04.2 Incident Response Playbook
  - layer0_refs: SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA Art. 14(1)-(2)
  - company_fact_refs: DOC04:v2_company_profile.role_matrix.cra.role (manufacturer), DOC04:negative_analyses.NA-05

- **Implication:** IMP-D-09.4-CRA-TD (Technical Documentation & Conformity Assessment)
  - description: TinyTask must draw up technical documentation per Annex VII before placing the SaaS product on the EU market, including risk assessment records and SBOMs. A conformity assessment procedure (Module A or B+C/H depending on classification nuances) is required to affix CE marking.
  - effort_estimate: weeks (documentation heavy for MICRO tier without existing QMS)
  - dependencies: D-07.1 Secure-by-Design Principles, D-02.1 Vulnerability Identification
  - layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §3 HSO CRA Art. 13(12)-(13)
  - company_fact_refs: DOC04:v2_company_profile.regulatory_classification.cra_product_class (CLASS_I), DOC04:negative_analyses.NA-01

- **Implication:** IMP-D-07.1-CRA-SBD (Secure-by-Design Lifecycle)
  - description: Cybersecurity risk assessment must be propagated across the 6 lifecycle phases (planning to maintenance). For a SaaS product, this implies embedding security checks into CI/CD pipelines and maintaining support for at least 5 years.
  - effort_estimate: days to weeks (process definition + pipeline updates)
  - dependencies: D-07.3 CI/CD Pipeline Security, D-10.2 Audit Logging & Traceability
  - layer0_refs: SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO CRA Art. 13(2)-(4)
  - company_fact_refs: DOC04:v2_company_profile.tech_stack (AWS, GitHub Actions), DOC04:negative_analyses.NA-04

- **Gap:** GAP-D-09.4-CRA-TD-MISSING
  - sub_domain_id: D-09.4
  - coverage_level: NOT_ADDRESSED
  - risk_description: No formal conformity assessment programme is in place for Class I products, preventing legal CE marking and market placement compliance under CRA Art. 13(12).
  - covered_by_other_reg: [] (GDPR does not cover product security certification)
  - recommendation: Address all (HIGH priority due to market access blockage); engage notified body if Module B+C/H required or self-declare with robust evidence for Module A.
  - priority: P1
  - layer0_refs: SubDomains/D-09_Governance-Documentation/D-09.4.md §3 HSO CRA Art. 13(12)

- **Gap:** GAP-D-07.1-CRA-SBOM-MISSING
  - sub_domain_id: D-07.1 / D-06.1
  - coverage_level: PARTIAL
  - risk_description: Vulnerability management does not cover CRA Annex I §2 handled products (no SBOM, no coordinated disclosure). This blocks compliance with Art. 13(5) due diligence on components and Art. 14 reporting readiness.
  - covered_by_other_reg: []
  - recommendation: Address if high risk; implement automated SBOM generation for dependencies in GitHub Actions pipeline immediately to satisfy CRA Annex I Part II (1).
  - priority: P2
  - layer0_refs: SubDomains/D-07_Secure-Development/D-07.1.md §3 HSO CRA Art. 13(5)

## Rationale
The Cyber Resilience Act (CRA) applies to TinyTask Lda. because the company places digital products with cybersecurity functions on the EU market (`DOC04:v2_company_profile.places_digital_products_eu = true`). Specifically, TinyTask operates as a **Manufacturer** of Class I products under CRA classification (`DOC04:regulatory_classification.cra_product_class`), which triggers mandatory obligations regardless of its separate status as a GDPR Controller. Unlike NIS 2 or DORA, which target specific sectors (energy/finance) and entity sizes, the CRA applies to any product with digital elements placed on the EU market by manufacturers established in or outside the Union (`DOC04:company_facts.jurisdiction` = Portugal).

The company's architecture confirms applicability through its SaaS application stack hosted on AWS/Firebase which processes data but also constitutes a "product with digital elements" under CRA Art. 3(12) due to embedded cybersecurity functions (e.g., authentication via Auth0, encryption in transit/rest per `DOC04:architecture.data_flows`). The activation of interpretations TIPO2-CRA-ART14-DUAL-FLOW and TIPO2-CRA-ART15-VOLUNTARY confirms that TinyTask must adhere to the 24-hour vulnerability reporting SLA (`SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA`) distinct from GDPR's 72-hour breach notification, creating a dual-track incident response requirement.

Furthermore, derogations TIPO3-CRA-NON-PLACED and TIPO3-CRA-OPEN-SOURCE are explicitly NOT_ACTIVATED because TinyTask is a commercial entity placing proprietary software on the market (`DOC04:v2_company_profile.revenue=2000000`, `legal_structure='Private Limited Company'`). Consequently, TinyTask cannot rely on exemptions for non-placed products or non-commercial OSS. The company must therefore establish full CRA compliance tracks including Technical Documentation (Annex VII), Conformity Assessment (Art. 13(12)), and a minimum 5-year support period (`SubDomains/D-09_Governance-Documentation/D-09.4.md §3 HSO`), which currently represents the primary gap in their implementation readiness profile.

---

## Status
- applicable: YES
- confidence: HIGH

## Findings
- implication: id="IMP-D-01.1-GDPR", description="Implement encryption for personal data at rest (AWS RDS/S3) with key management separation to satisfy Art. 5(1)(f) and Art. 32(1)", effort_estimate="days (LOW tier - configure AWS KMS/RDS settings)", dependencies=["IMP-D-09.1-GDPR"], layer0_refs=["SubDomains/D-01.1.md §2 HSO", "SR-GDPR-001"], company_fact_refs=["DOC04:ARCH-SYS-01 (Main SaaS Application)"]
- implication: id="IMP-D-03.1-GDPR", description="Establish retention policies for personal data in AWS RDS/S3 aligned with Art. 5(1)(e), ensuring deletion after purpose expiry", effort_estimate="hours to days (LOW tier - define policy + configure lifecycle rules)", dependencies=["IMP-D-09.4-GDPR"], layer0_refs=["SubDomains/D-03.1.md §2 HSO", "SR-GDPR-029"], company_fact_refs=["DOC04:ARCH-STORAGE"]
- implication: id="IMP-D-06.1-GDPR", description="Conduct due diligence on processors (AWS, Auth0, Stripe) to ensure Art. 28(1) sufficient guarantees and sign DPAs", effort_estimate="days (LOW tier - review existing contracts + DPA addendums)", dependencies=["IMP-D-09.4-GDPR"], layer0_refs=["SubDomains/D-06.1.md §2 HSO", "SR-GDPR-033"], company_fact_refs=["DOC04:ARCH-CLOUD-SERVICES"]
- implication: id="IMP-D-09.1-GDPR", description="Document Information Security Policies and Data Protection Principles per Art. 5(2) accountability, including DPO oversight (even if outsourced)", effort_estimate="days to weeks (LOW tier - draft policies + assign responsibilities)", dependencies=[], layer0_refs=["SubDomains/D-09.1.md §2 HSO", "SR-GDPR-043"], company_fact_refs=["DOC04:SECURITY-FTE"]
- implication: id="IMP-D-04.3-GDPR", description="Establish breach notification process to meet Art. 33(1) 72h deadline, including detection and logging mechanisms", effort_estimate="days (LOW tier - define playbook + integrate with monitoring)", dependencies=["IMP-D-10.1-GDPR"], layer0_refs=["SubDomains/D-04.3.md §2 HSO", "SR-GDPR-019"], company_fact_refs=["DOC04:ARCH-MONITORING"]
- gap: id="GAP-D-08.1-GDPR", sub_domain_id="D-08.1", coverage_level="PARTIAL", risk_description="Security awareness training is not formally documented or scheduled, risking non-compliance with Art. 39(1)(b) DPO monitoring obligations.", covered_by_other_reg=[], recommendation="Document and accept (LOW tier - create basic annual plan)", priority="P2", layer0_refs=["SubDomains/D-08.1.md §2 HSO"]
- gap: id="GAP-D-09.4-GDPR", sub_domain_id="D-09.4", coverage_level="PARTIAL", risk_description="Records of Processing Activities (RoPA) are not fully maintained per Art. 30(1), missing detailed data flow documentation.", covered_by_other_reg=[], recommendation="Address if high risk (LOW tier - create RoPA template)", priority="P2", layer0_refs=["SubDomains/D-09.4.md §2 HSO"]

## Rationale
GDPR applies to TinyTask Lda. because the company operates a commercial SaaS application processing personal data of EU residents, qualifying as a 'Controller' under Art. 4(7). The company's architecture (DOC04:ARCH-SYS-01) involves storing customer names and emails in AWS RDS/S3 within eu-west-1, triggering territorial scope under Art. 3(2) due to offering services to data subjects in the EU. As a MICRO entity with 8 employees, proportionality applies; however, core obligations like security of processing (Art. 32), breach notification (Art. 33), and accountability documentation (Art. 5(2)) remain mandatory regardless of size. The Regulatory Baseline confirms that GDPR Art. 32 requires appropriate technical measures for data at rest (D-01.1) and in transit, which aligns with TinyTask's use of TLS 1.3 and AES-256 encryption but lacks formal policy documentation (DOC04:SECURITY-FTE). The absence of a designated DPO or CISO creates gaps in governance oversight required by Art. 37/39, though outsourcing is permissible for MICRO entities if documented. No derogations apply as the processing scope is commercial SaaS, not household activity (TIPO3-GDPR-HOUSEHOLD NOT_ACTIVATED). Therefore, GDPR obligations are binding and must be implemented through tier-appropriate measures focused on essential controls like encryption key management, processor contracts with AWS/Auth0/Stripe, and basic incident response playbooks.


### P1C-LLM-01-OVERLAP-CLASSIFICATION

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-01.1 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Predicate `PRED-D01.1-GDPR-CRA-SAME-PARTY` evaluated TRUE (`is_manufacturer=True`, `product_stores_personal_data=True`). Layer 0 relationship CONDITIONAL activated to OVERLAP.
- D-01.1 : NIS2 ↔ CRA (SCOPE_DISJOINT): Predicate `PRED-D01.1-NIS2-CRA-SAME-PARTY` evaluated FALSE (`nis2_essential=False`). Company not in scope for NIS2; overlap impossible.
- D-01.1 : GDPR ↔ NIS2 (SCOPE_DISJOINT): Layer 0 relationship SAME, but NIS2 not applicable to company facts (`regulatory_classification.nis2_entity_class=NOT_APPLICABLE`). No same-party obligation exists.
- D-01.2 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Layer 0 relationship SAME. Both regulations apply to TinyTask as Controller/Manufacturer handling data in transit (TLS flows). Deterministic overlap confirmed by applicability intersection.
- D-01.3 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Layer 0 relationship SAME. Key management obligations converge on same product/data assets where both regs apply.
- D-01.4 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Layer 0 relationship SAME. Integrity mechanisms required by both for personal data stored/processed in the SaaS application.

## Findings
- **Active Sub-domains:** All four sub-domains within Domain D-01 are active (`D-01.1`, `D-01.2`, `D-01.3`, `D-01.4`) as TinyTask processes personal data (GDPR) and places digital products with cybersecurity functions on the EU market (CRA).
- **Scope Overlap Summary:** Significant overlap confirmed between GDPR and CRA across all sub-domains due to the integrated role of TinyTask acting as both Data Controller and Product Manufacturer for the same artefacts. No overlap exists involving NIS2, DORA, or AI Act due to inapplicability (`regulatory_classification` flags).
- **Applicable Regulations:** GDPR (Controller), CRA (Manufacturer Class I).
- **Layer 0 References:** `SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA`, `catalogs/scope_overlap_predicates.yaml#PRED-D01.1-GDPR-CRA-SAME-PARTY`.

## Rationale
The analysis activates Regulatory Baseline entries for Domain D-01 (Data Protection & Encryption) against TinyTask Lda.'s specific facts. The company is classified as a MICRO entity operating in Technology/Software, with dual regulatory roles: GDPR Controller and CRA Manufacturer (`DOC04:v2_company_profile`).

For Sub-domain D-01.1 (Data at Rest), the Regulatory Baseline defines the GDPR ↔ CRA relationship as CONDITIONAL regarding scope overlap. The activation predicate `PRED-D01.1-GDPR-CRA-SAME-PARTY` requires that the company is a manufacturer AND its product stores personal data (`company_facts.is_manufacturer == True and company_facts.product_stores_personal_data == True`). TinyTask's architecture confirms it places digital products on the EU market (CRA Class I) and processes/stores customer names, emails, and passwords in AWS RDS/S3 within `eu-west-1` (`DOC04:architecture.data_flows`, `DOC04:data_stores.STORE-01`). Therefore, the predicate evaluates to TRUE, resulting in an OVERLAP_CONFIRMED verdict. This means TinyTask must implement a unified encryption control set that satisfies both GDPR Art. 32(1) and CRA Annex I Part I (2)(e).

For Sub-domains D-01.2 through D-01.4, the Regulatory Baseline classifies GDPR ↔ CRA pairs as SAME (`verified_relationship: "SAME"`). Per non-negotiable constraints, these classifications are READ-ONLY and cannot be re-classified. However, overlap status is determined by applicability intersection. Since both GDPR and CRA apply to TinyTask for data in transit (TLS 1.3 flows), key management (AWS KMS usage), and integrity mechanisms (data accuracy/storage protection), the obligations converge on the same technical artefacts. Thus, OVERLAP_CONFIRMED is emitted deterministically based on applicability without altering the Layer 0 classification.

Pairs involving NIS2, DORA, or AI Act are marked SCOPE_DISJOINT or NOT_TRIGGERED because TinyTask's `regulatory_classification` explicitly flags these as `NOT_APPLICABLE`. For instance, predicate `PRED-D01.1-NIS2-CRA-SAME-PARTY` fails the `nis2_essential == True` check (`DOC04:regulatory_classification.nis2_entity_class=NOT_APPLICABLE`). Consequently, no cross-regulation coordination is required for these specific pairs in this domain lane.

All citations reference the frozen Regulatory Baseline files provided in `layer0_subdomain_refs`. No article numbers were invented; all regulatory anchors (e.g., GDPR Art. 32, CRA Annex I) are derived from the Layer 0 Security Objectives and CRDA sections cited above.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-02.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Relationship: SAME). Both regulations are applicable to TinyTask Lda., and the Regulatory Baseline defines this pair as "SAME" in sub-domain Vulnerability Identification. No re-classification performed; overlap is deterministic based on applicability of both regs.
- D-02.1 : GDPR ↔ NIS2, DORA, AI_Act: OVERLAP_NOT_TRIGGERED (Regulations not applicable to company).
- D-02.2 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable; only CRA applies per `company_facts`).
- D-02.3 : CRA ↔ NIS2: OVERLAP_NOT_TRIGGERED (NIS2 not applicable).
- D-02.4 : CRA ↔ DORA, AI_Act: OVERLAP_NOT_TRIGGERED (DORA/AI Act not applicable).

## Findings
- **Active Sub-domains:** All four sub-domains in Domain D-02 are technically active within the Regulatory Baseline structure (`layer0_subdomain_refs`), but regulatory overlap is only confirmed where both GDPR and CRA participate.
  - `D-02.1 Vulnerability Identification`: Active for GDPR & CRA (Overlap Confirmed).
  - `D-02.2 Patch Management & Updates`: Participating regs are CRA, DORA. Only CRA applies to TinyTask. No overlap with GDPR in this sub-domain per Baseline pairs provided.
  - `D-02.3 Coordinated Vulnerability Disclosure`: Participating regs are CRA, NIS2 partial. Only CRA applies.
  - `D-02.4 Threat-Led Penetration Testing`: Participating regs are CRA, DORA, AI_Act partial. Only CRA applies.
- **Scope Overlap Summary:** OVERLAP_CONFIRMED only for sub-domain D-02.1 (GDPR ↔ CRA). All other pairs involve regulations not applicable to TinyTask Lda. (NIS2, DORA, AI Act) or lack a defined pair in the provided Baseline data involving GDPR+CRA.
- **Applicable Regulations:** GDPR, CRA (`company_facts.applicable_regs`).
- **Layer0 References:** 
  - `SubDomains/D-02_Vulnerability-Management/D-02.1.md §1 CRDA` (GDPR↔CRA pair)
  - `SubDomains/D-02_Vulnerability-Management/D-02.2.md §1 HSO` (Participating regs: CRA, DORA)
  - `company_facts.regulatory_classification.cra_product_class = CLASS_I`, `gdpr.role = controller`.

## Rationale
The analysis confirms regulatory overlap for TinyTask Lda. in Domain D-02 specifically within sub-domain D-02.1 (Vulnerability Identification). The Regulatory Baseline (`layer0_subdomain_refs`) defines the relationship between GDPR and CRA in this sub-domain as "SAME" (verified_relationship: SAME), which is a READ-ONLY classification per AEGIS constraints. Since TinyTask Lda. is subject to both regulations—acting as a Controller under GDPR (processing personal data) and Manufacturer under CRA (placing digital products on EU market)—the overlap is deterministically confirmed without requiring conditional predicate evaluation for this specific pair.

For sub-domains D-02.2, D-02.3, and D-02.4, the provided Regulatory Baseline pairs do not include GDPR↔CRA combinations (e.g., D-02.2 lists CRA↔DORA; D-02.3 lists CRA↔NIS2). Consequently, no overlap exists between applicable regulations in these sub-domains for this company profile. The absence of NIS2, DORA, and AI Act applicability (`company_facts.regulatory_classification`) further ensures that pairs involving those regimes are marked as OVERLAP_NOT_TRIGGERED or SCOPE_DISJOINT relative to the active regulatory scope (GDPR+CRA). No conditional predicates were required for evaluation in this domain run because the provided `scope_overlap_predicates` input did not contain entries for D-02 sub-domains, and the static Baseline relationships ("SAME") suffice where both regs apply.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-03.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — DIFFERENT-PERSPECTIVE" applies; TinyTask is both Controller (GDPR) and Manufacturer (CRA), triggering HSOs in this sub-domain for both regulations simultaneously (`DOC04:v2_company_profile.role_matrix`).
- D-03.1 : GDPR ↔ NIS2: OVERLAP_NOT_TRIGGERED — Baseline relationship "SAME — DIFFERENT-PERSPECTIVE"; NIS2 not applicable to TinyTask (not an Annex I/II entity) per `DOC04:v2_company_profile.regulatory_classification`.
- D-03.1 : GDPR ↔ DORA: OVERLAP_NOT_TRIGGERED — Baseline relationship "SAME — COMPLEMENTARY"; DORA not applicable (non-financial entity).
- D-03.2 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — COMPLEMENTARY" on authentication; both regs apply to TinyTask's identity systems (`DOC04:v2_company_profile.applicable_regs`).
- D-03.2 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED — NIS2 not applicable.
- D-03.3 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — COMPLEMENTARY" on authorisation; both regs apply to TinyTask's access control policies (`DOC04:v2_company_profile.role_matrix`).
- D-03.3 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED — NIS2 not applicable.
- D-03.4 : GDPR ↔ CRA: OVERLAP_CONFIRMED — Baseline relationship "SAME — DIFFERENT-PERSPECTIVE" on secure defaults; both regs apply to TinyTask's product and data processing configurations (`DOC04:v2_company_profile.regulatory_classification`).

## Findings
- **Active Sub-Domains:** D-03.1 (Identity Lifecycle), D-03.2 (MFA), D-03.3 (Authorisation), D-03.4 (Secure Defaults). All four sub-domains are active for TinyTask as they contain HSOs applicable to both GDPR and CRA roles held by the company (`DOC04:v2_company_profile.role_matrix`).
- **Scope Overlap Summary:** OVERLAP_CONFIRMED on all pairs involving GDPR ↔ CRA within Domain D-03. The Regulatory Baseline classifies these relationships as "SAME — DIFFERENT-PERSPECTIVE" or "COMPLEMENTARY", indicating co-existing obligations rather than conflict, but requiring parallel compliance tracks for the same entity (`SubDomains/D-03_Identity-and-Access/D-XX.Y.md §1 CRDA`).
- **Applicable Regulations:** GDPR (Controller), CRA (Manufacturer). NIS2, DORA, and AI_Act are explicitly excluded per `DOC04:v2_company_profile.regulatory_classification`.
- **Layer 0 References:** 
    - SubDomains/D-03_Identity-and-Access/D-03.1.md §1 CRDA pair GDPR↔CRA (lines inferred from baseline structure)
    - SubDomains/D-03_Identity-and-Access/D-03.2.md §1 CRDA pair GDPR↔CRA
    - SubDomains/D-03_Identity-and-Access/D-03.3.md §1 CRDA pair GDPR↔CRA
    - SubDomains/D-03_Identity-and-Access/D-03.4.md §1 CRDA pair GDPR↔CRA

## Rationale
The Regulatory Baseline for Domain D-03 (Identity & Access Management) establishes that GDPR and CRA obligations coexist on the same sub-domains when an entity acts as both a Data Controller under GDPR and a Manufacturer of digital products with cybersecurity functions under CRA. TinyTask Lda. satisfies both roles: it processes personal data (`DOC04:v2_company_profile.processes_personal_data = true`) qualifying for GDPR, and places Class I digital products on the EU market (`DOC04:v2_company_profile.cra_product_class = CLASS_I`), triggering CRA obligations.

For sub-domains D-03.1 through D-03.4, the Regulatory Baseline classifies the relationship between GDPR and CRA as "SAME — DIFFERENT-PERSPECTIVE" or "COMPLEMENTARY". This indicates that while both regulations apply to identity management activities within this domain (e.g., verifying data subjects vs managing product user identities), they address distinct aspects of security. However, because TinyTask is subject to *both* regimes simultaneously on the same systems (`DOC04:architecture.systems` includes AWS/Firebase stacks handling personal data and serving as digital products), there is a confirmed scope overlap requiring dual compliance tracking.

No specific conditional predicates for Domain D-03 were provided in the input catalog (predicates listed applied to D-01, D-04, D-05, D-09). Therefore, activation relies on deterministic applicability: since both regulations are active per `DOC04:v2_company_profile.applicable_regs`, and HSOs exist for both regs in all four sub-domains (`layer0_subdomain_refs.hso_per_reg`), the overlap is confirmed. Pairs involving NIS2 or DORA result in OVERLAP_NOT_TRIGGERED because TinyTask does not meet the sector/entity thresholds defined in `DOC04:v2_company_profile.regulatory_classification`. The output preserves the READ-ONLY classifications from the Regulatory Baseline without re-classification, as required by AEGIS constraints.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-04.3 : GDPR ↔ CRA: OVERLAP_CONFIRMED. Predicate `PRED-D04.3-GDPR-CRA-SAME-ACTOR` evaluated TRUE (TinyTask is both Controller and Manufacturer, product processes personal data). Baseline relationship CONDITIONAL activated to confirmed overlap on incident notification timelines.
- D-04.1 : GDPR ↔ CRA: SAME — DIFFERENT-PERSPECTIVE. No conditional activation required; baseline preserved per Regulatory Baseline `SubDomains/D-04_Incident-Response/D-04.1.md`. NIS2, DORA pairs inactive (regulations not applicable).
- D-04.2 : GDPR ↔ CRA: SAME — DIFFERENT-PERSPECTIVE. No conditional activation required; baseline preserved per Regulatory Baseline `SubDomains/D-04_Incident-Response/D-04.2.md`. NIS2, DORA pairs inactive (regulations not applicable).
- D-04.4 : GDPR ↔ CRA: SAME — DIFFERENT-PERSPECTIVE. No conditional activation required; baseline preserved per Regulatory Baseline `SubDomains/D-04_Incident-Response/D-04.4.md`. NIS2, DORA pairs inactive (regulations not applicable).

## Findings
- **Active Sub-domains:** All 4 sub-domains in Domain D-04 are active (`D-04.1` to `D-04.4`) as GDPR and CRA apply to TinyTask Lda.'s SaaS product lifecycle (processing personal data + placing digital products on EU market).
- **Scope Overlap:** Confirmed overlap exists specifically in Sub-domain D-04.3 (Incident Notification & Reporting) due to the dual role of Controller (GDPR) and Manufacturer (CRA). This creates a parallel notification obligation where GDPR Art. 33 (72h) and CRA Art. 14 (24h/72h/14d tiers) must be managed simultaneously for personal data breaches involving product vulnerabilities.
- **Applicable Regulations:** Only GDPR and CRA are active per `company_facts.applicable_regs`. NIS2, DORA, and AI Act predicates were evaluated as NOT_TRIGGERED due to sector (Technology/Software), entity size (MICRO), and lack of high-risk AI systems or financial status.
- **layer0_refs:** SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA pair GDPR↔CRA lines 117-126; SubDomains/D-04_Incident-Response/D-04.1..D-04.4.md (baseline pairs).

## Rationale
The Regulatory Baseline for Domain D-04 indicates that while most regulation pairs maintain a baseline relationship of SAME or COMPLEMENTARY, the GDPR ↔ CRA pair in Sub-domain D-04.3 is marked CONDITIONAL pending company role verification. TinyTask Lda.'s `company_facts` confirm it acts as both a Controller (GDPR) and Manufacturer (CRA), satisfying the activation predicate for overlap (`is_manufacturer_and_controller == True`). Consequently, the scope_overlap verdict shifts from baseline to OVERLAP_CONFIRMED specifically for incident notification timelines in D-04.3. For other sub-domains (Detection, Containment, Recovery), no conditional predicates were provided or triggered; thus, the verified relationships remain as defined in the Regulatory Baseline files without re-classification. Regulations NIS2, DORA, and AI Act are excluded from overlap analysis for this domain invocation because they do not appear in `applicable_regs` (TinyTask is MICRO scale, non-financial sector, no high-risk AI), rendering their associated predicates INDETERMINATE or NOT_TRIGGERED based on applicability facts.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-05.1 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Conditional overlap confirmed as TinyTask is both Controller (GDPR) and Manufacturer (CRA Class I) processing personal data via SaaS product (`DOC04:v2_company_profile.processes_personal_data=True`, `DOC04:regulatory_classification.cra_product_class=CLASS_I`).
- D-05.1 : GDPR ↔ AI_Act (OVERLAP_NOT_TRIGGERED): No high-risk AI system deployed (`DOC04:role_matrix.ai_act.role=not_applicable`), predicate not met.
- D-05.2 : GDPR ↔ CRA (SCOPE_DISJOINT): Typically disjoint; overlap only if update logs contain personal data requiring separation architecture. TinyTask uses managed services where log ownership is shared, but baseline classification remains scope-disjoint for standard retention artefacts (`layer0_subdomain_refs.D-05.2.pairs[0].scope_overlap`).
- D-05.2 : GDPR ↔ AI_Act (OVERLAP_NOT_TRIGGERED): Predicate `PRED-D05.2-GDPR-AI-ACT-COMPLEMENTARY` requires high-risk AI (`DOC04:ai_system_classification=NOT_APPLICABLE`). Condition false -> Not Triggered.
- D-05.3 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Overlap confirmed as users are data subjects invoking Art. 17 erasure rights on a product with digital elements (`layer0_subdomain_refs.D-05.3.pairs[0].scope_overlap`). TinyTask processes personal data and places products in EU market.
- D-05.4 : GDPR (SINGLE_REG): No pairwise overlap; sole authority for Data Portability under Art. 20.

## Findings
- **Active Subdomains:** D-05.1, D-05.2, D-05.3 are active due to CRA/GDPR applicability (`DOC04:applicable_regs=['CRA', 'GDPR']`). D-05.4 is GDPR-only but relevant for data subject rights.
- **Scope Overlap Summary:** Significant overlap exists between GDPR and CRA in Data Minimisation (D-05.1) and Right to Erasure (D-05.3) due to TinyTask's dual role as Controller/Manufacturer. AI Act overlaps are inactive (`OVERLAP_NOT_TRIGGERED`) due to lack of high-risk AI systems.
- **Applicable Regulations:** GDPR, CRA. NIS2/DORA/AI_Act excluded based on `DOC04:regulatory_classification`.
- **layer0_refs:** 
  - SubDomains/D-05_Data-Lifecycle/D-05.1.md §1 CRDA pair GDPR↔CRA lines (inferred from input pairs)
  - SubDomains/D-05_Data-Lifecycle/D-05.2.md §1 CRDA pair GDPR↔AI_Act
  - SubDomains/D-05_Data-Lifecycle/D-05.3.md §1 CRDA pair GDPR↔CRA

## Rationale
The analysis confirms that TinyTask Lda., operating as a MICRO entity in the Technology/Software sector, triggers regulatory overlap primarily between GDPR and CRA within Domain D-05 (Data Lifecycle). This is driven by the company's dual status: it acts as a Data Controller under GDPR (`DOC04:role_matrix.gdpr.role=controller`) processing personal data of EU residents, while simultaneously acting as a Manufacturer under CRA for Class I digital products placed on the EU market (`DOC04:regulatory_classification.cra_product_class=CLASS_I`).

For D-05.1 (Data Minimisation), the overlap is confirmed because the same dataset processed by TinyTask's SaaS application constitutes both personal data subject to GDPR Art. 5(1)(c) and product data under CRA Annex I Part I (2)(g). The Regulatory Baseline indicates this relationship is CONDITIONAL on the company being an integrated manufacturer-controller, which matches `DOC04:v2_company_profile`. For D-05.3 (Right to Erasure), overlap is confirmed as users exercising GDPR Art. 17 rights are also invoking CRA Annex I Part I (2)(m) removal affordances on the same product artefacts.

Conversely, overlaps involving AI Act predicates (`PRED-D05.2-GDPR-AI-ACT-COMPLEMENTARY`) result in OVERLAP_NOT_TRIGGERED because TinyTask has no high-risk AI systems deployed (`DOC04:ai_system_classification=NOT_APPLICABLE`). Similarly, NIS2 and DORA overlaps are excluded as the company is not an essential entity or financial institution. The output reflects these determinations without re-classifying frozen Regulatory Baseline relationships (e.g., maintaining SCOPE_DISJOINT for standard retention artefacts in D-05.2 where personal data separation applies).

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-06.1 : GDPR ↔ CRA (OVERLAP_CONFIRMED): Regulatory Baseline indicates overlap when controller deploys a CRA-classified product (`layer0_subdomain_refs` D-06.1 pair). TinyTask is both Controller (GDPR) and Manufacturer (CRA), satisfying the condition for integrated vendor risk management obligations.
- D-06.2 : GDPR ↔ N/A (OVERLAP_NOT_TRIGGERED): Sub-domain D-06.2 SBOM participation list contains only CRA (`participating_regulations`: ["CRA"]). No pairwise relationship with GDPR exists in this sub-domain per Regulatory Baseline.
- D-06.3 : GDPR ↔ CRA (SCOPE_DISJOINT): Pair description notes "N typically — different contracting parties". While TinyTask is both Controller and Manufacturer, the contractual mechanisms differ (GDPR Art 28 vs CRA Economic Operator duties). Overlap exists in obligation scope but not on a single contract instrument per Baseline.
- D-06.4 : GDPR ↔ CRA (OVERLAP_NOT_TRIGGERED): Pair description specifies overlap "Y when the same non-EU entity is both...". TinyTask jurisdiction is Portugal (EU), failing this specific predicate condition for boundary management representatives.

## Findings
- **Active Sub-domains:** D-06.1, D-06.3 are active due to vendor relationships (AWS, Stripe) and contractual obligations under GDPR/CRA. D-06.2 is active solely for CRA compliance (SBOM). D-06.4 has limited applicability given EU jurisdiction.
- **Scope Overlap Summary:** Significant overlap confirmed in Vendor Risk Assessment (D-06.1) where TinyTask must manage suppliers as both a GDPR Controller and CRA Manufacturer. Contractual obligations (D-06.3) remain distinct layers despite the same party holding dual roles.
- **Applicable Regulations:** Only GDPR and CRA are active for this domain based on `company_facts.applicable_regs`. NIS2, DORA, AI_Act pairs are excluded from classification as they do not apply to TinyTask (MICRO scale, non-financial).
- **layer0_refs:** SubDomains/D-06_Vendor-Risk/D-06.1.md §1 CRDA pair GDPR↔CRA; SubDomains/D-06_Contractual-Obligations/D-06.3.md §1 CRDA pair GDPR↔CRA.

## Rationale
The classification is driven by TinyTask's dual role as a GDPR Controller and CRA Manufacturer, combined with its MICRO scale which excludes NIS2/DORA applicability (`company_facts.regulatory_classification`). For D-06.1 (Vendor Risk), the Regulatory Baseline (§1 CRDA) defines overlap when a controller deploys a CRA product; TinyTask's architecture confirms this via `DOC04:architecture.systems` and `role_matrix`. Consequently, vendor due diligence must satisfy both GDPR Art 28(1) guarantees and CRA component vetting. For D-06.3 (Contractual), the Baseline distinguishes between processor contracts (GDPR) and economic operator duties (CRA); while TinyTask holds both roles, they do not merge into a single instrument per `layer0_subdomain_refs` pair descriptions. D-06.4 boundary management predicates specifically target non-EU entities (`scope_overlap_predicates` logic in Baseline), which does not apply to this EU-based company, resulting in no overlap for that specific mechanism. All NIS2/DORA pairs are marked NOT_TRIGGERED as these regulations are explicitly excluded from `applicable_regs`.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-07.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Company is Controller per GDPR and Manufacturer per CRA; product processes personal data).
- D-07.2 : CRA ↔ DORA: SCOPE_DISJOINT (DORA not applicable to TinyTask Lda.).
- D-07.2 : CRA ↔ AI_Act: OVERLAP_NOT_TRIGGERED (AI Act high-risk system classification is NOT_APPLICABLE per company facts).
- D-07.3 : NIS2 ↔ CRA: SCOPE_DISJOINT (NIS2 not applicable; TinyTask is not an NSIE entity).
- D-07.4 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to non-financial entities like TinyTask Lda.).

## Findings
- **Active Sub-domains:** Only sub-domain `D-07.1` contains a verified relationship pair (`GDPR ↔ CRA`) where both regulations are active for the company and overlap conditions are met.
- **Scope Overlap Summary:** 
  - D-07.1 (Secure-by-Design): OVERLAP_CONFIRMED between GDPR Art. 25(1) data-protection by-design and CRA Annex I Part I product cybersecurity by-design. The same party acts as Controller and Manufacturer on the same artefact (`DOC04:architecture.systems`).
  - D-07.2 (Secure Coding): No overlap pair defined between active regs (GDPR/CRA). Baseline pairs involve non-applicable regs (DORA, AI_Act).
  - D-07.3 (CI/CD Pipeline): Pair `NIS2 ↔ CRA` is SCOPE_DISJOINT as NIS2 does not apply to this MICRO entity (`DOC04:regulatory_classification.nis2_entity_class`).
  - D-07.4 (Change Management): Pair `CRA ↔ DORA` is OVERLAP_NOT_TRIGGERED; company is non-financial (`DOC04:v2_company_profile.sector='Technology/Software'`).
- **Applicable Regulations:** GDPR, CRA.
- **layer0_refs:** 
  - SubDomains/D-07_Secure-by-Design/D-07.1.md §1 CRDA pair GDPR↔CRA lines (inferred from input pairs data)
  - SubDomains/D-07_Secure-Coding/D-07.2.md §1 CRDA
  - SubDomains/D-07_CI/CD-Pipeline-Security/D-07.3.md §1 CRDA
  - SubDomains/D-07_Change-Management/D-07.4.md §1 CRDA

## Rationale
The analysis activates Regulatory Baseline entries for Domain D-07 based on TinyTask Lda.'s specific regulatory profile (GDPR Controller + CRA Manufacturer). For sub-domain `D-07.1`, the baseline defines a verified relationship between GDPR and CRA with scope overlap conditional on the company being both controller and manufacturer processing personal data (`DOC04:role_matrix.gdpr.role='controller'` AND `DOC04:regulatory_classification.cra_product_class='CLASS_I'`). Since TinyTask places digital products (CRA) that process EU personal data (GDPR), this condition is met, resulting in OVERLAP_CONFIRMED. This requires a joint by-design stack where GDPR Art. 25(1) outputs feed into CRA Annex I Part I evidence trails (`SubDomains/D-07_Secure-by-Design/D-07.1.md`).

For sub-domains `D-07.2`, `D-07.3`, and `D-07.4`, the baseline pairs involve regulations not applicable to TinyTask (NIS2, DORA, AI_Act). Specifically, NIS2 is excluded due to entity size/sector (`DOC04:regulatory_classification.nis2_entity_class='NOT_APPLICABLE'`), DORA is excluded as non-financial (`DOC04:v2_company_profile.sector`), and AI Act is excluded as no high-risk system exists. Consequently, pairs involving these regulations are classified as SCOPE_DISJOINT or OVERLAP_NOT_TRIGGERED deterministically based on the activation predicates in `scope_overlap_predicates.yaml` (e.g., PRED-D09.2 requires financial sector). No re-classification of baseline relationships was performed; verdicts were derived strictly from company facts against provided predicate logic and sub-domain pair definitions.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-08.1 : GDPR ↔ NIS2: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.1 : GDPR ↔ CRA: SCOPE_DISJOINT (Different audiences per CRDA; workforce vs end-user instructions)
- D-08.1 : GDPR ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.1 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.1 : NIS2 ↔ DORA: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.1 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.2 : GDPR ↔ NIS2: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.2 : GDPR ↔ CRA: SCOPE_DISJOINT (Different audiences per CRDA; workforce vs integrator-B2B)
- D-08.2 : GDPR ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.2 : GDPR ↔ AI_Act: OVERLAP_NOT_TRIGGERED (AI Act not applicable per company classification)
- D-08.2 : NIS2 ↔ CRA: OVERLAP_NOT_TRIGGERED (NIS2 not applicable to TinyTask)
- D-08.2 : NIS2 ↔ DORA: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.2 : NIS2 ↔ AI_Act: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.2 : CRA ↔ DORA: OVERLAP_NOT_TRIGGERED (DORA not applicable to TinyTask)
- D-08.2 : CRA ↔ AI_Act: OVERLAP_NOT_TRIGGERED (AI Act not applicable per company classification)
- D-08.2 : DORA ↔ AI_Act: OVERLAP_NOT_TRIGGERED (Neither regulation applies directly)
- D-08.3 : NIS2 ↔ DORA: OVERLAP_NOT_TRIGGERED (Neither regulation applies to TinyTask management body training obligations)

## Findings
- **Active Sub-domains:** D-08.1, D-08.2 (D-08.3 inactive due to lack of applicable regulations).
- **Applicable Regulations:** GDPR, CRA.
- **Scope Overlap Summary:** No confirmed regulatory overlap within Domain D-08 for TinyTask Lda. All pairs involving NIS2, DORA, or AI Act are not triggered due to company scope (MICRO scale, non-financial, no high-risk AI). The only pair where both regulations apply is GDPR ↔ CRA; however, the Regulatory Baseline classifies this relationship as SCOPE_DISJOINT for sub-domains D-08.1 and D-08.2 because obligations target different audiences (internal workforce vs external end-user/integrator) with no consolidation rule.
- **layer0_refs:** SubDomains/D-08_Security-Awareness/D-08.1.md §1 CRDA, SubDomains/D-08_Security-Awareness/D-08.2.md §1 CRDA, SubDomains/D-08_Security-Awareness/D-08.3.md §1 CRDA.

## Rationale
The analysis activates the Regulatory Baseline for Domain D-08 (Security Awareness & Training) against TinyTask Lda.'s facts. The company is classified as MICRO scale in Technology/Software, with GDPR and CRA applicable (`DOC04:applicable_regs`), while NIS2, DORA, and AI Act are explicitly non-applicable per `DOC04:regulatory_classification`.

For sub-domain D-08.1 (General Security Awareness) and D-08.2 (Role-Specific Competence), the Regulatory Baseline (§1 CRDA pairs provided in input data) indicates that GDPR ↔ CRA relationships are SCOPE_DISJOINT. Specifically, GDPR Art. 39(1)(b) mandates workforce awareness training catalysed by a DPO for internal staff involved in processing (`DOC04:architecture.auth_systems`), whereas CRA Annex II §8(a)-(f) requires user-facing instructions shipped with the product or provided to integrators (B2B). These obligations address substantively different audiences and objects, preventing overlap confirmation despite both regulations applying.

All other pairs involve NIS2, DORA, or AI Act. Since TinyTask is not a financial entity (`DOC04:regulatory_classification.dora_article_2_entity`), not an essential/important entity under NIS 2 (`DOC04:regulatory_classification.nis2_entity_class`), and does not deploy high-risk AI systems (`DOC04:regulatory_classification.ai_system_classification`), these regulations do not trigger. Consequently, any pair involving them is marked OVERLAP_NOT_TRIGGERED deterministically based on the activation predicates requiring regulation applicability.

Sub-domain D-08.3 (Management Board Training) relies entirely on NIS2 Art. 20(2) and DORA Art. 5(4). As neither applies, this sub-domain is inactive for overlap classification purposes in this case context. No INSUFFICIENT_EVIDENCE conditions were encountered as company facts regarding sector, scale, and regulatory status are explicit in `DOC04:v2_company_profile`.

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-09.1 : GDPR ↔ CRA (Information Security Policies): OVERLAP_CONFIRMED. Company is both Controller (GDPR) and Manufacturer (CRA). Product processes personal data (`DOC04:architecture.data_stores.STORE-01`). Baseline `SubDomains/D-09_Governance-Documents/D-09.1.md §1 CRDA` indicates overlap when controller-manufacturer integration exists on same artefact.
- D-09.2 : GDPR ↔ CRA (Impact & Risk Assessments): OVERLAP_CONFIRMED. Company places digital products processing personal data (`DOC04:v2_company_profile.processes_personal_data`). Baseline `SubDomains/D-09_Governance-Documents/D-09.2.md §1 CRDA` confirms overlap when product processes personal data, requiring separate artefacts (DPIA vs Risk Assessment).
- D-09.3 : GDPR ↔ CRA (Asset Inventories): SCOPE_DISJOINT. Baseline `SubDomains/D-09_Governance-Documents/D-09.3.md §1 CRDA` lists participating regulations as NIS2, CRA, DORA only; GDPR is not a participant in this sub-domain per Regulatory Baseline provided.
- D-09.4 : GDPR ↔ CRA (Records of Processing): SCOPE_DISJOINT. Baseline `SubDomains/D-09_Governance-Documents/D-09.4.md §1 CRDA` states "N (typically)" with different record types and triggers; no OJ-level consolidation rule exists for documentation layers despite company being both Controller/Manufacturer.

## Findings
- **D-09.1**: Active sub-domain. Scope overlap confirmed due to dual role (`DOC04:role_matrix.gdpr.role=controller`, `DOC04:role_matrix.cra.role=manufacturer`). Requires layered policy stack (GDPR Art. 24 + CRA Art. 13/27).
- **D-09.2**: Active sub-domain. Scope overlap confirmed due to personal data processing in product (`DOC04:architecture.data_flows.FLOW-01`). Requires parallel risk assessments (GDPR DPIA vs CRA Annex VII §3) with no consolidation rule per Baseline `SubDomains/D-09_Governance-Documents/D-09.2.md`.
- **D-09.3**: Active sub-domain for CRA only. GDPR scope disjoint as not listed in participating regulations (`layer0_subdomain_refs.D-09.3.participating_regulations`). Company must maintain CRA technical documentation (Annex VII) but no GDPR asset inventory obligation here per Baseline.
- **D-09.4**: Active sub-domain for both regs, but scope disjoint on artefacts. Requires separate Records of Processing (`DOC04:regulatory_interactions.negative_analyses.NA-03` notes missing processor register) and CRA Technical Documentation (Annex VII). No substitution allowed per Baseline `SubDomains/D-09_Governance-Documents/D-09.4.md`.
- **Cross-sub-domain pattern**: Governance documentation requires strict separation of artefacts where regulations differ in audit purpose (DPA vs MSA), even when the same entity holds both roles.

## Rationale
The Regulatory Baseline for Domain D-09 indicates that overlap between GDPR and CRA is conditional on the company holding dual status as Controller and Manufacturer while processing personal data within the product scope (`SubDomains/D-09_Governance-Documents/D-09.1.md §1 CRDA`, `D-09.2.md`). TinyTask Lda. satisfies these conditions: it operates a SaaS application storing customer PII (GDPR Controller) and places digital products on the EU market as a Manufacturer (`DOC04:v2_company_profile.places_digital_products_eu=true`, `cra_product_class=CLASS_I`). Consequently, D-09.1 (Policies) and D-09.2 (Risk Assessments) are classified as OVERLAP_CONFIRMED because both regimes impose obligations on the same entity regarding the same artefacts or events. However, for D-09.4 (Records), the Baseline explicitly states "N (typically)" due to different record types serving distinct audit purposes (`SubDomains/D-09_Governance-Documents/D-09.4.md §1 CRDA`); thus, despite dual roles, no scope overlap exists for documentation consolidation. D-09.3 is SCOPE_DISJOINT because the Regulatory Baseline provided does not list GDPR as a participating regulation in that sub-domain (`layer0_subdomain_refs.D-09.3.participating_regulations`). All verdicts rely strictly on `company_facts` and `layer0_subdomain_refs` without re-classifying frozen relationships (e.g., maintaining "SCOPE_DISJOINT" for D-09.4 as per Baseline text).

---

## Status
- applicable: YES
- confidence: HIGH

## Pair classifications
- D-10.1 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Conditional predicate met: product processes personal data). Layer 2 flag present in Regulatory Baseline regarding monitoring opt-out conflict.
- D-10.2 : GDPR ↔ CRA: SCOPE_DISJOINT (Baseline classification "N (typically)" upheld; distinct artefacts required for RoPA vs Technical Documentation).
- D-10.3 : GDPR ↔ CRA: OVERLAP_CONFIRMED (Conditional predicate met: controller deploys CRA-regulated product as manufacturer).

## Findings
- **Active Sub-domains:** 3 of 3 provided in input scope (D-10.1, D-10.2, D-10.3) are applicable to TinyTask Lda. given GDPR and CRA applicability (`company_facts.applicable_regs`).
- **Scope Overlap Summary:** 
    - D-10.1 (Monitoring): Confirmed overlap due to SaaS product processing personal data (`DOC04:architecture.data_stores.STORE-01.personal_data = True`). Requires Layer 2 review for CRA opt-out vs GDPR mandatory monitoring conflict.
    - D-10.2 (Logging): Scope disjoint; obligations remain separate despite shared infrastructure logging capabilities.
    - D-10.3 (Testing): Confirmed overlap due to dual role as Manufacturer and Controller (`DOC04:role_matrix.cra.role = manufacturer`, `DOC04:role_matrix.gdpr.role = controller`). Testing programmes must address both regimes layeredly.
- **Applicable Regulations:** GDPR, CRA. NIS2, DORA, AI_Act excluded from activation per `company_facts.applicable_regs`.
- **layer0_refs:** 
    - SubDomains/D-10_Governance-Monitoring/D-10.1.md §1 CRDA pair GDPR↔CRA lines 73-82 (inferred)
    - SubDomains/D-10_Governance-Monitoring/D-10.2.md §1 CRDA pair GDPR↔CRA lines 45-60 (inferred)
    - SubDomains/D-10_Governance-Monitoring/D-10.3.md §1 CRDA pair GDPR↔CRA lines 90-110 (inferred)

## Rationale
The Regulatory Baseline for Domain D-10 indicates that overlap between GDPR and CRA is conditional on the company's role and product characteristics. For TinyTask Lda., `company_facts` confirms they are a Manufacturer under CRA (`role_matrix.cra.role`) and a Controller under GDPR (`role_matrix.gdpr.role`). Furthermore, their architecture explicitly processes personal data within EU jurisdiction (`architecture.data_stores.STORE-01.personal_data = True`, `jurisdiction: Portugal (EU)`).

For D-10.1 (Continuous Security Monitoring), the Baseline pair description states overlap is "Y (when the CRA-regulated product processes personal data)". Since TinyTask's SaaS application stores customer names and emails, this predicate evaluates to TRUE, resulting in OVERLAP_CONFIRMED. However, the Regulatory Baseline flags a Layer 2 conflict (`layer2_flag: true`) regarding user opt-out mechanisms under CRA versus mandatory monitoring under GDPR Art. 32(2).

For D-10.2 (Audit Logging), the Baseline classifies this pair as "N (typically)" with scope_disjoint_test indicating different record types and triggers. TinyTask's facts do not alter this structural separation; they must maintain separate RoPA records for GDPR and Technical Documentation for CRA, hence SCOPE_DISJOINT is maintained deterministically without re-classification.

For D-10.3 (Compliance Testing), the Baseline indicates overlap "Conditional (Y when the controller deploys CRA-regulated products)". As TinyTask manufactures their own digital product (`cra_product_class: CLASS_I`) and controls it as a SaaS provider, this condition is met. The verdict is OVERLAP_CONFIRMED, implying Phase 2 must derive layered testing obligations where GDPR effectiveness evaluation (Art. 32(1)(d)) coexists with CRA conformity assessment tests (Annex I Part II).

No re-classification of SAME/COMPLEMENTARY relationships was performed; all determinations relied on evaluating CONDITIONAL predicates against provided company facts or upholding READ-ONLY Baseline classifications where no conditional logic applied.


### P1C-LLM-02-COMPOUND-EVENT

_(no LLM response for this spec)_


### P1C-LLM-03-STRATEGIC-SYNTHESIS

_(no LLM response for this spec)_
