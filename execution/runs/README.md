# Execution runs — observação dos modelos no pipeline AEGIS

Cada pasta em `execution/runs/` é o **output completo** de uma scout
(Doc 05 + os outros docs nos run-all), o **relatório de avaliação
automática** (`eval/checker_report.md`) e o apontador para o digest
correspondente. Os **prompts** enviados aos modelos estão em
`../prompts/`.

## Estrutura

```
execution/
├── prompts/                    ← os 6 prompts enviados aos modelos
│   ├── base_system_prompt.md
│   ├── P1B-LLM-01-INTERPRETATION.md
│   ├── P1B-LLM-02-RATIONALE.md
│   ├── P1C-LLM-01-…md
│   ├── P1C-LLM-02-…md
│   ├── P1C-LLM-03-…md
│
└── runs/                       ← este directório
    ├── README.md               ← (este ficheiro) — único índice
    ├── by_model/               ← cross-refs locais (<modelo>/<run>)
    │                              gerado por scripts/runs_tools/link_run.py
    ├── qwen38_27b_runall_1862843/
    ├── ornith9b_scout_1867097/
    └── …
```

**Importante:** `by_model/` é regenerado localmente — está em
`.gitignore` (symlinks relativos não portam entre máquinas). Para
reconstruir depois de um clone:

```bash
python -m scripts.runs_tools.link_run --all --rebuild
```

## Como é que uma pasta se chama

`<modelo>_<tipo>_<JOBID>/` — três peças separadas por `_`:

- **modelo**: `qwen3.8`, `granite4.2`, `nemotron-3.5-lightning`, …
  (canónico: ver tabela de aliases em
  `scripts/runs_tools/link_run.py` para `qwen38_27b` → `qwen3.8`).
- **tipo**: `scout` (Doc 05 só), `scout_full` (9 docs + xlsx),
  `runall` (pipeline completa com partida/redução/orientação).
- **JOBID**: 7 dígitos do SLURM (ex. `1862843`).

## Índice por data (todos os jobs conhecidos)

| Data       | Job      | Pasta                                  | Tipo        | Resultado (no cluster) |
|------------|----------|----------------------------------------|-------------|-------------------------|
| 2026-08-24 | 1847659  | `qwen35_27b_runall_1847659`            | runall      | completed (1h22)        |
| 2026-09-01 | 1862843  | `qwen38_27b_runall_1862843`            | runall      | completed (42min)       |
| 2026-09-01 | 1862819  | `qwen38_27b_scout_1862819`             | scout       | completed (18min)       |
| 2026-09-01 | 1867097  | `ornith9b_scout_1867097`               | scout       | completed (8min)        |
| 2026-09-01 | 1867082  | `gemma4_26b_scout_1867082`             | scout       | completed (12min)       |
| 2026-09-02 | 1867429  | `granite4_2_30b_scout_1867429`         | scout       | completed (36min)       |
| 2026-09-02 | 1867430  | `nemotron3_5_30b_scout_1867430`       | scout       | completed (15min)       |
| 2026-09-02 | 1867431  | `muse_glimmer_30b_scout_1867431`       | scout       | completed (33min)       |

## Índice por modelo (bucket `by_model/`)

Cada bucket é uma pasta com symlinks para todas as runs desse modelo.
A maioria tem 1-2 entradas; os scouts paralelos (2026-09-02) tinham
3 modelos a correr, 1 por bucket.

```
by_model/
├── gemma4_26b/         → 1 run
├── granite4_2_30b/     → 1 run
├── muse_glimmer_30b/   → 1 run
├── nemotron3_5_30b/    → 1 run
├── ornith9b/           → 1 run
├── qwen3.5/            → 1 run  (qwen35_27b_*)
└── qwen3.8/            → 2 runs (qwen38_27b_*)
```

Para acrescentar uma nova run a um bucket:

```bash
# 1. depois do job terminar e copiar outputs para esta pasta
# 2. registar (regenera symlink no bucket apropriado):
python -m scripts.runs_tools.link_run nova_pasta_<JOBID>
# 3. actualizar esta secção do README com uma linha nova
```

## Ficheiros por pasta de run

Cada pasta tem o seguinte:

```
<run>/
├── 04_Company_Context_Assessment.md      ← runall / scout_full
├── 04a_Architecture_DataInventory.md     ← runall / scout_full
├── 04b_Security_Posture.md               ← runall / scout_full
├── 04c_ThirdParty_Landscape.md           ← runall / scout_full
├── 04d_Org_Roles_RACI.md                 ← runall / scout_full
├── 05_Regulatory_Applicability.md        ← sempre
├── 06_Clause_Mapping_Matrix.md           ← runall / scout_full
├── 07_Structured_Compliance_Matrix.md    ← runall / scout_full
├── 07b_Proportionality_Profile.md        ← runall / scout_full
├── Case_01_Phase1.xlsx                   ← runall / scout_full
└── eval/
    ├── checker_report.md                 ← avaliação automática
    └── checker_report.json
```

O tipo `scout` (Phase 1B only) gera **só** `05_Regulatory_Applicability.md`
mais `eval/` (devido ao sbatch `--run-phase-1b`). Os outros tipos
geram tudo. Se a run abortou no meio, podes ver só parte dos ficheiros —
o checklist serve de pista rápida.

## Digests PT (notas manuais em linguagem simples)

`reports/digests/<modelo>_<JOBID>.md` — uma página cada, com a nota
0-5 e o resumo em português sem jargão. Antes estavam em
`execution/reports/digests/` (legado) — ver `reports/digests/README.md`
para a tabela actualizada.

## Como submeter uma scout

```bash
# scout Phase-1B only (gerava 1 doc só):
sbatch examples/deucalion/scout-bench-m-aegis.sbatch <modelo:tag>

# scout pipeline completa (~1h30, gera 9 docs + xlsx):
sbatch examples/deucalion/scout-bench-m-aegis-full.sbatch <modelo:tag>

# Para scouts em paralelo (cada um num nó diferente): usar o wrapper
# para gerar job-names únicos:
eval "$(scripts/scouts/scout-full-submit.sh nemotron3.5:30b)"
eval "$(scripts/scouts/scout-full-submit.sh granite4.2:30b)"
eval "$(scripts/scouts/scout-full-submit.sh ornith:9b)"
```

**Importante:** não submetas scouts sem o teu pedido explícito (regra
registada na memória `deucalion-job-submission-requires-explicit-ask`).
**Antes** de escolheres a partição, corre
`~/.zcode/skills/hpc-deucalion/examples/gpu-pick.sh <modelo:tag>` — a
tabela indica se vai para `dev-a100-40` (liberta a fila 80) ou
`dev-a100-80`. **Depois** de submeter, confirma no `squeue -o "%.6R"`
que cada scout caiu num nó distinto (colisão de porta 11434 se
acontecer).

## Manutenção

| Acção | Comando |
|-------|---------|
| Adicionar nova run | cp -r <output_dir> ./execution/runs/<pasta>/ && python -m scripts.runs_tools.link_run <pasta> |
| Reconstruir buckets | python -m scripts/runs_tools.link_run --all --rebuild |
| Regenerar relatório eval | PYTHONPATH=src python -m scripts.eval.generate_report --run-dir ./execution/runs/<pasta>/ --preproc preproc_out --output-dir ./execution/runs/<pasta>/eval --output-md ./execution/runs/<pasta>/eval/checker_report.md --output-json ./execution/runs/<pasta>/eval/checker_report.json |
