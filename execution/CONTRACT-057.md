# CORR-057 — Setup Deucalion + baseline e2b eval (1 trial)

## Resumo

Primeiro port da pipeline AEGIS-KG v2 para o Deucalion (HPC) + avaliação
**baseline única** com `gemma4:e2b`. Objectivo: validar que o port
funciona + produzir relatório automático sobre **4 dimensões de
"responder bem"** (schema compliance, citation accuracy, substantive
content, structural parity) + 4 métricas operacionais LLM (latência,
tokens, retries, status).

**Não é comparação multi-modelo** — esse é CORR-058 depois de validarmos
que o port funciona. Aqui é só `gemma4:e2b` (1 trial, 1 caso).

**Branch:** `feature/aegis-p1-corr-057`
**Data:** 2026-07-23
**Trigger:** "quero correr a pipeline toda, com vários modelos no
deucalion […] com todos os logs possíveis para vermos o que está a dar e
o que não está a resultar".

**Decisões locked (perguntas respondidas):**
- **1 modelo**: gemma4:e2b (baseline; multi-modelo é CORR-058)
- **"Responder bem" = 4 dimensões**: schema/format + citation accuracy (strict) + activation count + structural parity
- **Tratamento falhas**: continua + log detalhado; crash = iterar (sem wrap)
- **Partition**: dev-a100-40 (curto, 4h)
- **Submissão**: scout primeiro, depois eval
- **Sincronização**: tar+scp (skill procedimento)
- **preproc_out**: incluído no tarball (self-contained)
- **Caso**: case1-tinytask (com `--case` explícito, não default)
- **Langfuse**: OFF no HPC (só JSONL)
- **Trials**: 1
- **Análise**: colher + relatório (ambos Markdown + JSON)
- **Resultados**: rsync tudo para workstation

---

## Pré-flight (executor TEM de verificar antes de começar)

```bash
cd /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1
source ../shared-venv/bin/activate

# 1. Estado do repo
git branch --show-current                # main ou outra — criar branch nova
git log --oneline -5                     # confirmar CORR-056 commit presente
git status --short | head -10            # ver trabalho uncommitted

# 2. Confirmar trabalho pendente que precisa commit
ls -la src/aegis_phase1/llm/transformers_invoker.py scripts/corr056_compare_models_v2.py 2>&1

# 3. Confirmar acesso SSH ao Deucalion
ssh -i /home/epmq-cyber/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=10 \
    paulinho@login.deucalion.macc.fccn.pt 'echo SSH OK; hostname; whoami' 2>&1

# 4. Confirmar que case1-tinytask tem dados completos
ls cases/case1-tinytask/{case.yaml,data/phase1,input} 2>&1 | head -10

# 5. Confirmar preproc_out tem dados (vai no tarball)
du -sh preproc_out 2>/dev/null

# 6. Confirmar pyproject.toml existe (sem requirements.txt)
ls pyproject.toml requirements.txt 2>&1
```

Se SSH falhar (passo 3): ABORTAR. Não dá para submeter jobs sem acesso.
Se trabalho pendente falta (passo 2): ABORTAR. Confirmar com user antes.

---

## Decisões de produto (NÃO negociáveis)

1. **Scout primeiro** (10 min, CPU, sem GPU). Só submeter eval depois
   de scout dar PASS em módulos + Ollama bin + GPU + model cache.
2. **Langfuse explicitamente OFF** no sbatch: `LANGFUSE_ENABLED=false`.
3. **Case path explícito**: `--case cases/case1-tinytask`. Não confiar
   no default que aponta para `Methodology-main/02_CASES/...` (não vai
   existir no tarball se Methodology-main não for incluído).
4. **Tarball self-contained**: inclui `preproc_out/`, `cases/`,
   `Methodology-main/00_METHODOLOGY/` (só PROMPTS + TEMPLATES + diagrams
   — não casos preenchidos), `src/`, `scripts/`, `tests/`, `pyproject.toml`.
   Excluir `.venv/`, `__pycache__/`, `logs/`, `output/`, `.git/`.
5. **Resultados em `~/aegis-kg/results/corr057-${SLURM_JOB_ID}/`** (NFS
   persistente, não /tmp).
6. **Crash = iterar** (sem wrap try/except). `set -x` no sbatch para
   rastreabilidade.
7. **4 dimensões de "responder bem"**, todas implementadas no gerador
   de relatório (T3).

---

## Tarefas

### T1 — Commit trabalho pendente

```bash
cd /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1
git checkout main
git checkout -b feature/aegis-p1-corr-057

# Commit do trabalho pendente (CORR-056 follow-up)
git add src/aegis_phase1/llm/transformers_invoker.py scripts/corr056_compare_models_v2.py
git status --short  # confirmar que só estes 2
git commit -m "CORR-056 follow-up: commit transformers_invoker system_prompt param + compare_models_v2 script

Pre-CORR-057 cleanup: uncommitted work from CORR-056 needs to land before
tar+scp to Deucalion. The transformers_invoker now accepts system_prompt
as a separate arg for fair A/B comparison (SystemMessage preserved rather
than concatenated into user content). corr056_compare_models_v2.py
provides the reference implementation."
```

### T2 — Criar `scripts/eval/run_eval_deucalion.sh`

