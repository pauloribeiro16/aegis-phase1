# AGENTS.md — aegis-phase1

**Purpose:** AI agent onboarding for the standalone AEGIS-KG Phase 1 workflow.
**Language:** All content in English (user may chat in Portuguese).

---

## 0. Framework policy — NIST CSF 2.0 ONLY

> **This project uses NIST CSF 2.0 as the sole control framework.**
> No other control framework (ISO 27001, NIST 800-53, OWASP, CSF 1.1, etc.)
> is used as a source of control identifiers or control families.

- **Canonical declaration:** [`docs/NIST_CSF_2.0_ONLY.md`](docs/NIST_CSF_2.0_ONLY.md)
- **Source catalogue:** `preproc_out/global/NIST_CSF_2.0_subcategories.json`
  (106 active subcategories, 22 active categories — NIST CSWP 29, 2024-02-26)
- **Audit (CSF coverage):** `python -m scripts.preprocess.audit_csf_mapping` must report `BROKEN == 0`
- **Audit (SO↔SR coherence):** `python -m scripts.preprocess.audit_so_sr_coherence` must report `sr_without_so.count == 0` (raw orphans only — the 8 SOs-without-SRs are deferred to CORR-030)
- **CI gate:** `bash .hooks/ci-frameworks.sh` (rejects unannotated references to other control frameworks)

When in doubt: pick the CSF 2.0 subcategory. If a regulation cannot be mapped to any
of the 106, mark the rule as `UNMAPPED_CSF` per `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md`.

---

## 1. Architecture

```
START → parse_inputs → subphase_a → subphase_b → subphase_c → END
```

| Phase | Nodes | Output |
|-------|-------|--------|
| **parse_inputs** | n01_parse_inputs | Loads CSV + context data |
| **subphase_a** | a02–a07, _validate_a | Company context, stakeholders, goals, complexity, compliance context |
| **subphase_b** | b01–b06, _validate_b | Regulations, clauses, domain mapping, coverage, responsibility, implementation |
| **subphase_c** | c01–c05, _validate_c | Complementarity, elaboration, strategic implications, obligations, matrix |

LangGraph state machine. Each subphase runs sequentially. No Neo4j, no eval.

### 1.1 Phase 1 v1.2 LLM Architecture (PROMPTS library integration)

**5 canonical LLMs** (down from 8 in legacy) defined in `00_METHODOLOGY/PROMPTS/`:

| LLM ID | Invocation | Stage | Replaces (legacy) |
|---|---|---|---|
| `P1B-LLM-01-INTERPRETATION` | `per_regulation` | Phase 1B | LLM-A |
| `P1B-LLM-02-RATIONALE` | `per_regulation` | Phase 1B | LLM-B/C/D (merged) |
| `P1C-LLM-01-OVERLAP-CLASSIFICATION` | `per_domain_lane` | Phase 1C Map | LLM-E |
| `P1C-LLM-02-COMPOUND-EVENT` | `global_reduce` | Phase 1C Reduce (2nd) | LLM-F |
| `P1C-LLM-03-STRATEGIC-SYNTHESIS` | `global_reduce` | Phase 1C Reduce (1st) | LLM-G |

**Removed (out of Phase 1 scope):** LLM-H (gap aggregation + remediation → Phase 2/3).

**Public API** (`src/aegis_phase1/prompts_v2/`):

```python
from aegis_phase1.prompts_v2 import (
    PromptLoader,           # Load PROMPTS/*.md + extract YAML frontmatter
    CatalogLoader,          # Load YAML catalogs (tipo2, tipo3, ...) + eval predicates
    Phase1LLMInvoker,       # Single LLM call: prompt → invoke → parse → validate
    Phase1Validator,        # JSON Schema + Layer 0 citation + no-reclass check
    JSONLLogger,            # Structured logging (JSONL + stdout summary)
    RobustParser,           # Multi-strategy JSON parser (handles gemma4:e2b issues)
    LLM_SPECS,              # Registry of 5 Phase 1 LLMs
)

loader = PromptLoader()  # defaults to ../Methodology-main/00_METHODOLOGY/PROMPTS
invoker = Phase1LLMInvoker(loader, ...)
result = invoker.invoke("P1B-LLM-01-INTERPRETATION", inputs, max_retries=2)
# result = {"status": "OK"|"INSUFFICIENT_EVIDENCE"|"FAILED_AFTER_RETRIES", ...}
```

**Logging (per implementation contract):**

- `logs/phase1/llm-calls.jsonl` — every LLM call (full I/O, validation result, latency, tokens)
- `logs/phase1/format-errors.jsonl` — parse failures (gemma4:e2b format issues)
- `logs/phase1/errors.log` — Python errors
- `logs/phase1/performance.csv` — latency + token metrics

