# LESSONS LEARNED — CORR-074 (Markdown-flexible redesign of the 5 P1 prompt specs)

**Status:** POST-MORTEM (2026-08-05)
**Branch:** `feature/aegis-p1-corr-074-markdown-flexible`
**Base:** HEAD of `main` post-CORR-072 merge
**Author:** opencode / MiniMax-M3
**Contract reference:** [`execution/CONTRACT-074.md`](CONTRACT-074.md) (capabilities data layer) is a **sibling** contract — CORR-074 (this retrospective) is the markdown-parser redesign that ran in parallel.

---

## 1. Summary

CORR-074 was a propagation contract: starting from the original P1B-LLM-01 redesign (markdown-flexible output, tolerant parser, verdict normaliser), it propagated the same pattern to the four remaining P1 specs — `P1B-LLM-02-RATIONALE`, `P1C-LLM-01-OVERLAP-CLASSIFICATION`, `P1C-LLM-02-COMPOUND-EVENT`, `P1C-LLM-03-STRATEGIC-SYNTHESIS`. Two worked examples were fixed because they violated `minItems: 2` (`compound_event_supply_chain.yaml`, `strategic_synthesis_3_lane.yaml`). Each spec was validated with **one** dry-run M3 call — no full pipeline runs. Final state: **782 passed / 12 failed** (12 pre-existing infra failures on `main`, Ollama/Langfuse). All 5 specs gained dedicated Pydantic models in `state.py`, dedicated parser classes (`P1BLLM01Parser` … `P1CLLM03Parser`), empirical regression tests, and three shared helpers (`_parse_status_prose`, `_extract_field_bt`, `_extract_bracketed_list_field`) extracted into base `MarkdownParser`.

---

## 2. Lessons — Parser Design

### L1: Verdict normalisers are non-negotiable

LLMs emit verdict variants that the strict Pydantic enum will reject out-of-hand:

| Spec | What M3 emits | Strict token |
|------|---------------|--------------|
| P1B-01 | `YES`, `APPLIES (YES)`, `APPLIES (PARTIAL)`, `NOT ACTIVATED`, `NOT ACTIVATED ` (trailing space) | `APPLIES` / `PARTIAL` / `NOT_ACTIVATED` |
| P1C-01 | `Severity: critical`, `CRITICAL`, `critical` | `CRITICAL` |
| P1C-03 | `Lane: high`, `Lane: medium`, `Lane: low` | `HIGH` / `MEDIUM` / `LOW` |

The parser must have `_VERDICT_NORMALISE_*` dicts that map aliases to the strict enum tokens **before** Pydantic validation. Otherwise Pydantic raises `ValidationError` and the whole call fails (the spec returns `None` and the pipeline falls back to `GenericMarkdownOutput`).

### L2: Capture heading verdicts in the regex, not in body field extraction

The `### ENTRY_ID — VERDICT` heading line is the most reliable place to extract verdict — body fields are noisy (M3 sometimes puts verdict prose mid-bullet). Use a regex with a **capturing group** for the verdict:

```python
r"^###\s+(?:(INT-\d+)|([A-Z][A-Z0-9_]+(?:-[A-Z0-9_]+)*))(?:\s*[—\-:]\s*\*{0,2}([A-Z_]+(?:\s+[A-Z_]+)*?)\s*(?:\([^)]*\)\s*)?\*{0,2})?\s*$"
```

Pass the **heading line** (not the body) to the `_SUBSEC_*` regex matchers.

### L3: `_parse_status_prose` must accept BOTH bullet and prose forms

M3 emits `## Status` as prose (`OK — HIGH confidence. <justification>`). Legacy tests use bullets (`- status: OK`). The parser must try the bullet form first (`re.search(r"-\s*status:\s*(\w+)", text)`), then fall through to the prose regex (`re.search(r"##\s+Status\s*\n+(.+?)(?=\n##|\Z)", text, re.DOTALL)`), returning the first non-None match. Do not force one shape on callers — both shapes appear in M3 output across versions.

