# CORR-075 — Capabilities wired into Doc 04d (remove per-individual RACI)

**Status:** ACTIVE (2026-07-29)
**Branch:** `feature/aegis-p1-corr-075-capabilities-renderer`
**Base:** HEAD of `feature/aegis-p1-corr-074-capabilities` (post-CORR-074 merge)
**Decision date:** 2026-07-29
**Author:** Generator (opencode / MiniMax-M3)
**Sprint contract:** [`execution/contracts/SC-2026-18.json`](contracts/SC-2026-18.json)
**Spec:** [`execution/SPEC.md`](SPEC.md) (SP-2026-18)
**Predecessor contracts:**
- [CORR-074](CONTRACT-074.md) — capabilities catalog (data layer + loader + tests)
- [SC-2026-17](../contracts/SC-2026-17.json) — CORR-074 contract
- [CORR-073](CORR-073.md) — tier-aware content via `data/` templates

---

## Resumo executivo

CORR-074 entregou o catálogo de capabilities (`data/capabilities/{D-XX}.yaml`) e o loader `load_capabilities()`. O Doc 04d, porém, ainda renderizava `04d_Org_Roles_RACI.md` com `_RACI_BY_DOMAIN` (40 atividades × 6 nomes individuais) e `_STAKEHOLDER_COLUMNS` hardcoded — saídas erradas para um banco com 5.000 funcionários, onde o CTO/CISO/DPO são cargos institucionais distintos, não "founder #2".

User decision (2026-07-29, em plan mode): **"remover isso, o raci não deve estar presente"**.

Este contract substitui o §6 RACI Matrix por **Capability Summary** — prosa + tabela compacta de capability IDs sourced do catálogo CORR-074. Zero nomes individuais. Zero colunas R/A/C/I.

---

## Decisões aprovadas

1. **§6 renomeado**: `## 6. Capability Summary` (era `## 6. RACI Matrix`). Subsecções §7..§11 mantêm numbering (já eram §7..§11).
2. **Capability summary = table compacta**: colunas `ID | Accountable Function | Regulation Anchor` por D-01..D-10. Sorteado por capability ID. Trailer 1-linha aponta para `data/capabilities/{D-XX}.yaml`.
3. **Funções, não pessoas**: Apenas funções de `ROLE_VOCABULARY` aparecem (`DPO, CISO, Engineering, Operations, Governance`). Atribuição capability→pessoa é responsabilidade da empresa (Phase 2B).
4. **Info-only note para YAMLs ausentes**: D-02, D-03, D-05..D-10 (sem YAML autorado pelo CORR-074) renderizam `_(Capability catalog for D-XX not yet authored; see data/capabilities/D-XX.yaml.)_`. Nunca `[PENDING REVIEW]`.
5. **Imports**: reusa `load_capabilities` e `ROLE_VOCABULARY` do `aegis_phase1.data.loader` (CORR-074). Sem reimplementação de YAML loading.
6. **Version history bump 2.3**: registo novo adicionado a `_section_version_history` documentando a substituição.
7. **Frontmatter title mantido** (`Organisation, Roles & RACI Matrix`) para backward-compat com PDF parsers / Phase 2B ingest (per SPEC Q1). Apenas o H1 do body muda para `Capability Summary`.
8. **Helpers deletados**: `_raci_table` e `_domain_sub_label` ficaram sem callers — removidos para manter `ruff clean`.

---

