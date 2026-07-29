# CORR-068 — 5 bugs do cross-case validation (cases 1/2/3)

## Resumo

Contract **focado** (3-4 sprints, ~2-3h trabalho), resolve os 5 bugs
identificados na validação cross-case (ver `BUGS-INVESTIGATION-REPORT.md`).

Os bugs foram descobertos ao correr a Phase 1 v2 nos 3 casos e verificar
que o pipeline reportava:
- applicable_regs errados (heurística sobrepõe-se ao user declaration)
- 0 tier rows em Doc 07b (Track B não recebe dados)
- 0 compound events em Doc 07 (LLM reduce recebe input vazio)
- Doc 07b front-matter com `case_study: UNKNOWN`

**Bugs por ordem de prioridade:**

| # | Sev | Bug | Ficheiro | LOC |
|---|---|---|---|---|
| 1 | CRITICAL | Heurística sobrepõe-se ao user-declared `applicable: true` | `applicability_context.py` | ~8 |
| 2 | HIGH | `domain_results[D-XX]["subdomains"]` hardcoded a `[]` | `orchestrator.py` | ~15 |
| 3 | HIGH (cascata 2) | P1C-LLM-02/03 recebem `aggregated_activations=[]` | (cascata) | 0 |
| 4 | LOW | Doc 07b front-matter `getattr(dict, ...)` falha | `doc_07b.py` | 1 |
| 5 | LOW (cascata 1) | Doc 04 front-matter lê `app_ctx` afectado | `doc_04.py` | 1 |

**Decisão do utilizador (2026-07-28):** "Um contrato para resolver isto"

**Branch:** `feature/aegis-p1-corr-068-5-bugfixes`
**Base:** `feature/aegis-p1-corr-067-langfuse-nesting-and-map-partial` (commit `0eea8e5`)
**Data:** 2026-07-28

---

## Contexto

Auditoria cross-case (3 runs reais com provider=minimax) identificou
que o pipeline tem 3 regressões independentes e 2 bugs de baixa
severidade. Detalhes completos em
`execution/BUGS-INVESTIGATION-REPORT.md` e
`execution/CASES-2-3-VALIDATION-REPORT.md`.

**Validação pré-contract:**
- 2667 unit tests verdes, 7 failures pré-existentes (idênticas em baseline)
- Casos 2/3 com scaffolding mínimo (12 ficheiros YAML) — não é parte do fix
- Todos os 3 runs validaram os bugs de forma reprodutível

---

## S1 — Fix Bug 2 (domain_results[D-XX]["subdomains"] hardcoded to [])

### Hipótese de fix

**File:** `src/aegis_phase1/v2/orchestrator.py`
**Function:** `_map_domains_via_p1c_llm_01` (line ~657-704)

O `_map_domains_via_p1c_llm_01` constrói o `domain_results` dict com
`"subdomains": []` hardcoded. Os dados reais (P1C-LLM-01 output) estão
em `adapted_subdomains_v3` (campo separado, formato v3). Os consumers
(`concatenator.py:59`, `reduce_synthesis() no orchestrator`) ainda lêem
o campo legacy `subdomains`.

Fix: popular o campo `subdomains` com a forma legacy mapeada do
`adapted_subdomains_v3` (mesma forma que o legacy `DomainProcessor`
produzia).

### Patch proposto

```python
# Map adapted_v3 (v3 shape) to legacy subdomains (v1 shape)
legacy_subdomains = [
    {
        "subdomain_id": sd.get("sub_domain_id", ""),
        "id": sd.get("sub_domain_id", ""),
        "reg_pair": sd.get("reg_pair", []),
        "company_scope_verdict": sd.get("company_scope_verdict", ""),
        "regulatory_baseline_relationship": sd.get("regulatory_baseline_relationship", ""),
        "layer0_refs": sd.get("layer0_refs", []),
    }
    for sd in adapted_v3
]
results[did] = {
    ...
    "subdomains": legacy_subdomains,  # ← was []
    "adapted_subdomains_v3": adapted_v3,
    ...
}
```

