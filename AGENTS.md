# AGENTS.md — aegis-phase1

**Purpose:** AI agent onboarding for the standalone AEGIS-KG Phase 1 workflow.
**Language:** All content in English (user may chat in Portuguese).

---

## 1. Architecture

Linear LangGraph state machine (5 sub-graphs inside a root):

```
START → load_baseline → MAP (10 domains) → Phase 1B (per reg) →
       REDUCE (det + synthesis + compound) → OUTPUT (10 docs) → END
```

| Sub-graph | Nodes | Output |
|---|---|---|
| **MAP** | `map_D01`..`map_D10` | Per-domain adapted objectives (v1.3 spec) |
| **Phase 1B** | `p1b_interp_{GDPR,CRA}` + `p1b_rat_{GDPR,CRA}` | Per-reg interpretation + rationale |
| **REDUCE** | `reduce_det` + `reduce_synthesis` + `reduce_compound` | Compound events + strategic synthesis |
| **OUTPUT** | `doc_04_body` + `doc_04a..04d` + `doc_05..07` + `xlsx` | Filled compliance docs |

**v2 implementation** (the only one in this repo):

```python
from aegis_phase1.v2.orchestrator import Phase1Orchestrator
from aegis_phase1.v2.graph import run_phase1_graph
# Legacy: scripts/run_phase1.py --run-all-traced (one Langfuse trace)
```

**Required Ollama model:** `gemma4:e2b` (`.env:OLLAMA_MODEL`).

---

## 2. Commands

```bash
source ../shared-venv/bin/activate   # OR use the .venv symlink
cp .env.example .env                  # edit LLM settings

# Tests (file-scoped first, then full unit suite)
pytest tests/unit/v2/ -v
pytest tests/unit/ -v --skip-slow
pytest tests/unit/v2/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"  # C7 (see §10)

# Quality
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/aegis_phase1/

# Per-domain MAP smoke (requires Ollama + gemma4:e2b)
python scripts/domain_adapt_experiment.py --domain D-10 --model gemma4:e2b

# Pre-flight before any subagent dispatch — see §10.1
bash .hooks/validate-contracts.sh
```

---

## 3. Testing

| Layer | Dir | What |
|---|---|---|
| Unit | `tests/unit/v2/` | v2 nodes, loaders, parsers, gates, graph |
| Smoke | `tests/unit/prompts_v2/` | Prompt loader + Phase1LLMInvoker (legacy v1.2) |

**Pattern:** AAA, dict-based state, mocked LLM (`MockInvoker` in `llm/unified.py`).
**Fixtures:** `tests/unit/v2/conftest.py` provides `mock_state`, `mock_company_context`, `mock_ontology`.

---

## 4. Project Structure

```
src/aegis_phase1/
└── v2/                          # ONLY active implementation
    ├── orchestrator.py          # Phase1Orchestrator (5 granular methods)
    ├── graph.py                 # 18-node StateGraph (4 compiled sub-graphs)
    ├── state.py, runner.py, cli/menu.py, llm.py
    ├── domain/                  # prompt, parser (V3), inputs, filters
    │   ├── prompt.py            # render_prompt() for MAP-DOMAIN-ADAPT v1.3
    │   ├── parser.py            # OutputParserV3 (v1.3 strict)
    │   ├── inputs.py, filters/, anchor_validator.py
    │   └── prompts/MAP-DOMAIN-ADAPT.md  # v1.3 spec
    ├── loader/ output/ reduce/ review/  # article/ambiguity loaders, doc_04..07, gates
    └── trace_graph.py           # DEPRECATED shim (CORR-018b replaced by graph.py)
llm/unified.py, llm/tracing.py   # UnifiedInvoker, Langfuse CallbackHandler
cases/case1-tinytask/            # TinyTask SaaS case (only case in tree)
docs/  execution/  logs/         # CONTRACTS.md, CONTRACT-NNN.md, llm-calls.jsonl
```

---

## 5. Key files (orientation map)

### In this repo

| File | What |
|---|---|
| `src/aegis_phase1/v2/orchestrator.py` | `Phase1Orchestrator` — main entry, owns state |
| `src/aegis_phase1/v2/graph.py` | 18-node LangGraph (root + 4 sub-graphs) |
| `src/aegis_phase1/v2/llm.py` | Ollama HTTP client + `OllamaUnreachableError` |
| `src/aegis_phase1/v2/domain/prompt.py` | `render_prompt()` (MAP-DOMAIN-ADAPT v1.3) |
| `src/aegis_phase1/v2/domain/parser.py` | `OutputParserV3` (v1.3 strict contract) |
| `src/aegis_phase1/v2/loader/article_loader.py` | `DOMAIN_ARTICLES` catalog (D-01..D-10) |
| `src/aegis_phase1/v2/loader/ambiguity_loader.py` | `_DOMAIN_CLAUSE_FILTER` (per-domain) |
| `src/aegis_phase1/v2/domain/prompts/MAP-DOMAIN-ADAPT.md` | v1.3 prompt spec (max_tokens, num_ctx) |
| `scripts/domain_adapt_experiment.py` | MAP per-domain benchmark (9 gates) |
| `scripts/preprocess/` | CORR-024: `preproc_out/` generator (351 md → JSON sharded) |
| `preproc_out/` (gitignored) | CORR-024: sharded JSON output, regenerated in CI |
| `execution/CONTRACT-NNN.md` | Current contract under implementation |
| `docs/CONTRACTS.md` | Master contract index (every CORR-NNN ever) |
| `docs/SPEC-observability.md` | Langfuse roadmap (CORR-009 → 015) |
| `methodology-00` (symlink) | → `../Methodology-main/00_METHODOLOGY` |

