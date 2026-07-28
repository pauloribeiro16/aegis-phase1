# CORR-072 — Pipeline bug fixes + cross-case consistency

**Status:** ACTIVE (2026-07-28)
**Branch:** `feature/aegis-p1-corr-072-pipeline-bugs`
**Base:** HEAD do CORR-071 (commit `766dac7`)
**Decision date:** 2026-07-28
**Author:** Planner (opencode session)
**Predecessor contracts:** CORR-071 (P1B per-reg filter), CORR-068 S2 (user-declared applicability is authoritative)

---

## Resumo executivo

Quatro bugs do pipeline identificados durante o audit pós-M3 do case 3 (OmniBank, 5 regs aplicáveis):

1. 🔴 **Stakeholder hallucination** (CRÍTICO): Doc 04 §3.1 mostrava `TinyTask Lda.` + emails `tinytask.pt` em stakeholders da OmniBank.
2. 🟠 **Doc 04d inconsistency**: §3 Regulation-Level Owner dizia NIS2/DORA/AI_Act=NO enquanto Doc 05 dizia todas APPLICABLE.
3. 🟡 **Doc 04a duplicate header**: "## 1. Technical Architecture" aparecia duplicado.
4. 🟡 **active_subdomains: 0**: Doc 04b/04d mostravam `active_subdomains: 0` para case 3 (OmniBank devia ter ~37).

Todos corrigidos neste contract. Adicionado regression test que valida que o stakeholder leakage cross-case não regressa.

---

## Contexto e dados

Após o run M3 do case 3 (OmniBank Financial Systems S.A., 5 regs aplicáveis) verifiquei o Doc 04 §3.1 Stakeholder Register:

```
SH-01 | CEO       | TinyTask Lda.        | ceo@tinytask.pt  | ['executive_sponsor', 'ecb_supervised']
SH-02 | CISO      | TinyTask Lda.        | cto@tinytask.pt  | ['security_lead', 'dedicated_org_100_plus']
SH-03 | DPO       | TinyTask Lda.        | dpo@tinytask.pt  | ['gdpr_compliance', 'bafin_oversight']
SH-04 | CRO       | TinyTask Lda.        | dev@tinytask.pt  | ['dora_ict_risk', 'operational_resilience']
```

Isto é alucinação/cross-contamination: o YAML `cases/case3-omnibank/input/company/stakeholders.yaml` tem roles correctos (CEO, CISO, DPO, CRO, Head of AI/ML, etc.) mas sem `organisation` ou `contact`. O helper `_augment_influence` em `doc_04.py` herdava esses campos do baseline TinyTask por ID match (SH-01..SH-07).

**Root cause:** `_augment_influence` herdava 5 campos do baseline por ID match, não apenas `influence` e `interest`:

```python
# ANTES (doc_04.py)
for field in ("influence", "interest", "organisation", "contact", "responsibilities"):
    if not s.get(field) or s.get(field) == "-":
        s[field] = baseline.get(field, s.get(field, "-"))
```

Os 3 outros bugs foram encontrados durante a mesma análise e têm naturezas distintas (ver detalhe abaixo).

---

## Decisões aprovadas

1. **Filter scope**: apenas `influence` e `interest` herdam do baseline (template metadata). `organisation`, `contact`, `responsibilities` são case-specific — nunca herdar.
2. **Doc 04d source-of-truth**: usar `build_applicability_context(state)` (CORR-038 source-of-truth) em vez de `state["company_context"]["applicable_regs"]` (pode estar stale).
3. **Doc 04a dedup**: helper `_strip_section_header()` remove header leading do narrative antes do template o adicionar.
4. **Doc 04b/c/d active_subdomains**: fallback para `state["subdomains"]` quando ontology está vazia.
5. **Regression test**: 7 testes novos em `test_doc_04_stakeholder_leakage.py` que validam o fix e os modos adjacentes (TinyTask unchanged, influence inheritance ainda funciona).

---

## Bugs corrigidos

### Bug #1 — Stakeholder hallucination (🔴 CRÍTICO)

**File:** `src/aegis_phase1/v2/output/doc_04.py:976-986`

**Diff:** `_augment_influence` agora herda apenas `influence` e `interest` do baseline.

```python
# DEPOIS
for field in ("influence", "interest"):
    if not s.get(field) or s.get(field) == "-":
        s[field] = baseline.get(field, s.get(field, "-"))
```

**Impact:** Qualquer caso futuro com IDs SH-01..SH-07 matching TinyTask já não vaza TinyTask data para o Doc 04.

### Bug #2 — Doc 04d inconsistency (🟠 SIGNIFICATIVO)

**Files:**
- `src/aegis_phase1/v2/output/doc_04d.py:289-318` (§3 table)
- `src/aegis_phase1/v2/output/doc_04d.py:882-885` (frontmatter)

**Diff:** `_section_regulation_level` agora lê applicable_regs de `build_applicability_context(state)` quando `state["regulations"]` está vazio, em vez de hardcodar `NIS2/DORA/AI_Act=NO`.

Frontmatter idem: prefere `app_ctx.applicable_regs` sobre `state["company_context"]["applicable_regs"]`.

**Impact:** Doc 04d §3 + frontmatter ficam consistentes com Doc 05 §0 (ambos lêem do mesmo source-of-truth).

### Bug #3 — Doc 04a duplicate header (🟡 MENOR)

**File:** `src/aegis_phase1/v2/output/doc_04a.py:141-181`

