# Execution runs — tudo o que os modelos produziram, num só sítio

Cada pasta em `execution/runs/` tem o **output completo** de um scout
(Doc 05 e, nos run-all, todos os documentos), o **relatório de avaliação
automática** (`eval/checker_report.md`) e apontadores para o digest com
notas. Os **prompts** usados estão em `execution/prompts/`.

## Como navegar

```
execution/
├── prompts/                     ← os 6 prompts enviados aos modelos
│   ├── base_system_prompt.md        (prâmbulo comum a todas as chamadas)
│   ├── P1B-LLM-01-INTERPRETATION.md (questão 1: interpretações/exclusões)
│   ├── P1B-LLM-02-RATIONALE.md      (questão 2: racional + lacunas)
│   ├── P1C-LLM-01-...md             (fase seguinte: por domínio)
│   ├── P1C-LLM-02-...md / -03-...md (reduce)
│   └── output_schemas.yaml — não copiado (specs ficam no Methodology-main)
├── runs/
│   └── <modelo>_<tipo>_<JOB>/
│       ├── 05_Regulatory_Applicability.md   ← output principal (sempre)
│       ├── 04*/06*/07*/...                  ← run-alls têm mais documentos
│       ├── run_log.txt                      ← log do job (quando existe)
│       └── eval/checker_report.md           ← avaliação automática
└── reports/digests/<modelo>_<JOB>.md        ← avaliação com notas 0-5
```

## Índice de runs

| Pasta (`execution/runs/…`) | Modelo | JOB | Tipo | Estado | Digest (notas) |
|---|---|---|---|---|---|
| `qwen38_27b_runall_1862843` | qwen3.8 27B | 1862843 | run-all ✅ | completo (REDUCE saltado — ver CORR-108) | `qwen38_runall_1862843.md` |
| `qwen38_27b_scout_1862819` | qwen3.8 27B | 1862819 | scout ✅ | 2/2 regulações | `qwen38_scout_1862819.md` |
| `qwen35_27b_runall_1847659` | qwen3.5 27B | 1847659 | run-all ✅ | completo (REDUCE saltado) | `qwen35_runall_1847659.md` |
| `ornith9b_scout_1867097` | ornith 9B | 1867097 | scout ✅ | 2/2 regulações | `ornith9b_scout_1867097.md` |
| `granite4_2_30b_scout_1867429` | granite 4.2 30B | 1867429 | scout ✅ | 2/2 regulações | `granite4_2_scout_1867429.md` |
| `nemotron3_5_30b_scout_1867430` | nemotron 3.5 30B | 1867430 | scout ✅ | 2/2 regulações | `nemotron3_5_scout_1867430.md` |
| `muse_glimmer_30b_scout_1867431` | muse glimmer 30B | 1867431 | scout ⚠️ | 1/2 regulações | `muse_glimmer_scout_1867431.md` |
| `gemma4_26b_scout_1867082` | gemma4 26B | 1867082 | scout ✅ | por avaliar | — |
| `qwen38_27b_runall_1868946` | qwen3.8 27B | 1868946 | run-all ⏳ | em curso (CORR-109 §9 + pipeline ponta-a-ponta) | — (sai a comparar pós-run) |
| `nemotron3_5_30b_scout_full_1869099` | nemotron 3.5 30B | 1869099 | scout-full ❌ | cancelado — modelo não está em cache do cluster e egress para ollama.ai bloqueado (2026-09-02 14:18) | — |
| `granite4_2_30b_scout_full_1869100` | granite 4.2 30B | 1869100 | scout-full ⏳ | em curso (cache confirmado, warm-up a 14:18) | — |
| `ornith-1_5_9b_scout_full_1869101` | ornith 1.5 9B | 1869101 | scout-full ❌ | cancelado — mesmo motivo (cache miss + sem egress) | — |

## Para recriar um scout

```bash
# Scout Phase-1B-only (modo antigo, ~30 min, 1 doc):
sbatch examples/deucalion/scout-bench-m-aegis.sbatch <modelo:tag>

# Scout pipeline completa (novo, ~1h30, gera os 9 docs + xlsx):
sbatch examples/deucalion/scout-bench-m-aegis-full.sbatch <modelo:tag>

# Para scouts em paralelo: usa o wrapper para distinguir os job-names
# (sem isto, todos os jobs aparecem como ``aegis_scout_full`` no squeue).
eval "$(scripts/scouts/scout-full-submit.sh nemotron3.5:30b)"
eval "$(scripts/scouts/scout-full-submit.sh granite4.2:30b)"
eval "$(scripts/scouts/scout-full-submit.sh ornith-1.5:9b)"
```

Regras: sequencial (nunca 2 scouts no mesmo nó), walltime ≥2× o scout
mais lento anterior. Após o run: copiar o Doc 05 para
`execution/runs/<modelo>_<JOB>/`, correr o checker (comando acima no
histórico do git) e escrever o digest.

## Estado do código da pipeline

O problema do "REDUCE saltado" (0 activações na fase por domínios) foi
corrigido no código — o leitor aceita agora os dois formatos que os
modelos produzem. **O próximo run-all já corre a pipeline completa**
(REDUCE incluído) com qualquer dos modelos.
