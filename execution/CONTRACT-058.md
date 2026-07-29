# CORR-058 — Unblock CORR-057 delivery (pytest install + report fix + scp)

## Resumo

Contract **pequeno** para desbloquear o push do CORR-057 e tornar o
`generate_report.py` robusto. 3 fixes independentes + push.

**3 problemas descobertos na auditoria pós-CORR-057:**

1. **Push bloqueado por bug pre-existing do hook.**
   `.hooks/validate-contracts.sh:83,87` chamam `.venv/bin/pytest` hardcoded.
   O `.venv` é symlink para `shared-venv-root` onde **pytest não está
   instalado** → `ModuleNotFoundError: No module named 'pytest'`.
   Fix: `pip install pytest` no `shared-venv-root`. Sem mexer no hook.

2. **`generate_report.py` dá 0% false-negative em P1C-LLM-01/03.**
   `scripts/eval/generate_report.py:125` faz `spec = e.get("spec_id", "UNKNOWN")`.
   Mas 898 de 1844 entries (49%) do jsonl legacy usam `prompt_spec_id`
   (top-level) em vez de `spec_id` → caem em `UNKNOWN` → relatados como
   0% compliance. Fix: fallback chain `spec_id → prompt_spec_id → UNKNOWN`.

3. **`rsync` não está instalado na workstation.**
   `Phase 5` do workflow doc usa `rsync` para trazer resultados do Deucalion.
   Substituir por tarball + scp (compatível sem instalar nada).

**Branch:** `feature/aegis-p1-corr-058` (criada a partir da `feature/aegis-p1-corr-057`)
**Data:** 2026-07-23
**Trigger:** auditoria pós-CORR-057 — 3 issues bloqueantes/informativos.

---

## Pré-flight (executor TEM de verificar antes de começar)

```bash
cd /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1
source ../shared-venv/bin/activate

# 1. Branch CORR-057 existe e está completa
git log --oneline feature/aegis-p1-corr-057 -5

# 2. Confirmar bug pytest (before fix)
ls -la "/home/epmq-cyber/Área de Trabalho/projects/shared-venv-root/bin/pytest" 2>&1 | head -2
bash -c 'source "/home/epmq-cyber/Área de Trabalho/projects/shared-venv-root/bin/activate" 2>&1; python -c "import pytest" 2>&1' | tail -3
# Esperado: ModuleNotFoundError: No module named 'pytest'

# 3. Confirmar bug spec extraction
python3 -c "
import json
total = 0; no_spec = 0
with open('logs/phase1/llm-calls.jsonl') as f:
    for line in f:
        try:
            e = json.loads(line); total += 1
            if 'spec_id' not in e: no_spec += 1
        except: pass
print(f'total={total} no_spec_id={no_spec}')
"
# Esperado: total=~1844 no_spec_id=~898

# 4. Confirmar generate_report.py linha 125
sed -n '125p' scripts/eval/generate_report.py
# Esperado: spec = e.get("spec_id", "UNKNOWN") ou similar

# 5. Confirmar rsync ausente
which rsync 2>&1 || echo "rsync NOT INSTALLED"
```

---

## Decisões de produto (NÃO negociáveis)

1. **`pip install pytest` no `shared-venv-root`**, sem mexer no hook.
   O symlink `.venv → shared-venv-root` + shebang `pytest` resolve para o
   python daquele venv — pip install lá resolve.
2. **Fix 1-liner em `generate_report.py:125`** com fallback chain.
   Tolerante a jsonl legacy (`prompt_spec_id`) E novo (`spec_id`).
3. **Substituir `rsync` por tarball+scp no doc.** Mais eficiente para
   muitos ficheiros pequenos que scp -r.
4. **Push ao fim** — depois dos fixes, hook vai passar e push desbloqueia.
5. **Não resolver os problemas do jsonl legacy além da spec extraction** —
   outputs aninhados etc são formatting que o report novo (Deucalion jsonl)
   já traz limpo.

---

## Tarefas

### T1 — Instalar pytest no shared-venv-root

```bash
# Activar o venv onde o hook efectivamente corre
source "/home/epmq-cyber/Área de Trabalho/projects/shared-venv-root/bin/activate"

# Confirmar que está activo
which python
# Esperado: /home/epmq-cyber/Área de Trabalho/projects/shared-venv-root/bin/python

# Instalar pytest
pip install pytest pytest-asyncio pytest-xdist 2>&1 | tail -5

# Confirmar que agora funciona
python -c "import pytest; print(f'pytest {pytest.__version__} OK')"

# Validar que o hook agora passa
cd "/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1"
.venv/bin/pytest --version
# Esperado: pytest 8.x.x
```

**Não é preciso commit** — pip install é estado do ambiente, não código.

### T2 — Fix generate_report.py spec extraction

**Ficheiro:** `scripts/eval/generate_report.py`

**Estado atual (linha 125):**
```python
spec = e.get("spec_id", "UNKNOWN")
```

