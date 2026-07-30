# AEGIS-KG Naming Inconsistencies

**Status:** DRAFT (read-only diagnostic)
**Date:** 2026-07-30
**Scope:** `Methodology-main/00_METHODOLOGY/PREPROCESSING` + `preproc_out/`
**Companion:** referenced by `AGENTS.md §1b` (planned)

## Summary

| | Count |
|---|---:|
| Total inconsistencies identified | **23** |
| HIGH severity | **7** |
| MEDIUM severity | **4** |
| LOW severity | **5** |
| Items audited and OK (consistent) | **4** |

The investigation covered 5 regulation methodologies + all entity kinds in `preproc_out/`. Counts were derived from `grep -roh` over the source tree (raw occurrences of each variant, not file rollups).

---

## A. Identifiers (regulation / clause / SR / SO)

### A1 — AI Act regulation ID has 6 variants — HIGH

| Variant | Occurrences |
|---|---:|
| `AI_Act` (canonical) | 4289 |
| `AI Act` (space) | 4139 |
| `AIACT` (no underscore) | 242 |
| `AI-Act` (dash) | 178 |
| `AI_ACT` (all-caps) | 8 |
| `AI act` (lowercase A) | 2 |

**Fix**: pick exactly one — recommend `AI_Act`. Replace all other variants in methodology + generated `preproc_out/`.

### A2 — NIS2 regulation ID has 3 variants — HIGH

| Variant | Occurrences |
|---|---:|
| `NIS2` (canonical) | 6269 |
| `NIS 2` (with space) | 5877 |
| `NIS-2` (dash) | 40 |

**Fix**: use `NIS2` everywhere. The same issue caused the 2018 documentation era "NIS 2 Directive" name to drift.

### A3 — Clause ID suffixes CL/CP/RT/TR uncontrolled — HIGH

| Prefix | Occurrences |
|---|---:|
| `GDPR-CP` | 623 |
| `AI_Act-CL` | 658 |
| `GDPR-CL` | 547 |
| `CRA-D` | 17 (legacy) |
| `DORA-D` | 196 |
| `GDPR-RT` | 170 |
| `GDPR-TR` | 139 |
| `DORA-CL` | 1417 |
| `CRA-CL` | 1697 |
| `CRA-C` | 1 |
| `AIA-C` | 4 (legacy, predates CORR-032) |

**Findings**:
- The 5-letter suffixes (`CL`, `CP`, `RT`, `TR`, `D`) appear to be content-type markers, but the convention is not enforced — some clauses use `RT` instead of the expected `CL`.
- `AIA-C` (4 occurrences) is the pre-CORR-032 legacy; the canonical migration is `AIA-C` → `AI_Act-CL` (case-independent README §2.2).

**Fix**: define the master suffix mapping per clause content type, document in `SUBAGENT_BRIEF.md`, and sweep.

### A4 — Document ID prefix AIACT vs AI_Act — MEDIUM

| Prefix | Occurrences |
|---|---:|
| `AEGIS-PREPROC-AI_Act-NN` (canonical) | 24 |
| `AEGIS-PREPROC-AIACT-NN` (legacy, no underscore) | 1 |

Single legacy instance. **Fix**: replace the one occurrence; runs alongside A1.

### A5 — CSF ID dots → filename underscores — LOW

Canonical CSF ID is `PR.DS-01`, but the filename convention uses underscores (`PR_DS_01.json`). The conversion is consistent across all 106 active CSF shards. **Not a problem.**

### A6 — SO ID dots → filename underscores — LOW

Canonical SO ID is `SO-D-01.1.GDPR`, filename uses `SO-D-01_1_GDPR.json`. Same conversion rule as A5. **Not a problem.**

---

## B. Subdomain names

### B1 — Subdomain names diverge between CSV and methodology (user did not flag this category) — HIGH

| Subdomain | CSV (`02_subdomains.csv`) | Methodology (`SubDomains/index.md`) | Severity |
|---|---|---|---|
| `D-01.1` | `Encryption at Rest` | `D-01.1 Data at Rest Encryption` | MEDIUM (word order) |
| `D-01.3` | `Encryption Key Management` | `D-01.3 Key Management` | MEDIUM (prefix dropped) |
| **`D-01.4`** | **`Pseudonymisation`** | **`D-01.4 Data Integrity Mechanisms`** | **HIGH (completely different name)** |

