# Plano Incremental, Faseado e Verificável para Adição de Casos de Uso (AEGIS Phase 1)

**Propósito:** Guia normativo e operacional para criar e validar novos casos de uso na Fase 1 da pipeline AEGIS.
**Princípio:** Mais escala, zero acoplamento no motor — arquitetura 100% data-driven com contratos estritos (Pydantic / CORR-102) e RefGate (CORR-112).

---

## 1. Visão Geral do Ciclo de Vida

```
F0: Spec & Config ──► F1: Entidade & Regras ──► F2: Arquitetura ──► F3: Validação Determinística ──► F4: E2E LLM & Gate
  (case.yaml)           (input/company/)         (input/architecture/)    (--deterministic-only)        (check_gate.py)
```

---

## 2. Fases de Implementação

### Fase 0 — Especificação e Metadados do Caso (`case.yaml`)
- Criar a diretoria: `cases/<case_id>/`
- Criar `cases/<case_id>/case.yaml`:
  - `case`: identificador canónico (ex: `"case4"`)
  - `name`: nome comercial da organização
  - `applicable_regulations`: subconjunto de `["GDPR", "CRA", "NIS2", "DORA", "AI_Act"]`
- **Validação (T2):**
  ```bash
  PYTHONPATH=src ../shared-venv-root/bin/python -c "
  import yaml; d = yaml.safe_load(open('cases/<case_id>/case.yaml'))
  assert 'case' in d and 'applicable_regulations' in d
  print('F0 OK: case.yaml válido')
  "
  ```

---

### Fase 1 — Factos Canónicos da Empresa e Governança (`input/company/` e `input/regulatory/`)
- Ficheiros obrigatórios em `input/company/`:
  - `classification.yaml`: Factos, escala (`MICRO`, `SMALL`, `MEDIUM`, `LARGE`), papéis regulamentares (`obligated_party`).
  - `business_goals.yaml`: Objetivos (`BG-01`..`BG-0N`, prioridades `HIGH`, `MEDIUM`, `LOW`).
  - `stakeholders.yaml`: Partes interessadas restritas ao `ROLE_VOCABULARY: {DPO, CISO, Engineering, Operations, Governance}`.
  - `implementation_readiness.yaml`: Maturidade nas 12 áreas de capacidade (Doc 04b).
  - `regulatory_classification.yaml`: Enums específicos das 5 regulações.
  - `role_matrix.yaml`: Matriz RACI regulatória.
- Ficheiros obrigatórios em `input/regulatory/`:
  - `applicability.yaml` e `interactions.yaml`.
- **Validação (T3):**
  ```bash
  PYTHONPATH=src ../shared-venv-root/bin/python -c "
  from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
  profile = CaseProfileLoader('cases/<case_id>').load()
  assert profile.company.scale in {'MICRO', 'SMALL', 'MEDIUM', 'LARGE'}
  assert len(profile.business_goals) > 0
  assert len(profile.stakeholders) > 0
  print('F1 OK: Factos e governança validados')
  "
  ```

---

### Fase 2 — Inventário da Arquitetura Técnica (`input/architecture/`)
- Ficheiros em `input/architecture/`:
  - `systems.yaml`: Aplicações e componentes.
  - `auth_systems.yaml`: Mecanismos de autenticação/IAM.
  - `cloud_services.yaml`: Fornecedores de computação e storage.
  - `data_flows.yaml`: Fluxos de dados.
  - `data_stores.yaml`: Bases de dados e logs.
  - *(Opcional)* `data_subjects.yaml`: Categorias de titulares de dados GDPR.
- **Validação (T3):**
  ```bash
  PYTHONPATH=src ../shared-venv-root/bin/python -c "
  from aegis_phase1.v2.loader.case_profile import CaseProfileLoader
  profile = CaseProfileLoader('cases/<case_id>').load()
  assert len(profile.architecture.systems) > 0
  print('F2 OK: Inventário arquitetural carregado')
  "
  ```

---

### Fase 3 — Validação Determinística Pré-LLM (Zero Custo)
- Execução determinística (sem consumo de LLM):
  ```bash
  PYTHONPATH=src ../shared-venv-root/bin/python -m aegis_phase1.v2.runner \
      --case cases/<case_id> \
      --deterministic-only \
      --output /tmp/test_<case_id>
  ```
- **Critérios de Aceitação:**
  - Código de saída `0`.
  - 6 artefactos gerados: Docs 04, 05, 06, 07, 07b e ficheiro Excel `.xlsx`.
  - Tags de proveniência `[deterministic]` em todas as secções.

---

### Fase 4 — Execução E2E com Modelo e Gate de Aceitação (CORR-112)
- Execução completa com RefGate em modo restrito:
  ```bash
  PYTHONPATH=src ../shared-venv-root/bin/python -m aegis_phase1.v2.runner \
      --case cases/<case_id> \
      --provider ollama \
      --model <model_tag> \
      --run-all \
      --output output/<case_id>_full
  ```
- **Certificação Final (`check_gate.py`):**
  ```bash
  PYTHONPATH=src ../shared-venv-root/bin/python scripts/eval/check_gate.py \
      --run-dir output/<case_id>_full
  ```
  - 0 referências ou artigos alucinados.
  - 0 secções com estado `PENDING`.
  - 100% de cobertura de tags de proveniência (`[deterministic]` ou `[LLM: ...]`).