**Alvo:**
```python
# CORR-058: tolerant spec extraction. Legacy jsonl uses top-level
# `prompt_spec_id` (898/1844 entries); new jsonl uses `spec_id`.
spec = (
    e.get("spec_id")
    or e.get("prompt_spec_id")
    or (e.get("metadata") or {}).get("prompt_spec_id")
    or "UNKNOWN"
)
```

### T3 — Re-validar smoke com o fix

```bash
cd "/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1"
source ../shared-venv/bin/activate

# Re-correr smoke
rm -rf /tmp/corr058_smoke
mkdir -p /tmp/corr058_smoke
python scripts/eval/generate_report.py \
    --jsonl logs/phase1/llm-calls.jsonl \
    --output-dir /tmp/corr058_smoke \
    --preproc preproc_out \
    --output-md /tmp/corr058_smoke/smoke_report.md \
    --output-json /tmp/corr058_smoke/smoke_data.json

# Confirmar que UNKNOWN diminuiu drasticamente
python3 -c "
import json
data = json.load(open('/tmp/corr058_smoke/smoke_data.json'))
for spec, s in sorted(data['per_spec'].items()):
    print(f'{spec}: {s[\"total_calls\"]} calls, {s[\"schema_compliance_pct\"]}% compliance')
"
# Esperado: P1B-LLM-01, P1B-LLM-02, P1C-LLM-01, P1C-LLM-02, P1C-LLM-03 aparecem com counts;
# UNKNOWN muito reduzido (idealmente 0).
```

### T4 — Substituir rsync por tarball+scp no workflow doc

**Ficheiro:** `docs/deucalion/corr057_eval_workflow.md`

**Procurar por** `rsync`:
```bash
grep -n "rsync" docs/deucalion/corr057_eval_workflow.md
```

**Substituir** cada ocorrência. Para Phase 5 (trazer resultados de volta),
usar 2 passos: tarball no Deucalion + scp para workstation (mais eficiente
que `scp -r` para muitos ficheiros pequenos):

Antes (NÃO funciona — rsync ausente):
```bash
rsync -avz --progress \
    paulinho@login.deucalion.macc.fccn.pt:~/aegis-kg/results/corr057-* \
    /home/epmq-cyber/Área\ de\ Trabalho/projects/aegis-phase1/results/
```

Depois (funciona sem instalar nada):
```bash
# Step 1 (no Deucalion): criar tarball dos resultados
ssh paulinho@login.deucalion.macc.fccn.pt
cd ~/aegis-kg
tar czf ~/corr057-results-$(date +%Y%m%d).tgz results/corr057-*/
exit

# Step 2 (workstation): trazer o tarball e extrair
scp paulinho@login.deucalion.macc.fccn.pt:~/corr057-results-*.tgz /tmp/
mkdir -p "/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1/results"
tar xzf /tmp/corr057-results-*.tgz -C "/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1/"

# Ver o relatório
cat "/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1/results/corr057-*/corr057_eval_report.md"
```

**Também verificar** se há outras referências a `rsync` no repo:
```bash
grep -rn "rsync" docs/ scripts/ examples/ 2>/dev/null | head -10
```

### T5 — Commit + push

```bash
cd "/home/epmq-cyber/Área de Trabalho/projects/aegis-phase1"
git checkout feature/aegis-p1-corr-057
git checkout -b feature/aegis-p1-corr-058

git add scripts/eval/generate_report.py docs/deucalion/corr057_eval_workflow.md execution/CONTRACT-058.md
git status --short

git commit -m "CORR-058: unblock CORR-057 delivery (pytest install + report spec fix + scp)

3 fixes for issues found in CORR-057 audit:

1. Pre-push hook (pre-existing): .hooks/validate-contracts.sh:83,87 calls
   .venv/bin/pytest but pytest wasn't installed in shared-venv-root (where
   .venv symlinks). Fix: pip install pytest in shared-venv-root. No code
   change.

2. generate_report.py spec extraction (line 125): was using
   e.get('spec_id', 'UNKNOWN') but legacy jsonl uses top-level
   prompt_spec_id (898/1844 entries = 49% falling into UNKNOWN bucket →
   false 0% compliance on P1C-LLM-01/03 in smoke). Fix: fallback chain
   spec_id → prompt_spec_id → metadata.prompt_spec_id → UNKNOWN.

3. rsync missing on workstation: Phase 5 of corr057_eval_workflow.md
   referenced rsync. Replace with tarball + scp (more efficient for many
   small files than scp -r, and doesn't require installing rsync).

After these fixes, the pre-push hook passes and CORR-057 can be pushed."

# Push ambas as branches
git push -u origin feature/aegis-p1-corr-057
git push -u origin feature/aegis-p1-corr-058

# Validar push
git log origin/feature/aegis-p1-corr-058..HEAD --oneline
# Esperado: vazio (tudo pushed)
```

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — pytest instalado no shared-venv-root
bash -c 'source "/home/epmq-cyber/Área de Trabalho/projects/shared-venv-root/bin/activate" && python -c "import pytest; print(pytest.__version__)"' 2>&1 | grep -qE "^[0-9]+\.[0-9]+" && echo "G1 OK" || { echo "FAIL G1: pytest not installed in shared-venv-root"; exit 1; }

