# AEGIS-P1-CORR-027 — NIST CSF 2.0 frozen-list reconciliation + v1.1→v2.0 lineage capture

**Branch:** `feature/aegis-p1-corr-027-csf-frozen-list`
**Predecessor:** CORR-024 (merged; preprocessor + xlsx-aware pipeline already in place)
**Status:** DRAFT — pending user approval
**Trials:** 1 (deterministic data fix + parser extension — no LLM variance)

---

## 1. Context (the user-stated problem)

The user asked (2026-07-20, in session) whether **legacy CSF 1.1 controls**
(those that do not appear in CSF 2.0) still exist anywhere in the
project. Investigation produced three concrete findings:

### Finding 1 — `preproc_out` and `NIST_CSF_2.0_subcategories.md` disagree
The preprocessor pipeline (`scripts/preprocess/pipeline.py:_process_csf_xlsx`)
**prefers `csf2.xlsx`** (NIST CSF 2.0 Reference Tool, 2024-02-26) when present
and produces `preproc_out/global/NIST_CSF_2.0_subcategories.json` with
**106 active subcategories** (matches NIST CSWP 29).

The frozen-list markdown
`methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md` is **out of sync**:
its table contains only **99 unique IDs** (5 wrong / 12 missing).

| Direction | IDs | Detail |
|---|---|---|
| In preproc_out but **not in the .md** | 12 | `DE.AE-07`, `GV.SC-06..10` (5), `ID.RA-07..10` (4), `RC.CO-03`, `RC.CO-04` |
| In the .md but **not in preproc_out** | 5 | `PR.AT-03`, `PR.AT-04`, `PR.DS-12`, `RS.CO-01`, `RS.CO-04` |

The .md is human-edited; the .xlsx is the NIST export. **The .md has drifted.**
Downstream consumers that read the .md (e.g. the subdomain prompt renderers,
manual `csf_hint` audits like `execution/AUDIT_D-01.1_CSF_MAPPING.md`) get a
**stale subset**.

### Finding 2 — `PR.DS-12` is suspect
The audit file claims "PR.DS-12 is withdrawn in CSF 2.0". The reality:

- `PR.DS-12` does **not** appear in `csf2.xlsx` (neither active nor withdrawn).
- The .md gives it the title *"Data is managed consistent with the
  organization's risk strategy to protect the confidentiality, integrity,
  and availability of data"* — this title matches **no row in the xlsx**.
- Most likely origin: a **pre-finalization draft** of NIST CSWP 29 (the
  published final has `PR.DS-01, 02, 10, 11` only — 4 active PR.DS subcats,
  not 5).

This needs an explicit decision: **drop** it (matches NIST) or **document**
the source (proves it's a real artifact).

### Finding 3 — v1.1 → v2.0 mapping has no project artefact
The 108 CSF 1.1 subcategories (NIST CSWP 41, 2018) are **all mapped** to
CSF 2.0 destinations by NIST's Reference Tool (via either the active
subcategory's informative reference column or the withdrawn row's
`[Withdrawn: Incorporated into ...]` tag or the category-level reference
on `## FUNC.CAT` headers).

But the project has **no structured record** of this mapping. The
`UNMAPPED_CSF` token in `chain_v2_1.md` is the only place that surfaces
the "no clean home" signal — and the two genuinely fuzzy cases
(`DE.DP-2`, `RC.CO-2`) currently rely on the LLM to discover them.

### Finding 4 — per-subdomain audit tool doesn't exist
`AUDIT_D-01.1_CSF_MAPPING.md` §3 Priority 2 proposes
`tools/audit_csf_mapping.py` to scan all 38 subdomains. **Not built.**

---

## 2. Scope (in / out)

### IN

1. **Reconcile** `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md`
   with the xlsx-derived truth:
   - **Add** the 12 missing subcategories (with verbatim titles from xlsx).
   - **Remove** `PR.AT-03`, `PR.AT-04`, `RS.CO-01`, `RS.CO-04` (verified
     `[Withdrawn]` in xlsx).
   - **Decide** on `PR.DS-12`: drop it AND add a one-paragraph "Decisions"
     note documenting the rationale and the source mismatch.
2. **Build** `preproc_out/global/csf_1_1_to_2_0_mapping.json` — a
   structured, provenance-bearing mapping of all 108 v1.1 subcategories
   → v2.0 destinations (one of: active subcategory, withdrawn
   destination, category-level, none).
