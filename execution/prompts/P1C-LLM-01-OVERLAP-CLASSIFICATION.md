---
prompt_spec_id: P1C-LLM-01-OVERLAP-CLASSIFICATION
prompt_spec_version: 1.0.0
legacy_aliases:
  - LLM-E
  - "Phase 1C complementarity + conflict classification"
phase: 1
sub_phase: 1C
semantic_task: per_domain_lane_overlap_activation
invocation_pattern: per_domain_lane
author: AEGIS Methodology maintainer
status: ACTIVE
created: 2026-07-13
updated: 2026-07-13
related_documents:
  - ./base_system_prompt.md
  - ./output_schemas.yaml#P1C-LLM-01
  - ./annotations/D-XX.yaml         # per-domain
  - ./examples/overlap_same_party.yaml
  - ../../../PHASE1_STRATEGY.md
  - ../../../REGULATORY_BASELINE.md
  - ../../../PREPROCESSING/SubDomains/index.md
  - ../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md
  - ../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md
---

# P1C-LLM-01-OVERLAP-CLASSIFICATION

> **Per-domain lane overlap activation.** Activates Regulatory Baseline CONDITIONAL entries per domain. **NO re-classification** of frozen Regulatory Baseline relationships. Invocation: 1 call per active domain (D-01..D-10).

---

## When to invoke

After Phase 1B (Doc 05 + Doc 06 rows ready) and Filter 2 (per-sub-domain activation computed deterministically). For each **active domain** D-XX where at least one sub-domain is applicable, invoke this LLM once.

The active domains set is computed from `coverage_matrix.sub_domains_active` filtered to unique D-XX prefixes.

## Inputs

```yaml
case_id: "Case_XX"
lane_id: "D-XX"          # domain (e.g., D-01)
domain_id: "D-XX"
domain_overview:
  domain_name: "Data Protection & Encryption"
  sub_domain_ids: [D-XX.1, D-XX.2, ...]
applicable_regs:         # regulations that touch ANY sub-domain in this domain
  - GDPR
  - CRA
p1b_outputs_by_reg:      # results from P1B-LLM-01 + P1B-LLM-02 per applicable reg
  GDPR:
    interpretations: [...]
    derogations: [...]
    synthesis: {rationale, implications, gaps}
  CRA:
    interpretations: [...]
    derogations: [...]
    synthesis: {rationale, implications, gaps}
company_facts:           # from Doc 04
  scope: "DOC04:ARCH-XX"
  products: [...]
  data_categories: [...]
  roles: [...]
layer0_subdomain_files:  # auto-loaded per sub_domain_id
  D-XX.1: "SubDomains/D-XX_Folder/D-XX.1.md"  # with §1 CRDA + §2 HSO + §3 Volere
  D-XX.2: "..."
layer0_annotation: "annotations/D-XX.yaml"   # per-domain annotations
layer0_overlap_predicates: "catalogs/scope_overlap_predicates.yaml"
```

## Task (verbatim, use as user message)

```
<task>
For the domain {D-XX} with sub_domains {sub_domain_ids}:

1. For EACH sub_domain_id in the domain:
   a. Load the Regulatory Baseline file: SubDomains/D-XX_Folder/{sub_domain_id}.md
   b. Read §1 CRDA — the pairwise verified relationships
      (verified_relationship_per_pair[] with one entry per reg pair)
   c. For each pair where layer0_relationship is "CONDITIONAL":
      - Read the activation_predicate from scope_overlap_predicates.yaml
      - Evaluate against company_facts (this is where your LLM call is needed
        to interpret the company's role, product, architecture)
      - Emit company_scope_verdict ∈ [OVERLAP_CONFIRMED, OVERLAP_NOT_TRIGGERED,
        SCOPE_DISJOINT, INDETERMINATE]
   d. For each pair where layer0_relationship is "SAME" or "COMPLEMENTARY"
      or "CONTRADICTORY" or "SCOPE_DISJOINT":
      - DO NOT re-classify
      - Emit company_scope_verdict deterministically based on activation_predicate:
        - if predicate requires scope overlap and same_party → OVERLAP_CONFIRMED
        - if predicate requires scope overlap but different parties → SCOPE_DISJOINT
        - if predicate is met → OVERLAP_CONFIRMED
        - else → OVERLAP_NOT_TRIGGERED

2. For the WHOLE domain:
   - total_sub_domains (from sub_domain_ids)
   - active_sub_domains (count where applicable == true)
   - pairwise_relationships (count of all pairs across all sub-domains in domain)

3. Emit ONE row per sub_domain_id with:
   - sub_domain_id
   - applicable (boolean)
   - scope_overlap (Y | CONDITIONAL | N) — Y if ANY pair is OVERLAP_CONFIRMED
   - applicable_regulations (list)
   - verified_relationship_per_pair[] (one per reg pair)
   - layer0_refs (mandatory: at least SubDomains/D-XX.Y.md + relevant CrossRegulation/DeepAnalysis/)

CRITICAL RULES:
- You are ACTIVATING Regulatory Baseline CONDITIONAL entries, NOT classifying.
- layer0_relationship for SAME/COMPLEMENTARY/CONTRADICTORY/SCOPE_DISJOINT
  is READ-ONLY. Do NOT change it.
- If you cannot determine, return INDETERMINATE.
</task>
```

