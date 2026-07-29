# AGENTS.md — aegis-phase1

**Purpose:** Onboarding for AI coding agents — AEGIS-KG Phase 1 pipeline.
**Language:** All content in English (user chats in Portuguese).
**Last Updated:** 2026-07-29 (sprint-contract rule added)

---

## 0. Index & proximity rule

This file is the **root AGENTS.md**. Domain-specific guidance lives in
sub-AGENTS.md files. **Nearest file wins**: when working in any folder,
read that folder's AGENTS.md first.

| Path | Topic |
|------|-------|
| `src/aegis_phase1/v2/AGENTS.md` | v2 pipeline (orchestrator, runner, output/, domain/, reduce/) |
| `src/aegis_phase1/prompts_v2/AGENTS.md` | 5 LLM specs, PROMPTS library, RobustParser |
| `tests/AGENTS.md` | testing patterns, mock_llm fixture |

**Phase 2 candidates** (not yet created — open when each folder gets
heavy traffic): `docs/AGENTS.md`, `scripts/preprocess/AGENTS.md`,
`src/aegis_phase1/llm/AGENTS.md`.

---

## 1. Framework policy — NIST CSF 2.0 ONLY

> This project uses NIST CSF 2.0 as the sole control framework.
> No other framework (ISO 27001, NIST 800-53, OWASP, CSF 1.1, etc.) is
> used as a source of control identifiers or control families.

- **Canonical declaration:** [`docs/NIST_CSF_2.0_ONLY.md`](docs/NIST_CSF_2.0_ONLY.md)
- **Source catalogue:** `preproc_out/global/NIST_CSF_2.0_subcategories.json` (106 active subcategories, 22 categories — NIST CSWP 29, 2024-02-26)
- **CI gate:** `bash .hooks/ci-frameworks.sh` (rejects unannotated references to other control frameworks)

If a regulation cannot be mapped to any of the 106, mark as
`UNMAPPED_CSF` per `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md`.

---

## 2. Architecture (overview)

```
START → parse_inputs → subphase_a → subphase_b → subphase_c → END
```

| Phase | Nodes | Output |
|-------|-------|--------|
| parse_inputs | n01 | CSV + context data |
| subphase_a | a02–a07 | company context, stakeholders, goals, complexity |
| subphase_b | b01–b06 | regulations, clauses, domain mapping, coverage |
| subphase_c | c01–c05 | obligations, elaboration, strategic, matrix |

LangGraph state machine (18 nodes in `src/aegis_phase1/v2/graph.py`).
5 canonical LLMs in `src/aegis_phase1/prompts_v2/` (P1B-01/02, P1C-01/02/03).
**Full details → `src/aegis_phase1/v2/AGENTS.md` and `src/aegis_phase1/prompts_v2/AGENTS.md`.**

---

## 3. Project Structure (compact)

```
src/aegis_phase1/
  v2/                # Production pipeline (CORR-037) — see AGENTS.md
  prompts_v2/        # 5 canonical LLMs — see AGENTS.md
  llm/               # UnifiedInvoker, ChatMinimax, ChatOllama, transformers
  config/            # case.yaml loader, defaults, models
  parsers/           # applicability rules, intake, JSON utils
  prompts/           # v1 legacy prompt templates (read-only)
  models.py          # Pydantic data models
  state.py           # Phase1State TypedDict
tests/
  unit/v2/           # v2 unit tests — see tests/AGENTS.md
  integration/       # End-to-end (skipped without services)
  fixtures/          # pipeline_inputs_golden/ for CORR-070 input contract
cases/
  case1-tinytask/    # SaaS MICRO (2 regs)
  case2-secureborder/ # security MEDIUM (4 regs)
  case3-omnibank/    # banking LARGE (5 regs)
data/                # YAML sources for tier/role/regulatory/control-evidence (CORR-073). Capabilities loader: data/capabilities/{D-XX}.yaml via data/loader.py:load_capabilities(). ROLE_VOCABULARY ∈ {DPO, CISO, Engineering, Operations, Governance}. Silent {} on missing.
docs/                # NIST_CSF_2.0_ONLY, PHASE1_FLOW_DESIGN, etc.
execution/           # CONTRACT-NNN.md, CORR-NNN-RUN-LOG.md, audit reports
```

---

## 4. Commands (file-scoped → full suite)

