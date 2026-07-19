# D-01.1 Audit — CSF 1.1 → CSF 2.0 Mapping Coverage

**Subdomain:** D-01.1 Data at Rest Encryption
**Date:** 2026-07-19
**Auditor:** AEGIS-KG (manual, pre-automation)

## 1. Current State

### 1.1 Subdomain entity (`preproc_out/entities/subdomains/D-01.1.json`)

| Field | Value |
|---|---|
| `id` | D-01.1 |
| `domain_id` | D-01 |
| `title` | D-01.1 Data at Rest Encryption |
| `participating_regulations` | (empty — should be [GDPR, NIS2, CRA, DORA]) |
| `csf_hint` | [PR.DS-01, PR.DS-11] — 2 CSF 2.0 subcategories |
| `hso_hl.id` | SO-D-01.1.HL |
| `security_requirements` | 4 (per-SR CSF mapping = empty list) |
| `hso_per_reg` | 4 sub-SOs (GDPR, NIS2, CRA, DORA) — no CSF mapping |
| `pairs` | 6 crossregulation pairs |

### 1.2 Aggregated cross-reference (`global/NIST_CSF_2.0_subcategories.json`)

| Field | Value |
|---|---|
| `cross_reference_aegis_subdomains.rows[D-01.1]` | `csf_ids=[PR.DS-01, PR.DS-11]`, `csf_categories=[]` |
| `all_subcategories[D-01.1]` | (not present — only main 106 active subcategories are listed) |

### 1.3 Source `.md` (`methodology-00/PREPROCESSING/SubDomains/D-01_Data-Protection/D-01.1.md`)

- 50,744 chars
- 4 Security Requirements (each with `nist_csf_mapping: []` in source YAML)
- Mentions CSF IDs in narrative: `PR.DS-01`, `PR.DS-02`, `PR.DS-10`, `PR.DS-12`, `GV.RM-04`

## 2. Gaps Detected

### 2.1 Stale mapping: `PR.DS-12` is withdrawn in CSF 2.0

| Old (CSF 1.1) | New (CSF 2.0) | Status |
|---|---|---|
| `PR.DS-12` | `PR.DS-11` (Backups of data are created, protected, maintained, and tested) | RENAMED |

**Action:** The legacy `.md` still references `PR.DS-12` in narrative text. The `csf_hint` in the shard is **already migrated** to `PR.DS-11`. No fix needed in the shard, but the source `.md` should be updated separately (out of scope for this audit).

### 2.2 Sparse CSF coverage (only 2 of 185 active subcategories)

The `csf_hint` has only **2 IDs** for a subdomain about "Data at Rest Encryption". The CSF 2.0 official has **at least 7 relevant subcategories** for this domain:

| CSF 2.0 ID | Function | Title | Currently in csf_hint? |
|---|---|---|---|
| `PR.DS-01` | PR | confidentiality/integrity/availability of data-at-rest | ✅ |
| `PR.DS-11` | PR | Backups of data are created, protected, maintained, and tested | ✅ |
| `PR.DS-10` | PR | confidentiality/integrity/availability of data-in-use | ❌ (gap) |
| `PR.AA-01` | PR | Identities and credentials for authorized users, services, and hardware are managed | ❌ (gap — relevant to encryption key access) |
| `PR.AA-05` | PR | Access permissions, entitlements, and authorizations are defined in a policy | ❌ (gap — relevant to "who can read the encrypted data") |
| `ID.AM-08` | ID | Systems, hardware, software, and data are inventoried throughout their lifecycle | ❌ (gap — required for "what to encrypt") |
| `GV.RM-04` | GV | A determination of risk tolerance is made and clearly communicated | ❌ (gap — already mentioned in source) |
| `DE.CM-09` | DE | Computing hardware and software, runtime environments, and their data are monitored | ❌ (gap — monitoring of encrypted data) |