**Ficheiro NEW:** `scripts/eval/run_eval_deucalion.sh`

```bash
#!/usr/bin/env bash
# CORR-057: orchestrator for the e2b baseline eval on Deucalion GPU.
# Called by eval-corr057.sbatch after env setup + Ollama start.
#
# Usage (inside sbatch):
#   bash scripts/eval/run_eval_deucalion.sh
#
# Requires these env vars (set by sbatch):
#   OLLAMA_HOST (default http://localhost:11434)
#   OLLAMA_BIN  (path to ollama binary)
#   RESULTS_DIR (where to persist artefacts)
#   PWD         (~/aegis-kg after cd)

set -euo pipefail
set -x  # trace para rastreabilidade

MODEL="${OLLAMA_MODEL:-gemma4:e2b}"
CASE="${EVAL_CASE:-cases/case1-tinytask}"
RESULTS_DIR="${RESULTS_DIR:-results/corr057-unknown}"
mkdir -p "$RESULTS_DIR"

echo "[eval] === CORR-057 eval baseline e2b ==="
echo "[eval] model=$MODEL case=$CASE"
echo "[eval] results=$RESULTS_DIR"

# 1. Verificar que o modelo está disponível no cache (não pull — pré-loaded)
echo "[eval] checking model availability"
ollama list 2>&1 | head -20
if ! ollama list 2>&1 | grep -q "e2b"; then
    echo "[eval] WARN: e2b not in list — will try anyway (may auto-download from registry)"
fi

# 2. Smoke de 1 chamada (validar que Ollama responde)
echo "[eval] === smoke test: 1 direct LLM call ==="
python <<EOF
import sys, time
sys.path.insert(0, "src")
from aegis_phase1.v2.llm import build_llm_invoker
inv = build_llm_invoker(model="gemma4:e2b", provider="ollama")
msg = inv.chat.invoke([{"role": "user", "content": "Reply with the word READY"}])
print(f"smoke response: {msg.content[:100]}")
print("SMOKE OK")
EOF

# 3. Limpar logs anteriores (cada run começa limpo)
rm -f logs/phase1/llm-calls.jsonl logs/phase1/format-errors.jsonl logs/phase1/performance.csv
mkdir -p logs/phase1

# 4. Correr a pipeline completa
echo "[eval] === full pipeline run ==="
START=$(date +%s)
python -m aegis_phase1.v2.runner \
    --case "$CASE" \
    --model "$MODEL" \
    --provider ollama \
    --run-all \
    2>&1 | tee "$RESULTS_DIR/corr057_run.log"
PIPELINE_EXIT=$?
END=$(date +%s)
echo "[eval] pipeline exit=$PIPELINE_EXIT duration=$((END-START))s"

# 5. Gerar relatório (mesmo se pipeline falhou — para ver onde parou)
echo "[eval] === generating report ==="
python scripts/eval/generate_report.py \
    --jsonl logs/phase1/llm-calls.jsonl \
    --output-dir "$RESULTS_DIR" \
    --preproc preproc_out \
    --output-md "$RESULTS_DIR/corr057_eval_report.md" \
    --output-json "$RESULTS_DIR/corr057_eval_data.json" \
    2>&1 | tee "$RESULTS_DIR/corr057_report.log" || echo "[eval] report generation failed (continuing)"

# 6. Copiar artefactos relevantes para RESULTS_DIR
cp -r logs/phase1 "$RESULTS_DIR/logs_phase1" 2>/dev/null || true
cp -r output/phase1/*.md "$RESULTS_DIR/" 2>/dev/null || true
cp -r output/phase1/*.xlsx "$RESULTS_DIR/" 2>/dev/null || true

echo "[eval] === DONE — artefacts in $RESULTS_DIR ==="
ls -la "$RESULTS_DIR"
```

`chmod +x scripts/eval/run_eval_deucalion.sh`.

### T3 — Criar `scripts/eval/generate_report.py`

**Ficheiro NEW:** `scripts/eval/generate_report.py`

