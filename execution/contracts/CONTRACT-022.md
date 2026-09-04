# CONTRACT — AEGIS-P1-CORR-022 Phase 2: MAP per-sub-domain adaptation (D-10.2)

**Contract ID:** AEGIS-P1-CORR-022 (Phase 2)
**Date:** 2026-07-18
**Planner:** Orchestrator (AEGIS)
**Spec File:** plano aprovado por user (in-session)
**Status:** APPROVED → IMPLEMENTING → VALIDATED
**Phase:** 2 of 2 (Phase 1 = filter_regs fallback + subdomains filter + prompt trim — done)
**Branch:** `feature/aegis-p1-corr-022` (continua; sem novo branch)
**Trials:** 1 (decisão user: "1 run passando tudo")
**Scope target:** **D-10.2 fechado** end-to-end. D-10.1, D-10.3, D-01..D-09 **fora de scope** (contracto separado).

## Scope

Substituir o contrato de output MAP (single `ADAPTED_OBJECTIVE` por domínio) pelo formato **per-sub-domain** (HL verbatim + direcionados por regulamento aplicável), com contexto rico (artigos OJ verbatim, ambiguidades, Track B), parser novo, validação factual de anchors, e logs reorganizados.

**Foco:** fechar **D-10.2 Audit Logging & Traceability** para TinyTask (GDPR + CRA aplicável).

## Output canónico (v1.2)

```
### D-XX.Y — <title>
**Objective.** <HL verbatim da fonte — 1 frase arquitetura-cêntrica, ≤500 chars>

**Directed objectives.**
- **<REG>**: <2-3 frases com anchor + scope + threshold + recipient, ≤800 chars>
- **<REG>**: <...>
```

## Files to change

| File | Action | Why |
|---|---|---|
| `src/aegis_phase1/v2/domain/prompts/MAP-DOMAIN-ADAPT.md` | rewrite v1.2 | spec com Task Specifics, HARD PROHIBITIONS (lista alargada), OUTPUT ANATOMY, Output Format canónico |
| `src/aegis_phase1/v2/domain/prompt.py` | modify | `_extract_objective_paragraph`: strip headings/blockquotes/tabelas antes de `**Objective.**`; `_render_subdomains`: HL verbatim + bullets verbatim; `_render_articles`: verbatim completo (sem truncate 200); `_render_ambiguities`: aplicáveis; `_render_track_b`: tier+rationale+attrs; `_render_cross_reg`: só pares aplicáveis |
| `src/aegis_phase1/v2/loader/subdomain_loader.py` | modify | fail-hard: `HLExtractionError` quando o bloco `.0` não tem `**Objective.**` canónico |
| `src/aegis_phase1/v2/loader/article_loader.py` | **create** | carrega `Regulation/<REG>/Articles/Art_N.md` verbatim |
| `src/aegis_phase1/v2/domain/filters/articles.py` | modify | devolver texto verbatim completo (não truncado) |
| `src/aegis_phase1/v2/domain/filters/ambiguities.py` | modify | filtrar por regs aplicáveis |
| `src/aegis_phase1/v2/domain/parser.py` | modify | `OutputParserV2` + `SubdomainAdaptation` + `ParseResultV2` |
| `src/aegis_phase1/v2/state.py` | modify | `DomainResult.adapted_subdomains: list[dict]` |
| `src/aegis_phase1/v2/domain/processor.py` | modify | `_ok_result` popula `adapted_subdomains`; usa `OutputParserV2` |
| `src/aegis_phase1/v2/output/doc_04b.py` | modify | `_section_adapted_objective` renderiza por sub-domínio |
| `src/aegis_phase1/v2/domain/anchor_validator.py` | **create** | `extract_anchors_from_source` + `validate_output_citations` |
| `tests/unit/v2/domain/test_prompt.py` | modify | cobrir novo render + verbatim |
| `tests/unit/v2/domain/test_parser.py` | modify | OutputParserV2 tests |
| `tests/unit/v2/domain/test_anchor_validator.py` | **create** | regressão Annex II vs Annex I |
| `tests/unit/v2/loader/test_subdomain_loader.py` | modify | fail-hard test |
| `scripts/d10_2_experiment.py` | modify | logs `runs/<model>_<ts>/{prompt,response.raw,response.parsed,meta}.json` + `MANIFEST.md` auto + gate G8 |
| `logs/phase1/v2/d10_2/runs/` | create | estrutura nova; apagar runs antigas (timestamps 20260717T15/16/17*) |

