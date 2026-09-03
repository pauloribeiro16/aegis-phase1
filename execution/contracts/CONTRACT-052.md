# CORR-052 — Fix G9 (base_system_prompt forces JSON, model ignores body instructions)

**Date:** 2026-07-22
**Branch:** `feature/aegis-p1-corr-052` (a criar de `feature/aegis-p1-corr-050`)
**Author:** Paulo Ribeiro (Mavis)
**Scope:** surgical — edit `Methodology-main/00_METHODOLOGY/PROMPTS/base_system_prompt.md` rule 4 to be format-agnostic
**Estimated time:** 15 min (1 file edit + 1 re-run + report)

---

## Context (from CORR-050 G9 FAIL)

CORR-050 introduced a markdown+regex parsing path for `P1B-LLM-01-INTERPRETATION`.
The MarkdownParser + Pydantic models are wired correctly. 7/7 parser tests pass.

But the real `--run-phase-1b` produces 4× SCHEMA_ERROR for P1B-LLM-01. Investigation
(`ask 16058c2f`) revealed:

1. The `invoker` correctly skips `format=json_schema` for P1B-LLM-01 (so the Ollama
   constraint is not forcing JSON).
2. The `loader` correctly loads my edited P1B-LLM-01-INTERPRETATION.md (with
   "Do NOT emit JSON" in the body).
3. **But the loader prepends `base_system_prompt.md` to all 5 LLMs**, and rule 4
   of that file says:
   > **4. Output MUST conform to the JSON Schema provided in the `<output_contract>`**
   > **block. Post-generation validation is enforced.**
4. The `<output_contract>` block is **not injected anywhere in the code** (grep
   returned 0 matches in `src/`). So the LLM receives "obey the schema" + "what
   schema?" → emits JSON by default (model-side preference).
5. The body-level "Do NOT emit JSON" instruction is **overridden** by the
   `<non_negotiable_constraints>` rule 4 in the base system prompt.

The user (Paulo) correctly identified the wrong prompt: `base_system_prompt.md`,
not `P1B-LLM-01-INTERPRETATION.md`.

---

## Plan

### T1 — Edit `base_system_prompt.md` rule 4 (format-agnostic)

Replace rule 4 (lines 57-58) with a version that conditions the output format on
the prompt body:

```diff
- 4. Output MUST conform to the JSON Schema provided in the <output_contract>
-    block. Post-generation validation is enforced.
+ 4. Output format is determined by the prompt body:
+    - If the body specifies a JSON Schema in <output_contract> (legacy),
+      output MUST be valid JSON conforming to that schema.
+    - If the body specifies a markdown template (## Status / ## Interpretations
+      / ## Derogations style, with bullet lists), output MUST be plain markdown.
+    - Do NOT mix formats. Do NOT emit JSON wrappers (\`\`\`json...\`\`\`) inside
+      a markdown output, or markdown sections inside a JSON output.
+    - Post-generation validation enforces the chosen format.
```

**Effect on the 5 LLMs:**

| LLM | Body says | base_system rule 4 says | Result |
|---|---|---|---|
| P1B-LLM-01 (CORR-050) | markdown template (## sections) | "if body says markdown → markdown" | **emits markdown** |
| P1B-LLM-02 (legacy) | JSON Schema in <output_contract> | "if body says JSON → JSON" | emits JSON (unchanged) |
| P1C-LLM-01 (legacy) | JSON Schema | JSON | emits JSON (unchanged) |
| P1C-LLM-02 (legacy) | JSON Schema | JSON | emits JSON (unchanged) |
| P1C-LLM-03 (legacy) | JSON Schema | JSON | emits JSON (unchanged) |

**No regression risk for the 4 legacy LLMs** — they will continue to emit JSON.
**G9 should now pass for P1B-LLM-01** — body says markdown, base_system now allows
markdown.

### T2 — Re-run `--run-phase-1b`

```bash
PYTHONPATH=src python -m aegis_phase1.v2.runner --case cases/case1-tinytask --run-phase-1b
```

Expected: 2× P1B-LLM-01 calls return `status="OK"` (or `INSUFFICIENT_EVIDENCE`,
which is a valid status per the parser). 4× P1B-LLM-02 calls still SCHEMA_ERROR
(out of scope for CORR-052; that's CORR-051).

### T3 — Commit + report

Single commit on `feature/aegis-p1-corr-052` (1 branch per contract, AGENTS.md §10).

Note: `base_system_prompt.md` lives in `Methodology-main/` (separate repo).
The edit is **NOT committed to aegis-phase1** — same situation as CORR-050-T1.
The aegis-phase1 commit message references the change but the file itself is
out of repo scope.

---

## Quality gates

| Gate | Status target | How to verify |
|---|---|---|
| **G1** | base_system rule 4 mentions "Output format is determined by the prompt body" | `grep "Output format is determined" base_system_prompt.md` |
| **G2** | base_system rule 4 mentions "plain markdown" | `grep "plain markdown" base_system_prompt.md` |
| **G3** | base_system rule 4 mentions "Do NOT mix formats" | `grep "Do NOT mix formats" base_system_prompt.md` |
| **G4** | P1B-LLM-01 body still says "Do NOT emit JSON" (regression check) | `grep "Do NOT emit JSON" P1B-LLM-01-INTERPRETATION.md` |
| **G5** | Parser tests still 7/7 pass (regression check) | `pytest tests/unit/prompts_v2/test_markdown_parser_corr050.py -v` |
| **G6** | 2/2 P1B-LLM-01 calls return OK or INSUFFICIENT_EVIDENCE (not SCHEMA_ERROR) | run log inspection |
| **G7** | 4/4 P1B-LLM-02 calls still SCHEMA_ERROR (regression check, but expected — CORR-051 scope) | run log inspection |
| **G8** | trace_id captured for the new run | `logs/phase1/corr052_*.txt` |
| **G9** | ci-csf + ci-frameworks PASS | `bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh` |
| **G10** | report at `execution/reports/corr052_report.md` | `ls` |

Expected: **9/10 PASS** (G7 expected-FAIL because P1B-LLM-02 is out of scope).

---

## Files to edit (this contract)

| Path | State | Notes |
|---|---|---|
| `Methodology-main/00_METHODOLOGY/PROMPTS/base_system_prompt.md` | MODIFIED (T1) | outside aegis-phase1 repo, like CORR-050-T1 |
| `execution/CONTRACT-052.md` | NEW (T0) | this file |
| `execution/reports/corr052_report.md` | NEW (T3) | end-of-contract report |
| `logs/phase1/corr052_run_phase1b.log` | NEW (T2) | runtime log |

**aegis-phase1 source code: UNTOUCHED.** The fix is entirely in the prompt layer.
This is intentional — if the model now follows the body instruction, the markdown
parser path is finally exercised with real markdown input.

---

## Out of scope

- Fixing the 4 legacy LLMs (P1B-LLM-02, P1C-01/02/03) — that's CORR-051
- Making the parser schema-tolerant (JSON-as-fallback) — not needed if the
  model cooperates after the base_system fix
- Adding few-shot examples to the prompts — not needed if the instruction
  hierarchy is fixed