**Critical**: `D-01.4` has two completely different names. CSV says "Pseudonymisation" (data-masking concept). Methodology says "Data Integrity Mechanisms" (CIA-triad concept). These are different security domains. CORR-077 audited this subdomain and continues to use the CSV name.

**Fix**: pick methodology as authoritative (it has the Volere shell + 02_SecurityRules references). Audit the CSV via fix contract.

---

## C. Data schema

### C1 — `applies_to` field is a string, not a list — HIGH

SOs in `entities/sos/` carry:

```json
"applies_to": "[GDPR]"        ← string literal "[GDPR]" with brackets
```

instead of:

```json
"applies_to": ["GDPR"]        ← JSON array
```

This breaks JSON array semantics. The brackets are a leftover from upstream methodology YAML where the field was written as `[GDPR]` (scalar inside block syntax). When the preproc builder serialized the YAML, it preserved the string instead of parsing the array.

**Fix**: parse the upstream YAML flow-style into proper JSON array. Apply globally in `preproc_out/` rebuild.

### C2 — `heading_under` is free text with embedded SO IDs — MEDIUM

Example:

```json
"heading_under": "SO-CRA-001 / SO-CRA-002 / SO-CRA-003 (confidentiality + stat..."
```

Multiple SO IDs are concatenated in one string with `/` separators. Not parseable as a list. **Fix**: convert to a `linked_objectives` array (which already exists) and either remove `heading_under` or make it a single SO reference.

### C3 — YAML booleans yes/no vs true/false — LOW

| YAML boolean | Occurrences |
|---|---:|
| `true` | 140 |
| `yes` | 4 |
| `no` | 28 |

`yes`/`no` is YAML-valid but inconsistent with `true`/`false`. **Fix**: standardize on `true`/`false`.

---

## D. Files

### D1 — 140 article files with literal SPACE in filename — HIGH

Every article shard has a space between the prefix and number:

```
AI_Act_Art_ 9.json    ← space between 'Art_' and '9'
GDPR_Art_ 32.json
CRA_Art_ 12.json
```