## Criteria (default-FAIL)

| ID | Weight | Tier | Descrição | Validation |
|---|---|---|---|---|
| **C1** | MUST | T3 | `_extract_objective_paragraph` para D-10.2 HL devolve o `**Objective.** Audit logging and traceability are established through a layered audit-records architecture...` (não `> CRDA-deep provenance...`) | inline python check |
| **C2** | MUST | T3 | `_render_subdomains` para D-10.2 contém: header `### D-10.2 —`, HL paragraph, `**Directed objectives.**`, 2 bullets `- **GDPR**:`, `- **CRA**:` | inline python check |
| **C3** | MUST | T3 | §3 render contém texto OJ verbatim completo (sem `…` truncation; ≥500 chars por artigo) | inline python check |
| **C4** | MUST | T3 | §5 contém só pares onde ambas as regs são aplicáveis (GDPR↔CRA para TinyTask); zero menções `NIS2`/`DORA`/`AI_Act`/`AI Act` em §5 | inline python check |
| **C5** | MUST | T3 | §6 contém ≥1 ambiguidade aplicável (não `(not used at MAP stage)`) | inline python check |
| **C6** | MUST | T3 | §7 contém `tier` + `rationale` + `inheritability` (não `(not used at MAP stage)`) | inline python check |
| **C7** | MUST | T3 | `OutputParserV2.parse(raw)` parseia output canónico (3 blocos D-10.1/.2/.3) com `success=True`, `len(subdomains)==3`, cada sub com HL + ≥1 directed | `pytest tests/unit/v2/domain/test_parser.py -k V2 -v` |
| **C8** | MUST | T3 | `DomainProcessor.process("D-10", state)` popula `result["adapted_subdomains"]` com lista de dicts | `pytest tests/unit/v2/domain/test_processor.py -k adapted_subdomains` |
| **C9** | MUST | T3 | `doc_04b._section_adapted_objective` renderiza `##### D-10.2 —` heading + HL + bullets quando `adapted_subdomains` está presente | `pytest tests/unit/v2/output/test_doc_04b.py` |
| **C10** | MUST | T3 | Anchor validator: dado output com `Annex II Part II (6)` e source só com `Annex I`, devolve `(False, ['Annex II'])`; dado output com só `Annex I`, devolve `(True, [])` | `pytest tests/unit/v2/domain/test_anchor_validator.py -v` |
| **C11** | MUST | T2 | Spec `MAP-DOMAIN-ADAPT.md` tem `prompt_spec_version: 1.2`, secções `## Task Specifics`, `## HARD PROHIBITIONS`, `## OUTPUT ANATOMY`, `## Output Format` | inline yaml check |
| **C12** | MUST | T4 | 1 run de `scripts/d10_2_experiment.py --model gemma4:e2b` passa gates G1-G8 (incluindo anchor validation); meta.json gravado | `python scripts/d10_2_experiment.py --model gemma4:e2b` |
| **C13** | MUST | T3 | `pytest tests/unit/v2/` → ≥285 passed, 0 failed | `pytest tests/unit/v2/ 2>&1 \| tail -3` |
| **C14** | MUST | T2 | Ruff + mypy clean nos ficheiros tocados | `ruff check <files>` + `mypy <files>` |
| **C15** | SHOULD | T3 | Logs reorganizados: pasta `runs/<model>_<ts>/` com `{prompt.txt, response.raw.txt, response.parsed.txt, meta.json}` + `MANIFEST.md` actualizado | `ls` confirma |
| **C16** | SHOULD | T3 | `_render_subdomains` com `applicable_regs=None` mantém comportamento legacy | `pytest -k legacy` |
| **C17** | NICE | T1 | Spec bumpa `updated: 2026-07-18` | grep frontmatter |

