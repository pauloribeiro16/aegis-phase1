---
document_id: AEGIS-VALIDATION-CORR-072
title: CORR-072 Validation Report (case 3 / OmniBank)
generated_at: "2026-07-28T15:52:37Z"
case_study: OmniBank Financial Systems S.A.
output_dir: /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1/output/case3/20260728-155237
elapsed_s: 0.85
---
# CORR-072 Validation Report

End-to-end validation of the 5 bug fixes landed in CORR-072. The 6 documents (04, 04a, 04b, 04c, 04d, 05) are rendered with case 3 (OmniBank) real YAML state, MOCK_LLM=1 (deterministic narrative fallback), and grepped for the bug patterns the fix intended to remove.

## Files Rendered

| Filename | Lines | Path |
| --- | ---: | --- |
| `04_Company_Context_Assessment.md` | 220 | `output/case3/20260728-155237/04_Company_Context_Assessment.md` |
| `04a_Architecture_DataInventory.md` | 153 | `output/case3/20260728-155237/04a_Architecture_DataInventory.md` |
| `04b_Security_Posture.md` | 316 | `output/case3/20260728-155237/04b_Security_Posture.md` |
| `04c_ThirdParty_Landscape.md` | 330 | `output/case3/20260728-155237/04c_ThirdParty_Landscape.md` |
| `04d_Org_Roles_RACI.md` | 322 | `output/case3/20260728-155237/04d_Org_Roles_RACI.md` |
| `05_Regulatory_Applicability.md` | 160 | `output/case3/20260728-155237/05_Regulatory_Applicability.md` |

## Fix Results

| # | Fix | Status | Evidence |
| ---: | --- | :---: | --- |
| 1 | stakeholder leakage (Doc 04 §3.1) | ✅ PASS | `Doc 04: 0 TinyTask/tinytask.pt lines (expect 0), 4 OmniBank lines (expect >=1), ` |
| 2 | regulation-level applicability (Doc 04d §3) | ✅ PASS | `Doc 04d §3 rows: NIS2 YES=1 NO=0; DORA YES=1 NO=0; AI_Act YES=1 NO=0 (expect YES` |
| 3 | duplicate section header (Doc 04a §1) | ✅ PASS | `Doc 04a: ## 1. Technical Architecture appears 1 times (expect exactly 1); ### 1.` |
| 4 | active_subdomains fallback (Doc 04b/04c/04d frontmatter) | ✅ PASS | `Frontmatter active_subdomains values (expect 38, the 38 subdomains from preproc_` |
| 5 | regression test (tests/unit/v2/output/test_doc_04_stakeholder_leakage.py) | ✅ PASS | `============================= test session starts ==============================` |

## Detailed Evidence

### Fix #1 — stakeholder leakage (Doc 04 §3.1) — ✅ PASS

```
  Doc 04: 0 TinyTask/tinytask.pt lines (expect 0), 4 OmniBank lines (expect >=1), 14 stakeholder rows (expect 7+)
```

### Fix #2 — regulation-level applicability (Doc 04d §3) — ✅ PASS

```
  Doc 04d §3 rows: NIS2 YES=1 NO=0; DORA YES=1 NO=0; AI_Act YES=1 NO=0 (expect YES>=1 / NO=0 for all three)
```

### Fix #3 — duplicate section header (Doc 04a §1) — ✅ PASS

```
  Doc 04a: ## 1. Technical Architecture appears 1 times (expect exactly 1); ### 1.2 Network Topology appears 1 times (expect exactly 1)
```

### Fix #4 — active_subdomains fallback (Doc 04b/04c/04d frontmatter) — ✅ PASS

```
  Frontmatter active_subdomains values (expect 38, the 38 subdomains from preproc_out):
    04b_Security_Posture.md: got 38, expected 38
    04c_ThirdParty_Landscape.md: got 38, expected 38
    04d_Org_Roles_RACI.md: got 38, expected 38
```

### Fix #5 — regression test (tests/unit/v2/output/test_doc_04_stakeholder_leakage.py) — ✅ PASS

```
  ============================= test session starts ==============================
  collecting ... collected 7 items
  
  tests/unit/v2/output/test_doc_04_stakeholder_leakage.py::test_omnibank_stakeholder_does_not_inherit_organisation PASSED [ 14%]
  tests/unit/v2/output/test_doc_04_stakeholder_leakage.py::test_omnibank_stakeholder_does_not_inherit_contact PASSED [ 28%]
  tests/unit/v2/output/test_doc_04_stakeholder_leakage.py::test_omnibank_stakeholder_does_not_inherit_responsibilities PASSED [ 42%]
  tests/unit/v2/output/test_doc_04_stakeholder_leakage.py::test_influence_inheritance_still_works PASSED [ 57%]
  tests/unit/v2/output/test_doc_04_stakeholder_leakage.py::test_tinytask_stakeholder_unchanged PASSED [ 71%]
  tests/unit/v2/output/test_doc_04_stakeholder_leakage.py::test_stakeholders_state_drives_no_tinytask_fallback PASSED [ 85%]
  tests/unit/v2/output/test_doc_04_stakeholder_leakage.py::test_section_3_stakeholder_register_no_tinytask_leak_in_render PASSED [100%]
  
  ============================== 7 passed in 0.03s ===============================
```

## Notes

- **Mock LLM behaviour:** P1B-LLM-01 / P1B-LLM-02 / P1C-LLM-01..03 are not invoked (MOCK_LLM=1). All narrative sections (Doc 04a §1 / §1.2; Doc 04b §3 Notes; Doc 04c §5.1; Doc 04d §5 / §9; Doc 05 §6.1 / §6.1b) render as PENDING REVIEW markers. This is expected and unrelated to the CORR-072 fixes.
- **Case 3 architecture YAMLs are empty placeholders** (`stores: []`, `services: []`); the §3 Compliance Mapping in Doc 04a shows ("_")-style rows where stores/flows are absent. This matches the pre-CORR-072 baseline behaviour.
- **Bug #4 fallback:** `state["subdomains"]` is populated with all 38 subdomains from `preproc_out/`; the fixed fallback in doc_04b/doc_04c/doc_04d `_active_subdomain_count` correctly reports 38.