### L4: Optional sections need Pydantic defaults, not None

`## Notes` is optional. If the parser sets `model.notes = None`, downstream renderers crash on `notes.strip()`. Use:

```python
class MyModel(BaseModel):
    notes: str = ""   # default, not Optional[str]
```

If the section is absent, leave the default; only set `model.notes = extracted_text` if extraction succeeded.

---

## 3. Lessons — Spec Design

### L5: Specs that describe "structured output" without prescribing format leave the LLM guessing

Always prescribe the markdown shape **AND** the verdict vocabulary. Without `## Status / ## Interpretations / ## Derogations / ## Notes` in the spec, M3 emitted JSON — because the JSON Schema at `output_schemas.yaml` was the only format hint. P1B-02's first attempt failed: spec said "structured output" but didn't list section headings; M3 chose JSON. After adding `## Status`, `## Interpretations`, `## Notes` to the spec, M3 switched to markdown on the next dry-run.

### L6: Worked examples that violate the spec teach the LLM to violate the spec

Two examples contradicted their own schema:

| File | Violation | Fix |
|------|-----------|-----|
| `examples/compound_event_supply_chain.yaml` | `regulations_triggered: ["GDPR"]` (1 item, schema `minItems: 2`) | Expanded to `["GDPR", "DORA"]` |
| `examples/strategic_synthesis_3_lane.yaml` | `affected_sub_domains: ["D-04.3"]` (1 item, schema `minItems: 2`) | Expanded to `["D-04.3", "D-05.1"]` |

Both contradicted the spec they were meant to illustrate. **Always validate examples against the schema** (run `python -c "import yaml, jsonschema; jsonschema.validate(yaml.safe_load(open(f)), yaml.safe_load(open('schema.yaml')))"`) before publishing. M3 uses examples as few-shot priors; bad examples → bad outputs.

### L7: Don't mix JSON and markdown in the same spec contract

The original P1B-02 spec asked for JSON. Adding a `## Output Format (mandatory)` markdown section while **keeping** the JSON Schema reference confuses both the LLM and the parser — M3 emitted JSON wrapped in a `## Output` heading, which neither parser could handle. Pick **ONE** format. CORR-074 picked markdown for all 5 specs (matches P1B-01 baseline).

---

## 4. Lessons — Process

### L8: One dry-run M3 call before any full pipeline run

CORR-074 used single-shot dry-runs per spec: 5 dry-runs total (one per spec), ~5-25s each (P1B-01 slowest at ~25s, P1C-01 fastest at ~5s), 1 M3 round-trip per spec, total dry-run budget **~80s** — vs. ≥160s for a full P1B+P1C run with the same signal. The single-shot gives clearer per-spec signal because it isolates the prompt's effect from the rest of the pipeline state. **Always** start with one dry-run before considering any larger validation.

### L9: Empirical parser tests with recorded raw output

`tests/unit/v2/test_p1X_markdown_parser_corr074.py` contains the actual raw M3 output (verbatim copy from the dry-run) and asserts the parser extracts it correctly:

```python
RAW_M3_OUTPUT = """## Status\nOK — HIGH confidence. ...\n\n### GDPR-CL01 — APPLIES (PARTIAL)\n**Interpretation:** ..."""
def test_p1c02_parses_gdpr_cl01():
    result = P1CLLM02Parser().parse(RAW_M3_OUTPUT)
    assert result.entries[0].entry_id == "GDPR-CL01"
    assert result.entries[0].verdict == "PARTIAL"  # normalised
```

These are the **regression contract** — if M3 changes behaviour, the test catches it deterministically. Without the verbatim copy, future M3 drift would silently break the parser.

### L10: Throttle M3 + base URL = `https://api.minimax.io/anthropic`

Anthropic-compatible endpoint. `MINIMAX_MIN_INTERVAL` env var (default 5s) controls rate-limit. For dry-runs, set to `0` (no throttle, fastest). For production, leave default 5s or increase to 10s if hitting 429s. The base URL is **not** `api.anthropic.com` — it's the Mavis gateway at `api.minimax.io`. Hardcoding the wrong URL is the #1 cause of M3 silent failures.