**Recommended `csf_hint` expansion for D-01.1:** `[PR.DS-01, PR.DS-11, PR.DS-10, PR.AA-01, PR.AA-05, ID.AM-08, GV.RM-04, DE.CM-09]`

### 2.3 Empty `nist_csf_mapping` per-SR

All 4 Security Requirements have `nist_csf_mapping: []`:

| SR | Title | Suggested CSF mapping |
|---|---|---|
| SR-D-01.1.GDPR (Personal data at rest) | (GDPR Art. 5(1)(f) + 32(1)(a)) | `PR.DS-01, PR.AA-05, GV.RM-04` |
| SR-D-01.1.NIS2 (NIS scope data at rest) | (NIS 2 Art. 21(2)(h)) | `PR.DS-01, PR.DS-11, GV.RM-04` |
| SR-D-01.1.CRA (Product data at rest) | (CRA Annex I (2)(e)) | `PR.DS-01, ID.AM-08, DE.CM-09` |
| SR-D-01.1.DORA (Financial-entity ICT data at rest) | (DORA Art. 9 + 24) | `PR.DS-01, PR.DS-11, PR.AA-01, GV.RM-04` |

**Action:** these need to be filled in. Currently ZERO SR has a CSF mapping in the shard.

### 2.4 Empty `participating_regulations`

The shard has `participating_regulations: []` but the source explicitly lists GDPR, NIS2, CRA, DORA. The crossregulation file confirms AI_Act is absent.

**Action:** fix to `["GDPR", "NIS2", "CRA", "DORA"]`.

## 3. Action Plan (proposed)

### Priority 1 (manual, immediate)

1. **Fix `participating_regulations`** in D-01.1: `[]` → `["GDPR", "NIS2", "CRA", "DORA"]`
2. **Expand `csf_hint`** from 2 to 8 IDs (add `PR.DS-10, PR.AA-01, PR.AA-05, ID.AM-08, GV.RM-04, DE.CM-09`)
3. **Fill `nist_csf_mapping` per-SR** (see table above)

### Priority 2 (semi-automated)

4. Build a `tools/audit_csf_mapping.py` script that, for each D-XX:
   - Reads the source `.md`
   - Extracts all CSF IDs mentioned in the YAML (currently empty)
   - Suggests additions based on keyword matching + function distribution
   - Reports gaps to a CSV/JSON file

### Priority 3 (full automation)

5. LLM-assisted mapping expansion: feed D-XX source + CSF 2.0 glossary, get suggested mapping, human review, apply.

## 4. Decisions to Take

Before I proceed:

- [ ] **Expand `csf_hint` to 8 IDs** (priority 1.2 above) for D-01.1 manually?
- [ ] **Fill `nist_csf_mapping` per-SR** (priority 1.3) for D-01.1 manually?
- [ ] **Fix `participating_regulations`** (priority 1.1)?
- [ ] **Build the audit tool first** (priority 2) — generate the report for all 38 subdomains so we can see the full picture?
- [ ] **Defer to automation** — just build the LLM-assisted mapping tool?

## 5. Validation

After fixes are applied, verify:
- `test_subdomain_d01_1_coverage`: 4 SRs with non-empty nist_csf_mapping
- `test_csf_hint_d01_1_expanded`: csf_hint has 8 IDs, all valid CSF 2.0
- `test_participating_regulations_d01_1`: 4 regulations present
- `test_no_orphan_csf`: no CSF ID in csf_hint that's not in CSF 2.0 official

## 6. Files Affected

- `preproc_out/entities/subdomains/D-01.1.json` (read + write)
- `preproc_out/global/NIST_CSF_2.0_subcategories.json` (update D-01.1 row)
- `scripts/preprocess/parsers/entities/subdomain.py` (source-of-truth fix for `participating_regulations` and `nist_csf_mapping`)
- `tests/unit/preprocess/test_subdomain_d01_1_audit.py` (new validation tests)
- `tools/audit_csf_mapping.py` (optional, for priority 2)
