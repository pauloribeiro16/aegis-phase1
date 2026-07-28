# CORR-071 — P1B per-regulation filter + size-budget guards (N1 + N2)

**Status:** ACTIVE (2026-07-28)
**Branch:** `feature/aegis-p1-corr-069-pre-existing-test-failures` (mesma branch do CORR-069/070 — AGENTS.md §10, padrão established)
**Base:** HEAD do CORR-070 (commit `30d68cb`)
**Decision date:** 2026-07-28
**Author:** Planner (opencode session)
**Predecessor contracts:** CORR-045 (per-lane filter pattern), CORR-070 (BUG-A reorder workaround — a remover)

---

## Resumo executivo

Eliminar a fragilidade do cap CORR-049 (512KB) em P1B-LLM-01/02,
**aplicando um filter per-reg** dentro de `run_phase_1b` (mesma lógica do
CORR-045 per-domain, mas por regulation em vez de por domain), e
**endurecer o contract** com um invariant semântico hard (`refs.filter(reg)`
deve estar aplicado) + um size-budget soft (warning, não fail).

**Resultado esperado:**
- Payload P1B cai de ~575KB → ~150-200KB (varia por reg: AI_Act 12 refs, GDPR 20, NIS2 16, CRA 27, DORA 23)
- Sem truncamento, sem `truncation_marker` no user prompt
- BUG-A (CORR-070 reorder workaround) torna-se estruturalmente impossível — **removido neste contract**
- Regressões futuras (filter removido, refs irrelevantes introduzidos, bloat gradual) detectadas pelo test suite

**Fora do scope:**
- N3 (chunking per-regulation_group para casos 50+ regs)
- Alterações aos spec templates em `Methodology-main/00_METHODOLOGY/PROMPTS/`
- Reorganização dos golden files (production-goldens/ vs committed) — contract futuro

---

## Contexto e dados

Auditoria cross-case de payloads LLM
(`execution/CROSS-CASE-LLM-PAYLOAD-AUDIT.md`) revelou que P1B-LLM-01/02
estão em ~575KB (109% do cap de 524288 bytes):

| Componente | Bytes | Acumulado |
|---|---|---|
| Catalog (tipo2+tipo3) | ~25K | 25K |
| Sub-domain refs (38 entries) | ~533K | 558K |
| `# TASK` marker | ~17K | 575K → **truncado** |

O CORR-070 fixou BUG-B (P1B-02 não recebia `p1b_llm_01_outputs`) e
mitigou BUG-A (reorder pôs catalog na cabeça antes do cap), mas o
problema estrutural mantém-se: **cada P1B lane recebe os 38 sub-domain
refs, mesmo que só 12-27 participem na regulation em causa**.

O CORR-045 já demonstrou o pattern de filter per-lane para P1C-01
(phase1_executor.py:291-303): filtra por `sub_domain_id.startswith(f"{domain_id}.")`,
resultando em 3-5 refs por lane em vez de 38. A mesma técnica aplica-se
a P1B com `participating_regulations contains reg`.

**Teoria:** o LLM P1B-LLM-01-INTERPRETATION opera per-regulation. Não
precisa de refs onde a regulation não participa. Filtrar por
participating_regulations é semanticamente correcto E estruturalmente
necessário.

---

## Decisões aprovadas (2026-07-28)

1. **Filter location:** dentro de `run_phase_1b` (executor side) — mesma
   localização do CORR-045. Protege todos os call-sites.
2. **BUG-A reorder fix:** **removido** neste contract. N1 torna-o
   redundante; manter seria "two fixes for one bug" (anti-pattern).
3. **Size budget thresholds:** P1B-01/02 ≤ 200K, P1C-01 ≤ 100K,
   P1C-02/03 ≤ 30K — **soft warning**, não hard fail. (Schema declara o
   valor; test loga warning se exceder.)
4. **Semantic guard:** hard fail via `TestPerRegFilterApplied` —
   invariant é `for ref in lane_refs: reg in ref.participating_regulations`.
   Não há `max_count` rígido (false negative risk).