## Quality dimensions

| Dim | Threshold |
|---|---|
| Correctness | 100% (C1-C12) |
| Pattern Compliance | 4/4 (C13-C17) |
| No Regressions | 100% (suite verde) |
| Data Integrity | 100% (HL verbatim + anchors validados) |

## Decisions

1. **Branch:** continuar `feature/aegis-p1-corr-022` (sem novo branch).
2. **HL extraction:** fail-hard (`HLExtractionError`).
3. **Anchor validation:** enforced como gate G8.
4. **Scope:** D-10.2 only. Restante fica para CORR-023.
5. **Trials:** 1 (user).
6. **Parser legacy:** manter `OutputParser` para backward compat.
7. **§3 verbatim:** sem truncation (default). Safety net: se artigo >5k chars, truncar a 5k + `(truncated)`.
8. **Fail-hard abort:** se `_extract_objective_paragraph` falhar para 1 sub-domínio, **aborta o MAP inteiro**.

## Risks

| Risco | Mitigação |
|---|---|
| LLM não cumpre formato | trials=1; se falhar C12, iterar no prompt (max 3); se persistir, escalar |
| Anchor validator false positives | normalizar antes de comparar |
| Artigos OJ verbatim incham prompt | safety net 5k chars/artigo |
| Loader verbatimparte | pre-flight check; fail-hard com mensagem útil |
| Doc 04b quebra downstream | manter `adapted_objective` (concat HLs) |
| Generalização para D-01..D-09 revelar formatos diferentes | não generalizar neste contract |

## Correction loop

- `max_cycles: 3`
- Por ciclo: Generator corrige → Evaluator re-avalia (fresh context)
- Após 3 ciclos sem PASS → STOP, reportar

## Sign-off

| Role | Status |
|---|---|
| user_approved | ✅ (2026-07-18, in-session) |
| generator_implemented | ✅ done (2026-07-18, run `gemma4_e2b_20260718T170725Z` — 9/9 gates PASS, 331 tests passed) |
| evaluator_verified | ✅ done (2026-07-18, collection-integrity check clean, 331/331 collected) |
| quality_log_updated | ✅ done (2026-07-18, `docs/CONTRACTS.md` CORR-022 section appended) |

## Execution plan

1. **Pre-flight:** confirmar branch + testes base verdes (285 passed).
2. **Grupo 1 (paralelo):** Fase A + B + C — 3 Generator subagents.
3. **Esperar todos Generator acabar.**
4. **Grupo 1 Evaluator:** fresh context, avalia C1-C11 + C13-C17.
5. **Grupo 2:** Fase D + E + F — 1 Generator.
6. **Grupo 2 Evaluator.**
7. **Fase H:** 1 run D-10.2 com e2b → avaliar C12.
8. **Commit se tudo PASS.**

---

# PHASE 3 — Output 3-blocos com Original/Adapted/Rationale/Adjustments/Considerations (2026-07-18)

## Driver

O e2b continua a usar o legacy `ADAPTED_OBJECTIVE/KEY_ADJUSTMENTS/CONFIDENCE` apesar do spec v1.2. As decisions do utilizador foram:

- **Output por sub-domínio = 3 blocos**: Generic/HL + GDPR + CRA.
- **Cada bloco tem 5 campos**: Original (verbatim), Adapted (ajustado), Rationale (porquê — perímetro + escala), Adjustments needed (alto-nível estratégico), Considerations (verbatim).
- **Drop** KEY_ADJUSTMENTS, **drop** CONFIDENCE.
- **Adapted** ajustado ao perímetro regulatório + escala/capacidade, **sem nomear empresa**.
- **Adjustments needed** = alto-nível estratégico (NÃO implementação Fase 2/3).
- **Considerations** = verbatim da fonte, todos os bullets.

