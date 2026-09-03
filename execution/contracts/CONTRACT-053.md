# CORR-053 — Make P1BLLM01Parser schema-tolerant (JSON-as-fallback)

**Date:** 2026-07-22
**Branch:** `feature/aegis-p1-corr-053` (from `feature/aegis-p1-corr-052`)
**Author:** Paulo Ribeiro (Mavis)
**Scope:** surgical — `markdown_parser.py` (P1BLLM01Parser), `invoker.py` (logging)

---

## Context

CORR-050 introduced markdown+regex parsing for P1B-LLM-01-INTERPRETATION.
CORR-052 tried to fix G6 by editing `base_system_prompt.md` rule 4. **It failed**:
the gemma4:e2b model continues to emit JSON, ignoring both the base_system rule
4 reformulation and the body-level "Do NOT emit JSON" instruction.

**Root cause (confirmed):** gemma4:e2b is too deeply trained to emit JSON for
"regulatory analysis" tasks. Prompt-only changes cannot re-train the model
in a single run.

**Strategy CORR-053:** make the parser **schema-tolerant** — accept BOTH markdown
AND JSON. The parser tries markdown first (the preferred format per the
contract); if that fails, falls back to JSON. This guarantees the pipeline
works regardless of what the model emits.

**No regression risk** for CORR-051 (other 4 LLMs) — only `P1BLLM01Parser` is
touched. The other 4 LLMs still go through the legacy JSON Schema validator
(unaffected).

---

## Plan

### T1 — JSON-as-fallback in `P1BLLM01Parser`

Modify `src/aegis_phase1/prompts_v2/markdown_parser.py` so that
`P1BLLM01Parser.parse(raw)` follows this decision tree:

```
1. Try markdown extraction (current behaviour).
   If success → return (Pydantic model, "")
2. If markdown fails → try JSON via RobustParser.
   - If JSON parses successfully AND validates against P1BLLM01Output schema
     → return (Pydantic model built from JSON, "")
   - If JSON parses but Pydantic validation fails → return (None, error_msg)
3. If both fail → return (None, "markdown parse failed: <err>; json parse failed: <err>")
```

The `P1BLLM01Output` Pydantic model already has all the fields needed. The JSON
path needs to:
- Strip envelope fields the LLM might emit (prompt_spec_id, schema_version,
  case_id, invocation_pattern) — the invoker injects them deterministically.
  OR: keep them and let Pydantic validate. Since they are model fields with
  defaults, the invoker will overwrite them anyway. **Keep them.**
- Map the JSON dict to P1BLLM01Output via `P1BLLM01Output.model_validate(json_dict)`.
  - Pydantic raises `ValidationError` if types are wrong. Catch and return
    meaningful error.

The JSON Schema for P1B-LLM-01 (from `output_schemas.yaml`) defines:
- `interpretations[]`: items with `entry_id`, `applicable`, `activation_rationale`,
  `layer0_refs[]` (minItems: 1), `company_fact_refs[]`.
- `derogations[]`: items with `entry_id`, `activation_verdict` (enum), `activation_rationale`,
  `layer0_refs[]` (minItems: 1).
- `status` (enum), `confidence` (enum).

These match the existing P1BLLM01 Pydantic models from CORR-050-T2.

### T2 — Add tests for JSON path

Extend `tests/unit/prompts_v2/test_markdown_parser_corr050.py` (or new file
`test_markdown_parser_corr053.py`) with tests:

- `test_json_fallback_parses_valid_json_output` — full valid JSON, no markdown
  → parser succeeds
- `test_json_fallback_validates_envelope_fields` — JSON includes prompt_spec_id
  etc. → parser still succeeds (Pydantic accepts)
- `test_json_fallback_rejects_invalid_status_enum` — JSON with `status: "BAD"`
  → parser returns error
- `test_json_fallback_rejects_missing_interpretations` — JSON without
  `interpretations` key → parser returns error
- `test_both_fail_returns_combined_error` — neither markdown nor JSON parses
  → parser returns (None, "markdown: ...; json: ...")
- `test_markdown_wins_over_json_when_both_present` — text with both
  ## sections and JSON → markdown path wins

### T3 — Instrument markdown path in `invoker.py`