---

## Sprints

### Sprint S1 — N1 implementation

**Goal:** adicionar per-reg filter em `run_phase_1b`.

**File:** `src/aegis_phase1/prompts_v2/phase1_executor.py`

**Lines to change:** 195-225 (per-reg loop em `run_phase_1b`)

**Pattern (reference: CORR-045 phase1_executor.py:291-303):**

```python
# Antes:
for reg in applicable_regs:
    out_01 = self.invoker.invoke(SPEC_INTERPRETATION, {**inputs, ...})

# Depois:
all_refs = inputs.get("layer0_subdomain_refs") or []   # snapshot uma vez
for reg in applicable_regs:
    # CORR-071: per-reg filter (CORR-045-style). Cada lane vê só refs
    # onde a regulation participa — não a taxonomia inteira.
    lane_refs: list[Any] = []
    if isinstance(all_refs, list):
        for ref in all_refs:
            if isinstance(ref, dict):
                pr = ref.get("participating_regulations") or []
                if reg in pr:
                    lane_refs.append(ref)
    out_01 = self.invoker.invoke(
        SPEC_INTERPRETATION,
        {**inputs, "layer0_subdomain_refs": lane_refs, ...},
    )
    out_02 = self.invoker.invoke(
        SPEC_RATIONALE,
        {**inputs, "layer0_subdomain_refs": lane_refs, ...,
         "p1b_llm_01_outputs": (out_01.get("parsed_output") or {})},
    )
```

**Critérios (T3 behavioural):**

| ID | Description | Test command | Expected |
|---|---|---|---|
| C1.1 | Filter é aplicado por lane | Mock LLM, assert `inputs.layer0_subdomain_refs` da chamada P1B-01 GDPR lane contém apenas refs com `reg=GDPR` em `participating_regulations` | All 20 GDPR refs têm "GDPR" in participating_regulations |
| C1.2 | Filter counts correctos per reg | Inspect `layer0_subdomain_refs` per lane num golden regenerated | GDPR=20, AI_Act=12, NIS2=16, CRA=27, DORA=23 (per preproc counts) |
| C1.3 | Empty refs case handled | Synthetic test: reg sem participating_regulations → `lane_refs=[]` | `out_01` recebe `layer0_subdomain_refs=[]`, não crash |
| C1.4 | Filter logic documentado | Manual: docstring de `run_phase_1b` referencia CORR-071 | Texto presente |
| C1.5 | Não-regressão smoke test | `pytest tests/unit/prompts_v2/test_smoke_e2e.py -v` | Pass (ou idêntico baseline) |
| C1.6 | Não-regressão structural tests | `pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsStructural -v` | Pass |
| C1.7 | Ruff clean | `ruff check src/aegis_phase1/prompts_v2/phase1_executor.py` | exit 0 |

---

### Sprint S2 — Cleanup BUG-A + Golden regen

**Goal:** remover o reorder workaround do BUG-A (já não é necessário
após S1) e regenerar os golden files com os tamanhos pós-filter.

**Files:**

1. `src/aegis_phase1/v2/orchestrator.py:1704-1730` — remover o reorder
   workaround + comentário de 8 linhas que o explica. Manter a ordem
   natural (catalog antes de refs é correcto mas não é mais a *única*
   coisa que nos salva do cap).

2. `tests/fixtures/pipeline_inputs_golden/_schema.json` — actualizar
   `known_issues_at_v1_0_0`:
   - Manter BUG-A entrada mas marcar `fixed_in: CORR-071` e
     `fix_out_of_scope_for_now: false`
   - Manter BUG-B entrada (resolvido no CORR-070, sem mudança)

3. `tests/fixtures/pipeline_inputs_golden/case{1,2,3}-*/P1B-LLM-{01,02}__*.json`
   — regenerar (~10-15 files). Esperar diff: `layer0_subdomain_refs`
   muito mais pequeno, restantes keys idênticas.

**Critérios:**

