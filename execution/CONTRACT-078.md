# CORR-078 — Archive dos 176 unmatched ambiguity sections

**Status:** ACTIVE (2026-08-04)
**Branch:** `feature/aegis-p1-corr-080-cross-regulation-section` (no new branch)
**Decision date:** 2026-08-04
**Author:** Planner (opencode / MiniMax-M3)
**Sprint contract:** [`execution/contracts/SC-2026-23.json`](contracts/SC-2026-23.json)
**Predecessor contracts:**
- [CORR-077](CONTRACT-077.md) — Article_ref join + regex fix (335/493 matched, 176 unmatched)
- [HANDOFF_merge_and_ambiguity.md](../scripts/preprocess/HANDOFF_merge_and_ambiguity.md)

---

## Resumo executivo

CORR-077 (este sprint anterior) recuperou 335/493 secções de ambiguidade (vs baseline 145). As restantes **176 secções unmatched** são **legítimas** — verificado:

| Categoria | Qtd | Razão |
|-----------|----:|--------|
| `false_positive_pattern3` | 73 | Regex pattern 3 capturou fragmento (ex: `R2-tightened`, `SCOPE-Q`, `Berry-relief`). Secção subjacente é real mas unlabelled. |
| `definition_section` | 34 | `CRA-D01..D38`, `DORA-D01..D38`, `NIS2-D05..D14` — Art. 3 definitions, sem SecurityRule. |
| `real_clause_no_sr` | 48 | `GDPR-RT19`, `NIS2-CL41`, `DORA-CL4-2` — cláusulas reais mas artigos sem SecurityRule no corpus. |
| `no_clause_id_intro` | 21 | Secções agregadoras sem clause_id (ex: `### 4(2) \`processing\``, `### 4.1 Intra-regulation`). |
| **Total** | **176** | |

**Este contract preserva as 176 secções num archive dedicado** `_archive_unmatched/` (opção (a) aprovada), com:
- Categoria documentada no header de cada ficheiro (não é perda de informação)
- Conteúdo verbatim do source (re-parsing futuro com heurísticas melhores)
- README índice com breakdown por categoria
- Coverage report estendido com referência ao archive

**Porquê arquivar (não descartar):**
1. **Audit trail** — futuro leitor vê o que foi extraído, matched, e unmatched.
2. **Re-parsing futuro** — se a heurística melhorar, as secções podem voltar a ser úteis sem re-derivar da fonte.
3. **Rastreabilidade** — 1:1 com source `Regulation/{REG}/Ambiguity/<filename>.md`.

---

## Decisões aprovadas

1. **Path:** `methodology-00/PREPROCESSING_by_domain/_archive_unmatched/` (top-level, opção (a)). Separado de `_archive/` (legacy) e `_ambiguity/` (global methodology).
2. **Estrutura:** `_archive_unmatched/{REG}/{filename}.md` — espelha `Regulation/{REG}/Ambiguity/{filename}.md`. Um ficheiro por source Ambiguity file que tem ≥1 unmatched section.
3. **Conteúdo:** Apenas as secções unmatched (não copia matched). Cada secção prefixada com `## Section N — <header>` para evitar colisão de headers.
4. **Header do ficheiro:** YAML-style comment block com `archive_id`, `source`, `unmatched_count`, `categories` (lista), `generated_by`. Sem timestamp (idempotência C16).
5. **README índice:** `_archive_unmatched/README.md` com breakdown por categoria, lista de todos os ficheiros (link relativo), e explicação das 4 razões.
6. **Coverage report estendido:** Secção "Unmatched archived" com breakdown por categoria + referência ao README.
7. **`parse_ambiguity_sections` retorna tuple:** `(matched: list, unmatched: list)`. Categorização feita inline durante o split (zero overhead adicional).
8. **Idempotência preservada:** sem timestamps nos ficheiros; re-run produz ficheiros byte-identical (C16).

---

## Acceptance criteria (7 MUST)

