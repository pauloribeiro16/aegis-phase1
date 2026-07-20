# NIST CSF 2.0 — The Only Control Framework in This Solution

**Status:** CANONICAL
**Authority:** AEGIS-P1-CORR-028 (2026-07-20)
**Applies to:** AEGIS-KG Phase 1 (and all downstream phases that inherit Phase 1 control mappings)
**Source of truth:** `preproc_out/global/NIST_CSF_2.0_subcategories.json` (NIST CSWP 29, 2024-02-26; xlsx-derived)

---

## 1. Policy statement

This solution uses **NIST CSF 2.0 (CSWP 29, 2024-02-26) as the SOLE and EXCLUSIVE control framework** for the cybersecurity controls that flow through it. No other control framework is used as a source of control identifiers, control families, or control mappings.

| Layer | What is used | What is not used |
|---|---|---|
| **Control identifiers (canonical list)** | The 106 active subcategories of NIST CSF 2.0 (6 Functions, 22 Categories) | ISO 27001 Annex A controls, NIST 800-53 control families, OWASP ASVS/Top 10, COBIT, CSF 1.1, etc. |
| **Control titles & descriptions** | NIST CSF 2.0 verbatim | Re-naming or paraphrasing from other frameworks |
| **Mappings (regulation → control)** | GDPR/NIS2/CRA/DORA/AI Act → NIST CSF 2.0 subcategories | Mapping through ISO 27001 or any intermediary framework |
| **Implementation examples** | NIST CSF 2.0's own `implementation_examples` (xlsx-derived) — kept as metadata, **not** used as authoritative guidance | OWASP, SANS, vendor-specific guidance as control framework |
| **Informative references** | NIST CSF 2.0's own `informative_references` (xlsx-derived) — kept as metadata for traceability to source standards | Treated as "control framework in use" |

## 2. What is NOT a control framework (and why they appear in the project)

The following frameworks are referenced in the project for reasons OTHER than as control frameworks. They are **explicitly out of scope** for control identification in Phase 1.

| Reference | Where it appears | Why it's allowed |
|---|---|---|
| **SOC 2 Type II / ISO 27001 certificate** | `src/aegis_phase1/v2/output/doc_04*.py`, `src/aegis_phase1/prompts_v2/track_b.py` | **Vendor attestation pattern**, NOT a control framework. Used to ask cloud/SaaS suppliers to evidence their security posture; the framework IN THIS SOLUTION remains CSF 2.0. Each reference is annotated with `# attestation pattern, NOT control framework (per NIST_CSF_2.0_ONLY.md C5)`. |
| **OWASP Top 10 / ASVS** | `src/aegis_phase1/v2/output/doc_04b.py`, `doc_04d.py` | **Implementation guidance**, NOT a control framework. Referenced for the secure-development practice; the controls themselves (e.g. PR.PS-06 Secure software development practices are integrated) are CSF 2.0. Each reference is annotated. |
| **NIST SP 800-53, SP 800-37, NICE Framework, CCM v4.0, etc.** | `preproc_out/entities/csfs/*.json` — `reference_families` field | **Informative references** (NIST's own metadata, xlsx-derived). Kept as traceability — the project does NOT use these as a control framework. Listed for audit, not for selection. |
| **CSF v1.1** | `archive/csf_v11_v20_mapping/` (snapshot) | **Archived lineage** (CORR-027 captured the v1.1→v2.0 transition). NOT used in any active path. |
| **ISO 27001, NIST 800-53, OWASP, NIST SSDF** | `methodology-00/REFERENCE/related_frameworks.md` | Listed as **"Out of Phase 1 scope"** — reserved for Phase 2/3 expansion. |

## 3. How to verify

Run these checks to confirm the policy is in force:

```bash
# 1. The canonical CSF 2.0 catalogue exists with exactly 106 active subcategories and 22 active categories
python -c "import json; d=json.load(open('preproc_out/global/NIST_CSF_2.0_subcategories.json')); print('cats:', len(d['categories']), 'subs:', len(d['subcategories']))"
# Expected: cats: 22 subs: 106

# 2. No sub-domain uses a control identifier outside the 106
python -m scripts.preprocess.audit_csf_mapping
# Expected: verdict_counts.BROKEN == 0

# 3. The frozen-list CI gate (parity between .md and JSON)
bash .hooks/ci-csf-frozen-list.sh
# Expected: OK: 106 CSF 2.0 subcategories in parity

# 4. The frameworks policy CI gate (no unannotated framework reference)
bash .hooks/ci-frameworks.sh
# Expected: exit 0
```

## 4. Known gaps (forward-looking)

This contract does **NOT** address the following gaps. They are tracked for future contracts:

| Gap | Deferred to | Why deferred |
|---|---|---|
| **50 of 106 CSF 2.0 subcategories are not mapped to any of the 38 AEGIS sub-domains** (reverse index incomplete) | **CORR-029** (LLM-assisted mapping) | User decision (2026-07-20): "Para já não quero fazer isto, esquece o mapeamento para já". Will be tackled when Phase 1B coverage needs to expand beyond the current 56/106. |
| **D-05.2 and D-05.4 have `csf_hint` with 0 active control IDs after the CORR-028 cleanup** (their only ID was `PR.DS-12`, now removed) | **CORR-029** | Same — covered by the broader reverse-index expansion. |
| **Phase 2/3 integration of ISO 27001, NIST 800-53, OWASP, NIST SSDF as separate control frameworks** | **Phase 2/3** | Per `methodology-00/REFERENCE/related_frameworks.md`: "Out of Phase 1 scope". |

## 5. Editing policy

Adding a new control framework is **forbidden** without an explicit contract change. If a downstream requirement emerges (e.g. a customer requires ISO 27001 alignment):

1. Open a new contract (e.g. `AEGIS-P1-CORR-030` for ISO 27001 integration).
2. Document the new framework as a parallel universe — do NOT replace CSF 2.0.
3. Provide a deterministic cross-walk between the two frameworks.
4. Update this file (§1) to list the new framework as a **secondary** control framework, with CSF 2.0 remaining **primary**.

## 6. See also

- `execution/CONTRACT-028.md` — the contract that established this policy
- `execution/CONTRACT-027.md` — predecessor (CSF 1.1 → 2.0 lineage; now archived)
- `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md` — human-readable frozen list (sub-agent reference)
- `preproc_out/global/NIST_CSF_2.0_subcategories.json` — machine-readable catalogue (script reference)
- `archive/csf_v11_v20_mapping/` — archived v1.1 → v2.0 mapping
- `AGENTS.md` § Framework policy (cross-reference)