Side-finding from CORR-052: when `parser.parse(raw)` fails, the invoker logs
`SCHEMA_ERROR` but **does not log the raw text** or the detailed `error_feedback`.
This makes debugging impossible.

Fix: add 5-10 lines to log raw + error_feedback when the markdown path fails.
Uses `self.llm_logger` (already a member of Phase1LLMInvoker).

```python
if parsed_model is None:
    # CORR-053: log raw + error_feedback for debugging
    if self.llm_logger:
        self.llm_logger.log({
            "event": "markdown_parse_error",
            "level": "ERROR",
            "timestamp": datetime.now(UTC).isoformat(),
            "spec_id": spec_id,
            "attempt": attempt,
            "model": self.model,
            "raw_response": raw,
            "raw_response_length": len(raw),
            "error_feedback": error_feedback,
        })
    validation_result = {...}
```

### T4 — Re-run `--run-phase-1b`

```bash
PYTHONPATH=src python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-phase-1b
```

**Expected:**
- 2/2 P1B-LLM-01 calls return `status="OK"` (the JSON the LLM emits IS valid
  P1B-LLM-01 schema-wise — it just doesn't have the `## Status` markdown section).
  The Pydantic model accepts the JSON, the invoker injects envelope, the
  markdown_parser returns the model.
- 4/4 P1B-LLM-02 calls still SCHEMA_ERROR (out of scope, CORR-051).

### T5 — Commit + report

3 commits on `feature/aegis-p1-corr-053`:
1. T1+T2: parser + tests
2. T3: invoker logging
3. T4+T5: run + report

---

## Quality gates

| Gate | Status target | How to verify |
|---|---|---|
| **G1** | P1BLLM01Parser.parse() returns Pydantic model for valid JSON | test_json_fallback_parses_valid_json_output |
| **G2** | Parser still handles markdown correctly (regression) | existing 7 tests pass |
| **G3** | Parser rejects invalid JSON (bad enum) | test_json_fallback_rejects_invalid_status_enum |
| **G4** | Parser rejects JSON missing required fields | test_json_fallback_rejects_missing_interpretations |
| **G5** | Markdown wins when both present | test_markdown_wins_over_json_when_both_present |
| **G6** | Both fail returns combined error | test_both_fail_returns_combined_error |
| **G7** | 7+6 = 13+ parser tests pass | pytest tests/unit/prompts_v2/test_markdown_parser_*.py |
| **G8** | 2/2 P1B-LLM-01 calls return OK or INSUFFICIENT_EVIDENCE in real run | run log inspection |
| **G9** | format-errors.jsonl has new entries with raw_response captured (T3) | format-errors.jsonl size grew |
| **G10** | trace_id captured for new run | logs/phase1/corr053_*.txt |
| **G11** | ci-csf + ci-frameworks PASS | hooks |
| **G12** | report at execution/reports/corr053_report.md | ls |

Expected: **12/12 PASS** — this should finally make G6 (P1B-LLM-01 OK) green.

---

## Files to edit

| Path | Action | Notes |
|---|---|---|
| `src/aegis_phase1/prompts_v2/markdown_parser.py` | MODIFY (T1) | P1BLLM01Parser: add JSON-as-fallback |
| `tests/unit/prompts_v2/test_markdown_parser_corr053.py` | NEW (T2) | 6 new tests |
| `src/aegis_phase1/prompts_v2/invoker.py` | MODIFY (T3) | log raw + error_feedback on markdown parse fail |
| `execution/CONTRACT-053.md` | NEW (T0) | this file |
| `execution/reports/corr053_report.md` | NEW (T5) | end-of-contract report |
| `logs/phase1/corr053_run_phase1b.log` | NEW (T4) | runtime log |
| `logs/phase1/corr053_langfuse_trace_id.txt` | NEW (T4) | trace |

**aegis-phase1 source:** `markdown_parser.py` (T1) + `invoker.py` (T3).
**Methodology-main/:** UNTOUCHED in this contract (CORR-052 already edited).

---

## Out of scope

- P1B-LLM-02, P1C-01/02/03 (legacy LLMs) — CORR-051
- Optimizing the JSON→Pydantic mapping for performance (premature)
- Adding unit tests for the other 4 LLMs' markdown parsers (don't exist yet)