### Critérios S1 (validação)

| # | Critério | Tipo | Como verificar |
|---|---------|------|----------------|
| 1 | Log: `concatenate: 10 domains -> N subdomains` (N > 0, ~38) | MUST | `grep concatenate logs/phase1/...pipeline.log` |
| 2 | Log: `apply_proportionality: N subdomains profiled (N > 0)` | MUST | `grep apply_proportionality logs/...` |
| 3 | Doc 07b §3 tem tier rows (MINIMAL, LIGHTWEIGHT, STANDARD, RIGOROUS, DEFERRED counts > 0) | MUST | `grep -c '^| MINIMAL' output/.../07b_Proportionality_Profile.md` |
| 4 | Doc 07 §3 coverage matrix: per-cell clause count > 0 | MUST | `grep '^| D-' output/.../07_Structured_Compliance_Matrix.md` |
| 5 | Re-run case 1: MAP 10/10 OK + P1C-LLM-02/03 status = OK (not INDETERMINATE) | MUST | `grep "P1C-LLM-02\|P1C-LLM-03" logs/.../pipeline.log` |
| 6 | Unit tests: 2667 pass (no regression) | MUST | `pytest tests/unit/ -q` |
| 7 | New unit test: `test_domain_results_subdomains_populated.py` covers the mapping | SHOULD | New test verifies the field is populated from adapted_v3 |

---

## S2 — Fix Bug 1 (heurística sobrepõe-se ao user declaration)

### Hipótese de fix

**File:** `src/aegis_phase1/v2/context/applicability_context.py`
**Lines:** 245-254

Inverter a prioridade: `v2_applicable_regs` é authoritative quando
presente, heurística é fallback.

### Patch proposto

```python
# Line 245-254 — REPLACE
v2_applicable_pre: list[str] = list(state.get("v2_applicable_regs", []))
applicable_computed = _compute_applicable_regs(predicates)
# NEW: user declaration is authoritative, heuristic is fallback
if v2_applicable_pre:
    applicable_computed = list(v2_applicable_pre)
elif not applicable_computed and v1_applicable_from_cc:
    applicable_computed = sorted(v1_applicable_from_cc)
```

### Critérios S2 (validação)

| # | Critério | Tipo | Como verificar |
|---|---------|------|----------------|
| 1 | Case 2 Doc 05: applicable_regs = [GDPR, CRA, NIS2, AI_Act] (4 regs, not 1) | MUST | `grep "APPLICABLE" output/case2/05_Regulatory_Applicability.md` |
| 2 | Case 3 Doc 05: applicable_regs = [GDPR, CRA, NIS2, DORA, AI_Act] (5 regs, not 2) | MUST | `grep "APPLICABLE" output/case3/05_Regulatory_Applicability.md` |
| 3 | Case 1 Doc 05: applicable_regs = [GDPR, CRA] (unchanged) | MUST | Same grep on case 1 (regression check) |
| 4 | Doc 05 DECLARATION GAPS empty for cases 2 and 3 (no declared_not_computed) | MUST | `grep "GAP" output/case2/05_...` returns no rows |
| 5 | Doc 04 front-matter `applicable_regs` shows user-declared list | MUST | `grep "^applicable_regs:" output/case2/04_...` |
| 6 | Re-run all 3 cases: tier = HIGH for cases 2/3, LOW for case 1 | MUST | `grep "^tier:" output/.../04_...` |
| 7 | Unit tests: 2667 pass (no regression) | MUST | `pytest tests/unit/ -q` |
| 8 | New unit test: `test_applicability_authoritative_from_v2.py` covers the priority inversion | SHOULD | Test the priority logic explicitly |

---

## S3 — Fix Bug 4 (Doc 07b front-matter getattr)

### Hipótese de fix

**File:** `src/aegis_phase1/v2/output/doc_07b.py`
**Line:** ~125

Substituir `getattr(ctx, "company_name", "UNKNOWN")` por
`_safe_attr(ctx, "company_name", "UNKNOWN")` (que já lida com dicts
correctamente).

### Patch proposto

