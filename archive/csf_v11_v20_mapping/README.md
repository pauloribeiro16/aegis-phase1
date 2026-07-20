# Archive: CSF 1.1 → CSF 2.0 lineage mapping

**Archived by:** AEGIS-P1-CORR-028 (2026-07-20)
**Originally produced by:** AEGIS-P1-CORR-027 (2026-07-19)
**Reason for archival:** This project now uses **NIST CSF 2.0 ONLY** as the
control framework. The CSF 1.1 → CSF 2.0 lineage mapping was a
**one-shot reconciliation artefact** that has served its purpose; the
106 active CSF 2.0 subcategories are now the canonical catalogue.

## Why archive, not delete

- The 17 unit tests + the parser + the JSON mapping have historical value
  (audit trail of "what changed between v1.1 and v2.0").
- The 1.1 → 2.0 transition is a **completed** work item (CORR-027 was
  signed off 2026-07-20, 17/17 tests green, 6 commits, PR #28).
- Keeping a snapshot under `archive/` preserves the artefact for any
  future audit, without cluttering the active code path.

## Contents

| File | Original location | Notes |
|---|---|---|
| `csf_1_1_to_2_0_mapping.json` | `preproc_out/global/csf_1_1_to_2_0_mapping.json` | 108 mappings, NIST CSWP 41 (2018-04-16) → NIST CSWP 29 (2024-02-26) |
| `csf_mapping.py` | `scripts/preprocess/parsers/entities/csf_mapping.py` | Builder for the mapping (parses csf2.xlsx + applies identity-rename rules) |
| `test_csf_v11_to_v20_mapping.py` | `tests/unit/preprocess/test_csf_v11_to_v20_mapping.py` | 17 unit tests covering C1-C3 of the CORR-027 contract |

## SHA-256 (snapshot at archival time)

```
824a613479e36aac8954cc65b808977131a55a30bb4d14a934d39e2cae70278b  csf_1_1_to_2_0_mapping.json
9e5c04b6285be979997a693e533fbbe86a26c4fa695925e08a7defc46c40ff55  csf_mapping.py
3c9569a9a9f7b0589fb13af099859bfa240e753ef3b9ce6074e600e9d8caafa0  test_csf_v11_to_v20_mapping.py
```

## Restoring (if ever needed)

```bash
# Restore the JSON to its original location
cp archive/csf_v11_v20_mapping/csf_1_1_to_2_0_mapping.json preproc_out/global/

# Restore the parser
cp archive/csf_v11_v20_mapping/csf_mapping.py scripts/preprocess/parsers/entities/

# Restore the tests
mkdir -p tests/unit/preprocess
cp archive/csf_v11_v20_mapping/test_csf_v11_to_v20_mapping.py tests/unit/preprocess/

# Re-enable the writer in scripts/preprocess/pipeline.py
# (search for the commented-out "ARCHIVED in CORR-028" block and uncomment)

# Re-run
python -m scripts.preprocess build
pytest tests/unit/preprocess/test_csf_v11_to_v20_mapping.py -v
```

## See also

- `docs/NIST_CSF_2.0_ONLY.md` — the canonical declaration of framework policy
- `execution/CONTRACT-027.md` — original contract for the v1.1 → v2.0 work
- `execution/CONTRACT-028.md` — this archival contract
- `execution/AUDIT_D-01.1_CSF_MAPPING.md` — the audit that motivated the CORR-027 work