```bash
# File-scoped tests (fast feedback, preferred)
PYTHONPATH=src pytest tests/unit/v2/output/test_doc_04_stakeholder_leakage.py -v

# Full unit suite (skip slow + integration)
PYTHONPATH=src pytest tests/unit/ -m "not slow"

# v1.2 smoke (requires Ollama running with gemma4:e2b)
PYTHONPATH=src pytest tests/unit/prompts_v2/test_smoke_e2e.py -v

# Lint
ruff check src/ tests/
ruff format --check src/ tests/

# Pipeline contract gate (CORR-070)
bash .hooks/ci-pipeline-inputs.sh

# CSF framework gate
bash .hooks/ci-frameworks.sh

# Setup (CANONICAL VENV: shared-venv-root is the working one)
PYTHONPATH=src python -c "from aegis_phase1.v2.runner import main; print('OK')"
```

**Full operational reference → `tests/AGENTS.md`** (mock_llm, fixtures, pytest flags).

---

## 5. Git Workflow (1 branch per contract)

**Rule:** 1 branch per contract. Phases are sequential **commits**, never separate branches.

```bash
# CORRECT
git checkout main
git checkout -b feature/aegis-p1-corr-NNN
# all phases = commits on this branch

# WRONG (anti-pattern — never)
git checkout -b feature/phase0-rebranding      # NO
git checkout -b feature/phase1-clause-ids     # NO
```

**Naming:** `feature/aegis-p1-corr-NNN-<short-name>`.

**Commit format:** `type(corr-NNN): short description`.

**Pre-flight check** before dispatching any subagent (orchestrator MUST run):
```bash
CURRENT_BRANCH=$(git branch --show-current)
python -c "from aegis_phase1.v2.runner import main; print('OK')"
PYTHONPATH=src pytest tests/unit/v2/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"
# If any check fails: abort the subagent, fix first.
```

**Detailed branch policy + validator integrity rule + subagent rule:
see `execution/CONTRACT-001.md` and CORR-NNN.md "Risks" sections.

---

## 6. Boundaries (Always / Ask first / Never)

| Tier | Action |
|------|--------|
| **Always** | Add tests for any code change. Run lint + tests before commit. Use type hints. Update nearest AGENTS.md if the rule belongs there. |
| **Ask first** | Adding new dependencies. Touching `Methodology-main/` (separate repo). Adding new regulation / entity kind to preproc. Neo4j / Langfuse / conftest changes. Renaming state keys. Schema changes mid-contract. |
| **Never** | Hardcode ports (use `.env`). Commit secrets or `.env` values. Edit `archive/`. Use `except: pass`. Withhold evidence (golden regen) when schema changes. |

---

## 7. Skills (Activate on Demand)

Skills load via `skill({name: "..." })`. Match a task to a skill's
trigger phrase and load immediately — don't paraphrase.

| Skill | When in this repo |
|-------|------|
| `sprint-contract` | **ALWAYS** load when the user asks for a contract (any size, any context); also: 3+ file changes, complex tasks, planning CORR-NNN contracts |
| `code-review` | Before merging, independent verification of changes |
| `python-best-practices` | Any Python code change |
| `project-conventions` | New AEGIS-KG naming, file structure, entity IDs |
| `context-checkpoint` | Context >70% during long sessions |
| `agents-md-writer` | Only when updating this file or any AGENTS.md |
| `pdf` | When case inputs include PDF (Phase 1 §Input Documents) |
| `docx` | When stakeholders provide .docx specs |
| `xlsx` | When case inputs include Excel (Phase 1 §Output) |
| `neo4j-verify` | Before/after Neo4j-related work (port 7688/7475, no hardcoded ports) |

Sub-AGENTS files list **folder-specific** trigger subsets — always read
nearest file first.

---

## Sub-AGENTS map

- **`src/aegis_phase1/v2/AGENTS.md`** — orchestrator, runner, output/, domain/, reduce/
- **`src/aegis_phase1/prompts_v2/AGENTS.md`** — 5 LLM specs, PROMPTS library
- **`tests/AGENTS.md`** — testing patterns, mock_llm, regression tests

---

**Contract ref:** execution/CONTRACT-072.md (most recent affecting AGENTS.md layout)
**Hierarchy rules:** all files ≤150 lines each; root hard limit 200; nearest file wins; split further if any sub-AGENTS grows.