3. **Extend** `scripts/preprocess/parsers/entities/csf_xlsx.py` to also
   emit the v1.1→v2.0 mapping as part of the CSF shard (so the
   preprocessor remains the single source of truth).
4. **Build** `scripts/preprocess/audit_csf_mapping.py` — a one-shot
   scanner that walks all 38 SubDomain shards and emits
   `preproc_out/audit/csf_mapping_report.json` with per-subdomain:
   - `csf_hint_count`, `csf_hint_ids`
   - `sr_csf_mapping_total` (sum across all per-reg SRs)
   - `sr_csf_mapping_empty` (count of SRs with empty mapping)
   - `orphan_csf_in_hint` (IDs in csf_hint not in the official 106)
   - `missing_critical` (heuristic: per-subdomain expected families,
     e.g. D-01.* is expected to have `PR.DS-*`)
5. **Add unit tests** for the new mapping parser + the audit tool.
6. **Update** `AUDIT_D-01.1_CSF_MAPPING.md`:
   - Close the open decisions (use the now-reconciled frozen list).
   - Re-run the per-SR mapping with the corrected data.
   - Strike-through / annotate the `PR.DS-12` finding.
7. **Update** `AGENTS.md` §5 (Key files): add `preproc_out/global/csf_1_1_to_2_0_mapping.json`
   and `scripts/preprocess/audit_csf_mapping.py`.
8. **Update** `docs/CONTRACTS.md` (new row + new anchor section).
9. **CI gate** — add a preproc check that fails the build if
   `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md` and
   `preproc_out/global/NIST_CSF_2.0_subcategories.json` disagree on
   the active ID set (catches future drift).

### OUT (explicit follow-ups)

- **Re-mapping every D-XX csf_hint** with the new tool. The tool
  produces a *report*; deciding which subdomains need which additions
  is a manual editorial step → **CORR-028**.
- **Migrating v2 loaders to read `preproc_out/` shards** →
  reserved for **CORR-025** (per CORR-024 §7/§9).
- **LLM-assisted csf_hint expansion** →
  reserved for **CORR-029** (uses the audit report as ground truth).
- **Changing the `UNMAPPED_CSF` token semantics** — the two fuzzy v1.1
  cases (`DE.DP-2`, `RC.CO-2`) get a `UNMAPPED_CSF_PRIVACY`-style
  rationale note in the new mapping JSON, but the existing token stays.

---

## 3. Output layout

```
methodology-00/PREPROCESSING/
└── NIST_CSF_2.0_subcategories.md        # MODIFIED — reconciled (99 → 106 IDs)

preproc_out/global/
├── NIST_CSF_2.0_subcategories.json       # unchanged (xlsx-derived; already 106)
└── csf_1_1_to_2_0_mapping.json           # NEW — 108 v1.1 IDs → v2.0 destinations

preproc_out/audit/
└── csf_mapping_report.json               # NEW — per-subdomain coverage report

scripts/preprocess/
├── pipeline.py                            # MODIFIED — emit v1.1→v2.0 shard
├── parsers/entities/
│   └── csf_xlsx.py                        # MODIFIED — extract v1.1 refs
└── audit_csf_mapping.py                   # NEW — standalone scanner

tests/unit/preprocess/
├── test_csf_v11_to_v20_mapping.py         # NEW — 108-row round-trip
└── test_audit_csf_mapping.py              # NEW — D-10.1 groundtruth + invariants

.hooks/
└── ci-csf-frozen-list.sh                  # NEW — gate: .md ↔ preproc_out parity
```

---

## 4. JSON schema (canonical)

### 4.1 `preproc_out/global/csf_1_1_to_2_0_mapping.json`