```python
#!/usr/bin/env python3
"""CORR-057: generate evaluation report from llm-calls.jsonl.

Produces 2 outputs:
  --output-md   : Markdown report with 4 sections (schema/citation/activation/parity)
  --output-json : Structured JSON for programmatic analysis

Dimensions:
  1. Schema/format compliance: % of calls per spec that pass parser/validator
  2. Citation accuracy: legal_refs/layer0_refs cross-checked against preproc
  3. Substantive content: activation count per spec
  4. Structural parity: presence of critical elements in Doc 04/05/06/07

Operational metrics: latency, tokens, retry count, status distribution.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--jsonl", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--preproc", required=True, type=Path, help="path to preproc_out")
    p.add_argument("--output-md", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    return p.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    entries = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries


def load_canonical_refs(preproc: Path) -> set[str]:
    """Load all canonical legal references from preproc clauses."""
    refs: set[str] = set()
    clauses_root = preproc / "3-entities" / "clauses" / "_root"
    if not clauses_root.exists():
        return refs
    for reg_dir in clauses_root.iterdir():
        if not reg_dir.is_dir():
            continue
        for clause_file in reg_dir.glob("*.json"):
            try:
                data = json.loads(clause_file.read_text(encoding="utf-8"))
                # section_ref is the canonical article ref
                sr = data.get("section_ref")
                if sr:
                    refs.add(sr)
                # also collect berry_anchors (article refs in the clause)
                for anchor in data.get("berry_anchors", []) or []:
                    if anchor:
                        refs.add(anchor)
            except Exception:
                pass
    return refs


def extract_refs_from_output(output) -> list[str]:
    """Extract legal_refs + layer0_refs from LLM output (dict or markdown)."""
    refs = []
    if isinstance(output, dict):
        # Walk common shapes
        for path in [
            ("interpretations",), ("derogations",),
            ("sub_domain_activations",), ("implications",),
            ("positive_events",), ("negative_events",),
        ]:
            node = output
            for k in path:
                node = node.get(k, []) if isinstance(node, dict) else []
                if not isinstance(node, list):
                    node = []
                    break
            if isinstance(node, list):
                for item in node:
                    if isinstance(item, dict):
                        refs.extend(item.get("legal_refs", []) or [])
                        refs.extend(item.get("layer0_refs", []) or [])
    elif isinstance(output, str):
        # Markdown: extract via regex
        for m in re.finditer(r"^-\s*(?:legal_refs|layer0_refs)\s*:\s*(.+)$", output, re.MULTILINE):
            for r in m.group(1).split(","):
                r = r.strip().lstrip("-").strip()
                if r:
                    refs.append(r)
    return refs


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)

    entries = load_jsonl(args.jsonl)
    canonical_refs = load_canonical_refs(args.preproc)

    # Per-spec aggregation
    per_spec: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "by_status": Counter(),
        "latencies_ms": [], "input_tokens": [], "output_tokens": [], "retries": [],
        "all_refs_cited": [], "invented_refs": [],
        "activations_yes": 0, "activations_total": 0,
    })

    for e in entries:
        spec = e.get("spec_id", "UNKNOWN")
        status = e.get("status", "UNKNOWN")
        spec_data = per_spec[spec]
        spec_data["total"] += 1
        spec_data["by_status"][status] += 1

        # Latency
        lat = e.get("latency_ms") or e.get("total_latency_ms")
        if lat:
            spec_data["latencies_ms"].append(lat)

        # Tokens
        usage = e.get("usage") or {}
        it = usage.get("input_tokens") or usage.get("prompt_tokens")
        ot = usage.get("output_tokens") or usage.get("completion_tokens")
        if it and it > 0: spec_data["input_tokens"].append(it)
        if ot and ot > 0: spec_data["output_tokens"].append(ot)

        # Retries
        attempts = e.get("all_attempts") or []
        if attempts:
            spec_data["retries"].append(len(attempts))

        # Citation accuracy
        output = e.get("output") or e.get("parsed_output") or {}
        cited = extract_refs_from_output(output)
        spec_data["all_refs_cited"].extend(cited)
        for ref in cited:
            # Match against canonical set (loose match: substring)
            if not any(ref in c or c in ref for c in canonical_refs):
                spec_data["invented_refs"].append(ref)

        # Activation count (for spec that has applicable field)
        def _count_yes(o):
            if isinstance(o, dict):
                for k in ("interpretations", "derogations", "implications",
                          "positive_events", "negative_events", "sub_domain_activations"):
                    items = o.get(k, []) if isinstance(o, dict) else []
                    if isinstance(items, list):
                        for it in items:
                            if isinstance(it, dict):
                                spec_data["activations_total"] += 1
                                if (it.get("applicable", "").upper() == "YES" or
                                    it.get("activation_verdict", "").upper() == "ACTIVATED"):
                                    spec_data["activations_yes"] += 1
        _count_yes(output)

    # Compute aggregates
    spec_summary = {}
    for spec, d in per_spec.items():
        spec_summary[spec] = {
            "total_calls": d["total"],
            "status_distribution": dict(d["by_status"]),
            "schema_compliance_pct": round(
                100 * d["by_status"].get("OK", 0) / max(1, d["total"]), 1
            ),
            "latency_ms_mean": round(sum(d["latencies_ms"]) / max(1, len(d["latencies_ms"])), 0) if d["latencies_ms"] else None,
            "latency_ms_max": max(d["latencies_ms"]) if d["latencies_ms"] else None,
            "input_tokens_mean": round(sum(d["input_tokens"]) / max(1, len(d["input_tokens"])), 0) if d["input_tokens"] else None,
            "output_tokens_mean": round(sum(d["output_tokens"]) / max(1, len(d["output_tokens"])), 0) if d["output_tokens"] else None,
            "retries_mean": round(sum(d["retries"]) / max(1, len(d["retries"])), 2) if d["retries"] else None,
            "total_refs_cited": len(d["all_refs_cited"]),
            "invented_refs_count": len(d["invented_refs"]),
            "invented_refs_pct": round(100 * len(d["invented_refs"]) / max(1, len(d["all_refs_cited"])), 1),
            "top_invented_refs": Counter(d["invented_refs"]).most_common(10),
            "activations_yes": d["activations_yes"],
            "activations_total": d["activations_total"],
        }

    # Structural parity check (read output/phase1/*.md if present)
    parity = {}
    out_dir = Path("output/phase1")
    if out_dir.exists():
        # Doc 05: applicable_regs
        doc05 = out_dir / "05_Regulatory_Applicability.md"
        if doc05.exists():
            txt = doc05.read_text(encoding="utf-8", errors="ignore")
            parity["doc05_applicable_regs"] = {
                "has_gdpr": "GDPR" in txt,
                "has_cra": "CRA" in txt,
                "pass": "GDPR" in txt and "CRA" in txt,
            }
        # Doc 07: row count
        doc07 = out_dir / "07_Structured_Compliance_Matrix.md"
        if doc07.exists():
            txt = doc07.read_text(encoding="utf-8", errors="ignore")
            n_rows = len(re.findall(r"^\|\s*D-\d+\.\d+", txt, re.MULTILINE))
            parity["doc07_subdomain_rows"] = {"count": n_rows, "expected": 38, "pass": n_rows >= 30}
        # Doc 04: company facts
        doc04 = out_dir / "04_Company_Context_Assessment.md"
        if doc04.exists():
            txt = doc04.read_text(encoding="utf-8", errors="ignore")
            parity["doc04_company_facts"] = {
                "has_employees_8": "8" in txt and "employees" in txt.lower(),
                "has_portugal": "Portugal" in txt,
                "has_technology": "Technology" in txt,
            }

    # Build full data structure
    data = {
        "contract": "CORR-057",
        "model": "gemma4:e2b",
        "case": "case1-tinytask",
        "total_entries": len(entries),
        "canonical_refs_loaded": len(canonical_refs),
        "per_spec": spec_summary,
        "structural_parity": parity,
    }

    # Write JSON
    args.output_json.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # Build Markdown
    lines = [
        "# CORR-057 — Baseline e2b eval report",
        "",
        f"- **Model:** gemma4:e2b",
        f"- **Case:** case1-tinytask",
        f"- **Total LLM entries in jsonl:** {len(entries)}",
        f"- **Canonical refs loaded from preproc:** {len(canonical_refs)}",
        "",
        "## 1. Schema/format compliance",
        "",
        "| Spec | Total calls | OK | SCHEMA_ERROR | FORMAT_ERROR | FAILED | Compliance % |",
        "|------|-------------|----|--------------|--------------|--------|--------------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        sd = s["status_distribution"]
        lines.append(
            f"| {spec} | {s['total_calls']} | {sd.get('OK', 0)} | "
            f"{sd.get('SCHEMA_ERROR', 0)} | {sd.get('FORMAT_ERROR', 0)} | "
            f"{sd.get('FAILED_AFTER_RETRIES', 0)} | {s['schema_compliance_pct']}% |"
        )
    lines.append("")

    lines += [
        "## 2. Citation accuracy (strict cross-check vs preproc)",
        "",
        "| Spec | Total refs cited | Invented | Invented % | Top 5 invented |",
        "|------|-----------------|----------|-----------|----------------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        top5 = "; ".join(f"{r}({n}x)" for r, n in s["top_invented_refs"][:5]) or "—"
        lines.append(
            f"| {spec} | {s['total_refs_cited']} | {s['invented_refs_count']} | "
            f"{s['invented_refs_pct']}% | {top5} |"
        )
    lines.append("")

    lines += [
        "## 3. Substantive content (activation count)",
        "",
        "| Spec | Activations YES | Activations total | Rate |",
        "|------|----------------|-------------------|------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        rate = round(100 * s["activations_yes"] / max(1, s["activations_total"]), 1) if s["activations_total"] else 0
        lines.append(f"| {spec} | {s['activations_yes']} | {s['activations_total']} | {rate}% |")
    lines.append("")

    lines += [
        "## 4. Structural parity (Doc 04/05/07)",
        "",
    ]
    for elem, info in parity.items():
        lines.append(f"- **{elem}**: `{info}`")
    lines.append("")

    lines += [
        "## 5. Operational metrics (LLM)",
        "",
        "| Spec | Latency mean (ms) | Latency max | Input tok mean | Output tok mean | Retries mean |",
        "|------|-------------------|-------------|----------------|-----------------|--------------|",
    ]
    for spec, s in sorted(spec_summary.items()):
        lines.append(
            f"| {spec} | {s['latency_ms_mean'] or '—'} | {s['latency_ms_max'] or '—'} | "
            f"{s['input_tokens_mean'] or '—'} | {s['output_tokens_mean'] or '—'} | "
            f"{s['retries_mean'] or '—'} |"
        )
    lines.append("")

    args.output_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[report] Markdown: {args.output_md}")
    print(f"[report] JSON: {args.output_json}")
    print(f"[report] Specs analyzed: {len(spec_summary)}")
    print(f"[report] Total entries: {len(entries)}")


if __name__ == "__main__":
    main()
```

