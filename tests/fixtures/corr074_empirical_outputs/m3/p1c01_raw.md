## Status
OK — HIGH confidence. Two sub-domains (D-01.1, D-01.2) and one pairwise regulation relationship (GDPR ↔ CRA) activated deterministically from the Regulatory Baseline against the company's confirmed processing of EU personal data.

## Domain Summary
- `total_sub_domains`: 2
- `active_sub_domains`: 2
- `pairwise_relationships`: 1

## Sub-domain Activations

### D-01.1
- `applicable`: true
- `scope_overlap`: Y
- `applicable_regulations`: ["GDPR", "CRA"]
- `layer0_refs`: ["SubDomains/D-01_Data-Protection/D-01.1.md"]

#### GDPR ↔ CRA
- `layer0_relationship`: CONDITIONAL
- `company_scope_verdict`: OVERLAP_CONFIRMED
- `rationale`: Company processes EU personal data (DOC04:ARCH-SYS-01, data_categories includes "personal_data") and acts as controller for admin data and processor for customer data, activating the GDPR↔CRA conditional pair for encryption-of-personal-data-in-transit/at-rest. Both regulations apply because the SaaS product handles EU personal data and is placed on the EU market as a product with digital elements.
- `layer0_refs`: ["SubDomains/D-01_Data-Protection/D-01.1.md §1 CRDA pair GDPR↔CRA", "SubDomains/D-01_Data-Protection/D-01.1.md §2 HSO"]

### D-01.2
- `applicable`: true
- `scope_overlap`: Y
- `applicable_regulations`: ["GDPR", "CRA"]
- `layer0_refs`: ["SubDomains/D-01_Data-Protection/D-01.2.md"]

#### GDPR ↔ CRA
- `layer0_relationship`: CONDITIONAL
- `company_scope_verdict`: OVERLAP_CONFIRMED
- `rationale`: Company processes EU personal data and operates a SaaS product (python/django/react on AWS eu-west-1) that constitutes a product with digital elements under CRA scope; both regulations apply to key management and cryptographic control objectives governing this data.
- `layer0_refs`: ["SubDomains/D-01_Data-Protection/D-01.2.md §1 CRDA pair GDPR↔CRA", "SubDomains/D-01_Data-Protection/D-01.2.md §2 HSO"]

## Notes
- `proportionality_tier` for case1-tinytask is MICRO (per Track B); D-01 outputs remain at regulatory floor but length is concise.
- Both sub-domains show `scope_overlap: Y` because the company facts confirm EU personal data processing AND placement of a product with digital elements on the EU market — both predicates of the GDPR↔CRA conditional pair are satisfied.
- No contradictions or scope-disjoint relationships in D-01 between GDPR and CRA per the Regulatory Baseline §1 CRDA.
- `p1b_outputs_by_reg` showed empty `interpretations`/`derogations` arrays for this case (MICRO tier, no Track A derogations invoked); the overlap verdict is therefore derived solely from the activation predicate evaluated against company facts and the frozen Regulatory Baseline.