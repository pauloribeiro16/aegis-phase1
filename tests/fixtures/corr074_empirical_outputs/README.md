# CORR-074 Empirical Outputs

This directory holds the **real LLM outputs** captured during CORR-074 dry-runs.
Each raw markdown file is the verbatim text the model emitted for a single
spec invocation, plus the structured parse result.

These fixtures serve two purposes:

1. **Regression contract.** Future parser changes run against these raws to
   ensure the parser still extracts them correctly.
2. **Audit trail.** Reviewers can compare what the model actually emitted
   against what the spec asked for, with no need to re-run the model.

## Layout

```
corr074_empirical_outputs/
├── README.md                  ← this file
├── m3/                        ← MiniMax-M3 (production provider)
│   ├── p1b01_raw.md
│   ├── p1b01_parse_result.json
│   ├── p1b02_raw.md
│   ├── p1b02_parse_result.json
│   ├── p1c01_raw.md
│   ├── p1c01_parse_result.json
│   ├── p1c02_raw.md
│   ├── p1c02_parse_result.json
│   ├── p1c03_raw.md
│   └── p1c03_parse_result.json
├── gemma4_e4b/                ← Ollama local gemma4:e4b
│   ├── p1b01_raw.md
│   └── p1b01_parse_result.json
├── gemma4_e2b/                ← Ollama local gemma4:e2b
│   ├── p1b01_raw.md
│   └── p1b01_parse_result.json
└── dry_run_scripts/           ← the dry-run scripts that produced the raws
    ├── dry_run_p1b01.py
    ├── dry_run_p1b02.py
    ├── dry_run_p1c01.py
    ├── dry_run_p1c02.py
    └── dry_run_p1c03.py
```

## Coverage

| spec_id | M3 | gemma4:e4b | gemma4:e2b |
|---|---|---|---|
| P1B-LLM-01-INTERPRETATION | ✅ | ✅ | ✅ |
| P1B-LLM-02-RATIONALE | ✅ | – | – |
| P1C-LLM-01-OVERLAP-CLASSIFICATION | ✅ | – | – |
| P1C-LLM-02-COMPOUND-EVENT | ✅ | – | – |
| P1C-LLM-03-STRATEGIC-SYNTHESIS | ✅ | – | – |

## Captured inputs

- **M3**: minimal payload (catalog paths only — M3 knows the catalog from training).
- **gemma4 (both)**: catalog content inlined in the `layer0_catalog` field (per L18 in `execution/LESSONS_LEARNED_CORR074.md`). Without inlining, gemma4 invents `entry_id`s.

## Captured run conditions

- All calls: `temperature=0.0`, `max_tokens=4096`.
- M3: `MINIMAX_MIN_INTERVAL=0` (no throttle for dry-runs), `https://api.minimax.io/anthropic` endpoint.
- Ollama: `num_ctx=128000`, `num_gpu=99`, `kv_cache_type=q8_0`, `localhost:11434`.
- Hardware: NVIDIA GeForce RTX 2070, 7.6 GiB VRAM.

## Reproducing a dry-run

```bash
cd /home/epmq-cyber/Área\ de\ Trabalho/projects/aegis-phase1

# M3
set -a && source .env && set +a
PYTHONPATH=src ../shared-venv-root/bin/python \
  tests/fixtures/corr074_empirical_outputs/dry_run_scripts/dry_run_p1b02.py

# Ollama (requires `ollama serve` running, models pulled)
PYTHONPATH=src ../shared-venv-root/bin/python \
  tests/fixtures/corr074_empirical_outputs/dry_run_scripts/dry_run_p1b01.py gemma4:e4b
```

The scripts write to `/tmp/` (not back into this directory) — copy the
results here if you want to refresh the regression baseline.

## Parse result schema

Each `*_parse_result.json` has the shape produced by the spec-specific
parser (`P1BLLM01Parser`, `P1BLLM02Parser`, etc.). Common fields:

- `parser_success: bool`
- `status: "OK" | "INSUFFICIENT_EVIDENCE" | "INDETERMINATE"`
- `confidence: "HIGH" | "MEDIUM" | "LOW"`
- per-section counts (e.g. `interpretations_count`, `derogations_count`)
- `notes_len: int`

When `parser_success=false`, `parse_error` carries the parser's feedback.