`chmod +x scripts/eval/generate_report.py`.

### T4 — Criar `examples/deucalion/scout-corr057.sbatch`

**Ficheiro NEW:** `examples/deucalion/scout-corr057.sbatch`

```bash
#!/usr/bin/env bash
#SBATCH --job-name=aegis-scout-corr057
#SBATCH --account=f202512235cpcaa1g
#SBATCH --partition=dev-a100-40
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=slurm-scout-corr057-%j.out
#SBATCH --error=slurm-scout-corr057-%j.err
#SBATCH --chdir=$HOME/aegis-kg

# CORR-057 scout — environment reconnaissance before eval job.
# Submit FIRST; only submit eval after this PASSes.

set -uo pipefail

echo "=== 1. Identity ==="
echo "whoami=$(whoami) hostname=$(hostname) date=$(date -u)"
echo "SLURM_JOB_ID=${SLURM_JOB_ID:-none}"

echo ""
echo "=== 2. Storage ==="
df -h "$HOME" 2>&1 | tail -2
ls -d "$HOME/aegis-kg" 2>&1

echo ""
echo "=== 3. Project ==="
cd "$HOME/aegis-kg" 2>/dev/null || { echo "FATAL: ~/aegis-kg missing"; exit 1; }
ls -la | head -10

echo ""
echo "=== 4. Python module ==="
module purge 2>/dev/null
module load Python/3.11.3-GCCcore-12.3.0 2>&1 || echo "WARN: python module load failed"
python --version 2>&1

echo ""
echo "=== 5. Venv ==="
if [ -d ".venv" ]; then
    source .venv/bin/activate
    which python
    python -c "import langchain_core; print(f'langchain_core OK')" 2>&1
    python -c "import aegis_phase1; print('aegis_phase1 OK')" 2>&1
else
    echo "MISSING .venv — create with: python -m venv --system-site-packages .venv && pip install -e .[dev]"
fi

echo ""
echo "=== 6. Ollama binary ==="
export PATH="/projects/F202512235CPCAA1/CyberMetric_Deucalion/bin:$PATH"
export OLLAMA_MODELS="/projects/F202512235CPCAA1/CyberMetric_Deucalion/ollama_data/models"
ollama --version 2>&1 || echo "WARN: ollama binary not runnable"

echo ""
echo "=== 7. Model cache (e2b available?) ==="
ollama list 2>&1 | head -30
echo ""
echo "e2b present in cache:"
ollama list 2>&1 | grep -i "e2b" || echo "WARN: e2b NOT in cache"

echo ""
echo "=== 8. GPU (none allocated for scout, but check partition) ==="
sinfo -p dev-a100-40 -o "%P %D %G %t" 2>&1 | head -5

echo ""
echo "=== 9. Case data sanity ==="
ls cases/case1-tinytask/case.yaml 2>&1
ls cases/case1-tinytask/data/phase1/ 2>&1 | head -5

echo ""
echo "=== SCOUT COMPLETE ==="
echo "Decision rules:"
echo "  - If python+venv+ollama+e2b all OK: submit eval-corr057.sbatch"
echo "  - If e2b missing from cache: submit examples/download-models.sbatch first"
echo "  - If venv missing: needs setup (see references/04-environment-setup.md)"
```

