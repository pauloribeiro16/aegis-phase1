# Phase 1 v1.2 prompts_v2 — Usage Guide

The `prompts_v2` package integrates the canonical 5 Phase 1 LLMs (defined in
`../Methodology-main/00_METHODOLOGY/PROMPTS/`) into aegis-phase1.

## Quick start

```python
from aegis_phase1.prompts_v2 import get_invoker

invoker = get_invoker()
result = invoker.invoke("P1B-LLM-01-INTERPRETATION", {
    "case_id": "Case_01_TinyTask_SaaS",
    "lane_id": "GDPR",
    "applicable_regs": ["GDPR"],
    "classification": {"role": "Controller", "tier": "LOW"},
    "company_facts": {"sector": "saas", "employees": 8},
    "layer0_catalog": {"tipo2": [...]},
    "layer0_subdomain_refs": ["SubDomains/D-01.1.md"],
}, max_retries=2)

print(result["status"])              # "OK" | "INSUFFICIENT_EVIDENCE" | "FAILED_AFTER_RETRIES" | ...
print(result["parsed_output"])       # dict matching output_schemas.yaml schema
print(result["total_latency_ms"])     # float
```

## 5 Phase 1 LLMs

| ID | Invocation | Stage |
|---|---|---|
| `P1B-LLM-01-INTERPRETATION` | per_regulation | Phase 1B |
| `P1B-LLM-02-RATIONALE` | per_regulation | Phase 1B |
| `P1C-LLM-01-OVERLAP-CLASSIFICATION` | per_domain_lane | Phase 1C Map |
| `P1C-LLM-02-COMPOUND-EVENT` | global_reduce | Phase 1C Reduce (2nd) |
| `P1C-LLM-03-STRATEGIC-SYNTHESIS` | global_reduce | Phase 1C Reduce (1st) |

Removed (out of Phase 1 scope): LLM-H (gap aggregation → Phase 2/3).

## Logging

Every LLM call is logged to:
- `logs/phase1/llm-calls.jsonl` (full I/O, validation result, latency, tokens)
- `logs/phase1/format-errors.jsonl` (parse failures for gemma4:e2b)
- Python errors logged to `llm-calls.jsonl` with `event: "python_error"`

Logs are gitignored.

## Configuration

Read from environment:
- `OLLAMA_MODEL` (default: `gemma4:e2b`)
- `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- `OLLAMA_TIMEOUT` (default: 180 seconds)

Override in `.env`:
```
OLLAMA_MODEL=gemma4:e2b
OLLAMA_BASE_URL=http://localhost:11434
```

## Layer 0 path

The `prompts_v2` package reads from `../Methodology-main/00_METHODOLOGY/PROMPTS/`.
Override the default location by passing a custom `prompts_root` Path to `PromptLoader()`.

## Validation

The `Phase1Validator` (returned by `get_validator()`) validates outputs against:
1. JSON Schema (from `output_schemas.yaml`)
2. Layer 0 file existence (every `layer0_refs[]` path must resolve)
3. No re-classification (P1C-LLM-01 specific: `layer0_relationship` must be in the allowed enum)

Validation failures cause `status: "SCHEMA_ERROR"` or a non-empty `validation["schema_errors"]` / `validation["citation_errors"]`.

## Robust parsing

`gemma4:e2b` is a small quantized model and may produce non-conforming JSON.
The `RobustParser` tries 5 strategies in order:
1. `json_strict` — pure JSON parsing
2. `extract_markdown_block` — ```yaml ... ``` code block
3. `extract_first_object` — first balanced `{...}`
4. `extract_first_array` — first balanced `[...]` (prioritized when input contains `[`)
5. `repair_common_errors` — fix single quotes + trailing commas

If all strategies fail, status becomes `PARSE_ERROR` and the raw response is logged to `format-errors.jsonl`.

## Node integration example

```python
# In src/aegis_phase1/nodes/c01_complementarity.py
def c01_complementarity_v2(state: dict) -> dict:
    from aegis_phase1.prompts_v2 import get_invoker
    invoker = get_invoker()
    out = invoker.invoke("P1C-LLM-01-OVERLAP-CLASSIFICATION", {...})
    return {"c01_v2_status": out.get("status"), ...}
```

## Tests

```bash
# Run unit tests (no Ollama needed)
PYTHONPATH=src pytest tests/unit/prompts_v2/ --ignore=tests/unit/prompts_v2/test_smoke_e2e.py -v

# Run smoke test (requires Ollama with gemma4:e2b)
PYTHONPATH=src pytest tests/unit/prompts_v2/test_smoke_e2e.py -v
```