| ID | Description | Test command | Expected |
|---|---|---|---|
| C2.1 | Reorder workaround removido | `grep -c "CORR-070 Bug A" src/aegis_phase1/v2/orchestrator.py` | 0 |
| C2.2 | Orchestrator passa refs crus (sem filter) | Inspecção visual: comentário menciona CORR-071 | Texto presente |
| C2.3 | Golden file sizes caíram | `wc -c tests/fixtures/pipeline_inputs_golden/case*/P1B-LLM-*` max | ≤ 200000 |
| C2.4 | Schema `known_issues` actualizado | `jq '.known_issues_at_v1_0_0."P1B-LLM-01_and_P1B-LLM-02".fixed_in' _schema.json` | `"CORR-071"` |
| C2.5 | Structural tests passam (não perdemos keys) | `pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsStructural -v` | Pass |
| C2.6 | Golden drift tests não falham | `pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsGoldenDrift -v` | Pass (drift é WARN, não fail) |
| C2.7 | Não-regressão smoke | `pytest tests/unit/prompts_v2/test_smoke_e2e.py -v` | Pass |
| C2.8 | Ruff clean | `ruff check src/aegis_phase1/v2/orchestrator.py` | exit 0 |

---

### Sprint S3 — N2 semantic guard + soft size budget

**Goal:** adicionar hard semantic test (P1B lanes devem ter apenas refs
relevantes) e ajustar size budget test para manter como soft warning.

**Files:**

1. `tests/fixtures/pipeline_inputs_golden/_schema.json` — adicionar
   `per_reg_filter_required: true` para P1B-LLM-01 e P1B-LLM-02. Ajustar
   `user_prompt_max_bytes`: P1B 524288 → 200000, P1C-01 mantém 524288
   (já é pequeno), P1C-02/03 mantém 524288. Manter
   `truncation_marker_expected` no schema coerente com a nova realidade
   (P1B: `null` agora).

2. `tests/unit/prompts_v2/test_pipeline_inputs.py` — adicionar nova
   test class `TestPerRegFilterApplied` (hard fail) e ajustar
   `test_inputs_size_within_budget` para continuar como soft-warn.

**Critérios:**

| ID | Description | Test command | Expected |
|---|---|---|---|
| C3.1 | `TestPerRegFilterApplied` adicionado | `pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPerRegFilterApplied -v` | All pass |
| C3.2 | Hard fail se filter não aplicado | Synthetic: criar golden com ref contendo "GDPR" mas lane="AI_Act" → test FAIL | Hard fail |
| C3.3 | Schema declara `per_reg_filter_required` | `jq '.specs."P1B-LLM-01-INTERPRETATION".per_reg_filter_required' _schema.json` | `true` |
| C3.4 | Schema declara P1B max_bytes soft (200K) | `jq '.specs."P1B-LLM-01-INTERPRETATION".user_prompt_max_bytes' _schema.json` | `200000` |
| C3.5 | Size budget test continua soft-warn | Inspect `test_pipeline_inputs.py::test_inputs_size_within_budget` | `logger.warning(...)` sem `assert` |
| C3.6 | CI gate verde | `bash .hooks/ci-pipeline-inputs.sh` | exit 0 |
| C3.7 | Ruff clean | `ruff check tests/unit/prompts_v2/test_pipeline_inputs.py` | exit 0 |
| C3.8 | Full suite verde | `pytest tests/unit/prompts_v2/ -v` | All pass (sem regressões) |

---

## Quality dimensions

| Dimension | Threshold | Rationale |
|---|---|---|
| Correctness | 100% MUST pass | 17 critérios MUST, todos T3 behavioural |
| Pattern Compliance | 4/4 | Filter segue padrão CORR-045; cleanup segue padrão CORR-070 |
| No Regressions | 100% | Smoke + structural + size budget tests |
| Data Integrity | 100% | Goldens regenerados preservam keys; BUG-A documentado |

---

## Files to change (resumo)

