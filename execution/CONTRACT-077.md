# CORR-077 — Article_ref join + regex fix in `reorg_by_domain_md.py`

**Status:** ACTIVE (2026-08-04)
**Branch:** `feature/aegis-p1-corr-080-cross-regulation-section` (no new branch — work on current)
**Decision date:** 2026-08-04
**Author:** Planner (opencode / MiniMax-M3)
**Sprint contract:** [`execution/contracts/SC-2026-22.json`](contracts/SC-2026-22.json)
**Spec:** [`scripts/preprocess/HANDOFF_merge_and_ambiguity.md`](../scripts/preprocess/HANDOFF_merge_and_ambiguity.md)

---

## Resumo executivo

A implementação anterior do `reorg_by_domain_md.py` (HANDOFF §0–9, já em master) gerou 38 ficheiros `D-XX.Y.md` com 4 partes. Mas duas lacunas reais causaram match rate muito baixa em NIS2 e DORA:

1. **Bug regex Parser A (NIS2):** o padrão `[A-Za-z_]+-\w+` não aceita dígitos no prefixo. NIS2 contém o dígito `2` → 45 YAML blocks NIS2 lidos, **0** clause_ids extraídos → `clause_to_subs` NIS2 vazio.
2. **Esquemas de ID ortogonais (DORA):** Ambiguity usa `DORA-CL17-1` (article-prefixed: Art. N + clause M); SecurityRules usa `DORA-CL17` (flat #17, refere Art. 9). Sem match possível por clause_id.

Resultado baseline: NIS2 0/97, DORA 0/173.

**Este contract implementa Option B do plano aprovado:** join secundário por `article_ref` (extraído do YAML `source_clauses` + header da secção Ambiguity), com prefix-match como fallback. NIS2 fica resolvido pelo fix de regex; DORA recupera parcialmente via article_ref.

**Resultado esperado (simulado):**

| Reg | Baseline | Depois |
|-----|---------:|-------:|
| GDPR | 72/92 (78%) | 82/99 (83%) |
| CRA | 41/70 (59%) | 51/74 (69%) |
| NIS2 | 0/97 (0%) | **83/101 (82%)** |
| DORA | 0/173 (0%) | **90/179 (50%)** |
| AI_Act | 32/61 (52%) | 32/61 (52%) |
| **Total** | **145/493 (29%)** | **338/514 (66%)** |

DORA tecto a ~50% é fundamental: 77 articles Ambiguity (sobretudo Ch. II Sec. I governance + Ch. III incident reporting) não geram SecurityRules. Documentado como limitação conhecida.

---

## Decisões aprovadas

1. **Fix regex Parser A (1-char):** `[A-Za-z_]+-\w+` → `[A-Za-z0-9_]+-\w+`. Sem impacto nas outras regs (todas usam prefixo só de letras).
2. **Parser A retorna tuple:** `parse_clause_to_subs(src) -> (clause_to_subs, article_to_subs)`. Segundo índice é o join secundário.
3. **Novo helper `_normalize_article_ref(art: str) -> str`:** extrai `"Art. 9(2)"`, `"Annex I Part I"`, etc. Whitespace-normalizado. Devolve `""` se não reconhecível.
4. **Parser B adiciona fallback article_ref:** após tentar match por clause_id, extrai article_ref do header da secção (primeira linha). Tenta match exacto e depois prefix-match. Grava `"match_strategy": "clause_id" | "article_ref"` em cada secção matched (audit trail; não usado no merged file).
5. **Union de sub_domains** quando article_ref liga a múltiplos SRs (comportamento alinhado com HANDOFF §8.5 — many-to-many é esperado). Sem duplicação dentro do mesmo ficheiro merged.
6. **Sem nota inline no merged file** (opção (c) aprovada): informação de estratégia fica apenas no coverage report.
7. **Coverage report gerado** em `methodology-00/PREPROCESSING_by_domain/audit/coverage_by_reg.md`: per-reg tabela com clause_id-matched, article_ref-matched, unmatched, rate, e lista das 5 limitations conhecidas.
8. **Sem regressão na estrutura Part 1–4:** o output por D-XX.Y mantém-se inalterado (apenas o conteúdo do Part 4 muda — mais secções).

---

## Acceptance criteria (11 MUST)

| # | Criterion | Weight |
|---|-----------|--------|
| **C1** | Parser A regex fix — `clause_to_subs` contém entries de NIS2 | MUST |
| **C2** | Parser A também constrói `article_to_subs` (≥100 keys) | MUST |
| **C3** | Parser B article_ref fallback — DORA matched > 0 | MUST |
| **C4** | Total matched ≥ 300 secções (baseline = 145) | MUST |
| **C5** | NIS2 matched ≥ 70 secções (baseline = 0) | MUST |
| **C6** | Coverage report `audit/coverage_by_reg.md` existe com 5 secções | MUST |
| **C7** | `methodology-00/PREPROCESSING/` intocado (`git status` vazio) | MUST |
| **C8** | 38 ficheiros merged, todos com `# Part 1..4` | MUST |
| **C9** | Ruff check + format limpos | MUST |
| **C10** | Idempotência — re-run com `--clean` produz mesma contagem | MUST |
| **C11** | Log do script mostra per-reg breakdown com strategy distinction | MUST |

Detalhe das test_commands em [`contracts/SC-2026-22.json`](contracts/SC-2026-22.json).

---

## Implementation notes (pre-flight)

### Simulação pré-contratual

Corrida standalone em 2026-08-04 (Python 3.11, regex equivalente à do plano):

```
=== After Parser A fix ===
clause_to_subs: 338 entries
article_to_subs: 213 entries

=== Final per-reg stats (simulated) ===
Reg         Extracted    Matched    by clause_id    by article_ref
GDPR               99         82              72                10
CRA                74         51              41                10
NIS2              101         83              74                 9
DORA              179         90               0                90
AI_Act             61         32              32                 0

Total: extracted=514, matched=338
```

Confirma que o plano atinge os números dos critérios C1–C5.

### Edge cases documentados

- **Falsos positivos do pattern 3 (`Cross-clause`, `Berry-relief`):** inalterados. Não matcham clause_to_subs nem article_ref (não há article_ref nessas posições).
- **NIS2 short-form `NIS2-CNN`** (T3-mapping narrative, e.g., "T3 NIS2-C08"): permanece unmatched. Sem mapeamento possível sem tabela manual. Documentar.
- **CRA `CRA-DNN`** (definições Ambiguity-only, sem equivalente em SecurityRules): permanece unmatched. Documentar.
- **DORA articles sem SecurityRule** (governance Ch. II Sec. I, incident reporting Ch. III): permanece unmatched. Documentar.
- **Many-to-many via article_ref:** header `Art. 9(2)` pode ligar a múltiplos SRs (3 DORA-SRs partilham `Art. 9(2)`). Union de sub_domains é o comportamento. Sem duplicação intra-file.

### Files delivered

#### Modified

| File | Change |
|------|--------|
| `scripts/preprocess/reorg_by_domain_md.py` | Parser A regex fix + tuple return + article_ref extraction; Parser B article_ref fallback + match_strategy tracking; main() passa 2 indexes para stage_domains; coverage report generation |

#### Generated (regenerated each `--clean`)

| File | Source |
|------|--------|
| `methodology-00/PREPROCESSING_by_domain/audit/coverage_by_reg.md` | NEW — coverage statistics per regulation |

---

## Out of scope (deferred)

- **CRA `CRA-DNN` definitions mapping:** seria preciso um mapping table manual `CRA-DNN → CRA-CLNN` ou extract article-based join com definição-de-composição. Fora do escopo deste sprint.
- **NIS2 short-form `NIS2-CNN` mapping:** análoga situação. Fora do escopo.
- **DORA articles sem SecurityRule:** não há forma de os gerar — é uma lacuna do corpus-fonte. Documentado.
- **Inline notes em merged files:** opção (c) escolhida — informação fica apenas no coverage report.

---

## Conclusão

Este contract recupera 193 secções de ambiguidade adicionais (+133% vs baseline) sem qualquer regressão estrutural. NIS2 sai de 0% para 82%, DORA de 0% para 50%. As limitações remanescentes são todas fundamentais (lacunas do corpus-fonte) e ficam documentadas em `audit/coverage_by_reg.md` para auditabilidade futura.