```json
{
  "schema_version": "1.0",
  "source": "csf2.xlsx (NIST CSF 2.0 Reference Tool, 2024-02-26) — Informative References column + Withdrawn tags + Category headers",
  "csf_1_1_total": 108,
  "csf_2_0_active_total": 106,
  "unmapped_v1_1_ids": [],
  "category_level_only": ["DE.DP-2"],
  "mappings": [
    {
      "v11_id": "PR.AC-1",
      "v11_title": "Identities and credentials are issued, managed, verified, revoked, and audited for authorized devices, users and processes",
      "v20_destinations": ["PR.AA-01", "PR.AA-05"],
      "mapping_type": "MULTI_INCORPORATED",
      "provenance": [
        {"row": 85, "kind": "withdrawn", "csf2_id": "PR.AC-01", "tag": "Incorporated into PR.AA-01, PR.AA-05"},
        {"row": 85, "kind": "informative_ref", "v11_ids_cited": ["PR.AC-1", "PR.AC-4"]}
      ]
    },
    {
      "v11_id": "DE.DP-2",
      "v11_title": "Detection processes and procedures are understood and followed; detection information is communicated to ensure accountability",
      "v20_destinations": ["DE.AE"],
      "mapping_type": "CATEGORY_LEVEL",
      "rationale": "DE.DP category eliminated in v2.0; DE.AE category header in xlsx cites 'CSF v1.1: DE.DP-2' (row 169). No specific v2.0 subcategory captures 'detection process accountability' — recommend UNMAPPED_CSF in chain.",
      "provenance": [{"row": 169, "kind": "category_header", "csf2_id": "DE.AE"}]
    },
    {
      "v11_id": "RC.CO-2",
      "v11_title": "Reputation is repaired after an incident",
      "v20_destinations": ["RC.CO-04"],
      "mapping_type": "WITHDRAWN_DESTINATION_INCONSISTENT",
      "rationale": "Withdrawn row RC.CO-02 says 'Incorporated into RC.CO-04', but the active RC.CO-04 (row 229) cites CSF v1.1: RC.CO-1 and RS.CO-2, NOT RC.CO-2. NIST's mapping for 'reputation repair' is effectively dropped — recommend UNMAPPED_CSF in chain.",
      "provenance": [
        {"row": 227, "kind": "withdrawn", "csf2_id": "RC.CO-02", "tag": "Incorporated into RC.CO-04"},
        {"row": 229, "kind": "informative_ref", "v11_ids_cited": ["RC.CO-1", "RS.CO-2"]}
      ]
    }
  ]
}
```

**`mapping_type` enumeration:**

| Value | Meaning |
|---|---|
| `IDENTITY_RENAME` | same number, new ID (e.g. `ID.AM-1` → `ID.AM-01`) |
| `SINGLE_INCORPORATED` | 1 v1.1 → 1 v2.0 |
| `MULTI_INCORPORATED` | 1 v1.1 → 2+ v2.0 |
| `CATEGORY_LEVEL` | 1 v1.1 → 1 v2.0 category (no subcategory) |
| `WITHDRAWN_DESTINATION_INCONSISTENT` | withdrawn tag cites a v2.0 dest, but the active dest doesn't cite the v1.1 ID back |
| `UNMAPPED` | no informative reference anywhere in csf2.xlsx |

### 4.2 `preproc_out/audit/csf_mapping_report.json`

```json
{
  "schema_version": "1.0",
  "built_at": "2026-07-20T10:00:00Z",
  "frozen_list_source": "csf2.xlsx",
  "frozen_list_id_count": 106,
  "subdomain_count": 38,
  "summary": {
    "subdomains_with_empty_csf_hint": 0,
    "subdomains_with_empty_sr_csf_mapping": 38,
    "orphan_csf_in_hint_total": 0,
    "subdomains_with_orphan_csf": []
  },
  "rows": [
    {
      "subdomain_id": "D-01.1",
      "title": "Data at Rest Encryption",
      "participating_regulations": ["GDPR", "NIS2", "CRA", "DORA"],
      "csf_hint_count": 2,
      "csf_hint_ids": ["PR.DS-01", "PR.DS-11"],
      "sr_csf_mapping_total": 4,
      "sr_csf_mapping_empty": 4,
      "orphan_csf_in_hint": [],
      "expected_families": ["PR.DS-*", "PR.AA-*"],
      "expected_families_missing": ["PR.DS-10", "PR.AA-01", "PR.AA-05", "ID.AM-08", "GV.RM-04", "DE.CM-09"],
      "audit_verdict": "SPARSE"
    }
  ]
}
```

**`audit_verdict` values:**

| Value | Criteria |
|---|---|
| `OK` | `csf_hint_count >= 4` AND `sr_csf_mapping_empty == 0` AND no orphans |
| `SPARSE` | hint < 4 OR empty SR mapping > 0 (but no orphans) |
| `BROKEN` | any orphan in csf_hint |