## Output canónico (v1.3)

```
### D-XX.Y — <title>

**Generic Objective.**
- Original: <HL verbatim da fonte>
- Adapted: <HL adaptado ao perímetro regulatório + escala/capacidade, sem nomear empresa>
- Rationale: <porquê a adaptação — perímetro + escala>
- Adjustments needed: <acções alto-nível estratégicas, NÃO implementação concreta>
**Considerations.**
- <bullet 1 verbatim da fonte>
- <bullet 2 verbatim>
...

**GDPR Objective.**
- Original: <sub-SO GDPR verbatim>
- Adapted: <adaptado>
- Rationale: <porquê>
- Adjustments needed: <acções>
**Considerations.**
- <bullets verbatim do sub-SO GDPR>
...

**CRA Objective.**
- Original: <sub-SO CRA verbatim>
- Adapted: <adaptado>
- Rationale: <porquê>
- Adjustments needed: <acções>
**Considerations.**
- <bullets verbatim do sub-SO CRA>
...
```

## Worked example (D-10.2)

```
### D-10.2 — Audit Logging & Traceability

**Generic Objective.**
- Original: Audit logging and traceability are established through a layered audit-records architecture spanning compliance records with integrity and traceability, product-level technical documentation traceability, entity-level information security policy documentation, and AI-system event logging with retention floors.
- Adapted: Audit logging and traceability are established through a 2-layer audit-records architecture spanning entity-level compliance records (GDPR) and product-level technical documentation traceability (CRA), with log retention floors set per applicable regulation.
- Rationale: Source HL describes 4 layers (GDPR/CRA/DORA/AI_Act); for this regulatory perimeter only GDPR + CRA apply, so the architecture narrows to 2 layers. NIS2 is out-of-scope (T3-vs-text gap).
- Adjustments needed: Drop DORA Art. 9(4)(a) CIA+A policy layer and AI Act Art. 12(1)+(2) automatic event logging layer from scope. Preserve retention floors: GDPR 'as long as necessary' envelope + CRA '10 years or support period, whichever longer'.
**Considerations.**
- 4 of 5 regulations participate (GDPR, CRA, DORA, AI Act — NIS 2 is fully out-of-scope per CRDA T3-vs-text gap).
- CRDA-deep verified (6 pairs: 6 SAME — COMPLEMENTARY — no EQUAL, no CORRECTED, no GENUINE TENSION).
- Notable OJ-consistent reconciliation (NOT a tension) — floor-within-ceiling pattern (AI Act 6-month floor within GDPR 'as long as necessary' envelope).
- Scope caveats: GDPR ↔ CRA substantively scope-disjoint (different record types, different triggers).

**GDPR Objective.**
- Original: The controller and processor maintain compliance records in writing or in electronic form with integrity and traceability sufficient to demonstrate compliance and to support supervisory-authority inspections (Art. 30(3) + Art. 5(2) + Art. 31 GDPR), including records of processing activities, consent records, processor contract records, breach notification records, and DPIA records — made available to the supervisory authority on request (Art. 30(3)).
- Adapted: The controller and processor maintain compliance records in writing or in electronic form with integrity and traceability sufficient to demonstrate compliance and to support supervisory-authority inspections (Art. 30(3) + Art. 5(2) + Art. 31 GDPR). For a micro-entity with limited security FTE, this is operationalised through lightweight electronic records with a defined retention envelope.
- Rationale: Original is already applicable (GDPR is in scope); adaptation adds operationalisation guidance for micro-scale entities without naming the company.
- Adjustments needed: Define retention envelope explicitly. Establish record integrity controls (e.g., cryptographic hash on records). Document supervisory-authority response procedure.
**Considerations.**
- GDPR's anchor is the strictest for personal data on the at-rest dimension even where CRA state-of-the-art is the strictest in absolute terms.
- The `appropriate` threshold is anchored by the five Art. 32(1) preamble factors.
- Records include RoPA, consent, processor contracts, breach notifications, DPIA.

**CRA Objective.**
- Original: The manufacturer maintains the technical documentation (Annex VII §5-§8 CRA — harmonised standards applied, test reports, copy of the EU declaration of conformity, SBOM on MSA reasoned request), preserves the cybersecurity risk-assessment documentation (Annex VII §3 + Art. 13(4) sentence 1) during the support period (10 years or support period, whichever longer) with updates as appropriate, and ensures test reports demonstrating verification of conformity with Annex I Part I and Part II are part of the technical documentation and available on reasoned request from market surveillance authorities (Annex VII §6 + Annex I Part II (3) + Art. 13(22) CRA).
- Adapted: The manufacturer maintains the technical documentation (Annex VII §5-§8 CRA), preserves the cybersecurity risk-assessment documentation (Annex VII §3 + Art. 13(4) sentence 1) during the support period (10 years or support period, whichever longer), and ensures test reports demonstrating conformity with Annex I Part I and Part II are available on reasoned request from market surveillance authorities (Annex VII §6 + Annex I Part II (3) + Art. 13(22) CRA). For a micro-entity product, the technical documentation may leverage existing CI pipelines for test reports.
- Rationale: Original is already applicable (CRA is in scope); adaptation adds operationalisation guidance for micro-scale product manufacturers.
- Adjustments needed: Define support period explicitly. Implement SBOM generation as part of the build pipeline. Establish MSA-response procedure for reasoned requests.
**Considerations.**
- CRA's anchor is the strictest in absolute terms (state-of-the-art harmonised-standards floor).
- 10-year or support-period retention aligns with D-09.4 Records of Processing.
- Test reports (Annex VII §6) and risk-assessment documentation (Annex VII §3) are the operational artefacts that MSAs inspect.
```