### In `methodology-00/` (Methodology-main source tree)

| Path | What |
|---|---|
| `methodology-00/PROMPTS/P1B-LLM-0[12]-*.md` | Phase 1B prompts (interpretation, rationale) |
| `methodology-00/PROMPTS/P1C-LLM-0[123]-*.md` | Phase 1C prompts (overlap, compound, synthesis) |
| `methodology-00/PREPROCESSING/SubDomains/D-XX_*/` | 10 domain corpora (D-01..D-10) |
| `methodology-00/PREPROCESSING/Regulation/{GDPR,CRA,NIS2,DORA,AI_Act}/` | OJ article text |
| `methodology-00/PREPROCESSING/AMBIGUITY_ANALYSIS/` | ~280 clause ambiguity cards |
| `methodology-00/PHASE1_STRATEGY.md` | Phase 1 strategy overview |
| `methodology-00/REGULATORY_BASELINE.md` | Layer 0 (renamed regulatory_baseline) spec |
| `methodology-00/MANIFESTO.md` | AEGIS-KG manifesto |

---

## 6. Code Style & Git Workflow

- **Python:** PEP 8, Ruff (line-length 100, py311). Types: `X | None`, `list[X]`.
- **Naming:** `snake_case` files/fns, `PascalCase` classes, `UPPER_CASE` constants.
- **Logging:** `logger = logging.getLogger(__name__)` mandatory. `logger.debug()` on expected, `logger.exception()` on unexpected. No bare `except:`.
- **Branch:** `feature/<contract-id>-<short-name>` (1 branch per contract — see §10).
- **Commit:** `type: short description`. PR: squash-merge, reference contract ID.

---

## 7. Boundaries

| Tier | Action |
|---|---|
| **Always** | Add `logger`, type hints, tests. Run `.hooks/validate-contracts.sh` before subagent dispatch. |
| **Ask first** | Adding dependencies, Neo4j code, Langfuse changes, `conftest.py` edits. |
| **Never** | Hardcode ports (use `.env`), commit `.env`, edit `archive/`, use `except: pass`, create one branch per phase. |

---

## 8. Skills

| Skill | When |
|---|---|
| `sprint-contract` | 3+ file changes, complex tasks |
| `code-review` | Before merging |
| `python-best-practices` | Any Python change |
| `project-conventions` | AEGIS-KG naming patterns |
| `context-checkpoint` | Context > 70% |

---

## 9. Critical Rules

- **No Neo4j/KG code** (not present in Phase 1). Ports: 11434 (Ollama) only — no 7687/7474/7475/7688.
- **case.yaml** lives in `cases/<case>/case.yaml`, loaded by `config.case_loader`.
- **Tracing:** opt-in Langfuse via `llm/tracing.py` — disabled by default. Set `LANGFUSE_ENABLED=true` in `.env`.
- **Mock LLM:** `MOCK_LLM=true` in `.env` to skip real API calls.
- **Templates:** `cases/<case>/templates/phase1/` (placeholders `[snake_case]`).
- **Reference output** at `methodology-00/` parent (Case_01_TinyTask_SaaS/01_PHASE1_CONTEXT/).
- **`.env` location:** `src/.env` — loaded by `aegis_phase1/env.py`.

---

## 10. Branch Policy (MANDATORY)

> **Anti-pattern lesson (2026-07-14).** One branch per phase (e.g. `feature/phase0-*`) caused catastrophic state fragmentation. **Rule: 1 branch per contract.** Phases = sequential **commits** on that branch, never separate branches. Subagents receive the contract branch name and MUST NOT create or switch branches.

```bash
git checkout main && git checkout -b feature/aegis-p1-corr-NNN  # CORRECT
# WRONG: git checkout -b feature/phase1-foo  → never do this
```

### 10.1 Pre-flight check + validator integrity (REQUIRED)

Before any subagent dispatch AND before claiming a contract complete: branch clean, modules importable, test **collection** clean (NOT just execution summary), `bash .hooks/validate-contracts.sh` green.

```bash
# 1. Branch + working tree
git branch --show-current
# 2. Critical modules importable
python -c "from aegis_phase1.v2.orchestrator import Phase1Orchestrator"
python -c "from aegis_phase1.v2.runner import main"
python -c "from aegis_phase1.v2.llm import build_llm_invoker"
# 3. Test collection clean (NOT just execution summary — collection errors hide in tail output)
pytest tests/unit/v2/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"  # must be empty
# 4. Contract validator
bash .hooks/validate-contracts.sh
```

A validator that reports "X tests passed" without `--co -q | grep ERROR` clean **has FAILED**. Full audit trail per contract in `docs/CONTRACTS.md` (CORR-001 → latest).
