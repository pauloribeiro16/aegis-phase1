# AGENTS.md — aegis-phase1

**Purpose:** AI agent onboarding for the standalone AEGIS-KG Phase 1 workflow.
**Language:** All content in English (user may chat in Portuguese).

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

---

## 2. Commands

```bash
# Setup
pip install -e ".[all]"
cp .env.example .env          # edit LLM settings

# Test (file-scoped first)
pytest tests/unit/workflow/phase1/test_validate_a.py -v
pytest tests/unit/nodes/ -v
pytest tests/unit/ -v          # full unit suite
pytest tests/ -v --skip-slow   # skip marked slow

# Lint & typecheck
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/aegis_phase1/

# Pre-commit
pre-commit run --all-files
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

`cases/case1-tinytask/` — 22 CSVs, 4 templates, context docs.

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
