# CORR-079 — Run log

**Status:** PASS (3 commits + 1 cleanup)
**Date:** 2026-07-30
**Branch:** `feature/aegis-p1-corr-079-rich-sidebars`

## Commits

| SHA | Type | Description |
|---|---|---|
| `12f6ee4` | docs | spec + contract + prose doc for sidebar 4-tabs |
| `9b5c807` | feat(viz) | sidebar 4 tabs (WS2) — Rendered / JSON / Markdown / Context |
| `a09652e` | fix(viz) | catastrophic-backtracking regex → linear split (WS3 perf) |
| `203f26e` | chore | gitignore docs/visualization/ build artifacts + untrack build_regulation_chain.py |
| (next) | docs | run log + quality log + HTML size optimization (this commit) |

## Sprint outcomes

| Sprint | Goal | Status | Key result |
|---|---|---|---|
| WS1 | Embed rawMd / sourceRole / obligatedParty / obligationType / crossRefs in payload | PASS | 5 new fields wired per spec; sidebar 4-tabs data layer ready |
| WS2 | Sidebar 4 tabs (Rendered / JSON / Markdown / Context) | PASS | 4 `detail-tab-btn` elements + 4 `tab-pane` containers in HTML |
| WS3 | Replace catastrophic-backtracking regex in `_read_clause_md` | PASS | Linear `str.find` + slice — build time dropped from >120s timeout to ~25s |
| Cleanup | Gitignore artifacts + reduce HTML 13.2 MB → 7.3 MB | PASS | `docs/visualization/build_regulation_chain.py` untracked; HTML ≤ 8 MB |

## HTML size optimization (commit this)

Before optimization (initial state after WS3):
- **HTML size:** 13.2 MB (12.86 MB embedded JSON)

Optimization applied (a + b + c + size-only MD fields):

| Field | Size before | Action | Saving |
|---|---|---|---|
| `articles[].securityRules[]` | 2581 KB | **dropped** (IDs only via `securityRuleIds`) | −2581 KB |
| `articles[].securityObjectivesFull[]` | 191 KB | **dropped** (IDs only via `securityObjectives`) | −191 KB |
| `regulations[].aggregatedSos[]` | 136 KB | **dropped** (top-level `sos[]` has them) | −136 KB |
| `regulations[].aggregatedSrs[]` | 1203 KB | **dropped** (top-level `srs[]` has them) | −1203 KB |
| `regulations[].raw02` (02_SecurityRules_NIST.md) | 1236 KB | **replaced by `raw02Size` int** (Context tab shows length only) | −1236 KB |
| `regulations[].raw01` (01_SecurityObjectives.md) | 182 KB | **replaced by `raw01Size` int** | −182 KB |
| `regulations[].rawValidation` | 175 KB | **replaced by `rawValidationSize` int** | −175 KB |
| `regulations[].rawAudit` | 92 KB | **replaced by `rawAuditSize` int** | −92 KB |
| `articles[].rawMd` | 2973 KB | **kept** (Markdown tab content) | 0 |
| `clauses[].rawMd` | 452 KB | **kept** (Markdown tab content) | 0 |
| `regulations[].rawReadme` | 112 KB | **kept** (Markdown tab fallback for regulations) | 0 |

After optimization:
- **HTML size:** 7.46 MB → **7.25 MB** on disk (gzipped JSON 7.20 MB)

JSON breakdown after optimization:

| Top-level field | Size |
|---|---|
| `articles` | 3160 KB (3.1 MB) — dominated by `rawMd` |
| `clauses` | 1908 KB (1.9 MB) — dominated by `instances` + `rawMd` + `intraSectionNotes` |
| `srs` | 1224 KB (1.2 MB) |
| `sos` | 956 KB (956 KB) |
| `regulations` | 121 KB (was 3145 KB) |
| **Total embedded JSON** | **7.20 MB** |

Total reduction: **13.2 MB → 7.3 MB (−45%)**

## Sample entity verification

| Entity | Field | Value |
|---|---|---|
| `articles[0]` (AI_Act_Art. 9) | `rawMd` | 70773 chars ✓ |
| `articles[0]` | `sourceRole` | `"primary_source"` ✓ |
| `articles[0]` | `crossRefs` | `{'sos': [], 'srs': [], 'clauses': ['DORA-CL16-2']}` ✓ |
| `articles[0]` | `securityRuleIds` | 12 IDs ✓ |
| `articles[0]` | `securityObjectives` | 8 IDs ✓ |
| `articles[0]` | `securityRules` (full) | **absent** (optimized out) ✓ |
| `articles[0]` | `securityObjectivesFull` | **absent** (optimized out) ✓ |
| `clauses[0]` | `rawMd` | 4379 chars ✓ |
| `clauses[0]` | `obligatedParty` / `obligationType` | populated when present in source (none for sample) ✓ |
| `clauses[0]` | `crossRefs` | `{'sos': [], 'srs': [], 'clauses': []}` ✓ |
| `regulations[0]` (AI_Act) | `rawReadme` | 31514 chars ✓ |
| `regulations[0]` | `raw02Size` | 133258 ✓ |
| `regulations[0]` | `aggregatedSos` / `aggregatedSrs` | **absent** (optimized out) ✓ |

## HTML structure verification

| Check | Result |
|---|---|
| `grep -c "detail-tab-btn"` | 9 (4 actual `<button>` + 5 CSS/JS refs) |
| `grep -c 'class="tab-pane"'` | 9 (4 actual panes + 5 other classes containing "tab-pane") |
| 4 `<button class="detail-tab-btn" data-tab="...">` | Rendered, JSON, Markdown, Context ✓ |

## Build artifacts

| File | Size | Status |
|---|---|---|
| `docs/visualization/build_regulation_chain.py` | 77.8 KB | gitignored (was tracked by accident at `a09652e`) |
| `docs/visualization/regulation_chain.html` | 7.46 MB | gitignored (regenerated via build script) |
| `/tmp/corr079_viz_backup/build_regulation_chain.py` | 77.8 KB | backup (updated 2026-07-30 18:04) |
| `/tmp/corr079_viz_backup/regulation_chain.html` | 7.46 MB | backup (updated 2026-07-30 18:04) |

## Lessons

1. **Profile before optimizing.** The rawMd content was suspected but the real bloat was duplicated arrays (`articles[].securityRules` × 99 + `regulations[].aggregatedSrs` × 5 = ~3.7 MB) plus the regulation-level `raw02` (1.2 MB) that was only referenced for its byte length.
2. **Distinguish content from metadata.** The Context tab listed MD files with their sizes but never rendered the content. Replacing the strings with size integers preserved UX with zero functionality loss.
3. **gitignore ephemeral artifacts at the door.** Build scripts that regenerate gigabyte-scale outputs should not be tracked. Adding `docs/visualization/build_*.py` to .gitignore prevents the same accidental-commit pattern.