## Phase 3 criteria (extend Phase 2)

| ID | Weight | Tier | Descrição |
|---|---|---|---|
| **P3-C1** | MUST | T3 | Spec v1.3 com 3-blocos × 5-campos + worked example |
| **P3-C2** | MUST | T3 | `_render_subdomains` passa, por sub-domínio: HL `**Objective.**` + Considerations verbatim + per-reg `**Objective.**` + Considerations verbatim |
| **P3-C3** | MUST | T3 | `OutputParserV3.parse(raw)` extrai 3 blocos por sub-domínio, cada um com 5 campos |
| **P3-C4** | MUST | T3 | `DomainResult.adapted_subdomains_v3` populated pelo processor |
| **P3-C5** | MUST | T3 | `doc_04b` renderiza 3 blocos × 5 campos quando `adapted_subdomains_v3` presente |
| **P3-C6** | MUST | T3 | Sem KEY_ADJUSTMENTS, sem CONFIDENCE no output spec |
| **P3-C7** | MUST | T4 | 1 run `scripts/d10_2_experiment.py --model gemma4:e2b` passa G1-G9 |
| **P3-C8** | MUST | T3 | Output D-10.2 tem 3 blocos × 5 campos cada |
| **P3-C9** | MUST | T3 | Sem conectivos proibidos (Furthermore, Moreover, Additionally, Also, In addition, Besides, On top of that, As well as) |
| **P3-C10** | MUST | T3 | Sem empresa (TinyTask, MICRO, SMALL, MEDIUM, LARGE, MAX, 0.85, 8 employees) |
| **P3-C11** | MUST | T3 | Anchor validation: todos os anchors no Adapted existem no Original |
| **P3-C12** | MUST | T3 | `pytest tests/unit/v2/` → ≥311 passed, 0 failed |
| **P3-C13** | MUST | T2 | Ruff + mypy clean nos ficheiros tocados |
| **P3-C14** | SHOULD | T3 | Output para D-10.1 e D-10.3 também cumpre a estrutura 3-blocos × 5-campos |