### L11: Sub-agent instructions must explicitly say "do NOT run the full pipeline"

Sub-agents default to running full validation if not told otherwise. Always include in the sub-agent brief: *"DO NOT run `--run-all` or any full-pipeline flag. Only ONE M3 dry-run call. Return the raw output verbatim."* Without this clause, a sub-agent may consume 5+ minutes running the full pipeline and waste the entire dry-run budget on a single prompt iteration.

---

## 5. Lessons — Architecture

### L12: `GenericMarkdownOutput` is a fallback, not a destination

All 4 secondary specs (P1B-02, P1C-01/02/03) used to route through `GenericMarkdownParser` → `GenericMarkdownOutput`, which stores section bodies verbatim in `sections[name]`. This is fine as a **stepping stone**, but each spec with structured content deserves its own Pydantic model + dedicated parser. Otherwise renderers can't access typed fields (`sub_domains`, `risk_level`, `implications`) and the structured data is lost — renderers fall back to dumping the raw markdown, which defeats the point.

### L13: Shared helpers in base `MarkdownParser`, spec-specific logic in subclasses

`_parse_status_prose`, `_extract_field_bt`, `_extract_bracketed_list_field` are `@staticmethod` / `@classmethod` of base `MarkdownParser`. Each subclass overrides only `SECTION_PATTERNS`, `_SUBSEC_*` regexes, `_VERDICT_NORMALISE_*` dicts, and `_build_model()`. First 2 specs (P1B-01, P1B-02) tolerated inline helpers, but by P1C-01 extraction was obvious. Refactor on the **third** spec — premature abstraction is worse than brief duplication.

### L14: Pydantic `min_length` is a parser-side contract enforcer

When the spec says "implications must span ≥2 sub-domains", put `min_length=2` on the Pydantic field. If M3 violates, the parser returns `None` instead of silently accepting partial data. Caught the P1C-03 implication-validation issue early in dry-runs — M3 first emitted a single implication, parser rejected it, prompt was tightened to require ≥2.

---

## 6. Lessons — Tooling

### L15: `git diff --stat` before dispatching any sub-agent

Sub-agents can report "3 gaps" against an outdated view of the worktree. Always check `git status --porcelain` and `git diff --stat` first to know exactly what's modified. Saved time when the P1B-02 sub-agent reported P1B-01 gaps that had already been fixed in the prior commit.

### L16: `_archive/corr061/markdown_parser.py` is the canonical parser module despite its archive path

It is referenced via `prompts_v2/markdown_parser.py:MARKDOWN_PARSERS` (re-export registry). **Don't move it** — the import path is load-bearing. The `_archive/` prefix is historical: it was archived when CORR-061 was superseded, but the parser survived via the registry re-export. If a future contract renames this file, the registry in `prompts_v2/markdown_parser.py` must be updated in the same commit.

---

## 7. Recommendations for future CORR contracts

- **Always** specify format AND vocabulary in the spec. Don't trust the LLM to figure out which shape to emit.
- **Always** validate worked examples against the JSON Schema before adding to `examples/`.
- **Always** keep parser + spec in the same contract — they drift otherwise (P1B-01 baseline took 3 iterations to converge).
- **Always** extract shared helpers to base class on the **third** spec; the first 2 tolerate duplication.
- **Always** use **sequential** sub-agents when touching overlapping files (`state.py`, `markdown_parser.py`) — parallel sub-agents raced each other on registry edits in the initial attempt and cost 30 minutes in merge conflicts.
- **Always** validate parser changes with the full `tests/unit/v2/` suite — the 12 pre-existing failures are noise (infra: Ollama/Langfuse); look at NEW failures only.
- **Always** set `MINIMAX_MIN_INTERVAL=0` for dry-runs; restore default (5s) for production.
- **Never** mix JSON and markdown in the same spec contract (L7).
- **Never** accept partial Pydantic models with `None` for optional sections (L4).

---