All logs are gitignored (see `.gitignore`).

**Required Ollama model:** `gemma4:e2b` (set in `.env` via `OLLAMA_MODEL`). The invoker uses Ollama's `format` parameter to constrain output to a JSON Schema; the `RobustParser` falls back to 5 strategies (json_strict, extract_markdown_block, extract_first_object, extract_first_array, repair_common_errors) when the model produces non-conforming output.

---

## 2. Commands

```bash
# Setup (shared venv — all packages pre-installed)
source ../shared-venv/bin/activate
cp .env.example .env          # edit LLM settings

# OR fresh install:
# pip install -e ".[all]"

# Test (file-scoped first)
pytest tests/unit/workflow/phase1/test_validate_a.py -v
pytest tests/unit/nodes/ -v
pytest tests/unit/ -v          # full unit suite
pytest tests/ -v --skip-slow   # skip marked slow

# Phase 1 v1.2 smoke test (requires Ollama running with gemma4:e2b)
PYTHONPATH=src pytest tests/unit/prompts_v2/test_smoke_e2e.py -v

# Lint & typecheck
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/aegis_phase1/

# Pre-commit
pre-commit run --all-files

# CORR-027: rebuild preproc_out + run the CSF audit
python -m scripts.preprocess build                              # regenerate preproc_out/
python -m scripts.preprocess.audit_csf_mapping                 # CSF coverage report (38 subdomains)
python -m scripts.preprocess.audit_so_sr_coherence             # SO↔SR coherence report (CORR-029)
bash .hooks/ci-csf-frozen-list.sh                              # .md ↔ preproc_out parity gate
bash .hooks/ci-frameworks.sh                                   # framework policy gate (CORR-028)
```

---

## 3. Testing

| Layer | Dir | What |
|-------|-----|------|
| Unit | `tests/unit/` | Individual nodes, parsers, models, utils |
| Integration | `tests/integration/` | End-to-end run (skipped without services) |

**Pattern:** AAA (Arrange-Act-Assert), dict-based state, mocked LLM.\
**Shared fixtures:** `tests/conftest.py` provides `minimal_state`, `case1_path`, `mock_llm`.

---

## 4. Project Structure

```
src/aegis_phase1/          # Main package
├── config/                # case.yaml loader, defaults, models
├── llm/                   # Ollama client, tracing stub
├── nodes/                 # 23 LangGraph node functions
├── parsers/               # applicability rules, intake, JSON utils
├── prompts/               # subphase_a/b/c prompt templates
├── shared/                # document producer, template parser
├── subphases/             # subphase orchestration
├── graph.py               # LangGraph state machine
├── models.py              # Pydantic data models
├── state.py               # Phase1State TypedDict
└── env.py                 # .env loader
```

```
cases/case1-tinytask/
├── case.yaml                      # Case config (env vars expanded at load)
├── context/                       # Input context docs (00_Taxonomy, 01_Company, 02_Regulatory, 03_Design, ontology)
├── data/phase1/                   # 22 CSV files (regulations, clauses, domains, etc.)
├── templates/phase1/              # OUTPUT templates with [placeholders] to fill
│   ├── 04_Company_Context_Assessment.md
│   ├── 05_Regulatory_Applicability.md
│   ├── 06_Clause_Mapping_Matrix.md
│   └── 07_Structured_Compliance_Matrix.md
└── output/phase1/                 # Filled output (written by produce_documents)
```

**Reference (filled) documents** — `/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/` contains the expected filled output for comparison. Templates use `[snake_case_placeholders]`; reference docs have real TinyTask data.

---

## 5. Code Style

**Python:** PEP 8 by Ruff (line-length 100, py311).\
**Naming:** `snake_case` files/fns, `PascalCase` classes, `UPPER_CASE` constants.\
**Types:** `X | None`, `list[X]`, never `Optional`/`List`.\
**Logging:** `logger = logging.getLogger(__name__)` mandatory.\
**Errors:** `logger.debug()` on expected, `logger.exception()` on unexpected. No bare `except:`.

---

## 6. Git Workflow

| Action | Convention |
|--------|------------|
| Branch | `feat/<name>`, `fix/<name>`, `refactor/<name>` |
| Commit | `type: short description` |
| PR | Squash-merge, reference contract ID |

---

## 7. Boundaries

| Tier | Action |
|------|--------|
| **Always** | Add `logger = logging.getLogger(__name__)`, type hints, tests |
| **Ask first** | Adding dependencies, Neo4j code, Langfuse, conftest changes |
| **Never** | Hardcode ports (use `.env`), commit `.env`, edit `archive/`, use `except: pass` |

---

## 8. Skills (Activate on Demand)

