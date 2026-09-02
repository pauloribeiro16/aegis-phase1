# CORR-057 — Baseline e2b eval report

- **Model:** gemma4:e2b
- **Case:** case1-tinytask
- **Total LLM entries in jsonl:** 5
- **Canonical refs loaded from preproc:** 1381

## 1. Schema/format compliance

| Spec | Total calls | OK | SCHEMA_ERROR | FORMAT_ERROR | FAILED | Compliance % |
|------|-------------|----|--------------|--------------|--------|--------------|
| P1B-LLM-01-INTERPRETATION | 1 | 1 | 0 | 0 | 0 | 100.0% |
| P1B-LLM-02-RATIONALE | 1 | 1 | 0 | 0 | 0 | 100.0% |
| P1C-LLM-01-OVERLAP-CLASSIFICATION | 1 | 1 | 0 | 0 | 0 | 100.0% |
| P1C-LLM-02-COMPOUND-EVENT | 1 | 1 | 0 | 0 | 0 | 100.0% |
| P1C-LLM-03-STRATEGIC-SYNTHESIS | 1 | 1 | 0 | 0 | 0 | 100.0% |

## 2. Citation accuracy (strict cross-check vs preproc)

| Spec | Total refs cited | Invented | Invented % | Top 5 invented |
|------|-----------------|----------|-----------|----------------|
| P1B-LLM-01-INTERPRETATION | 0 | 0 | 0.0% | — |
| P1B-LLM-02-RATIONALE | 0 | 0 | 0.0% | — |
| P1C-LLM-01-OVERLAP-CLASSIFICATION | 0 | 0 | 0.0% | — |
| P1C-LLM-02-COMPOUND-EVENT | 0 | 0 | 0.0% | — |
| P1C-LLM-03-STRATEGIC-SYNTHESIS | 0 | 0 | 0.0% | — |

## 3. Substantive content (activation count)

| Spec | Activations YES | Activations total | Rate |
|------|----------------|-------------------|------|
| P1B-LLM-01-INTERPRETATION | 1 | 1 | 100.0% |
| P1B-LLM-02-RATIONALE | 2 | 2 | 100.0% |
| P1C-LLM-01-OVERLAP-CLASSIFICATION | 0 | 0 | 0% |
| P1C-LLM-02-COMPOUND-EVENT | 0 | 0 | 0% |
| P1C-LLM-03-STRATEGIC-SYNTHESIS | 0 | 0 | 0% |

## 4. Structural parity (Doc 04/05/07)


## 5. Operational metrics (LLM)

| Spec | Latency mean (ms) | Latency max | Input tok mean | Output tok mean | Retries mean |
|------|-------------------|-------------|----------------|-----------------|--------------|
| P1B-LLM-01-INTERPRETATION | — | — | — | — | — |
| P1B-LLM-02-RATIONALE | — | — | — | — | — |
| P1C-LLM-01-OVERLAP-CLASSIFICATION | — | — | — | — | — |
| P1C-LLM-02-COMPOUND-EVENT | — | — | — | — | — |
| P1C-LLM-03-STRATEGIC-SYNTHESIS | — | — | — | — | — |

## 6. Parser gate (CORR-105 — independent L1 verdict)

| Spec | Pass | Fail | First 3 errors |
|------|------|------|----------------|
| P1B-LLM-01-INTERPRETATION | 1 | 0 | — |
| P1B-LLM-02-RATIONALE | 1 | 0 | — |
| P1C-LLM-01-OVERLAP-CLASSIFICATION | 0 | 1 | P1C-LLM-01-OVERLAP-CLASSIFICATION: no `## Section` headers found in markdown |
| P1C-LLM-02-COMPOUND-EVENT | 0 | 1 | P1C-LLM-02-COMPOUND-EVENT: no `## Section` headers found in markdown |
| P1C-LLM-03-STRATEGIC-SYNTHESIS | 0 | 1 | P1C-LLM-03-STRATEGIC-SYNTHESIS: no `## Section` headers found in markdown |
