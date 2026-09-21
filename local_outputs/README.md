# Case1-tinytask run-all outputs (CORR-116 + CORR-117)

Cada pasta = um JOB do Deucalion (1 GPU A100-80, partition normal-a100-80, modelo Ollama 0.32.13).

| Pasta | Job | Modelo | Walltime | Exit | Docs |
|---|---|---|---|---|---|
| `run_s3d_1904495/` | 1904495 | nemotron-3.5-lightning:30b | 53min | 0:0 | 9 md + xlsx |
| `run_corr117__1905317/` | 1905317 | qwen3.8:27b | 54min | 0:0 | 9 md + xlsx |
| `run_corr117__1905318/` | 1905318 | muse-glimmer:30b | 67min | 0:0 | 9 md + xlsx |
| `run_corr117__1905319/` | 1905319 | ornith-1.5:35b | 106min | 0:0 | 9 md + xlsx |

## Artefactos em cada run

| Ficheiro | O que é |
|---|---|
| `04_Company_Context_Assessment.md` | Doc 04 principal — síntese de factos da empresa |
| `04a_Architecture_DataInventory.md` | Doc 04a — arquitectura + inventário de dados |
| `04b_Security_Posture.md` | Doc 04b — postura de segurança |
| `04c_ThirdParty_Landscape.md` | Doc 04c — landscape de terceiros |
| `04d_Org_Roles_RACI.md` | Doc 04d — RACI |
| `05_Regulatory_Applicability.md` | Doc 05 — applicability regulations (GDPR + CRA no case1) |
| `06_Clause_Mapping_Matrix.md` | Doc 06 — clauses mapped to sub-domains |
| `07_Structured_Compliance_Matrix.md` | Doc 07 — matriz final |
| `07b_Proportionality_Profile.md` | Doc 07b — proportionality profile |
| `Case_01_Phase1.xlsx` | Excel consolidado (1 sheet por doc + cross-tabs) |

## Como comparar

```bash
# Diff Doc 05 entre modelos (devem chegar à mesma applicability)
diff -u local_outputs/run_s3d_1904495/05_Regulatory_Applicability.md \
        local_outputs/run_corr117__1905317/05_Regulatory_Applicability.md | head -50

# Md5 cross-check (já confirmado: 4 modelos, 4 hashes distintos)
md5sum local_outputs/*/05_Regulatory_Applicability.md
```

## Origem

Pulled do cluster Deucalion em 2026-09-10 via `scp -i ~/.ssh/id_ed25519 paulinho@login.deucalion.macc.fccn.pt:/projects/.../output/<JOB>/*`.

Outputs adicionais no cluster (não puxados — geração intermédia):
- `output/phase1/raw/P1B-LLM-*/<timestamp>__attempt*.md` — raw LLM markdown antes do parse (~30 raws novos)
- `output/phase1/raw/P1C-LLM-01-OVERLAP-CLASSIFICATION/<timestamp>__attempt*.md` — MAP raws (que provaram o S2.2 fix)