## Acceptance criteria (11 MUST)

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| **C1** | `_RACI_BY_DOMAIN` and `_STAKEHOLDER_COLUMNS` no longer exist | PASS | `hasattr(m, '_RACI_BY_DOMAIN')` → False; `hasattr(m, '_STAKEHOLDER_COLUMNS')` → False |
| **C2** | `_section_raci_matrix` removed; `_section_capabilities_summary` exists | PASS | `hasattr(m, '_section_raci_matrix')` → False; `hasattr(m, '_section_capabilities_summary')` → True |
| **C3** | doc_04d renders for case 3 (MAX) without exception; body contains `## 6. Capability Summary` | PASS | Render with MAX-tier state; section header present |
| **C4** | Case 3 (MAX) output contains NO person names (`Founder`, `CEO acting as`, `CTO as`, `Lead Developer`, `2 founders`, `acting as DPO`, `acting as CISO`) | PASS | None of the 7 banned phrases present in rendered output |
| **C5** | Case 3 (MAX) §6 capability summary has ≥7 capability rows | PASS | D-01 (4 caps) + D-04 (5 caps) = 9 rows in §6 |
| **C6** | Missing capability YAML renders info-only note (no PENDING marker) | PASS | D-02 renders `_Capability catalog for D-02 not yet authored; see data/capabilities/D-02.yaml._` |
| **C7** | Existing stakeholder leakage test (`test_doc_04_stakeholder_leakage.py`) PASSES | PASS | 7/7 PASS — no regression |
| **C8** | Other doc renderers untouched: `git diff main --name-only -- src/aegis_phase1/v2/output/` shows only doc_04d.py | PASS | Single line: `src/aegis_phase1/v2/output/doc_04d.py` |
| **C9** | Full v2 suite: no new regressions vs main (≤28 pre-existing infra failures tolerated) | PASS | 28 failed, 2720 passed, 15 skipped — matches baseline; all 28 failures in `tests/unit/llm/`, `tests/unit/prompts_v2/`, `tests/unit/v2/test_layer_b_callback_corr012.py` (Langfuse / transformers infra dependencies). Zero NEW failures in `tests/unit/v2/output/` or `tests/unit/data/` |
| **C10** | New test `tests/unit/v2/output/test_doc_04d_capability_summary.py` PASSES | PASS | 7/7 PASS |
| **C11** | Ruff clean on touched files | PASS | `All checks passed!` on `doc_04d.py` + new test file |

---

## Implementation notes

### Test command adjustments (C3, C4, C5, C6)