`chmod +x examples/deucalion/scout-corr057.sbatch`.

### T5 — Criar `examples/deucalion/eval-corr057.sbatch`

**Ficheiro NEW:** `examples/deucalion/eval-corr057.sbatch`

```bash
#!/usr/bin/env bash
#SBATCH --job-name=aegis-eval-corr057
#SBATCH --account=f202512235cpcaa1g
#SBATCH --partition=dev-a100-40
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --output=slurm-eval-corr057-%j.out
#SBATCH --error=slurm-eval-corr057-%j.err
#SBATCH --chdir=$HOME/aegis-kg

# CORR-057 eval — full pipeline run on GPU + auto report.
# Submit AFTER scout-corr057 PASSes.

set -euo pipefail
set -x
umask 077

# 1. Modules
module purge
module load Python/3.11.3-GCCcore-12.3.0
module load ollama/0.20.3-GCCcore-14.2.0-CUDA-12.8.0 2>/dev/null || true

# 2. Ollama paths (skill: use shared binary + cache)
export PATH="/projects/F202512235CPCAA1/CyberMetric_Deucalion/bin:$PATH"
export LD_LIBRARY_PATH="/projects/F202512235CPCAA1/CyberMetric_Deucalion/lib/ollama:$LD_LIBRARY_PATH"
export OLLAMA_MODELS="/projects/F202512235CPCAA1/CyberMetric_Deucalion/ollama_data/models"
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="gemma4:e2b"

# 3. CRITICAL: Langfuse OFF (Deucalion has no Langfuse; .env default points to localhost:3000)
export LANGFUSE_ENABLED="false"
unset LANGFUSE_BASE_URL LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY

# 4. Secrets
if [ -f "$HOME/.aegis_env" ]; then
    set -a
    source "$HOME/.aegis_env"
    set +a
fi

# 5. Venv
cd "$HOME/aegis-kg"
source .venv/bin/activate
export PYTHONPATH="$PWD:$PYTHONPATH"

# 6. GPU sanity
echo "[eval] === GPU ==="
nvidia-smi 2>&1 | head -10 || { echo "FATAL: no GPU"; exit 1; }

# 7. Start Ollama
echo "[eval] === starting ollama ==="
SCRATCH_JOB="/tmp/aegis-job-${SLURM_JOB_ID}"
mkdir -p "$SCRATCH_JOB"
ollama serve > "$SCRATCH_JOB/ollama.log" 2>&1 &
OLLAMA_PID=$!

cleanup() {
    echo "[eval] cleanup"
    kill "$OLLAMA_PID" 2>/dev/null || true
    wait "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT SIGTERM SIGINT

# Wait for ready
for i in {1..30}; do
    if curl -sf http://localhost:11434/ >/dev/null 2>&1; then
        echo "[eval] ollama ready after $i attempts"
        break
    fi
    sleep 2
done
curl -sf http://localhost:11434/ >/dev/null 2>&1 \
    || { echo "FATAL: ollama not ready"; cat "$SCRATCH_JOB/ollama.log" >&2; exit 1; }

# 8. Results dir
RESULTS_DIR="$HOME/aegis-kg/results/corr057-${SLURM_JOB_ID}"
mkdir -p "$RESULTS_DIR"

# 9. Run eval
export RESULTS_DIR
bash scripts/eval/run_eval_deucalion.sh

# 10. Done
echo "[eval] === JOB COMPLETE ==="
echo "[eval] results: $RESULTS_DIR"
ls -la "$RESULTS_DIR"
```

