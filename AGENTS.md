# AGENTS.md — aegis-phase1

**Purpose:** Onboarding for AI coding agents — AEGIS-KG Phase 1 pipeline.
**Language:** All content in English (user chats in Portuguese).
**Last Updated:** 2026-07-29 (sprint-contract rule added)

---

## 0. Index & proximity rule

This file is the **root AGENTS.md**. Domain-specific guidance lives in sub-AGENTS.md files. **Nearest file wins**: when working in any folder, read that folder's AGENTS.md first.

| Path | Topic |
|------|-------|
| `src/aegis_phase1/v2/AGENTS.md` | v2 pipeline (orchestrator, runner, output/, domain/, reduce/) |
| `src/aegis_phase1/prompts_v2/AGENTS.md` | 5 LLM specs, PROMPTS library, RobustParser |
| `tests/AGENTS.md` | testing patterns, mock_llm fixture |

**Phase 2 candidates** (not yet created — open when each folder gets heavy traffic): `docs/AGENTS.md`, `scripts/preprocess/AGENTS.md`, `src/aegis_phase1/llm/AGENTS.md`.

---

## 1. Framework policy — NIST CSF 2.0 ONLY

> This project uses NIST CSF 2.0 as the sole control framework.
> No other framework (ISO 27001, NIST 800-53, OWASP, CSF 1.1, etc.) is used as a source of control identifiers or control families.

- **Canonical declaration:** [`docs/NIST_CSF_2.0_ONLY.md`](docs/NIST_CSF_2.0_ONLY.md)
- **Source catalogue:** `preproc_out/global/NIST_CSF_2.0_subcategories.json` (106 active subcategories, 22 categories — NIST CSWP 29, 2024-02-26)
- **CI gate:** `bash .hooks/ci-frameworks.sh` (rejects unannotated references to other control frameworks)

If a regulation cannot be mapped to any of the 106, mark as `UNMAPPED_CSF` per `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md`.

---

## 1b. Naming conventions

> Full audit: `docs/NAMING_INCONSISTENCIES.md`. Update this card when the canonical form changes.

| Entity | Canonical format | Example |
|---|---|---|
| Regulation | `GDPR`, `CRA`, `NIS2`, `DORA`, `AI_Act` | `AI_Act` |
| Clause | `{REG}-{SUFFIX}{NN}` (SUFFIX ∈ CL, CP, RT, TR) | `GDPR-CL06` |
| Article | `{REG}_Art. {N}` | `AI_Act_Art. 9` |
| Subdomain ID | `D-{NN}.{N}` | `D-01.4` |
| SO canonical | `SO-{REG}-{NNN}` | `SO-GDPR-001` |
| SO per-reg | `SO-D-{NN}.{N}.{REG}` | `SO-D-01.1.GDPR` |
| SO HL | `SO-D-{NN}.{N}.HL` | `SO-D-01.1.HL` |
| SR | `SR-{REG}-{NNN}` | `SR-AI_Act-014` |
| CSF | `{FUNC}.{CAT}-{NN}` | `PR.DS-01` |
| Doc ID | `AEGIS-PREPROC-{REG}-{NN}` | `AEGIS-PREPROC-AI_Act-00` |

**Forbidden**: spaces in filenames; `NIS 2` → use `NIS2`; `AI Act` → use `AI_Act`; `applies_to` as string → use JSON array.

---

## 2. Architecture (overview)

```
START → LOAD → Phase 1B → MAP → REDUCE → OUTPUT → END
```

| Phase | Owner | Calls | Output |
|-------|-------|-------|--------|
| LOAD | orchestrator.load() | `PreprocCatalogLoader` + `CaseProfileLoader` + `CatalogLoader` | `state["v2_*"]` (subdomains, SRs, SOs, clauses, pairs, audit, role_models, control_evidence, capabilities) |
| Phase 1B | `run_phase_1b()` | `P1B-LLM-01-INTERPRETATION` + `P1B-LLM-02-RATIONALE` (per regulation) | `state["aggregated_data"]["rationale_by_reg"]` |
| MAP | `map_domains()` | `P1C-LLM-01-OVERLAP-CLASSIFICATION` (per D-XX, ×10) | `state["domain_results"]` + `state["per_spec_markdown"]` |
| REDUCE | `reduce()` | deterministic concat/merge/conflicts/proportionality + `P1C-LLM-03-STRATEGIC-SYNTHESIS` + `P1C-LLM-02-COMPOUND-EVENT` (global) | `state["aggregated_data"]` (synthesis, compound_events, profile, conflicts) |
| OUTPUT | `generate_outputs()` | 9 deterministic renderer modules + `xlsx_generator` | 9 markdown docs + 1 xlsx |

Phase 1B runs BEFORE MAP (CORR-060) — per-regulation interpretation feeds the per-domain classification prompt as an input.