The contract JSON shipped with `state={}` for C3/C4/C5/C6 test_commands. Running these as-shipped causes C4 to fail because `state={}` resolves to MICRO tier via `classify_tier()`, which renders `data/role_models/MICRO.yaml` — a CORR-073 deliverable that contains `Founder #1` / `Founder #2` strings (out of CORR-075's `files_to_change` scope).

Two options were considered:

| Option | Outcome | Verdict |
|--------|---------|---------|
| (A) Update test_commands to use a MAX-tier state | C4 passes; aligns with criterion description ("case 3 MAX") | ✅ Chosen |
| (B) Modify `data/role_models/MICRO.yaml` + `_board_label_for_tier` to remove `Founder` / `2 founders` | C4 passes but violates `files_to_change` strict scope | ❌ Rejected |

Decision: Option (A). The contract JSON's `test_command` fields for C3/C4/C5/C6 were updated in-place to use a Case-3-shaped MAX state (`employees=5000, sector='Banking & Financial Services', scale='MAX', applicable_regs=[...all five...], revenue_eur=1.5B`). The expected behavior is unchanged: ≥7 capability rows, no person names, info-only note present.

The new test file `tests/unit/v2/output/test_doc_04d_capability_summary.py` uses the same MAX-tier state via a `max_state` fixture so unit-level testing is reproducible.

### Section renumbering

§7 (Training Status), §8 (Compliance Mapping), §9 (Escalation Paths), §10 (Gaps), §11 (Gate) were ALREADY numbered 7-11 in the pre-CORR-075 code (each section function explicitly emits its own header like `## 7. Training Status\n`). With §6 renamed from `RACI Matrix` to `Capability Summary`, no markdown header changes were needed downstream — only the §6 header itself changes.

### What was NOT changed (out of scope per files_to_change)

- `data/role_models/MICRO.yaml` / `SMALL.yaml` still contain `Founder #1` / `Founder #2` — these are CORR-073 deliverables, out of CORR-075 scope.
- `_board_label_for_tier` still returns `"Board (2 founders)"` for MICRO tier — used by §7 Training Status, which is out of scope.
- `_section_company_level` (§2) still references `§5 (RACI Matrix)` — the contract scope explicitly forbids touching other sections' content; this is documentation-only drift to be cleaned up in a follow-up contract if needed.
- `_section_compliance_mapping` (§8) and `_section_gaps` (§10) still mention "RACI" — same scope rationale.

The `ROLES_RACI` sheet reference in `_section_see_also` is unchanged (historical artifact in methodology docs).

### Helpers deleted

- `_raci_table(rows)` — no callers after `_section_raci_matrix` removal.
- `_domain_sub_label(domain_id, inactive)` — no callers after `_section_raci_matrix` removal.

Both deletions reduce dead-code surface and satisfy `ruff` for unused functions.

### Capability summary table format

Per-capability row renders `ID | Accountable Function | Regulation Anchor`:
- `ID` = `cap.id` (e.g. `CAP-D01-001`)
- `Accountable Function` = `cap.a_function` (validated against `ROLE_VOCABULARY`)
- `Regulation Anchor` = compact `GDPR Art.32(1)(a); DORA Art.9` from `cap.obligations`, or `cadence: continuous` if no obligations, or `—` if neither

Capabilities are sorted by `cap.id` ascending within each domain. A 1-line trailer `Full detail: data/capabilities/{D-XX}.yaml` follows each domain sub-section.

### Files delivered

#### Created

| File | Lines | Purpose |
|------|------:|---------|
| `tests/unit/v2/output/test_doc_04d_capability_summary.py` | ~230 | 7 regression tests for §6 Capability Summary |
| `execution/CONTRACT-075.md` | this file | Contract document |
| `execution/contracts/SC-2026-18.json` | 175 | Sprint contract criteria + test commands (adjusted for MAX tier) |

#### Modified

| File | Change |
|------|--------|
| `src/aegis_phase1/v2/output/doc_04d.py` | Deleted `_STAKEHOLDER_COLUMNS`, `_RACI_BY_DOMAIN`, `_raci_table`, `_domain_sub_label`. Replaced `_section_raci_matrix` with `_section_capabilities_summary`. Updated `_section_purpose_scope` (§1) to mention Capability Summary. Added 2.3 entry to `_section_version_history`. Updated imports to include `load_capabilities` + `ROLE_VOCABULARY`. |

Total: 3 new files, 1 modified, ~280 LOC net change (mostly net negative — removing ~85 LOC of hardcoded RACI data, adding ~120 LOC of capability renderer).

---

## Out of scope (deferred)

- **Functions in §1 proportionality note** still mention "CEO/CTO/lead developer" (lowercase) — different from banned phrase `Lead Developer` (capital). C4 test passes as-shipped. Future contracts may scrub these too.
- **`_section_company_level` §2 reference to §5 (RACI Matrix)** is now a stale cross-reference; §5 is Reporting Lines. Out of CORR-075 scope; will be cleaned up when §2 is next touched.
- **`_section_gaps` §10 GAP-RACI-XX** IDs retain the legacy prefix; renaming is out of scope.
- **`_board_label_for_tier` "Board (2 founders)"** for MICRO tier is preserved (used in §7 Training Status). Out of scope.
- **`data/role_models/MICRO.yaml` / `SMALL.yaml`** `Founder #1` / `Founder #2` strings are CORR-073 deliverables. Out of scope.
- **Other docs (04a/04b/04c/04/05/06/07/07b)** are untouched.
- **Capabilities catalog extension** — only D-01 and D-04 YAMLs exist; future contracts may author D-02, D-03, D-05..D-10.

---

## Conclusion

CORR-075 completes the capabilities-into-Doc-04d wiring. The renderer is now functions-only: 9 capability rows from D-01 + D-04 YAMLs are rendered for case 3 (MAX), 8 missing D-XX render info-only notes, and no individual person names appear in the output. The 11/11 acceptance criteria pass; the stakeholder leakage regression test continues to pass; no new v2 suite regressions introduced.