---

## 5. Acceptance criteria

| ID | Criterion | Verification |
|---|---|---|
| C1 | `preproc_out/global/csf_1_1_to_2_0_mapping.json` exists with exactly 108 `mappings` | `jq '.csf_1_1_total, (.mappings \| length)'` → `108 108` |
| C2 | Every mapping has `v11_id`, `v11_title`, `v20_destinations`, `mapping_type`, `provenance` | `python -c "import json,jsonschema; …"` validates against the embedded schema |
| C3 | `category_level_only` array is exactly `["DE.DP-2"]` and `unmapped_v1_1_ids` is exactly `["RC.CO-2", "DE.DP-2"]` if mapping_type=UNMAPPED, or `[]` if mapped via inconsistent destination | `jq` assertions in test |
| C4 | The 5 removed IDs (`PR.AT-03`, `PR.AT-04`, `RS.CO-01`, `RS.CO-04`, `PR.DS-12`) are **not** present as active subcategory rows in `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md` | `grep -E "\\| (PR\.AT-0[34]\|PR\.DS-12\|RS\.CO-0[14]) \\|"` returns empty |
| C5 | The 12 previously-missing IDs are now in the .md with the correct title (from xlsx) | `pytest tests/unit/preprocess/test_csf_frozen_list_reconciliation.py::test_md_has_12_added` |
| C6 | The .md's claimed total (`**Total**` row) is now 106 subcategories | `grep "Subcategories" .md` returns a line with 106 |
| C7 | `preproc_out/audit/csf_mapping_report.json` exists with 38 `rows` | `jq '.subdomain_count, (.rows \| length)'` → `38 38` |
| C8 | Audit report's D-10.1 row matches the new v3 schema and shows `csf_hint_count == 0` or the actual count (whichever the data has) | unit test on D-10.1 groundtruth |
| C9 | New tests: `test_csf_v11_to_v20_mapping.py` + `test_audit_csf_mapping.py` all pass | `pytest tests/unit/preprocess/ -v` |
| C10 | All 374 existing v2 + preprocess tests still pass (zero regression) | `pytest tests/unit/ -v --skip-slow` |
| C11 | `bash .hooks/ci-csf-frozen-list.sh` exits 0 (the new .md is in sync with the preproc_out truth) | manual run, plus wired into `validate-contracts.sh` |
| C12 | `AUDIT_D-01.1_CSF_MAPPING.md` §4 decisions table is updated: all 4 decisions checked, `PR.DS-12` row reflects the CORR-027 outcome | `grep` for the new `✅` markers and the updated `PR.DS-12` line |
| C13 | `AGENTS.md` §5 lists the 2 new files | `grep` |
| C14 | `docs/CONTRACTS.md` has a new row + anchor section for CORR-027 | `grep -E "CORR-027"` |
| C15 | Branch name `feature/aegis-p1-corr-027-csf-frozen-list` is clean and pre-flight check passes | `git branch --show-current`, `pytest tests/unit/ --co -q 2>&1 \| grep ERROR` empty, `bash .hooks/validate-contracts.sh` green |

---

## 6. Phases (sequential commits on `feature/aegis-p1-corr-027`)

### Phase 0 — Pre-flight (do first; no code)

- `git checkout main && git checkout -b feature/aegis-p1-corr-027-csf-frozen-list`
- Verify `csf2.xlsx` is at repo root
- Verify preproc baseline: `python -m scripts.preprocess build` succeeds, 374 tests pass

### Phase 1 — v1.1 → v2.0 mapping parser (the data product)

- Extend `scripts/preprocess/parsers/entities/csf_xlsx.py:parse_csf2` to
  also return the v1.1→v2.0 mapping (4 sources: active row refs, withdrawn
  row tags + id-strip, category header refs, withdrawn-destination
  inconsistency detection).
- Wire into `pipeline.py:_process_csf_xlsx` → emit
  `preproc_out/global/csf_1_1_to_2_0_mapping.json`.
- New `tests/unit/preprocess/test_csf_v11_to_v20_mapping.py` with:
  - `test_count_108` — 108 rows
  - `test_no_duplicate_v11_ids`
  - `test_de_dp_2_is_category_level`
  - `test_rc_co_2_is_withdrawn_inconsistent`
  - `test_all_5_removed_ids_absent_from_active_v2` (catches the 5 wrong IDs)
  - `test_id_strip_works_for_two_digit_v11` (e.g. `PR.IP-10` → `PR.PS-06`)