LangGraph state machine (`src/aegis_phase1/v2/graph.py`). 5 canonical LLMs in `src/aegis_phase1/prompts_v2/` (P1B-01/02, P1C-01/02/03). **Full details → `src/aegis_phase1/v2/AGENTS.md` and `src/aegis_phase1/prompts_v2/AGENTS.md`.**

### 2.1 LLM notes (provider · teacher-student · markdown parsing)

**Providers** (CORR-061): `ollama` (`ChatOllama`, default `gemma4:e4b`), `transformers` (`ChatTransformers`, no Ollama), `minimax` (`ChatMinimax`, M3/M2.7 via Mavis gateway). Select via `--provider` or `MOCK_LLM=true`.

**Teacher-Student** (CORR-061): Teacher M3 (Anthropic via Mavis) produces the gold standard; students `gemma4:e4b` and `qwen` iterate via prompt engineering; `MarkdownParser` (regex + Pydantic) extracts structured fields for diffing; loop is prompt → generate → parse → compare → diff → adjust; Quality Log records each iteration.

**Markdown parsing** (CORR-050): LLMs emit natural markdown (not JSON-Schema-constrained JSON). The 5 LLM specs use `MarkdownParser` (per-spec registered in `prompts_v2/markdown_parser.py:MARKDOWN_PARSERS`): the LLM emits a markdown template (`## Status`, `## Interpretations`, etc.) per `<output_contract>`; `RobustParser` falls back to JSON; `MarkdownParser` extracts fields via regex + Pydantic; `Phase1LLMInvoker._attempt` injects envelope fields (`case_id`, `prompt_spec_id`, `schema_version`) — **never** emitted by the LLM. **NO** format-constraining parameter is passed to the chat model.

---

## 3. Project Structure (compact)

```
src/aegis_phase1/
  v2/                # Production pipeline (CORR-037) — see AGENTS.md
    context/ output/ domain/ reduce/   # contexts, renderers, MAP filters, REDUCE
  prompts_v2/        # 5 canonical LLMs + RobustParser + MarkdownParser
  llm/ data/ config/ parsers/ prompts/ # invokers, data, case.yaml, intake, v1
  models.py state.py
tests/               # unit/v2/, integration/, fixtures/, data/
cases/               # case1-tinytask, case2-secureborder, case3-omnibank
data/                # YAML sources for tier/role/regulatory/control-evidence (CORR-073)
docs/ scripts/eval/ execution/         # docs + eval + contracts
```

Capabilities loader: `data/capabilities/{D-XX}.yaml` via `data/loader.py:load_capabilities()`.
`ROLE_VOCABULARY ∈ {DPO, CISO, Engineering, Operations, Governance}`. Silent `{}` on missing.

---

## 4. Commands (file-scoped → full suite)

```bash
# File-scoped tests
PYTHONPATH=src pytest tests/unit/v2/output/test_doc_04_stakeholder_leakage.py -v
# Full unit suite (skip slow + integration; -n auto for parallel)
PYTHONPATH=src pytest tests/unit/ -m "not slow" -n auto
# v1.2 smoke (needs Ollama + gemma4:e4b)
PYTHONPATH=src pytest tests/unit/prompts_v2/test_smoke_e2e.py -v

# Provider flags
PYTHONPATH=src python -m aegis_phase1.v2.runner --case cases/case1-tinytask --mock-llm
PYTHONPATH=src python -m aegis_phase1.v2.runner --case cases/case1-tinytask --provider ollama --model gemma4:e4b
PYTHONPATH=src python -m aegis_phase1.v2.runner --case cases/case1-tinytask --provider minimax --model MiniMax-M3
PYTHONPATH=src python -m aegis_phase1.v2.runner --case cases/case1-tinytask --deterministic-only --output /tmp/out

# Lint
ruff check src/ tests/ && ruff format --check src/ tests/
# CI gates
bash .hooks/ci-pipeline-inputs.sh   # CORR-070
bash .hooks/ci-frameworks.sh        # CSF policy
bash .hooks/validate-contracts.sh   # CORR-058

# Capabilities loader smoke

PYTHONPATH=src python -c "from aegis_phase1.data import load_capabilities, ROLE_VOCABULARY; print(ROLE_VOCABULARY); print(list(load_capabilities('D-01').keys()))"

# Setup (CANONICAL VENV: ../shared-venv-root/bin/python — worktree-relative)
PYTHONPATH=src ../shared-venv-root/bin/python -c "from aegis_phase1.v2.runner import main; print('OK')"
```

**Full operational reference → `tests/AGENTS.md`** (mock_llm, fixtures, pytest flags).

---

## 5. Git Workflow (1 branch per contract)


**Rule:** 1 branch per contract. Phases are sequential **commits**, never separate branches.

```bash
# CORRECT
git checkout main && git checkout -b feature/aegis-p1-corr-NNN
# WRONG (anti-pattern — never)
git checkout -b feature/phase0-rebranding      # NO
```

