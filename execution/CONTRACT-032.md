# AEGIS-P1-CORR-032 — Normalize all entity IDs to a single canonical form

**Branch:** `feature/aegis-p1-corr-032-id-normalization`
**Predecessor:** CORR-031 (entities-by-D-XX layout, merged in this branch's parent)
**Status:** DRAFT
**Trials:** 1 (deterministic text-substitution + regex migration)

---

## 1. Context (user decision 2026-07-20)

The AEGIS-KG entity IDs have drifted over the v0.x → v1.x → v2.x evolution. The user said: *"temos de normalizar isto, em todo o lado. Tipo as tem AIA outras vezes AI_A. Nas clausulas umas vezes tem AI_CL outras vezes CL apenas. Isto acontece de uma forma generica em todo este. Temos de normalizar tudo o possivel para não haver desentendimentos e registar as regras a seguir para não se repetir isto."*

Three concrete decisions captured from `ask_user` 2026-07-20:

1. **Clauses** use the canonical form **`{REG}-CL{NN}`** (e.g. `CRA-CL01`, `AI_Act-CL01`).
2. **AI_Act prefix** is **`AI_Act`** everywhere (not `AIACT` or `AIA`).
3. **Scope** is **renumber + rewrite** the source MDs in `Methodology-main` AND update the
   aegis-phase1 pipeline/parsers/audit/tests to match.

## 2. The drift inventory

| Pattern | Count | Where | Canonical replacement |
|---|---|---|---|
| `AIA-C{NN}` | 50 files, 29 clauses | AI_Act clause source MDs (Ambiguity/01..08) | `AI_Act-CL{NN}` |
| `GDPR-C{NN}` | 46 files, 28 clauses | GDPR source (no CL prefix) | `GDPR-CL{NN}` |
| `DORA-C{NN}` | 52 files, 38 clauses | DORA source (no CL prefix) | `DORA-CL{NN}` |
| `NIS2-CL{NN}` | 25 files, 53 clauses | NIS2 source (CL prefix already) | unchanged ✅ |
| `CRA-CL{NN}` | 51 files, 175 clauses | CRA source (CL prefix already) | unchanged ✅ |
| `DORA-CL{NN}` | 0 files | (target form, none yet) | unchanged |
| `GDPR-CL{NN}` | 32 files, 84 clauses | Mixed with `GDPR-C{NN}` | unchanged ✅ (target form) |
| `CL{NN}-{M}` (DORA orphan) | 7 files, 115 clauses | DORA cross-article v0.1 orphans | `DORA-CL{NN}-{M}` |
| `AIACT-CL{NN}` | 2 files, 4 clauses | Templates 06/02 | `AI_Act-CL{NN}` |
| `SO-AIACT-NNN` | 14 master SOs | 01_SecurityObjectives.md | `SO-AI_Act-NNN` |
| `SR-AIACT-NNN` | 24 master SRs | 02_SecurityRules_NIST.md | `SR-AI_Act-NNN` |
| `SO-D-XX.Y.AIACT` | 0 files | (none — already AI_Act) | unchanged ✅ |

**Total source files affected:** 222 (Methodology-main)

The pipeline side has its own drift: `_REG_NORMALIZE` in `parsers/entities/subdomain.py` only
accepts `"AI Act"` and `"AI_Act"` (not `AIACT`); `_entity_kind` in `pipeline.py` recognises
`AI_Act-CL` and `AIACT-CL` but the disk has `AIA-C`; etc.

## 3. Canonical ID conventions (NEW — added to AGENTS.md §11)

| Entity | Format | Example |
|---|---|---|
| Subdomain | `D-XX.Y` | `D-04.3` |
| Sub-SO (per-reg) | `SO-D-XX.Y.{REG}` | `SO-D-04.3.CRA` |
| Sub-SO (high-level) | `SO-D-XX.Y.HL` | `SO-D-04.3.HL` |
| Master SO | `SO-{REG}-{NNN}` (3-digit) | `SO-CRA-001`, `SO-AI_Act-001` |
| SR | `SR-{REG}-{NNN}` (3-digit) | `SR-CRA-001`, `SR-AI_Act-001` |
| Clause | `{REG}-CL{NN}` (2-digit) | `CRA-CL01`, `AI_Act-CL01` |
| Pair | `D-XX.Y_{REG_A}-{REG_B}` (alphabetic) | `D-04.3_CRA-AI_Act` |
| CSF | `GV.OC-01` (NIST standard) | unchanged |

**Reg canonical names (filesystem + JSON):**
`CRA`, `GDPR`, `NIS2`, `DORA`, `AI_Act`. The `AI_Act` form (with underscore) is canonical;
all aliases (`AI Act`, `AIACT`, `AIA`, `AIA-CL`, `AIA-C`, `AI-CL`, `AI-C`, `AI_Act-CL`)
are accepted on input but normalised to `AI_Act` on output.

## 4. Output criteria

| # | Criterion | Weight |
|---|-----------|--------|
| B1-1 | All 222 affected Methodology-main source MDs use canonical IDs (AIA-CNN→AI_Act-CLNN, etc.) | MUST |
| B1-2 | All 14 master `SO-AIACT-NNN` rewritten to `SO-AI_Act-NNN` in 01_SecurityObjectives.md | MUST |
| B1-3 | All 24 master `SR-AIACT-NNN` rewritten to `SR-AI_Act-NNN` in 02_SecurityRules_NIST.md | MUST |
| B1-4 | All 115 DORA orphan `CL{NN}-{M}` rewritten to `DORA-CL{NN}-{M}` | MUST |
| B2-1 | `_REG_NORMALIZE` accepts `AIACT`, `AIA`, `AI Act`, `AI_Act` (legacy aliases) and emits `AI_Act` | MUST |
| B2-2 | `_entity_kind` recognises `AI_Act-CL`, `AIA-C`, `AIACT-CL` on input | MUST |
| B2-3 | All preproc_out/entities/ shards have canonical IDs (no drift) | MUST |
| B2-4 | Audit invariants preserved: 282 full / 0 partial / 0 unresolved | MUST |
| B3-1 | New test `test_id_normalization.py` asserts: (a) no `AIA-C\d+` in preproc_out/, (b) no `SO-AIACT-`, (c) no `SR-AIACT-`, (d) all clauses match `{REG}-CL\d+` | MUST |
| B3-2 | All existing tests still pass (684 unit + 70 preprocess) | MUST |
| B4-1 | AGENTS.md §11 "Canonical ID conventions" documents the rules so the drift doesn't reappear | MUST |

## 5. Validation commands

| What | Command | Expected |
|------|---------|----------|
| No drift in source | `grep -rE 'AIA-C\|SO-AIACT-\|SR-AIACT-\|CL\d+-\d+\b' Methodology-main/00_METHODOLOGY/ \| wc -l` | 0 matches (in 01/02/03/Ambiguity dirs) |
| No drift in preproc | `grep -rE 'AIA-C\|AIACT-CL' aegis-phase1/preproc_out/entities/ \| wc -l` | 0 matches |
| Audit | `python -m scripts.preprocess.audit_so_sr_coherence` | `Coverage: full=282, partial=0, unresolved=0` |
| Tests | `PYTHONPATH=src pytest tests/unit/preprocess/ -q` | ≥70 pass |
| AGENTS.md | `grep -c "Canonical ID conventions" AGENTS.md` | 1 (the new section) |

## 6. Risk

- The renumbering touches 222 source files; any miss will cause a coverage gap.
  The new `test_id_normalization.py` catches misses by scanning preproc_out/.
- Aliases in `_REG_NORMALIZE` are forward-compatible: input can be any of the
  legacy forms, output is always `AI_Act`. The pipeline can still read older
  source MDs while we migrate.
- Migration is fully reversible (git revert) since it's text substitution.

## 7. Out of scope

- DORA `CL{NN}-{M}` format: keeping the `-{M}` suffix because DORA has multi-clause
  per article. The canonical form is `DORA-CL{NN}-{M}` (NN = article, M = clause
  within article).
- CSF subcategory IDs: NIST standard, not our format.
- Article IDs (Art_01.md, etc): directory structure, not IDs.