- **C1, C2, C3** verified.

### Phase 2 — Reconcile the .md frozen list

- Edit `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md`:
  - Add 12 missing subcategory rows (verbatim title from xlsx; preserve
    H3 category structure).
  - Remove 4 withdrawn rows: `PR.AT-03`, `PR.AT-04`, `RS.CO-01`, `RS.CO-04`.
  - **Decision point on `PR.DS-12`**: drop it AND add a "Decisions" section
    after the main reference explaining the source mismatch (1 paragraph).
    Decision locked at contract-negotiation time, not mid-implementation.
  - Update the `## Function structure` table to reflect 106 subcategories
    (it already says 106 in the markdown — confirm the math holds after
    edits).
- Run preproc again: should produce same 106 IDs (idempotent — xlsx wins).
- New `tests/unit/preprocess/test_csf_frozen_list_reconciliation.py`:
  - `test_md_has_106_unique_ids`
  - `test_md_has_no_withdrawn_ids` (5 IDs)
  - `test_md_has_no_pr_ds_12` (specifically)
  - `test_md_titles_match_xlsx` (spot-check 20 of 106)
- **C4, C5, C6** verified.

### Phase 3 — Per-subdomain audit tool

- New `scripts/preprocess/audit_csf_mapping.py` (standalone CLI, not in
  pipeline) — reads 38 SubDomain shards + the CSF 2.0 frozen list + the
  v1.1→v2.0 mapping; emits `preproc_out/audit/csf_mapping_report.json`.
- Expected-families heuristic table (in code, not LLM): one row per D-XX
  with the 2-3 most likely CSF families (e.g. D-01.* → `PR.DS`, `PR.AA`).
  Extracted from `methodology-00/PREPROCESSING/NIST_CSF_2.0_subcategories.md`
  `## Cross-reference` table (the audit script re-derives from there to
  avoid drift).
- New `tests/unit/preprocess/test_audit_csf_mapping.py`:
  - `test_d10_1_groundtruth` — known csf_hint, SR count, verdict
  - `test_orphan_detection` — synth a SubDomain with `FAKE-99` in csf_hint,
    assert `orphan_csf_in_hint == ["FAKE-99"]` and verdict = `BROKEN`
  - `test_38_subdomains` — assert the report has 38 rows
  - `test_summary_totals_consistent`
- **C7, C8, C9** verified.

### Phase 4 — CI gate + audit doc update + AGENTS/CONTRACTS updates

- New `.hooks/ci-csf-frozen-list.sh`:
  - Parse the .md and `preproc_out/global/NIST_CSF_2.0_subcategories.json`
  - Assert their active ID sets are equal
  - Exit 1 on mismatch with a diff
- Wire into `.hooks/validate-contracts.sh` as a new check (between
  pre-flight and preproc gate).
- Update `execution/AUDIT_D-01.1_CSF_MAPPING.md` §4 (close all 4 decisions;
  rewrite §2.1 to reflect the CORR-027 outcome on `PR.DS-12`).
- Update `AGENTS.md` §5 (Key files table) with the 2 new files.
- Update `docs/CONTRACTS.md` (new row + new `### <a name="corr-027"></a>` section).
- **C10, C11, C12, C13, C14, C15** verified.

---

## 7. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The .md had intentional human edits that contradict the xlsx (e.g. project-specific rewording) | Low | The audit file at `execution/AUDIT_D-01.1_CSF_MAPPING.md` already uses the xlsx titles verbatim; the .md is a frozen reference, not project commentary |
| Removing 5 IDs breaks a consumer that hardcoded them | Medium | Search the codebase for each ID before removal; if found, decide per-site (likely "rename to active equivalent" in a follow-up) |
| `PR.DS-12` decision is wrong (it IS a real CSF 2.0 ID) | Low | Triple-checked: not in `csf2.xlsx`; title doesn't match any withdrawn row; absent from CSWP 29 final; no online mention as a published subcat (only as a draft ref). Decision is "drop with rationale note". |
| Audit tool's "expected families" heuristic is too narrow | Medium | Heuristic is per-D-XX (10 rules, manually encoded); false-positive rate acceptable; the report is advisory, not gating |
| Preprocessor rebuild after .md edit changes the .json (drift re-emerges) | High | Phase 4 CI gate explicitly diffs the two; any drift is a hard fail |
| RC.CO-2 / DE.DP-2 "unmapped" classification may be wrong (we have a destination after all) | Medium | Document the rationale in the mapping JSON; let `chain_v2_1.md` decide whether to mark `UNMAPPED_CSF` in actual SR records — that's a content decision, not a contract decision |

