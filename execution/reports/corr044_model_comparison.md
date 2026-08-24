# CORR-044 — Model comparison: gemma4:e2b vs gemma4:e4b (12b aborted)

**Date:** 2026-07-22 13:17-13:33 (e4b run) / 12b aborted after 25min
**Branch:** `feature/aegis-p1-corr-044`
**Runs:**
- e2b: `logs/phase1/corr044_run_traced_v5.log` (13:03-13:12)
- e4b: `logs/phase1/corr044_e4b.log` (13:17-13:33)
- 12b: `logs/phase1/corr044_12b_ABORTED.log` (13:34-13:58, killed — see below)
- Outputs snapshotted at: `output/phase1/run_e2b/` and `output/phase1/run_e4b/`

## Test setup

| Model | Size on disk | Context | Run time | Status |
|-------|--------------|---------|----------|--------|
| `gemma4:e2b` | 7.2 GB | default | ~9 min | complete, 38 subdomains, 20 LLM calls |
| `gemma4:e4b` | 9.6 GB | default | ~16 min | complete, 38 subdomains, 20 LLM calls |
| `gemma4:12b` | 7.6 GB | default | 25 min for D-01 only | **ABORTED** (would take 2-3h) |

All runs used the same `--run-all-traced --case cases/case1-tinytask` path,
same MOCK_LLM=false, same gemma4:e2b→e4b→12b model swap.

## Quantitative comparison

| Metric | e2b | e4b | Delta |
|--------|-----|-----|-------|
| Pipeline runtime | 9 min | 16 min | +78% (1.78x) |
| Total tokens | 63 108 | 74 104 | +17% |
| Total LLM time (sum) | 259 482 ms | 540 524 ms | +108% (2.08x) |
| Avg LLM latency | 12 974 ms | 27 026 ms | +108% (2.08x) |
| LLM calls (count) | 20 | 20 | 0 |
| OTel transient errors | 0 | 0 | 0 |
| concatenate subdomains | 38 | 38 | 0 |
| Doc 06 clause rows | 174 | 174 | 0 |
| Doc 07 subdomain rows | 38 | 38 | 0 |
| Doc 07b D-rows | 93 | 93 | 0 |

## Per-doc size comparison (e2b vs e4b)

| Document | e2b size | e4b size | Δ |
|----------|---------:|---------:|---:|
| 04_Company_Context_Assessment | 10 906 | 10 906 | +0% |
| 04a_Architecture_DataInventory | 5 584 | 5 826 | +4% |
| **04b_Security_Posture** | **145 111** | **158 945** | **+10%** |
| 04c_ThirdParty_Landscape | 8 499 | 8 499 | +0% |
| 04d_Org_Roles_RACI | 19 363 | 19 274 | -0% |
| 05_Regulatory_Applicability | 12 311 | 12 343 | +0% |
| 06_Clause_Mapping_Matrix | 34 879 | 34 879 | +0% |
| 07_Structured_Compliance_Matrix | 15 894 | 15 848 | -0% |
| 07b_Proportionality_Profile | 22 419 | 22 377 | -0% |

**Doc 04b é o único que difere significativamente** (+10% em e4b). É o doc
com mais prosa gerada por LLM (~145KB vs ~10-30KB dos outros). O e4b gera
texto mais longo e específico (ver diff abaixo).

## Structural diff (ignoring timestamps)

| Document | Diff lines (sem timestamps) | What differs |
|----------|---:|---|
| **Doc 06** (deterministic — clause→subdomain mapping) | **0** | **idêntico** |
| **Doc 07** (LLM narrative §6.1 + structural matrix) | **4** | só o parágrafo §6.1 (narrative) |
| **Doc 07b** (LLM-heavy per-subdomain proportionality) | **4** | só metadata timestamps |
| **Doc 04b** (LLM-heavy per-domain assessment, 38 domains) | **2209** | prosa dos 10 domínios + parágrafos narrativos |

