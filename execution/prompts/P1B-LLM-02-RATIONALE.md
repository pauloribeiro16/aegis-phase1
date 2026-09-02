---
prompt_spec_id: P1B-LLM-02-RATIONALE
prompt_spec_version: 1.0.0
legacy_aliases:
  - "LLM-B (merged)"
  - "LLM-C (merged)"
  - "LLM-D (merged)"
  - "Phase 1B per-regulation synthesis (rationale + implications + gaps)"
phase: 1
sub_phase: 1B
semantic_task: per_regulation_synthesis_merged
invocation_pattern: per_regulation
author: AEGIS Methodology maintainer
status: ACTIVE
created: 2026-07-13
updated: 2026-07-13
related_documents:
  - ./base_system_prompt.md
  - ./output_schemas.yaml#P1B-LLM-02
  - ./examples/strategic_synthesis_3_lane.yaml
  - ../../../PHASE1_STRATEGY.md
  - ../../../REGULATORY_BASELINE.md
  - ../../../PREPROCESSING/SubDomains/index.md
  - ../../diagrams/fluxdiagram/phase1/phase1b_regulatory_mapping.md
  - ../../diagrams/fluxdiagram/phase1/phase1b_nuances_and_reasoning.md
---

# P1B-LLM-02-RATIONALE

> **Per-regulation synthesis (rationale + implications + gaps merged).**
> Invocation: 1 call per `applicable_reg`. Replaces legacy LLM-B + LLM-C + LLM-D (single-call consolidation).

---

## Why a single call?

The legacy 8-LLM Phase 1 design had 4 LLMs per regulation (rationale + implications + gaps) consuming the same inputs. This caused:
- Token waste: ~75% context duplication across 3 calls
- Cross-section inconsistency: rationale contradicts implications
- High latency: 3 sequential calls per regulation

P1B-LLM-02 consolidates into **one structured-output call** with all 3 sections.

## When to invoke

After `P1B-LLM-01-INTERPRETATION` has completed for the same regulation (so `interpretations[]` and `derogations[]` are available as inputs).

## Inputs

```yaml
case_id: "Case_XX"
lane_id: "REG"
applicable_regs: [REG]
classification:                   # from Phase 1B Step 3
  role: "Controller"
  tier: "LOW"
  classification_basis: "Doc 04 §5"
p1b_llm_01_output:                 # from P1B-LLM-01-INTERPRETATION
  interpretations: [...]
  derogations: [...]
company_facts:                     # from Doc 04 (04a-04d)
  architecture_ref: "DOC04:ARCH-07"
  data_categories: [...]
  products: [...]
  role_obligations: [...]
layer0_subdomain_refs:             # sub-domains activated by this regulation
  - "SubDomains/D-01.1.md"
coverage_matrix_row:               # from Filter 2 (Doc 06 row for this regulation)
  sub_domains_covered: [D-01.1, D-04.3]
  sub_domains_partial: []
  sub_domains_not_addressed: []
```

## Task (verbatim, use as user message)

```
<task>
For the regulation {REG} and the company's classification:

1. RATIONALE (2-3 paragraphs, 200-2000 chars):
   Explain WHY this regulation applies to THIS specific company.
   Reference:
   - Company facts from Doc 04 (architecture, data categories, products, role)
   - Specific regulatory articles (cited from Regulatory Baseline, NOT invented)
   - Applicable interpretations and derogations from P1B-LLM-01 output
   - How company architecture makes the regulation binding

   AVOID:
   - Generic boilerplate ("GDPR applies because the company processes data")
   - Invented article numbers
   - Unverifiable statistical claims

2. IMPLICATIONS (1-5 structured items):
   For each activated sub-domain (from layer0_subdomain_refs), describe:
   - id: "IMP-D-XX.Y-N"
   - description: what this regulation requires for THIS company
   - effort_estimate: pick from enum based on Doc 04 + tier
   - dependencies: list of other sub-domain implications that block this one
   - layer0_refs: which SubDomains/ files support this
   - company_fact_refs: which Doc 04 sections

   EFFORT ESTIMATE MUST BE TIERS-AWARE:
   - LOW (8 emp): hours to days
   - MEDIUM (50 emp): weeks
   - HIGH (5000+ emp): months to FTE-quarters

3. GAPS (0-N structured items):
   Identify sub-domains NOT covered by this regulation (or only partially).
   For each gap:
   - gap_id: "GAP-D-XX.Y"
   - sub_domain_id: D-XX.Y
   - coverage_level: NOT_ADDRESSED | PARTIAL
   - risk_description: 1-2 sentences (use Regulatory Baseline Considerations)
   - covered_by_other_reg: [list of other applicable regs that cover this]
   - recommendation: tier-proportional (LOW: document and accept; MEDIUM: address if high risk; HIGH: address all)
   - priority: P1 | P2 | P3
   - layer0_refs

If you cannot determine applicability, return INSUFFICIENT_EVIDENCE.
</task>
```

## Output Schema

Reference: [`./output_schemas.yaml#P1B-LLM-02`](output_schemas.yaml#P1B-LLM-02)

Top-level fields:
- `prompt_spec_id`: "P1B-LLM-02-RATIONALE"
- `invocation_pattern`: "per_regulation"
- `lane_id`: "{REG}"
- `synthesis.rationale`: 200-2000 chars (tier-aware length)
- `synthesis.implications[]`: 1-5 structured items
- `synthesis.gaps[]`: 0-N structured items
- `status`, `confidence`

## Quality Criteria

- [ ] Rationale references ≥2 specific Doc 04 facts and ≥1 regulatory article
- [ ] Rationale is NOT generic boilerplate (must fail if any sentence could apply to any company)
- [ ] Implications cite Regulatory Baseline sub-domain file for every entry
- [ ] Effort estimate is tier-appropriate (low for MICRO, high for MAX)
- [ ] Gaps distinguish NOT_ADDRESSED vs PARTIAL
- [ ] Gap recommendation is tier-proportional
- [ ] No invented statistics ("40% effort reduction" without basis)

## Model Configuration

```yaml
model: MiniMax-M2.7
temperature: 0.0
max_tokens: 4096   # higher than P1B-LLM-01 due to 3-section output
```

## Post-generation Validation

1. JSON Schema validation
2. Rationale length within tier bounds:
   - LOW: 200-800 chars
   - MEDIUM: 400-1500 chars
   - HIGH: 600-2000 chars
3. Boilerplate detection: if ≥30% of rationale sentences could apply to any company, return INDETERMINATE
4. Implications cite Regulatory Baseline: every `layer0_refs[]` resolves to existing file
5. Effort estimate tier consistency: cross-check against `company.tier`

## Cross-references

- **Diagram:** [`../../diagrams/fluxdiagram/phase1/phase1b_regulatory_mapping.md`](../../diagrams/fluxdiagram/phase1/phase1b_regulatory_mapping.md)
- **Reference:** [`../../diagrams/fluxdiagram/phase1/phase1b_nuances_and_reasoning.md`](../../diagrams/fluxdiagram/phase1/phase1b_nuances_and_reasoning.md)
- **Upstream:** [`./P1B-LLM-01-INTERPRETATION.md`](P1B-LLM-01-INTERPRETATION.md) (provides interpretations + derogations)
- **Base system prompt:** [`./base_system_prompt.md`](base_system_prompt.md)
- **Schema:** [`./output_schemas.yaml`](output_schemas.yaml#P1B-LLM-02)

---

## Change log

- v1.0.0 (2026-07-13): Initial canonical release. Merges legacy LLM-B + LLM-C + LLM-D into single-call synthesis.