**Naming:** `feature/aegis-p1-corr-NNN-<short-name>`. **Commit format:** `type(corr-NNN): short description`.

**Pre-flight** before any subagent (orchestrator MUST run):
```bash
CURRENT_BRANCH=$(git branch --show-current)
python -c "from aegis_phase1.v2.runner import main; print('OK')"
PYTHONPATH=src pytest tests/unit/v2/ --co -q 2>&1 | grep -E "ERROR|ModuleNotFoundError"
# If any check fails: abort the subagent, fix first.
```

**Detailed branch policy + validator integrity rule + subagent rule: see `execution/CONTRACT-001.md` and CORR-NNN.md "Risks" sections.

---

## 6. Boundaries (Always / Ask first / Never)

| **Always** | Add tests for any code change. Run lint + tests before commit. Use type hints. Update nearest AGENTS.md if the rule belongs there. **Load the `hpc-deucalion` skill BEFORE touching the Deucalion cluster** (ssh, scp, sbatch, srun, squeue, model pulls on the login node, sync of code from workstation). Found a new Deucalion-cluster error (script bug, SLURM symptom, Ollama failure, network/quota issue)? Update the **`hpc-deucalion` skill** (source-of-truth at `~/Área de Trabalho/projects/my-skills/hpc-deucalion/`) with a row in its "Error playbook" section in the same commit that fixes the error — the skill is the living record, no recurring failure should pass twice. |
| **Ask first** | Adding new dependencies. Touching `Methodology-main/` (separate repo). Adding new regulation / entity kind to preproc. Neo4j / Langfuse / conftest changes. Renaming state keys. Schema changes mid-contract. |
| **Never** | Hardcode ports (use `.env`). Commit secrets or `.env` values. Edit `archive/`. Use `except: pass`. Withhold evidence (golden regen) when schema changes. Never `sbatch` heavy work on a login node (Rule #1 of `hpc-deucalion`). Never run two Ollama-serving scouts on the same node simultaneously (they collide on port 11434). |

---

## 7. Skills (Activate on Demand)

Skills load via `skill({name: "..." })`. Match a task to a skill's trigger phrase and load immediately — don't paraphrase.

> **Registered 2026-09-01:** skills marked *(symlinked)* live in
> `~/Área de Trabalho/projects/my-skills/` and are symlinked into
> `~/.zcode/skills/`. `agent-orchestration` is additionally symlinked into
> this repo's `.zcode/skills/` (workspace scope). **Restart ZCode** after
> changing skill registrations.

| Skill | When in this repo |
|-------|------|
| `sprint-contract` *(symlinked)* | **ALWAYS** load when the user asks for a contract (any size, any context); also: 3+ file changes, complex tasks, planning CORR-NNN contracts |
| `agent-orchestration` *(workspace)* | Any eval cycle (checker → judge → digest → matrix), contract planning, model-scoring, or validation gates — the distilled operating cycle (see also `execution/reports/EVAL_PROTOCOL.md`) |
| `hpc-deucalion` *(symlinked)* | **ALWAYS load before ANY Deucalion work** — covers staged-launch process (4 stages: local preflight → cluster smoke 1 GPU → real run → scale), job scripts using `_lib/common.sh` (porta unica por JOB, RUN_LOG desde linha 1, cache check por manifest dir), `scripts/hpc/preflight_local.sh` antes do Estadio 1, e `scripts/runs_tools/status.sh`. The skill has an "Error playbook" that must be updated whenever a new symptom is discovered (see § 6 Always). |
| `code-review` *(symlinked)* | Before merging, independent verification of changes |
| `python-best-practices` *(symlinked)* | Any Python code change |
| `project-conventions` *(symlinked)* | New AEGIS-KG naming, file structure, entity IDs |
| `context-checkpoint` *(symlinked)* | Context >70% during long sessions |
| `agents-md-writer` *(symlinked)* | Only when updating this file or any AGENTS.md |
| `neo4j-verify` *(symlinked)* | Before/after Neo4j-related work (port 7688/7475, no hardcoded ports) |
| `pdf` / `docx` / `xlsx` | **Via the official `document-skills` plugin** (not my-skills) — when case inputs/outputs include those formats |

Sub-AGENTS files list **folder-specific** trigger subsets — always read nearest file first.

---

## Sub-AGENTS map

- **`src/aegis_phase1/v2/AGENTS.md`** — orchestrator, runner, output/, domain/, reduce/
- **`src/aegis_phase1/prompts_v2/AGENTS.md`** — 5 LLM specs, PROMPTS library
- **`tests/AGENTS.md`** — testing patterns, mock_llm, regression tests

**Contract ref:** execution/CONTRACT-072.md. **Hierarchy rules:** all files ≤150 lines each; root hard limit 200; nearest file wins; split further if any sub-AGENTS grows.