## Output Schema

Reference: [`./output_schemas.yaml#P1C-LLM-01`](output_schemas.yaml#P1C-LLM-01)

Top-level fields:
- `prompt_spec_id`: "P1C-LLM-01-OVERLAP-CLASSIFICATION"
- `invocation_pattern`: "per_domain_lane"
- `lane_id`: "D-XX"
- `domain_id`: "D-XX"
- `domain_overlap_analysis`: {total_sub_domains, active_sub_domains, pairwise_relationships}
- `sub_domain_activations[]`: ONE entry per sub-domain
- `status`, `confidence`

## Quality Criteria

- [ ] Every `sub_domain_activations` row has `layer0_refs[]` ≥1 entry pointing to a real file
- [ ] Every `verified_relationship_per_pair` matches the Regulatory Baseline source
- [ ] No re-classification: SAME/COMPLEMENTARY/CONTRADICTORY/SCOPE_DISJOINT preserved verbatim from Regulatory Baseline
- [ ] CONDITIONAL pairs always produce a `company_scope_verdict` (no SKIP)
- [ ] INDETERMINATE returned when predicates require missing facts
- [ ] Total sub_domain count matches `sub_domain_ids` input

## Model Configuration

```yaml
model: MiniMax-M2.7
temperature: 0.0
max_tokens: 4096
# Sub-domain row is bounded, but with 38 sub-domains × N pairs,
# output can grow. 4096 is safe for HIGH tier with 5 regulations.
```

## Per-domain Annotations

This prompt is enriched by `annotations/D-XX.yaml`. Example usage:

```yaml
# From annotations/D-04.yaml (Incident Response)
domain_specific_instructions: |
  D-04 Incident Response has the HIGHEST cross-regulation tension potential.
  Pay special attention to:
  - GDPR 72h vs CRA 24h vs NIS 2 24h vs DORA 24h notification timelines
  - Same-actor vs different-actor obligations (controller vs manufacturer)
  - Regulator-specific routing (DPA, MSA, CSIRT, national CA, ESA)
```

## Few-shot Example

See [`./examples/overlap_same_party.yaml`](examples/overlap_same_party.yaml)

## Post-generation Validation

1. JSON Schema validation against `output_schemas.yaml#P1C-LLM-01`
2. Re-classification check: extract `verified_relationship` from Regulatory Baseline source; compare to LLM output. If different → INSUFFICIENT_EVIDENCE.
3. Pair completeness: every applicable (reg_A, reg_B) pair from Regulatory Baseline must appear in output
4. Citation existence: every `layer0_refs[]` file exists
5. Sync check: if another lane (D-YY) produced a different verdict for the same (sub_domain, reg_A, reg_B) → flag for INDETERMINATE (Phase 2 / human review)

## Cross-references

- **Diagram:** [`../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md`](../../diagrams/fluxdiagram/phase1/phase1c_consolidation.md)
- **Reference:** [`../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md`](../../diagrams/fluxdiagram/phase1/phase1c_synthesis_reference.md) §1
- **Lanes architecture:** [`../../diagrams/fluxdiagram/phase1/subdomain_lanes.md`](../../diagrams/fluxdiagram/phase1/subdomain_lanes.md)
- **Base system prompt:** [`./base_system_prompt.md`](base_system_prompt.md)
- **Schema:** [`./output_schemas.yaml`](output_schemas.yaml#P1C-LLM-01)

---

## Change log

- v1.0.0 (2026-07-13): Initial canonical release. Replaces legacy LLM-E with per-domain-lane activation pattern. **NO re-classification** invariant enforced.