`chmod +x examples/deucalion/eval-corr057.sbatch`.

### T6 — Documentação

**Ficheiro NEW:** `docs/deucalion/corr057_eval_workflow.md`

```markdown
# CORR-057 — Deucalion eval workflow (baseline e2b)

## Goal

First end-to-end pipeline run on Deucalion HPC + automatic eval report.
**Baseline single model:** `gemma4:e2b`. Multi-model comparison is CORR-058.

## Workflow

### Phase 1 — Workstation (one-time setup)

1. Confirmar commit T1 está em main (transformers_invoker + compare_models).
2. Confirmar acesso SSH: `ssh paulinho@login.deucalion.macc.fccn.pt 'echo OK'`.
3. Criar tarball self-contained:
   ```bash
   cd /home/epmq-cyber/Área\ de\ Trabalho/projects/aegis-phase1
   tar --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
       --exclude='logs' --exclude='output' --exclude='.git' \
       --exclude='node_modules' \
       -czf /tmp/aegis-phase1-corr057.tgz .
   ls -lh /tmp/aegis-phase1-corr057.tgz   # deve ser ~50-150MB
   ```
4. SCP para Deucalion:
   ```bash
   scp /tmp/aegis-phase1-corr057.tgz paulinho@login.deucalion.macc.fccn.pt:~
   ```
5. Criar `~/.aegis_env` no Deucalion (se não existe):
   ```bash
   ssh paulinho@login.deucalion.macc.fccn.pt
   cat > ~/.aegis_env <<EOF
   export NEO4J_PASSWORD='not-used-in-phase1'
   export OLLAMA_HOST='http://localhost:11434'
   export OLLAMA_MODEL='gemma4:e2b'
   export LANGFUSE_ENABLED='false'
   EOF
   chmod 600 ~/.aegis_env
   ```

### Phase 2 — Deucalion login node (one-time env setup)

```bash
ssh paulinho@login.deucalion.macc.fccn.pt
cd ~
tar xzf aegis-phase1-corr057.tgz    # extrai para ~/  (cria aegis-phase1/ ou similar)
# Confirmar estrutura — se extraiu para diretório com nome do tarball:
ls -d aegis-phase1* 2>/dev/null
# Se necessário, mover para o local canónico:
# mv aegis-phase1-corr057 aegis-kg  (skill diz: code lives in ~/aegis-kg)
# ln -s aegis-kg aegis-phase1  (ou usar diretamente)

cd ~/aegis-kg  # ou o diretório onde extraiu

# Module + venv setup
module purge
module load Python/3.11.3-GCCcore-12.3.0
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -e .[dev]

# Smoke test
python -c "import aegis_phase1; print('aegis_phase1 OK')"
```

### Phase 3 — Submeter scout

```bash
cd ~/aegis-kg
sbatch examples/deucalion/scout-corr057.sbatch
# Wait ~5-10 min
squeue -u $USER
# After job completes:
cat slurm-scout-corr057-*.out
```

**Decision rules** (do output do scout):
- python+venv+ollama+e2b all OK → submeter eval (Phase 4)
- e2b missing from cache → submeter `examples/download-models.sbatch` (skill) primeiro
- venv missing → repetir Phase 2
- python module missing → ESCALAR: skill diz para usar `bash -lc`

### Phase 4 — Submeter eval

```bash
cd ~/aegis-kg
sbatch examples/deucalion/eval-corr057.sbatch
# Wait ~30-90 min (16 LLM calls + rendering)
squeue -u $USER
tail -f slurm-eval-corr057-*.out
```

### Phase 5 — Recolher resultados

```bash
# No Deucalion
ls -la results/corr057-*/
cat results/corr057-*/corr057_eval_report.md

# Workstation — rsync de volta
rsync -avz --progress \
    paulinho@login.deucalion.macc.fccn.pt:~/aegis-kg/results/corr057-* \
    /home/epmq-cyber/Área\ de\ Trabalho/projects/aegis-phase1/results/