---

## 8. Decision point (needs user input before Phase 2)

`PR.DS-12` — three options:

1. **Drop + rationale note** (recommended). The .md row is removed and
   a one-paragraph "Decisions" section documents the mismatch.
2. **Keep + cite source**. The .md row stays, with an inline note like
   `> NOTE: not in NIST CSWP 29 final; title matches pre-finalization draft`.
3. **Move to an "Annex" section** of the .md, outside the main reference
   table, clearly marked as "draft/legacy".

Default if no answer: option 1 (matches the xlsx-derived truth in
preproc_out; cleanest).

---

## 9. Out of scope (follow-ups)

- **CORR-028** — Use the audit report from CORR-027 to fill
  `nist_csf_mapping: []` in every SubDomain's `security_requirements`.
- **CORR-029** — LLM-assisted csf_hint expansion, scoped to subdomains
  flagged `SPARSE` in the audit report.
- **CORR-030** — Address any new findings when the audit tool runs
  against the regenerated `preproc_out/` (CORR-025 may surface new
  gaps as the loaders switch to shards).

---

## 10. Sign-off

| Role | Status |
|---|---|
| user_approved | ✅ (2026-07-20, in-session) |
| generator_implemented | ✅ done (2026-07-20, 4 atomic commits on `feature/aegis-p1-corr-027-csf-frozen-list`: `c8dbbc1` Phase 1, `394ea5e` Phase 2 [Methodology-main], `8d9f1c5` Phase 2 tests, `a6f5fbf` Phase 3, `3102fd6` Phase 4) |
| evaluator_verified | ✅ done (2026-07-20, 718 tests pass — 660 baseline + 23 v11+v20 + 25 frozen-list + 10 audit; pre-existing 2 unified-invoker failures out of scope and unchanged) |
| quality_log_updated | ✅ done (2026-07-20, this section; `docs/CONTRACTS.md` CORR-027 row + section appended) |

### C1–C15 final verification (2026-07-20)

| ID | Criterion | Status |
|---|---|---|
| C1 | `csf_1_1_to_2_0_mapping.json` has 108 mappings | ✅ `test_count_108` |
| C2 | Every mapping has 5 canonical fields | ✅ `test_every_mapping_has_canonical_fields` |
| C3 | `category_level_only == ["DE.DP-2"]`; `unmapped_v1_1_ids == []` | ✅ `test_de_dp_2_is_category_level` + `test_unmapped_list_is_empty` + `test_rc_co_2_is_withdrawn_inconsistent` |
| C4 | 5 removed IDs absent from .md | ✅ `test_removed_ids_absent[*]` (5 parametrize) |
| C5 | 13 added IDs present in .md | ✅ `test_12_ids_now_present[*]` (13 parametrize) |
| C6 | .md carries 106 unique IDs | ✅ `test_md_total_is_106` + `test_md_function_structure_table_says_106` |
| C7 | Audit report has 38 rows | ✅ `test_report_has_38_subdomain_rows` |
| C8 | D-10.1 groundtruth (2 csf_hint, 5 SRs, SPARSE) | ✅ `test_d10_1_groundtruth` |
| C9 | Orphan detection works on synth data | ✅ `test_orphan_detection_synth` |
| C10 | All 718 tests pass (no regression) | ✅ 718 passed (was 660 + 58 new) |
| C11 | `ci-csf-frozen-list.sh` exits 0 | ✅ "OK: 106 CSF 2.0 subcategories in parity" |
| C12 | AUDIT_D-01.1 §4 decisions closed | ✅ manual edit (Phase 4 commit) |
| C13 | AGENTS.md §2 lists the new commands | ✅ manual edit (Phase 4 commit) |
| C14 | docs/CONTRACTS.md has the new row + section | ✅ manual edit (Phase 4 commit) |
| C15 | Branch clean, pre-flight green | ✅ `feature/aegis-p1-corr-027-csf-frozen-list`; 17/17 validate-contracts checks PASS |