| File | Action | Sprint |
|---|---|---|
| `src/aegis_phase1/prompts_v2/phase1_executor.py` | modify `run_phase_1b` (~15 LOC) | S1 |
| `src/aegis_phase1/v2/orchestrator.py` | remove reorder workaround (~10 LOC) | S2 |
| `tests/fixtures/pipeline_inputs_golden/_schema.json` | update `known_issues_at_v1_0_0` + add `per_reg_filter_required` + adjust max_bytes | S2 + S3 |
| `tests/fixtures/pipeline_inputs_golden/case{1,2,3}-*/P1B-LLM-*` | regenerate (~10-15 files) | S2 |
| `tests/unit/prompts_v2/test_pipeline_inputs.py` | add `TestPerRegFilterApplied` (~40 LOC) + tweak size budget test | S3 |
| `execution/CONTRACT-071.md` | create (este ficheiro) | S0 |
| `execution/CORR-071-RUN-LOG.md` | create (execution log) | final |
| `AGENTS.md` | update §12.5 known issues table | final |

---

## Riscos

| Risk | Likelihood | Mitigation |
|---|---|---|
| Filter remove ref que LLM realmente precisa | LOW | CORR-045 provou pattern; spec P1B-LLM-01 é per-reg; refs sem reg não são material válido |
| Golden regen revela outro bug latente | MEDIUM | `TestPipelineInputsGoldenDrift` é WARN-only por design |
| Schema change quebra CI gate noutro sítio | LOW | CI gate verifica schema vs goldens; ambos actualizados em conjunto |
| Reorder removal quebra caso edge onde filter não filtra nada | LOW | S1 C1.3 explicitamente testa `lane_refs=[]` |

**Rollback:** `git revert <commit>` por sprint. Nenhuma migration de dados.

---

## Validação por sprint

```bash
# S1
PYTHONPATH=src pytest tests/unit/prompts_v2/test_smoke_e2e.py -v
PYTHONPATH=src pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPipelineInputsStructural -v
ruff check src/aegis_phase1/prompts_v2/phase1_executor.py

# S2
grep -c "CORR-070 Bug A" src/aegis_phase1/v2/orchestrator.py
wc -c tests/fixtures/pipeline_inputs_golden/case*/P1B-LLM-*
PYTHONPATH=src pytest tests/unit/prompts_v2/ -v
ruff check src/aegis_phase1/v2/orchestrator.py

# S3
PYTHONPATH=src pytest tests/unit/prompts_v2/test_pipeline_inputs.py::TestPerRegFilterApplied -v
PYTHONPATH=src pytest tests/unit/prompts_v2/ -v
bash .hooks/ci-pipeline-inputs.sh
ruff check tests/unit/prompts_v2/test_pipeline_inputs.py
```

---

## Sequência de execução

1. **Pre-flight check** — ✓ done (branch limpa para novos commits, 209 tests collected, imports OK)
2. **S1** → commit `fix(corr-071): per-reg filter in run_phase_1b`
3. **S2** → commit `chore(corr-071): remove CORR-070 BUG-A reorder + regen goldens`
4. **S3** → commit `test(corr-071): hard semantic guard for per-reg filter`
5. **Update AGENTS.md** §12.5 known_issues table (BUG-A → CORR-071)
6. **Quality Log update** em `execution/QUALITY_LOG.md`

**Commit strategy:** 3 commits separados (rastreabilidade por sprint).
Não squash — o filter, o cleanup e o test são logicamente distintos.

---

## Lições aprendidas (a fechar após wrap-up)

- **Pattern reuse:** CORR-045 per-lane filter é generalizável a
  qualquer dimensão de particionamento (D-XX para P1C, REG para P1B).
  Quando o próximo particionamento aparecer (ex: per-tier, per-company_role),
  é só adaptar o predicate.
- **Two-fixes anti-pattern:** o reorder do BUG-A + o filter do BUG-A
  resolvem o mesmo problema. Manter os dois é uma armadilha de
  manutenção. Optou-se por remover o reorder.
- **Soft vs hard guards:** size budgets são úteis como sinal de bloat
  mas perigosos como teto (false negatives em regs com muitas
  participações). Semantic predicates são o invariant real; budgets
  são radar de bloat.