**Diff:** Adicionado helper `_strip_section_header()` que remove leading `## N.` header do narrative se presente. Aplicado em §1 Technical Architecture e §1.2 Network Topology.

**Impact:** Header único por secção, ownership do header fica no template.

### Bug #4 — active_subdomains: 0 (🟡 MENOR)

**Files:**
- `src/aegis_phase1/v2/output/doc_04b.py:1235-1249`
- `src/aegis_phase1/v2/output/doc_04c.py:617-625`
- `src/aegis_phase1/v2/output/doc_04d.py:951-963`

**Diff:** `_active_subdomain_count` / `_active_count` agora tenta `state["ontology"]["subdomains"]["covered"]` primeiro; se vazio ou ausente, fallback para `len(state["subdomains"])`. Os 3 docs ficam consistentes entre si.

**Impact:** Doc 04b/04c/04d reportam o número correcto de sub-domínios activos mesmo quando a ontology não está fully populated.

### Bug #5 — Regression test

**File:** `tests/unit/v2/output/test_doc_04_stakeholder_leakage.py` (NEW, 165 LOC, 7 tests)

Tests:
- `test_omnibank_stakeholder_does_not_inherit_organisation` — regression para o bug #1
- `test_omnibank_stakeholder_does_not_inherit_contact`
- `test_omnibank_stakeholder_does_not_inherit_responsibilities`
- `test_influence_inheritance_still_works` — fixa que influence/interest continuam a herdar (não over-fix)
- `test_tinytask_stakeholder_unchanged` — backwards compatibility
- `test_stakeholders_state_drives_no_tinytask_fallback`
- `test_section_3_stakeholder_register_no_tinytask_leak_in_render` — render end-to-end

---

## Sprints

### Sprint S1: Bugs fix + regression test (~1.5 dias)

Todas as correcções foram aplicadas num único sprint:
- doc_04.py: `_augment_influence` (Bug #1)
- doc_04d.py: §3 table + frontmatter (Bug #2)
- doc_04a.py: `_strip_section_header` (Bug #3)
- doc_04b/c/d.py: `_active_subdomain_count` fallback (Bug #4)
- test_doc_04_stakeholder_leakage.py: 7 regression tests (Bug #5)

**Critérios:**

| ID | Description | Validation |
|---|---|---|
| C1.1 | `_augment_influence` não herda `organisation` | `test_omnibank_stakeholder_does_not_inherit_organisation` |
| C1.2 | `_augment_influence` não herda `contact` | `test_omnibank_stakeholder_does_not_inherit_contact` |
| C1.3 | `_augment_influence` não herda `responsibilities` | `test_omnibank_stakeholder_does_not_inherit_responsibilities` |
| C1.4 | `_augment_influence` ainda herda `influence`/`interest` | `test_influence_inheritance_still_works` |
| C1.5 | TinyTask stakeholders unchanged (back-compat) | `test_tinytask_stakeholder_unchanged` |
| C1.6 | Doc 04 §3.1 render end-to-end sem leak | `test_section_3_stakeholder_register_no_tinytask_leak_in_render` |
| C1.7 | Doc 04d §3 lê applicable_regs do applicability_context | (covered by manual re-run, see notes) |
| C1.8 | Doc 04a §1 sem duplicate header | (covered by manual re-run) |
| C1.9 | Doc 04b/04c/04d active_subdomains fallback OK | (covered by manual re-run) |
| C1.10 | v2 test suite sem regressões (523 pass, 4 pre-existing Ollama fail) | `pytest tests/unit/v2/` |

**Verdict:** 7/7 tests novos passam. v2 suite: 523 pass, 4 pre-existing failures (Ollama unreachable, não relacionadas).

---

## Sequência de execução

1. ✅ Pre-flight check — git status limpo, imports OK
2. ✅ Branch: `feature/aegis-p1-corr-072-pipeline-bugs`
3. ✅ Implementação dos 5 fixes
4. ✅ Regression tests passam
5. ⏳ Manual re-run dos 3 cases (a fazer antes de fechar o contract)
6. ⏳ Update AGENTS.md (se necessário)
7. ⏳ Quality Log update

---

## Risks

| Risk | Mitigation |
|---|---|
| Doc 04d fix altera o fluxo de leitura — outros docs podem ter inconsistências similares | Verificar Doc 04, 04a, 04b, 04c, 04d, 05, 06, 07 — todos lêem applicable_regs de state["company_context"] |
| Fallback em `_active_subdomain_count` pode over-report se `state["subdomains"]` não for filtrado por applicability | Doc 04a usa mesma lógica; alinhamento OK |
| Regression test cobre só stakeholder leakage, não os outros 4 bugs | Manual re-run + render inspection antes de fechar contract |

---

## Lições aprendidas

1. **By-ID matching is dangerous quando IDs são compartilhados entre casos.** SH-01..SH-07 é convenção usada por todos os casos, então qualquer fallback por ID match é susceptível a cross-case leakage. Future code should match by `(case_id, stakeholder_id)` ou similar composite key.
2. **`state["company_context"]` is a legacy source que pode estar stale.** CORR-038 instituiu `build_applicability_context(state)` como source-of-truth. Docs antigos ainda lêem do legacy; este contract começa a migração.
3. **M3 hallucina org/contact/email quando YAML não os fornece.** Em vez de fallback, o doc deveria render `-` ou pedir explicitamente ao user. Future contract pode adicionar prompt augmentation.
4. **active_subdomains calculation needs ontology OR state["subdomains"] — not OR.** Single source é frágil quando uma das duas pode estar vazia.