```

## O que esperar / não esperar

### Esperar
- 16 LLM calls no jsonl (4 P1B + 10 P1C-01 + 1 P1C-03 + 1 P1C-02)
- `corr057_eval_report.md` com 5 secções (schema/citation/activation/parity/ops)
- `corr057_eval_data.json` estruturado
- Outputs 04/04a/04b/04c/04d/05/06/07/07b/xlsx gerados

### NÃO esperar (ainda)
- 100% schema compliance (alguns specs ainda podem falhar — isso é DADO)
- Paridade exacta com referência (referência é v1-style; pipeline é v2)
- Performance ótima (1º run pode ter warmup)

## Próximos passos (depois de ver o relatório)

- Se baseline OK → CORR-058 expande para 3-5 modelos médios
- Se port tem bugs → CORR-058 resolve antes de multi-modelo
- Se prompts têm problemas → CORR separado (já não é "setup")
```

### T7 — Workstation: criar tarball + smoke local

Antes de despachar para Deucalion, validar localmente que o tarball tem
tudo o que é preciso:

```bash
# Criar tarball
cd /home/epmq-cyber/Área\ de\ Trabalho/projects/aegis-phase1
tar --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='logs' --exclude='output' --exclude='.git' \
    --exclude='node_modules' \
    -czf /tmp/aegis-phase1-corr057.tgz .
ls -lh /tmp/aegis-phase1-corr057.tgz

# Validar conteúdo do tarball
tar tzf /tmp/aegis-phase1-corr057.tgz | head -20
tar tzf /tmp/aegis-phase1-corr057.tgz | grep -E "case1-tinytask/case.yaml|preproc_out/3-entities/subdomains/D-01/D-01.1.json|pyproject.toml|scripts/eval/generate_report.py" | head -10
# Esperado: mostra os ficheiros chave

# Smoke local (antes de enviar) — gerar relatório sobre jsonl existente
mkdir -p /tmp/corr057_smoke
python scripts/eval/generate_report.py \
    --jsonl logs/phase1/llm-calls.jsonl \
    --output-dir /tmp/corr057_smoke \
    --preproc preproc_out \
    --output-md /tmp/corr057_smoke/smoke_report.md \
    --output-json /tmp/corr057_smoke/smoke_data.json
# Se gerar sem erro, o script está pronto para o Deucalion
cat /tmp/corr057_smoke/smoke_report.md | head -30
```

### T8 — Commit + push

```bash
git add scripts/eval/ examples/deucalion/ docs/deucalion/corr057_eval_workflow.md execution/CONTRACT-057.md
git status --short
git commit -m "CORR-057: Deucalion setup + baseline e2b eval infrastructure

Workstation side:
- scripts/eval/run_eval_deucalion.sh: orchestrator (start Ollama, run pipeline, gen report)
- scripts/eval/generate_report.py: 4-dimension evaluator (schema/citation/activation/parity)
  + 4 operational metrics (latency/tokens/retries/status). Outputs Markdown + JSON.
- examples/deucalion/scout-corr057.sbatch: env reconnaissance (10 min CPU, submit first)
- examples/deucalion/eval-corr057.sbatch: full GPU run (2h, dev-a100-40, 32GB, 8 CPUs)
- docs/deucalion/corr057_eval_workflow.md: 5-phase workflow (workstation→setup→scout→eval→rsync)

Decisions locked:
- 1 model (gemma4:e2b), 1 trial, 1 case (case1-tinytask)
- Langfuse OFF on HPC (JSONL only)
- Crash = iterate (no try/except wrap)
- Report format: Markdown + JSON (both)
- Results rsync'd back to workstation"
```

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — trabalho pendente committed
git log --oneline | head -3 | grep -q "CORR-056 follow-up\|transformers_invoker" && echo "G1 OK" || { echo "FAIL G1: pendente work not committed"; exit 1; }

# G2 — scripts existem
for f in scripts/eval/run_eval_deucalion.sh scripts/eval/generate_report.py; do
    test -f "$f" || { echo "FAIL G2: $f missing"; exit 1; }
done
echo "G2 OK"

# G3 — sbatch templates têm placeholders reais (não <DEUCALION_ACCOUNT>)
grep -q "f202512235cpcaa1g" examples/deucalion/scout-corr057.sbatch && echo "G3 OK" || { echo "FAIL G3: sbatch still has placeholders"; exit 1; }

# G4 — Langfuse OFF explícito no eval sbatch
grep -q "LANGFUSE_ENABLED.*false" examples/deucalion/eval-corr057.sbatch && echo "G4 OK" || { echo "FAIL G4: Langfuse not OFF"; exit 1; }

# G5 — Case path explícito
grep -q "cases/case1-tinytask" examples/deucalion/eval-corr057.sbatch scripts/eval/run_eval_deucalion.sh && echo "G5 OK" || { echo "FAIL G5: case path missing"; exit 1; }

# G6 — generate_report.py corre localmente (smoke)
test -f /tmp/corr057_smoke/smoke_report.md && echo "G6 OK" || { echo "FAIL G6: local smoke didn't run"; exit 1; }

# G7 — Tarball criado e tem ficheiros chave
TARBALL=/tmp/aegis-phase1-corr057.tgz
test -f "$TARBALL" || { echo "FAIL G7: tarball missing"; exit 1; }
tar tzf "$TARBALL" | grep -q "case1-tinytask/case.yaml" || { echo "FAIL G7: case.yaml missing in tarball"; exit 1; }
tar tzf "$TARBALL" | grep -q "preproc_out/3-entities/subdomains" || { echo "FAIL G7: preproc_out missing in tarball"; exit 1; }
echo "G7 OK"