```python
# Line ~125 — REPLACE
# OLD: "case_study": getattr(ctx, "company_name", "UNKNOWN") if ctx else "UNKNOWN",
# NEW: usa o _safe_attr local que já existe e lida com dicts
"case_study": _safe_attr(ctx, "company_name", "UNKNOWN"),
```

### Critérios S3 (validação)

| # | Critério | Tipo | Como verificar |
|---|---------|------|----------------|
| 1 | Doc 07b front-matter `case_study` = "TinyTask Lda." (case 1) | MUST | `grep "^case_study:" output/case1/07b_...` |
| 2 | Doc 07b front-matter `case_study` = "SecureBorder Solutions B.V." (case 2) | MUST | Same |
| 3 | Doc 07b front-matter `case_study` = "OmniBank Financial Systems S.A." (case 3) | MUST | Same |
| 4 | Doc 07b front-matter `scale` = MICRO/LARGE (not "-") | MUST | `grep "^scale:" output/.../07b_...` |
| 5 | Doc 07b front-matter `security_fte` = 0.85/25.0/100.0 (not 0) | MUST | `grep "^security_fte:" output/.../07b_...` |
| 6 | Unit tests: pass (no regression) | MUST | `pytest tests/unit/ -q` |

---

## S4 — Validação final (re-run all 3 cases, zero regression)

### Actividade

1. Re-run case 1 (TinyTask) with `provider=minimax` and `model=MiniMax-M3`
2. Re-run case 2 (SecureBorder) with same
3. Re-run case 3 (OmniBank) with same
4. Compare output front-matter and Doc 05/07/07b bodies against expected values
5. Run full unit test suite — confirm 2667+ pass, no new failures
6. Write a run log summarising the validation

### Critérios S4 (validação)

| # | Critério | Tipo | Como verificar |
|---|---------|------|----------------|
| 1 | All 3 cases complete "PIPELINE COMPLETE" without errors | MUST | `grep "PIPELINE COMPLETE" logs/.../pipeline.log` for each case |
| 2 | All 3 cases: 10/10 MAP domains OK | MUST | `grep "MAP complete" logs/.../pipeline.log` |
| 3 | All 3 cases: Doc 05 applicable_regs = user-declared list | MUST | grep above |
| 4 | All 3 cases: Doc 07b §3 has tier counts > 0 | MUST | grep above |
| 5 | All 3 cases: Doc 07 §3 has per-cell clause counts > 0 | MUST | grep above |
| 6 | All 3 cases: P1C-LLM-02/03 status = OK (not INDETERMINATE) | MUST | `grep "P1C-LLM-02.*→ OK\|P1C-LLM-03.*→ OK" logs/.../pipeline.log` |
| 7 | All 3 cases: Doc 04/07b front-matter correct (case_study, scale, security_fte) | MUST | grep above |
| 8 | Unit tests: 2667 pass (no regression) | MUST | `pytest tests/unit/ -q` |
| 9 | Run log written: `execution/CORR-068-VALIDATION-LOG.md` | MUST | File exists with green checks |

---

## Ficheiros a alterar (estimativa)

| Ficheiro | S1 | S2 | S3 | Total LOC |
|----------|----|----|----|-----------|
| `src/aegis_phase1/v2/orchestrator.py` | x | — | — | +15 |
| `src/aegis_phase1/v2/context/applicability_context.py` | — | x | — | +8 |
| `src/aegis_phase1/v2/output/doc_07b.py` | — | — | x | +1 |
| `tests/unit/v2/test_domain_results_subdomains.py` (new) | x | — | — | +30 |
| `tests/unit/v2/test_applicability_authoritative_from_v2.py` (new) | — | x | — | +25 |
| `tests/unit/v2/test_doc_07b_frontmatter.py` (new) | — | — | x | +15 |

**Estimativa total:** 6 ficheiros, ~95 linhas (+70 código, +70 testes).

---

## Comandos de validação

