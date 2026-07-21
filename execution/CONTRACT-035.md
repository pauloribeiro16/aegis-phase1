# CORR-035 — DA outputs cleanup (audit infra + 5 bug fixes)

## Resumo

Auditoria automatizada dos 38 JSONs `DomainAnalysis/D-XX.Y.json` em
`preproc_out/crossregulation/DomainAnalysis/`, identificação de 6
problemas, e fix em 6 commits sequenciais.

**Branch:** `feature/aegis-p1-corr-035`
**Data:** 2026-07-21
**Trigger:** auditoria ad-hoc após entrega do CORR-034

---

## Estado inicial (baseline — pré-CORR-035)

```
Scanned 38 DomainAnalysis JSONs (+ index.json)
Findings by severity:
  CRITICAL  0
  HIGH      37
  MEDIUM    248
  LOW       5
```

Total: **290 findings** em 38 ficheiros.

---

## Os 6 problemas (com raízes após investigação)

| # | Problema | Raiz | Sev | Findings |
|---|---|---|---|---|
| A | `downstream_implication_top` vaza `\n---` (28) ou `\n## <próximo D-XX>` (9) | `_extract_h4_section` apanha até EOF+HR do sub-domínio seguinte | HIGH | 37 |
| B | `why == why_note` em todos os pares | `_extract_why_metadata` popula `note` com prosa completa, não stripada | MEDIUM | 186 |
| C | `sr_ids_per_pair` perde 188 SRs NIS2 | `_SR_RE = SR-[A-Z_]+-\d{3}` não aceita dígitos no nome do reg | HIGH | 188 SRs perdidos |
| D | `macro_domain` errado em D-10.1/2/3 (diz `D-09` mas sub é `D-10.*`) | Frontmatter source MD com bug | MEDIUM | 3 |
| E | `scope` axis populado em D-01..D-03 (52 pares em 12 ficheiros) | Source MDs D-01..D-03 têm 3ª coluna "Scope" nas tabelas dos pares; D-04..D-10 só têm 2 | MEDIUM | 52 |
| F | `emergent_tensions` em falta em 5 ficheiros (3+ participants) | Source MD sem marker `<!-- emergent -->` | LOW | 5 |

**Reclassificação do bug C:** promoção de MEDIUM → HIGH após descobrir
que são **188 SRs NIS2 perdidos** sistematicamente (não apenas 7 pares
visíveis). Qualquer consumer que use `sr_ids_per_pair` para linking está
a perder ~25% dos SRs.

---

## Decisões de produto

1. **Bug E**: fix no **parser** (ignorar 3ª coluna da tabela do par).
   Não editar 12 source MDs.
2. **Bug B**: strippar o qualifier do `note` no helper
   `_extract_why_metadata`. Não remover o campo (preserva retro-compat).
3. **Estrutura**: 6 commits sequenciais (cada um revertível), 1 contract,
   1 branch.

---

## Estrutura dos 6 commits

```
feature/aegis-p1-corr-035
├─ commit 1: audit infra (script + 30+ tests + CI hook + este contract)
├─ commit 2: bug A  — _extract_h4_section leak fix    (4 tests)
├─ commit 3: bug C  — _SR_RE regex fix                (4 tests)
├─ commit 4: bug B  — why_note qualifier strip        (4 tests)
├─ commit 5: bug D  — macro_domain correction in 3 source MDs (3 tests)
│             + bug F: 5 emergent_tensions markers    (5 tests)
└─ commit 6: bug E  — scope axis strip + full rebuild + re-audit
```

**Convenção AGENTS.md §10:** 1 branch por contract, sem sub-branches,
commits sequenciais, sem amending.

---

## Ficheiros

### Commit 1 (este)
- `execution/CONTRACT-035.md` (este)
- `scripts/audit/audit_da_outputs.py` (novo, ~430 linhas)
- `scripts/audit/__init__.py` (novo, vazio)
- `tests/unit/audit/__init__.py` (novo, vazio)
- `tests/unit/audit/test_audit_da_outputs.py` (novo, ~430 linhas, 30+ tests)
- `.hooks/ci-da-audit.sh` (novo, ~50 linhas)

### Commits 2-6
- `scripts/preprocess/parsers/narrative.py` (fixes em `_extract_h4_section`, `_SR_RE`, `_extract_why_metadata`, `_extract_comparison_sections_domain`)
- `methodology-00/PREPROCESSING/CrossRegulation/DomainAnalysis/D-10_Monitoring-Audit/D-10.{1,2,3}.md` (3 fixes de frontmatter)
- 5 markers `<!-- emergent -->` em source MDs D-04.1, D-04.2, D-04.4, D-06.1, D-07.3
- `preproc_out/crossregulation/DomainAnalysis/**/D-*.json` (regenerados pelo build)

---

## Quality gates (final)

Todos têm de passar antes de merge:

```bash
# 0 findings na auditoria (todos os níveis)
PYTHONPATH=src python -m scripts.audit.audit_da_outputs --only CRITICAL
PYTHONPATH=src python -m scripts.audit.audit_da_outputs --only HIGH
PYTHONPATH=src python -m scripts.audit.audit_da_outputs --only MEDIUM
PYTHONPATH=src python -m scripts.audit.audit_da_outputs --only LOW

# Test suite
pytest tests/ -q

# Preproc invariants preservados
python -m scripts.preprocess build
python -m scripts.preprocess.audit_csf_mapping     # 0 BROKEN
python -m scripts.preprocess.audit_so_sr_coherence # full=282, partial=0, unresolved=0

# CI gates
bash .hooks/ci-frameworks.sh        # OK
bash .hooks/ci-csf-frozen-list.sh   # OK
bash .hooks/ci-da-audit.sh          # OK (novo)
```

**Definição de done:** 0 findings + 282 full preservados + CI verde.

---

## Riscos

| Risco | Mitigação |
|---|---|
| Strip do `why_note` quebra consumers | Manter `why` intacto; só alterar `why_note`; documentar em CHANGELOG |
| Regex `_SR_RE` causar falsos matches em strings tipo `SR-XY-9-999` | Testes com 5 reg names canónicos; nenhum match incorreto esperado em DA |
| D-01..D-03 source ter dados não-descritivos na 3ª coluna "Scope" | Verifiquei 12 ficheiros: conteúdo é sempre descritivo (`Art. X(1)(f) CIA; ...; scope = ...`) — seguro strippar |
| Re-build altera ordering de pares (dedup) | Verificar diff antes/depois; 0 dup pairs esperado |
| `_extract_h4_section` strip agressivo demais | Testes com fixtures de 3 padrões (HR alone, H2 leak, H3 leak) + regressão sobre 38 ficheiros |

---

## Métricas

- **Linhas adicionadas:** ~580 (script + tests + fixes)
- **Testes novos:** ~42
- **Ficheiros source MD editados:** 8 (3 macro_domain + 5 emergent_tensions)
- **Ficheiros preproc_out regenerados:** 38 (via `preprocess build`)
- **Commits:** 6
