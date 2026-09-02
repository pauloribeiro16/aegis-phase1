# Execution runs — índice de scouts no Deucalion

Onde estão os ficheiros produzidos por cada run e que prompts os produziram.

## Caminhos

| O quê | Onde |
|---|---|
| Output no cluster | `/projects/F202512235CPCAA1/CyberMetric_Deucalion/aegis-phase1/output/scout_<JOBID>/` (ou `run_<model>_<JOBID>/` nos run-all) |
| Log SLURM | `<cluster>:.../aegis-phase1/slurm-scout-<modelo>-<JOBID>.{out,err}` |
| Log do run | `<cluster>:.../aegis-phase1/logs/scout_runs/scout_<model>_<JOBID>.log` |
| Mirror local | `../Deucalion/results/<modelo>_<JOBID>/` (fora do repo, pasta irmã) |
| Digest avaliado | `execution/reports/digests/<modelo>_<JOBID>.md` |
| Scorecard | `execution/reports/model_matrix.md` |

## Prompts utilizados (cópias em `execution/prompts/`)

Todas as chamadas LLM usam `base_system_prompt.md` + o prompt específico da fase:

| Fase | Prompt | Quando corre |
|---|---|---|
| Questão 1 (por regulação) | `P1B-LLM-01-INTERPRETATION.md` | Scout e run-all |
| Questão 2 (por regulação) | `P1B-LLM-02-RATIONALE.md` | Scout e run-all |
| Fase seguinte (por domínio ×10) | `P1C-LLM-01-OVERLAP-CLASSIFICATION.md` | Só run-all |
| REDUCE 1 | `P1C-LLM-03-STRATEGIC-SYNTHESIS.md` | Só run-all |
| REDUCE 2 | `P1C-LLM-02-COMPOUND-EVENT.md` | Só run-all |

## Runs completados

| JOB | Modelo | Tipo | Estado | Doc 05 (KB) | Digest |
|---|---|---|---|---|---|
| 1847659 | qwen3.5:27b | run-all | ✅ | — (ver mirror) | `qwen35_runall_1847659.md` |
| 1862819 | qwen3.8:27b | scout | ✅ | 42 | `qwen38_scout_1862819.md` |
| 1862843 | qwen3.8:27b | run-all | ✅ | — | `qwen38_runall_1862843.md` |
| 1867097 | ornith:9b | scout | ✅ | 50 | `ornith9b_scout_1867097.md` |
| 1867429 | granite4.2:30b | scout | ✅ | 24 | `granite4_2_scout_1867429.md` |
| 1867430 | nemotron-3.5:30b | scout | ✅ | 39 | `nemotron3_5_scout_1867430.md` |
| 1867431 | muse-glimmer:30b | scout | ✅ (1/2 regs) | 24 | `muse_glimmer_scout_1867431.md` |
| 1867082 | gemma4:26b | scout | ✅ (por avaliar) | 42* | — |
| 1867205 | granite4.2:30b (1ª tent.) | scout | ❌ walltime | — | — |
| 1866405/40/45/60/76 | gemma-4-31B (HF) | scout | ❌ provider bugs | — | — |

*Mirror: `../Deucalion/results/gemma4_26b_runall_1867082/05_Regulatory_Applicability.md`

## Runs falhados/cancelados (histórico)

| JOB | Motivo |
|---|---|
| 1846584 | gemma-4-31B: provider transformers ignorado (CORR-106 corrigiu; pivot para Ollama) |
| 1846591 | qwen3.8: Ollama 0.31.1 não conhece o renderer (resolvido com 0.32.13) |
| 1867124-26, 1867193-95 | scouts em paralelo no mesmo nó → conflito de porta 11434 (regra: sequencial) |
| 1867200 | muse: arquitectura desconhecida no 0.31.1 (resolvido com 0.32.13) |
| 1868526/27 | gpt-oss/qwen3.5:9b — submissão não solicitada, cancelados |

## Para recriar um scout

```bash
# no login node, dentro de aegis-phase1:
sbatch examples/deucalion/scout-bench-m-aegis.sbatch <modelo:tag>
```

Regras de ouro: sequencial (nunca 2 no mesmo nó), walltime ≥2× o scout
mais lento anterior, e após o run: copiar Doc 05 para o mirror + correr
`scripts/eval/generate_report.py --run-dir <mirror> --preproc preproc_out
--output-{dir,md,json} ... --use-parser-gate`.
