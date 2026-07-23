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