| # | Criterion | Weight |
|---|-----------|--------|
| **C12** | 176 unmatched sections archived (count = 73 fp + 34 def + 48 real + 21 no-id) | MUST |
| **C13** | Cada ficheiro archived tem header com `archive_id`, `source`, `unmatched_count`, `categories`, `generated_by` | MUST |
| **C14** | `_archive_unmatched/README.md` lista todos os ficheiros com categoria + source path | MUST |
| **C15** | Coverage report tem secção "Unmatched archived" com breakdown por categoria | MUST |
| **C16** | Idempotência — re-run produz mesmos ficheiros (mesmo archive_id, mesma ordem de secções) | MUST |
| **C17** | Conteúdo verbatim — `diff` entre secção source e archive = vazio para secções unmatched | MUST |
| **C18** | Ruff check + format limpos | MUST |

Detalhe das test_commands em [`contracts/SC-2026-23.json`](contracts/SC-2026-23.json).

---

## Implementation notes (pre-flight)

### Categorização inline no Parser B

```python
CATEGORY_FNS = {
    "false_positive_pattern3": lambda cid: cid and not re.match(r"^(GDPR|CRA|NIS2|DORA|AI_Act)-", cid),
    "definition_section": lambda cid: cid and re.match(r"^(GDPR|CRA|NIS2|DORA|AI_Act)-D\d+$", cid),
    # "real_clause_no_sr": clause_id NOT in clause_to_subs AND NOT a definition AND NOT a FP
    # "no_clause_id_intro": no clause_id extracted
}

def _categorize_unmatched(clause_id: str | None) -> str:
    if clause_id is None:
        return "no_clause_id_intro"
    if re.match(r"^(GDPR|CRA|NIS2|DORA|AI_Act)-D\d+$", clause_id):
        return "definition_section"
    if not re.match(r"^(GDPR|CRA|NIS2|DORA|AI_Act)-", clause_id):
        return "false_positive_pattern3"
    return "real_clause_no_sr"
```

A categoria é atribuída **antes** do match check (não depois) — uma secção com `clause_id=GDPR-CL24` que não casa é categorizada como `real_clause_no_sr` mesmo que tivesse podido casar via article_ref.

### Group & write

```python
def write_unmatched_archive(dst, unmatched, dry_run):
    if dry_run:
        return
    grouped = defaultdict(list)
    for u in unmatched:
        grouped[(u["reg"], u["file"])].append(u)
    # ... per (reg, file): build header + per-section content, write to dst/_archive_unmatched/{REG}/{file}.md
```

### Files delivered

#### Modified

| File | Change |
|------|--------|
| `scripts/preprocess/reorg_by_domain_md.py` | Parser B returns tuple + inline categorize; new `write_unmatched_archive()`; new `write_unmatched_index()` (README); main() passes unmatched; coverage report extended with archive section; module docstring updated |

#### Generated (regenerated each `--clean`)

| Path | Source |
|------|--------|
| `methodology-00/PREPROCESSING_by_domain/_archive_unmatched/README.md` | `write_unmatched_index()` |
| `methodology-00/PREPROCESSING_by_domain/_archive_unmatched/{REG}/{filename}.md` | `write_unmatched_archive()` — ~50-60 files |
| `methodology-00/PREPROCESSING_by_domain/audit/coverage_by_reg.md` | `write_coverage_report()` extended |

---

## Out of scope (deferred)

- **Re-parse unmatched** com heurísticas melhores (e.g., manual mapping `CRA-DNN → CRA-CLNN`) — fora do escopo deste sprint.
- **Mover archive para dentro de `_archive/`** (opção (b)) — decisão (a) já tomada e aprovada.
- **Compactar archive** (e.g., gzip) — overhead não justifica o tamanho (~50 ficheiros).

---

## Conclusão

Este contract preserva 176 secções de ambiguidade que o parser actual não consegue mapear para sub_domains. Cada secção fica arquivada com a sua categoria e conteúdo verbatim, garantindo audit trail completo e permitindo re-parsing futuro sem aceder novamente ao corpus-fonte (que é READ-ONLY). O coverage report passa a distinguir **matched** vs **archived unmatched** vs **total source sections**.