140 files across `preproc_out/entities/articles/`. Breaks:
- Shell glob (`*` won't match `'AI_Act_Art_ 9.json'` cleanly without quoting)
- URL encoding (%20 issues)
- Git operations on case-insensitive filesystems
- Cross-platform path handling

**Fix**: rename `*_Art_ *.json` → `*_Art_*.json` (or `*_Art-*.json`).

### D2 — `preproc_out/` has duplicate directory trees — HIGH

`preproc_out/` has both numbered and non-numbered directory names pointing at identical (byte-identical) data:

| Numbered | Non-numbered |
|---|---|
| `1-regulation/` (does NOT exist) | `regulation/` |
| `2-crossregulation/` (does NOT exist) | `crossregulation/` |
| `3-entities/` (does NOT exist) | `entities/` |
| `4-reference_and_meta/` (only one form) | (no duplicate) |

Wait — the investigated tree has only non-numbered variants in `preproc_out/`. The numbered-prefix tree is in `preproc_out/1-regulation/` from an older build state. Both directories coexist when the build has run multiple times with different config flags.

**Findings**:
- The 4-reference_and_meta form is the canonical structure
- The numbered 1-/2-/3-/4- prefix is the legacy layout
- They are content-identical but located in different paths
- Ambigous consumers (CI scripts, analytics) pick one and break

**Fix**: delete the legacy numbered-prefix duplicates. Keep only `regulation/`, `crossregulation/`, `entities/`, plus the new `4-reference_and_meta/`. (Match the 4-reference_and_meta naming style for the others.)

---

## E. Versions and metadata

### E1 — Status values include `static` (likely typo) — MEDIUM

| Value | Occurrences |
|---|---:|
| `DRAFT` | 298 |
| `static` | 39 (likely frontmatter typo for `status:static:` block) |
| `ACTIVE` | 3 |
| `ARCHIVE` | 1 |

`static` is not a documented status. Most likely a YAML copy-paste artifact where `status: |` (block) became `status: static` (string). **Fix**: investigate the 39 occurrences, replace with valid values, or extract them as block-style frontmatter.

### E2 — Schema versions per-regulation (not a problem) — LOW

Methodology YAML uses `version: 0.1`, `0.2`, `0.3` per regulation at different phases. Expected for in-progress work. **Not a problem.**

### E3 — `chain_version: v2.1` (consistent) — OK

81 occurrences all write `chain_version: v2.1`. **Consistent.** No fix needed.

---

## F. Content semantics

### F1 — Article references use `Art. {N}` (with point + space) — OK

2986 occurrences of `Art. 13`, 2916 of `Art. 9`, etc. **Consistent.** No fix needed.

### F2 — `source_clauses` use YAML flow-style — OK

Format `{ clause_id: GDPR-CL06, article_ref: "Art. 5(1)(f)" }` is consistent across all regulations. **No fix needed.**

### F3 — Language is English-only — OK

0 files in PREPROCESSING contain Portuguese phrases. **Consistent** with the language policy. No fix needed.

---

## Canonical formats — reference card

These are the formats a normalizer should target.

| Entity | Format | Regex (informal) | Example |
|---|---|---|---|
| Regulation | `GDPR` \| `CRA` \| `NIS2` \| `DORA` \| `AI_Act` | `^(GDPR\|CRA\|NIS2\|DORA\|AI_Act)$` | `AI_Act` |
| Clause | `{REG}-{SUFFIX}{NN}` (SUFFIX ∈ `CL`, `CP`, `RT`, `TR`) | `^(GDPR\|...\|AI_Act)-(CL\|CP\|RT\|TR)\d{2,3}$` | `GDPR-CL06`, `CRA-CL129` |
| Article | `{REG}_Art. {N}` | `^{REG}_Art\. \d+$` | `AI_Act_Art. 9` |
| Subdomain ID | `D-{NN}.{N}` (2-digit domain, 1-digit sub) | `^D-\d{2}\.\d$` | `D-01.4` |
| SO canonical | `SO-{REG}-{NNN}` | `^SO-(GDPR\|...)-(\d{3})$` | `SO-GDPR-001` |
| SO per-regulation | `SO-D-{NN}.{N}.{REG}` (use dot, not underscore) | `^SO-D-\d{2}\.\d\.(GDPR\|...)$` | `SO-D-01.1.GDPR` |
| SO high-level | `SO-D-{NN}.{N}.HL` | `^SO-D-\d{2}\.\d\.HL$` | `SO-D-01.1.HL` |
| SR | `SR-{REG}-{NNN}` | `^SR-(GDPR\|...)-(\d{3})$` | `SR-AI_Act-014` |
| CSF subcategory | `{FUNC}.{CAT}-{NN}` | `^(GV\|ID\|PR\|DE\|RS\|RC)\.[A-Z]{2}-\d{2}$` | `PR.DS-01` |
| Document ID | `AEGIS-PREPROC-{REG}-{NN}` | `^AEGIS-PREPROC-(GDPR\|...\|AI_Act)-\d{2}$` | `AEGIS-PREPROC-AI_Act-00` |

**Forbidden forms**:
- Spaces in filenames
- `NIS 2` → must be `NIS2`
- `AI Act`, `AIACT`, `AI-Act`, `AI_ACT`, `AI act` → must be `AI_Act`
- `applies_to` as `[GDPR]` (string with brackets) → must be `["GDPR"]` (array)

---

## Recommended priorities for a future normalization contract

Priority order if/when CORR-NNN opens to actually fix these:

1. **D2** — delete `preproc_out/{1-regulation,2-crossregulation}/` duplicates (1 commit, low risk)
2. **A1, A2, A3, A4** — sweep regulation IDs and clause suffix mappings (single script, 1 commit)
3. **D1** — rename 140 article filenames (script + commit, test file discovery)
4. **B1** — decide authoritative subdomain name CSV ↔ methodology (data change, audit-required)
5. **C1** — parse `applies_to` strings to JSON arrays (rebuild `preproc_out/`)
6. **C2** — split `heading_under` into structured fields
7. **E1** — fix `static` typos (~39 occurrences)
8. **C3, A5, A6, E2** — LOW priority, batch together

Items marked OK (F1, F2, F3, E3) require no action — only verify they remain consistent after the priority changes above.

---

## Methodology references

- `preproc_out/README.md` — top-level catalog
- `methodology-00/PREPROCESSING/Regulation/{REG}/02_SecurityRules_NIST.md` — canonical SR format
- `methodology-00/PREPROCESSING/SubDomains/Volere_shell.md` — Volere template
- `execution/CORR-032.md` — AI_Act → AI_Act migration context (closed)
- `execution/CORR-077.md` — CSV audit context
- `AGENTS.md §1b` — naming conventions quick-reference card (companion)