**Conclusão chave:** A **estrutura** (tabelas, contagens, mapeamentos) é
**idêntica** entre e2b e e4b. A única diferença significativa está no
**texto livre narrativo** gerado pelo LLM, e mesmo aí o e4b apenas
produz versões mais longas e específicas (não contradiz o e2b).

## Exemplo de diff (Doc 04b §3, D-02 Encryption)

**e2b (conciso, ~1 parágrafo por sub-domínio):**
> Adapted: Data stored in systems must be protected from unauthorized
> access through appropriate technical measures, primarily encryption
> using suitable keys, tailored to identified risks and the current
> state of the art.
>
> Rationale: Adapts the requirement to focus on capability alignment for
> small entities while maintaining risk-based approach required by
> regulations.
>
> Adjustments needed: Implement a foundational encryption strategy
> covering all persistent storage locations.

**e4b (mais detalhado, mais prescriptive):**
> Adapted: Personal data stored electronically, whether in databases
> or file systems, must be rendered unintelligible to unauthorized
> parties using strong encryption techniques. This measure must align
> with assessed organizational risks and industry best practices.
>
> Rationale: The micro scale and tech sector nature imply reliance on
> digital storage, making data at rest encryption critical for
> compliance (GDPR/CRA) and foundational security hygiene.
>
> Adjustments needed: Implement mandatory full disk and database
> encryption; establish a rigorous key management policy separating keys
> from the data store.

Ambos cumprem o mesmo objectivo (recomendar encryption + KMS); o e4b
produz texto mais rico e actionable.

## 12b — aborted

O gemma4:12b é impraticável para a pipeline traced:
- 12 min para D-01 (e2b: ~25s, e4b: ~50s por D-XX).
- Estimativa 2-3h para o run completo, com risco de OOM (RAM do
  sistema, Ollama).
- Log: `logs/phase1/corr044_12b_ABORTED.log` (1 MAP done, 0 P1B, 0 P1C).

**Recomendação:** Não usar 12b para runs traced. O 26b seria
proporcionalmente ainda pior.

## Verdict — gemma4:e2b vs gemma4:e4b

**Diferença NÃO é justificável** para o caso de uso CORR-044:

1. **Estrutura idêntica** (mesmas tabelas, contagens, mappings). G4, G7, G8
   passam em ambos com os mesmos números (38 subdomains, 174 clauses, 93
   D-rows).
2. **Texto narrativo mais rico no e4b** (+10% no Doc 04b) é nice-to-have,
   não muda compliance substance (mesmas regulamentações citadas, mesmas
   ações propostas, mais detalhamento).
3. **Custo 1.78x em tempo** + **2.08x em LLM latency** + **17% mais
   tokens** vs ganho marginal de qualidade.
4. **Modelos e2b e e4b são ambos "efficient" gemma4 variants** — o
   e2b foi escolhido em CORR-042 precisamente porque o prompt structure
   está afinado para o seu output (RobustParser 5-strategy fallback
   para os seus format bugs específicos).

**Decisão recomendada:** manter `gemma4:e2b` como Phase 1 canonical
model. O e4b pode ser útil para:
- Review de outputs críticos (cross-check com 2º modelo)
- Casos onde a prosa detalhada é valor (e.g. auditoria externa)
- Smoke tests de "what would a bigger model say"

**Não usar para runs de produção** dado o custo quase 2x sem ganho
substantivo em compliance structure.

## OpenTelemetry stability

Ambos os runs completaram com **0 OpenTelemetry transient errors**,
confirmando que a limpeza de disco (Paulo) resolveu o problema do OTLP
server. O trace_id `ee184cd1f11094708244c268a34af3ce` (e2b v5) está
presente no Langfuse (confirmado via `traces?orderBy=timestamp.desc`).
O trace_id `fbfa3fb4adcf9ce14d2caec8a50a48b5` (e4b) também.