# G2 — Hook passa (collection + run)
bash .hooks/validate-contracts.sh 2>&1 | tail -5
# Esperado: exit 0; nenhum "ModuleNotFoundError"

# G3 — generate_report.py tem fallback chain
grep -A3 "spec = " scripts/eval/generate_report.py | grep -q "prompt_spec_id" && echo "G3 OK" || { echo "FAIL G3: fallback chain missing"; exit 1; }

# G4 — Smoke re-corrido com sucesso, UNKNOWN drasticamente reduzido
python3 -c "
import json
data = json.load(open('/tmp/corr058_smoke/smoke_data.json'))
unknown = data['per_spec'].get('UNKNOWN', {}).get('total_calls', 0)
total = sum(s['total_calls'] for s in data['per_spec'].values())
pct = 100 * unknown / max(1, total)
print(f'UNKNOWN: {unknown}/{total} ({pct:.1f}%)')
assert pct < 10, f'Too many UNKNOWN: {pct:.1f}%'
print('G4 OK')
" || { echo "FAIL G4: UNKNOWN > 10% — fallback not working"; exit 1; }

# G5 — rsync substituído no workflow doc
COUNT=$(grep -c "rsync" docs/deucalion/corr057_eval_workflow.md)
[ "$COUNT" = "0" ] && echo "G5 OK" || { echo "FAIL G5: ainda tem $COUNT referências a rsync"; exit 1; }

# G6 — Push funciona
LINES=$(git log origin/feature/aegis-p1-corr-058..HEAD --oneline 2>&1 | wc -l)
[ "$LINES" = "0" ] && echo "G6 OK" || { echo "FAIL G6: branch not fully pushed"; exit 1; }

# G7 — Suite de testes ainda verde
pytest tests/unit/v2/ tests/unit/prompts_v2/ -q --tb=no 2>&1 | tail -1 | grep -qE "passed" && echo "G7 OK" || { echo "FAIL G7"; exit 1; }

# G8 — CI gates (que o hook já valida, mas confirmar explicitamente)
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G8 OK" || { echo "FAIL G8"; exit 1; }

echo "=== ALL 8 GATES PASSED ==="
```

**Definição de done:** G1–G8 todos PASS.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `scripts/eval/generate_report.py` | **MODIFY (T2)** — fallback chain spec extraction |
| `docs/deucalion/corr057_eval_workflow.md` | **MODIFY (T4)** — substituir rsync por tarball+scp |
| `/tmp/corr058_smoke/` | **NEW (T3)** — re-validação smoke |
| `execution/CONTRACT-058.md` | **NEW** (este) |

**Não modificar:** `.hooks/` (T1 resolve sem mexer), `src/` (sem code changes
no código de produção), testes, preproc_out, cases.

---

## Estrutura de commits

```
feature/aegis-p1-corr-058 (em cima de corr-057)
└─ commit 1: T2+T4 fixes (generate_report.py spec fallback + scp no workflow doc)
```

Push faz-se das 2 branches no fim (T5).

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| `pip install pytest` parte algo em shared-venv-root | pytest é puramente aditivo; não afecta nada existente. Caso raro: versão incompatível → rollback `pip uninstall pytest` |
| Smoke continua com UNKNOWN alto mesmo após fix | Significa que legacy jsonl tem outra forma de encoding do spec. Inspecionar 1 entry UNKNOWN: `python3 -c "import json; [print(json.dumps(json.loads(l))[:300]) for l in open('logs/phase1/llm-calls.jsonl') if 'spec_id' not in l and 'prompt_spec_id' not in l][:3]"` |
| `git push` falha por outra razão (auth) | Skill recomenda tar+scp como fallback; tarball já existe em /tmp |
| `validate-contracts.sh` falha por testes a falhar (não por pytest) | Suíte v2 já passava antes; confirma que não há regressão |
| `tar czf` no Phase 5 falha por `results/corr057-*/` não existir | O eval sbatch cria `~/aegis-kg/results/corr057-${SLURM_JOB_ID}/`; se job falhou, dir não existe — reportar |
| `which rsync` continua a falhar mesmo depois do T4 | Era esperado — T4 só mexe no doc, não instala rsync. Por design |

---

## Pós-CORR-058

**Se G1–G8 passam:** CORR-057 + CORR-058 estão pushed em origin.
User pode seguir Phase 1-5 do workflow doc sem bloqueadores.

**Próximo passo (manual do user):**
1. Phase 1: `scp /tmp/aegis-phase1-corr057.tgz paulinho@...`
2. Phase 2: setup venv no Deucalion
3. Phase 3: `sbatch scout-corr057.sbatch`
4. Phase 4: `sbatch eval-corr057.sbatch`
5. Phase 5: tarball+scp resultados de volta (já com o fix do T4)

Depois de ver o `corr057_eval_report.md` real do Deucalion, decidimos
CORR-059 (multi-modelo, se port OK) ou CORR-059 (fix port, se houver bugs).

---

## Change log

- 2026-07-23: v1.0 — contract inicial para desbloquear entrega do CORR-057.
  3 fixes: pip install pytest (sem mexer no hook), generate_report.py spec
  fallback chain, rsync → tarball+scp.