## Phase 3 gates (extend Phase 2)

| Gate | Descrição |
|---|---|
| G1 | Cada sub-domínio tem 3 blocos (Generic + GDPR + CRA) |
| G2 | Sem empresa |
| G3 | GDPR + CRA presentes como blocos próprios |
| G4 | Anchors legais em Original e Adapted |
| G5 | Sem conectivos proibidos |
| G6 | Sem headings genéricas |
| G7 | Parser V3 success |
| G8 | Anchor validation factual |
| **G9 (novo)** | Cada bloco tem os 5 campos (Original, Adapted, Rationale, Adjustments needed, Considerations) |

## Phase 3 Files to change

| File | Action |
|---|---|
| `src/aegis_phase1/v2/domain/prompts/MAP-DOMAIN-ADAPT.md` | rewrite spec v1.3 + worked example |
| `src/aegis_phase1/v2/domain/prompt.py` | modify `_render_subdomains` para passar HL verbatim + per-reg verbatim + considerations verbatim; adicionar `_extract_considerations` helper |
| `src/aegis_phase1/v2/domain/parser.py` | add `OutputParserV3` + `SubdomainAdaptationV3` + `ParseResultV3` (mantém V2 + legacy) |
| `src/aegis_phase1/v2/state.py` | add `DomainResult.adapted_subdomains_v3: list[dict]` |
| `src/aegis_phase1/v2/domain/processor.py` | usa OutputParserV3 |
| `src/aegis_phase1/v2/output/doc_04b.py` | renderiza 3 blocos × 5 campos |
| `tests/unit/v2/domain/test_parser.py` | novos testes V3 |
| `tests/unit/v2/domain/test_processor.py` | actualizar para V3 |
| `tests/unit/v2/output/test_doc_04b.py` | actualizar para V3 |
| `scripts/d10_2_experiment.py` | gate G9 + novos campos em meta.json |

## Phase 3 decisions

1. **Parser:** OutputParserV3 novo; V2 e legacy mantidos para backward compat.
2. **Considerations:** verbatim da fonte, todos os bullets (safety net 1500 chars por bloco se exceder).
3. **Drop:** KEY_ADJUSTMENTS e CONFIDENCE removidos do output spec.
4. **Adapted:** ajustado ao perímetro regulatório (quais regs aplicam) + escala/capacidade, sem nomear empresa.
5. **Adjustments needed:** alto-nível estratégico (NÃO implementação Fase 2/3).
6. **Worked example:** spec inclui exemplo D-10.2 completo.
7. **Sub-domínios:** só aplicáveis (filtro mantém).
8. **Trials:** 1.

## Phase 3 risks

| Risco | Mitigação |
|---|---|
| e2b pode não conseguir gerar estrutura rica (45 campos por D-10.2) | worked example concreto no spec; fallback para e4b se e2b falhar consistentemente |
| Considerations verbatim podem ser longas | safety net 1500 chars/bloco |
| Parser V3 pode falhar em malformações | tolerância: bloco parcial é aceite |
| Modelo pode incluir empresa no Adapted | gate G2 + system prompt reforçado |
| Generalização para D-01..D-09 | fora de scope |

## Phase 3 execution plan

1. Pre-flight: branch + testes base verdes.
2. Subagent A: spec v1.3 + prompt.py render.
3. Subagent B: parser V3 + state/processor/doc_04b (paralelo com A).
4. Subagent C: scripts/d10_2_experiment.py (gate G9).
5. Run benchmark D-10.2 com gemma4:e2b.
6. Se e2b falhar consistentemente (45 campos é muito): tentar e4b.
7. Commit se PASS.