## 8. Files changed in CORR-074

Total: 5 specs + 4 parser classes + 2 example fixes + 1 Pydantic model expansion = **12 files** (7 in-tree + 5 in sibling repo).

### aegis-phase1 (in-tree)

- `src/aegis_phase1/v2/state.py` — 5 Pydantic model groups + ~25 enums (InterpretationEntry, RationaleEntry, OverlapClassificationEntry, CompoundEventEntry, StrategicSynthesisEntry)
- `src/aegis_phase1/_archive/corr061/markdown_parser.py` — 4 parser classes (`P1BLLM02Parser`, `P1CLLM01Parser`, `P1CLLM02Parser`, `P1CLLM03Parser`) + shared helpers + `MARKDOWN_PARSERS` registry updates
- `tests/unit/v2/test_p1b01_markdown_parser_corr074.py` — NEW, 16 regression tests
- `tests/unit/v2/test_p1b02_markdown_parser_corr074.py` — NEW, 12 regression tests
- `tests/unit/v2/test_p1c01_markdown_parser_corr074.py` — NEW, 14 regression tests
- `tests/unit/v2/test_p1c02_markdown_parser_corr074.py` — NEW, 11 regression tests
- `tests/unit/v2/test_p1c03_markdown_parser_corr074.py` — NEW, 13 regression tests

### Methodology-main (sibling repo)

- `00_METHODOLOGY/PROMPTS/P1B-LLM-01-INTERPRETATION.md` — v1.0.0 → v1.1.0
- `00_METHODOLOGY/PROMPTS/P1B-LLM-02-RATIONALE.md` — v1.0.0 → v1.1.0
- `00_METHODOLOGY/PROMPTS/P1C-LLM-01-OVERLAP-CLASSIFICATION.md` — v1.0.0 → v1.1.0
- `00_METHODOLOGY/PROMPTS/P1C-LLM-02-COMPOUND-EVENT.md` — v1.0.0 → v1.1.0
- `00_METHODOLOGY/PROMPTS/P1C-LLM-03-STRATEGIC-SYNTHESIS.md` — v1.0.0 → v1.1.0
- `00_METHODOLOGY/PROMPTS/examples/compound_event_supply_chain.yaml` — `regulations_triggered`: 1 → 2 items
- `00_METHODOLOGY/PROMPTS/examples/strategic_synthesis_3_lane.yaml` — `affected_sub_domains`: 1 → 2 items

Total LOC: ~1,850 (parsers ~900, tests ~650, spec edits ~300).

---

## 9. Sequence followed

CORR-074 used **sequential** sub-agents (parallel was tried and abandoned — see L13):

1. **P1B-01 baseline** (already in main) → 16 regression tests.
2. **P1B-02 first** — simplest `per_regulation` shape, no nested fields.
3. **P1C-01 second** — `per_domain_lane`, nested pairs `reg→domain`.
4. **P1C-03 third** — `global_reduce`, depends on P1C-01 shape, implications ≥2.
5. **P1C-02 fourth** — `global_reduce`, depends on P1C-03 verdict vocabulary.
6. **Worked-examples fix** (parallel with P1B-02 — no file overlap, safe).

Each sub-agent did **exactly one M3 dry-run** and returned raw output. The orchestrator compared raw output against the parser's expectations: ✅ accept (parser extracted all fields, enums normalised) or ❌ reject + tighten (added section heading, added verdict vocab token, or fixed schema). After 1-2 tightenings per spec, all 5 converged. Total iterations: 5 specs × ~1.5 tightenings ≈ 8 M3 calls including the dry-runs.

---

## 10. References

- [`execution/CONTRACT-074.md`](CONTRACT-074.md) — sibling capabilities data-layer contract (different scope)
- [`src/aegis_phase1/_archive/corr061/markdown_parser.py`](../../src/aegis_phase1/_archive/corr061/markdown_parser.py) — canonical parser module (see L16)
- [`tests/AGENTS.md`](../../tests/AGENTS.md) — pre-existing infra failure notes (the 12 unchanged failures)
- [`AGENTS.md`](../../AGENTS.md) — naming conventions, framework policy
---