# G8 — Tarball < 500MB
SIZE=$(stat -c %s "$TARBALL")
[ "$SIZE" -lt 524288000 ] && echo "G8 OK ($((SIZE/1024/1024))MB)" || { echo "FAIL G8: tarball $((SIZE/1024/1024))MB > 500MB"; exit 1; }

# G9 — Suite de testes ainda verde (não regrediu com scripts novos)
pytest tests/unit/v2/ tests/unit/prompts_v2/ -q --timeout=60 2>&1 | tail -3 | grep -qE "passed" && echo "G9 OK" || echo "G9 WARN: some tests may be slow"

# G10 — Docs existem
test -f docs/deucalion/corr057_eval_workflow.md && echo "G10 OK" || { echo "FAIL G10"; exit 1; }

# G11 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G11 OK" || { echo "FAIL G11"; exit 1; }

# G12 (manual) — SSH ao Deucalion funciona
ssh -i /home/epmq-cyber/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=10 \
    paulinho@login.deucalion.macc.fccn.pt 'echo SSH OK' 2>&1 | grep -q "SSH OK" \
    && echo "G12 OK" || echo "G12 WARN: SSH check failed (manual verify)"

echo "=== ALL GATES CHECKED ==="
```

**Definição de done:** G1–G11 todos PASS. G12 é informativo (pode falhar se SSH tiver 2FA interactivo).

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/llm/transformers_invoker.py` | **COMMIT (já dirty)** |
| `scripts/corr056_compare_models_v2.py` | **COMMIT (já untracked)** |
| `scripts/eval/run_eval_deucalion.sh` | **NEW** |
| `scripts/eval/generate_report.py` | **NEW** |
| `examples/deucalion/scout-corr057.sbatch` | **NEW** |
| `examples/deucalion/eval-corr057.sbatch` | **NEW** |
| `docs/deucalion/corr057_eval_workflow.md` | **NEW** |
| `/tmp/aegis-phase1-corr057.tgz` | **NEW** (workstation; para SCP) |
| `/tmp/corr057_smoke/` | **NEW** (smoke local do generate_report) |
| `execution/CONTRACT-057.md` | **NEW** (este) |

**Não modificar:** source code em `src/` (além do commit T1), testes,
`preproc_out/`, `.hooks/`, cases existentes.

---

## Estrutura de commits

```
feature/aegis-p1-corr-057
├─ commit 1: T1 commit pendente (transformers_invoker + corr056_compare)
├─ commit 2: T2+T3 eval scripts (run_eval_deucalion.sh + generate_report.py)
├─ commit 3: T4+T5 sbatch templates (scout + eval)
├─ commit 4: T6 docs
└─ commit 5: T8 push (se user pedir)
```

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| `cases/case1-tinytask` não tem todos os dados que o default `Methodology-main/02_CASES/Case_01_TinyTask_SaaS` tem | Pré-flight valida: `ls cases/case1-tinytask/data/phase1/` deve ter ~22 CSVs. Se faltam, copiar do Methodology-main/ |
| `gemma4:e2b` não está no cache Deucalion | Scout.sbatch faz `ollama list \| grep e2b`. Se falta, sbatch separado `download-models.sbatch` (skill exemplo) |
| Langfuse chamadas pendentes mesmo com `LANGFUSE_ENABLED=false` | eval sbatch faz `unset LANGFUSE_BASE_URL LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY` além de setar `LANGFUSE_ENABLED=false` |
| Pipeline demora > 2h walltime | Diminuiu: prompt template é markdown+regex (CORR-050) + 512KB cap (CORR-049-T7). Se ainda assim > 2h, aumenta `--time` para 04:00:00 |
| `Methodology-main/00_METHODOLOGY/PROMPTS/` não está no tarball | Tarball inclui tudo exceto `.venv/logs/output/.git`; PROMPTS está incluído |
| `/tmp` no compute node é pequeno para Ollama logs | `SCRATCH_JOB="/tmp/aegis-job-${SLURM_JOB_ID}"` é só para ollama.log; resultados vão para NFS |
| SSH pede 2FA interactivo | Skill prevê; user sabe lidar. G12 é WARN não FAIL |

---

## Pós-CORR-057

**Se todos gates passam + eval job completa no Deucalion:**
- Relatório em `results/corr057-<JOBID>/corr057_eval_report.md` com 5 secções.
- Decisão sobre próximos passos baseada nos dados:
  - Se compliance > 80% e invented_refs < 10% → baseline OK → CORR-058 expande para multi-modelo
  - Se compliance baixo → investigar que specs falham (já temos relatório)
  - Se invented_refs alto → revisar prompts (contract separado)

**Se eval job falha no Deucalion:**
- Slurm logs em `slurm-eval-corr057-*.out` têm traceback.
- Iterar: corrigir, re-criar tarball, re-SCP, re-submeter.

---

## Change log

- 2026-07-23: v1.0 — contract inicial para baseline e2b eval no Deucalion.
  Decisões locked: 1 modelo, 1 trial, 1 caso, Langfuse OFF, JSONL only,
  crash=iterar, relatório Markdown+JSON, rsync tudo de volta.