Skills are loaded via `skill({ name: "skill-name" })`.

| Skill | When |
|-------|------|
| `sprint-contract` | 3+ file changes, complex tasks |
| `code-review` | Before merging, independent verification |
| `python-best-practices` | Any Python code change |
| `project-conventions` | AEGIS-KG naming patterns |
| `context-checkpoint` | Context > 70% |

---

## 9. Critical Rules

- **No Neo4j/KG code** (not present in Phase 1)
- **Ports: 11434** (Ollama only). No 7687/7474/7475/7688
- **case.yaml** lives in `cases/<case>/case.yaml`, loaded by `config.case_loader`
- **Tracing:** opt-in Langfuse via `llm/tracing.py` — disabled by default
- **Mock LLM:** set `MOCK_LLM=true` in `.env` to skip real API calls
- **Templates** are in `cases/<case>/templates/phase1/` with `[snake_case_placeholders]`
- **Reference output** at `Methodology-main/02_CASES/Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/`
- **`.env` location:** `src/.env` (not project root) — loaded by `aegis_phase1/env.py`

---

## 10. Branch Policy (MANDATORY — 2026-07-14)

> **Anti-pattern lesson learned.** Creating one branch per phase (e.g. `feature/phase0-*`, `feature/phase1-*`) caused catastrophic state fragmentation: committed files on one branch did not exist on the next, working-tree changes followed checkouts, and subagents produced code that imported non-existent modules. Validators reported false positives because pytest errors during collection were hidden in tail output.

**Rule:** **1 branch per contract.** Phases are sequential **commits** on that branch, never separate branches.

```bash
# CORRECT (one branch per contract):
git checkout main
git checkout -b feature/aegis-p1-corr-001
# all phases = commits on this branch

# WRONG (anti-pattern — never do this):
git checkout -b feature/phase0-rebranding      # NO
git checkout -b feature/phase1-clause-ids     # NO
```

**Branch naming:** `feature/<contract-id>-<short-name>` (e.g. `feature/aegis-p1-corr-001`).

**Subagent rule:** Subagents (Executor/Validator) receive the contract branch name as part of their prompt and MUST NOT create or switch branches. All work happens on the current branch.

### 10.1 Pre-flight Check (REQUIRED before dispatching any subagent)

Before dispatching an Executor or Validator subagent, the orchestrator MUST run:

```bash
# 1. Verify we're on the correct branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

# 2. Verify working tree is clean (or only new files)
MODIFIED_COUNT=$(git status --short | wc -l)
echo "Uncommitted files: $MODIFIED_COUNT"

# 3. Verify critical modules are importable
python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator; print('orchestrator OK')"
python -c "from aegis_phase1.v2.runner import main; print('runner OK')"
python -c "from aegis_phase1.v2.llm import build_llm_invoker; print('llm OK')"

# 4. Verify tests can be COLLECTED (not just executed)
pytest tests/unit/v2/ --co -q 2>&1 | tail -5
# Look for "ERROR" lines — if any, abort dispatch.
```

**If any check fails:** abort the subagent dispatch, fix the issue first. Do NOT proceed with stale or broken state.

### 10.2 Validator Integrity Rule

Validators MUST verify test COLLECTION (not just execution summary). The following is FORBIDDEN:

```bash
# WRONG — hides collection errors in tail output:
pytest tests/unit/v2/ 2>&1 | tail -5

# CORRECT — surfaces collection errors explicitly:
pytest tests/unit/v2/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"
pytest tests/unit/v2/ -v 2>&1 | grep -E "ERROR|FAILED|ModuleNotFoundError"
```

A validator that reports "X tests passed" without confirming collection completeness has FAILED its duty.

### 10.3 Historical reference

The contract `AEGIS-P1-CORR-001` (2026-07-14) was the first contract executed under this policy, after the 7-branch fragmentation incident. See commit `1001a10` for the consolidated single-branch commit (Phases 0-6 as logical commit groups).

## 11. Canonical ID conventions (CORR-032 — MANDATORY 2026-07-20)

All entity IDs in the AEGIS-KG preproc must follow a single canonical
form. This section is the **single source of truth** for ID conventions;
if a new entity type is added, follow the patterns below or update this
section **before** introducing the new ID.

### 11.1 Canonical forms