## 10. Lessons added post-Ollama validation (2026-08-05)

Empirical validation with `gemma4:e4b` and `gemma4:e2b` against P1B-LLM-01 surfaced 3 new lessons that the M3-only validation had missed.

### L17: `prompts_v2/loader.py` `# TASK` suffix overrides the spec body

The loader hardcodes the user prompt suffix as:
```python
user = f"# INPUTS for {spec_id}\n\n```json\n{inputs_json}\n```\n\n# TASK\n\nExecute the task defined in the system prompt. Return output matching the JSON Schema in `output_schemas.yaml#{spec_id}`."
```

This suffix says **"Return output matching the JSON Schema"** regardless of what the spec body declares. M3 ignored this and followed the `## Output Format (mandatory)` block in the body. Gemma 4 followed the suffix literally and emitted JSON.

**Fix:** detect `## Output Format (mandatory)` (or `## Output Format`) in the spec body and emit a markdown-aware suffix instead. The detection is one substring check; the cost is negligible.

Citation: `src/aegis_phase1/prompts_v2/loader.py:174-194` (CORR-074 post-Ollama fix).

### L18: Catalogs must be INLINED in the input, not referenced by path

When the input passes only the path string (`"methodology-main:/.../tipo2_interpretations.yaml"`), gemma4 invents plausible-but-wrong `entry_id`s (`T2_CRA_01_Product_Type_Definition`, `D-02.3`) because it cannot read the file. M3 aced the entry_ids with the same minimal input because it had the catalog in training data.

**Fix:** the input `layer0_catalog` block must contain the actual entries (list of dicts), not paths. For P1B-01 this means inlining the YAML rows for the applicable reg's `tipo2_entries` and `tipo3_entries`. Payload grows by ~2-3KB per reg, well within budget.

Citation: dry-run comparison `/tmp/corr074-ollama/p1b01_gemma4_e4b_raw.txt` (invented IDs) vs `/tmp/corr074-ollama/p1b01_gemma4_e4b_v2_raw.txt` (correct IDs after inlining).

### L19: Subsection regex must accept `D-XX.Y` (with period) and `(YES)` annotations

The original `_SUBSEC_INT` regex pattern `[A-Z][A-Z0-9_]+(?:-[A-Z0-9_]+)*` matched `TIPO2-CRA-ART14-DUAL-FLOW` but rejected `D-02.3` (period not in char class). Separately, the verdict `(?:\([^)]*\s*)?\*{0,2})?` failed on `APPLIES (YES)` because the inner `\s*` consumed the space before the parenthesis.

**Fix:** widen the ENTRY_ID char class to `[A-Z][A-Z0-9_.\-]+` (accepts period and hyphen anywhere) and decouple the parenthesis annotation from the preceding whitespace (`(?:\s*\([^)]*\))?` as a standalone optional group).

Citation: `src/aegis_phase1/_archive/corr061/markdown_parser.py:732-752` (CORR-074 post-Ollama fix).

### Ollama vs M3 dry-run summary (P1B-01)

| Model | Input | Latency | Format | Entry IDs | Parse |
|---|---|---|---|---|---|
| M3 | minimal | 7.14s | markdown | correct (via training) | OK |
| gemma4:e4b | minimal (pre-fix loader) | 343s | JSON | n/a | FAIL |
| gemma4:e4b | minimal (post-fix loader) | 78s | markdown | invented | partial |
| gemma4:e4b | catalog inlined | 89s | markdown | correct | OK |
| gemma4:e2b | minimal (post-fix loader) | 26s | markdown | invented | partial |
| gemma4:e2b | catalog inlined | 29s | markdown | correct | OK |

Takeaway: M3 is 10-30× faster and tolerates a thinner input, but gemma4 produces equivalent output quality when given (a) the markdown-aware `# TASK` suffix and (b) the catalog content inlined. For local validation runs, gemma4 is a viable option; for production throughput, M3 remains the recommendation.