```bash
# S1
PYTHONPATH=src python -m pytest tests/unit/v2/test_domain_results_subdomains.py -v
PYTHONPATH=src python -m pytest tests/unit/ -q   # no regression

# S2
PYTHONPATH=src python -m pytest tests/unit/v2/test_applicability_authoritative_from_v2.py -v
PYTHONPATH=src python -m pytest tests/unit/ -q   # no regression

# S3
PYTHONPATH=src python -m pytest tests/unit/v2/test_doc_07b_frontmatter.py -v
PYTHONPATH=src python -m pytest tests/unit/ -q   # no regression

# S4: re-run all 3 cases (cf. CASES-2-3-VALIDATION-REPORT.md setup)
export MINIMAX_API_KEY="$(cat /tmp/m3_key_for_test)"
for c in case1-tinytask case2-secureborder case3-omnibank; do
    PYTHONPATH=src python -m aegis_phase1.v2.runner \
        --case cases/$c \
        --provider minimax \
        --model MiniMax-M3 \
        --output output/${c}_corr068 \
        --run-all
done
```

---

## Risco

- **S1 (Bug 2):** baixo. Só preenche um campo que estava vazio. Consumers
  existentes continuam a funcionar (alguns podem agora ter mais dados,
  que é o desejado).
- **S2 (Bug 1):** baixo. Inverte a prioridade heuristic/declaration.
  Edge case: se `v2_applicable_regs` é `[GDPR]` (caso 1) e user queria
  `[GDPR, CRA]`, o pipeline vai reportar só GDPR. Mas o teste runtime
  confirma que `case 1.applicable_regs = ['CRA', 'GDPR']` correcto.
  Só seria problema se alguém usar state.json persistido de uma era
  pré-CORR-061 com `v2_applicable_regs` vazio — nesse caso cai para a
  heurística (fallback, comportamento actual).
- **S3 (Bug 4):** trivial. 1 linha. `_safe_attr` já existe e funciona.
- **S4:** puro re-run. Se algum critério falhar, há uma regression
  escondida que precisa investigação.

---

## Não-objetivos (out of scope)

- S1 (CORR-067 Langfuse CHAIN nesting) — deferido
- Adicionar `--provider anthropic` (MiniMax Messages já fala Anthropic protocol)
- Refactor da heurística de sector para incluir mais keywords
- Migrar consumers do shim v1_compat para ler v2_* keys directamente
- Completar o scaffolding de case 2/3 (architecture YAMLs, role_matrix,
  regulatory_interactions, implementation_readiness) — testes correm
  com o mínimo; expandir é trabalho separado

---

## Estado final esperado (depois do S4)

| Doc | Field | Case 1 | Case 2 | Case 3 |
|---|---|---|---|---|
| 04 front | `applicable_regs` | [CRA, GDPR] | [AI_Act, CRA, GDPR, NIS2] | [AI_Act, CRA, DORA, GDPR, NIS2] |
| 04 front | `tier` | LOW | HIGH | HIGH |
| 04 front | `case_study` | TinyTask Lda. | SecureBorder Solutions B.V. | OmniBank Financial Systems S.A. |
| 05 body | APPLICABILITY SUMMARY | [CRA, GDPR] | [AI_Act, CRA, GDPR, NIS2] | [AI_Act, CRA, DORA, GDPR, NIS2] |
| 05 body | DECLARATION GAPS | none | none | none |
| 07b front | `case_study` | TinyTask Lda. | SecureBorder Solutions B.V. | OmniBank Financial Systems S.A. |
| 07b front | `scale` | MICRO | LARGE | LARGE |
| 07b front | `security_fte` | 0.85 | 25.0 | 100.0 |
| 07b body | §3 tier rows | > 0 | > 0 | > 0 |
| 07 body | §3 coverage matrix | non-zero counts | non-zero counts | non-zero counts |
| 07 body | §4 strategic implications | non-empty | non-empty | non-empty |
| 07 body | §5 compound events | non-empty | non-empty | non-empty |
| P1C-LLM-02/03 | status | OK | OK | OK |

**Sucesso = todos os campos acima correctos para os 3 casos + zero
regressões nos unit tests (2667 pass).**