| Entity kind | Format | Example |
|---|---|---|
| Subdomain | `D-XX.Y` | `D-04.3` |
| Sub-SO (per-reg) | `SO-D-XX.Y.{REG}` | `SO-D-04.3.CRA` |
| Sub-SO (high-level) | `SO-D-XX.Y.HL` | `SO-D-04.3.HL` |
| Master SO | `SO-{REG}-{NNN}` (3-digit, zero-padded) | `SO-CRA-001`, `SO-AI_Act-001` |
| Security Rule | `SR-{REG}-{NNN}` (3-digit, zero-padded) | `SR-CRA-001`, `SR-AI_Act-001` |
| Source clause | `{REG}-CL{NN}` (2-digit, zero-padded) | `CRA-CL01`, `AI_Act-CL01` |
| Cross-reg pair | `D-XX.Y_{REG_A}-{REG_B}` (alphabetic REG_A < REG_B) | `D-04.3_CRA-AI_Act` |
| CSF subcategory | `GV.OC-01` (NIST standard, not ours) | unchanged |

### 11.2 Regulation canonical names

The 5 regulations have **one** canonical name each. The filesystem
folder, the JSON `regulation` field, and any code reference all use
this name.

| Canonical | Aliases accepted on input (legacy) |
|---|---|
| `CRA` | — |
| `GDPR` | — |
| `NIS2` | `NIS 2`, `NIS_2` |
| `DORA` | — |
| `AI_Act` | `AI Act`, `AIACT`, `AIA`, `AI` |

Aliases are accepted in `_REG_NORMALIZE` (parsers/entities/subdomain.py)
and `_entity_kind` (scripts/preprocess/pipeline.py) **for backward
compatibility with pre-CORR-032 source MDs**, but the **output** is
always the canonical form.

### 11.3 Source-clause ID special cases

- **DORA** has multi-clause-per-article. The canonical form is
  `DORA-CL{NN}-{M}` where `NN` is the article number and `M` is the
  ordinal clause within that article (e.g. `DORA-CL17-1` for the first
  clause of Art. 17).
- **AI_Act** uses the per-article `Ambiguity/0N_AI_Act_Art*.md` files,
  not the older 06_AI_Act.md cross-article file (which is superseded).
- **GDPR / CRA / NIS2** use single clauses per article (no `-M` suffix).

### 11.4 Naming anti-patterns (do NOT introduce these)

The following forms are **forbidden** in new source MDs and in any
parser output. They will be caught by `test_id_normalization.py` in CI.

- `AIA-C{NN}`, `AIA-CL{NN}`, `AI-C{NN}`, `AI-CL{NN}` (use `AI_Act-CL{NN}`)
- `AIACT-C{NN}`, `AIACT-CL{NN}` (use `AI_Act-CL{NN}`)
- `SO-AIACT-NNN`, `SR-AIACT-NNN` (use `SO-AI_Act-NNN`, `SR-AI_Act-NNN`)
- `GDPR-C{NN}`, `DORA-C{NN}` (use `GDPR-CL{NN}`, `DORA-CL{NN}`)
- `CL{NN}-{M}` standalone (use `DORA-CL{NN}-{M}` — DORA is the only
  regulation using this pattern)

### 11.5 Migration scripts

Two helper scripts in `Methodology-main/`:

- **`scripts/migrate_canonical_ids.py`** (or equivalent) — bulk
  regex-driven rewrite of all `00_METHODOLOGY/**/*.md`. Re-runnable
  idempotently. Skips `_archive/`, `_build/`, and `.git/`.

The aegis-phase1 pipeline side:

- **`scripts/preprocess/parsers/entities/subdomain.py`** —
  `_REG_NORMALIZE` map: source of truth for `REG → REG` aliases
  (add a new entry here when introducing a new regulation, never
  inline-rewrite in a parser).
- **`scripts/preprocess/pipeline.py`** — `_entity_kind` function:
  source of truth for `entity_id → kind` classification. Add new
  clause/SO/SR prefix patterns here as the canonical form evolves.

### 11.6 Validation

```bash
# Source-level (run from Methodology-main/)
grep -rE "AIA-C[0-9]|SO-AIACT|SR-AIACT|\bDORA-C[0-9]\b|\bGDPR-C[0-9]\b|AIACT-C" \
  00_METHODOLOGY/ --include="*.md" --exclude-dir=_archive | head -5
# Expected: empty output (or only the 1-line historical note in
# 00_METHODOLOGY/PREPROCESSING/Regulation/AI_Act/00_README.md).

# Preproc-level (run from aegis-phase1/)
PYTHONPATH=src pytest tests/unit/preprocess/test_id_normalization.py -v
# Expected: 6 tests pass.
```

If a new ID drift appears, fix it in the same PR — don't defer.

### 11.7 When to update this section

Add a new entry to this table when:
- A new entity kind is introduced (e.g. a "scenario" or "evidence" type)
- A new regulation is onboarded (add to the canonical name table AND
  to the `_REG_NORMALIZE` map)
- A new clause-Sub-domain mapping convention is adopted (e.g. if
  NIS2 starts using the `-M` suffix)

The next person to onboard something will read this section first.
