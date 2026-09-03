# CORR-054-rework — Commit correto + re-verificação real

## Resumo

O CORR-054 original foi **bem implementado** (code diffs válidos, 4/4 testes
passam, fix de None-safety legítimo) mas tem **3 problemas** que invalidam
a aceitação:

1. **Trabalho não commitado.** Branch errada (`feature/aegis-p1-corr-053`),
   `src/aegis_phase1/prompts_v2/invoker.py` dirty, teste untracked.
   Commit message em lado nenhum menciona "CORR-054".
2. **Claim 5 (run real spl=13290/upl=355/OK/5.5s) sem suporte em artifact.**
   `logs/phase1/llm-calls.jsonl` tem 1723 entries; **nenhuma** com spl=13290
   ou upl=355. Só 1 de 1723 tem prompts completos (SCHEMA_ERROR com
   spl=16569/upl=11692). Os números foram inventados ou mal persistidos.
3. **Claim 6 cita ficheiro inexistente** (`test_smoke_p1b_llm_01_gdpr.py`).
   As 3 falhas do `test_langfuse_callback_corr011.py` são genuinamente
   pré-existentes (CORR-055 resolve).

Este contract **fecha o 1 e o 2**. O 3 fica para CORR-055.

**Branch:** `feature/aegis-p1-corr-054` (NOVA — não continuar na `corr-053`)
**Data:** 2026-07-22
**Trigger:** auditoria pós-CORR-054 — "user não acreditava; auditor
confirmou trabalho bem feito mas não commitado + claim 5 fabricada".

---

## Pré-flight (executor TEM de verificar antes de começar)

```bash
cd /home/epmq-cyber/Área de Trabalho/projects/aegis-phase1
source ../shared-venv/bin/activate

# 1. Confirmar que trabalho existe (uncommitted)
git status --short | grep -E "invoker.py|test_corr054"
# Esperado: mostra " M src/aegis_phase1/prompts_v2/invoker.py"
# e "?? tests/unit/prompts_v2/test_corr054_prompts_logged.py"

# 2. Confirmar diffs são os esperados
git diff src/aegis_phase1/prompts_v2/invoker.py | grep -E "request|system_prompt|user_prompt" | head -10
# Esperado: mostra adições dos 4 sites com request field

# 3. Confirmar que 4 testes passam ANTES de mexer
pytest tests/unit/prompts_v2/test_corr054_prompts_logged.py -v 2>&1 | tail -10
# Esperado: 4 passed

# 4. Confirmar Ollama + Langfuse up
curl -s http://localhost:11434/api/tags | jq -r '.models[].name' | grep e2b   # gemma4:e2b
curl -s http://localhost:3000/api/public/health                                # {"status":"OK"}

# 5. Disco com espaço
df -h / | awk 'NR==2 {print "Free:", $4}'
# Esperado: ≥ 5G
```

Se qualquer pré-flight falhar: ABORTAR. Reportar output exacto.

---

## Decisões de produto (NÃO negociáveis)

1. **Branch nova corretamente nomeada.** `feature/aegis-p1-corr-054` a
   partir de main. Não continuar na `corr-053`.
2. **Cherry-pick ou aplicação manual dos diffs** do trabalho uncommitted.
   O code já existe na working tree — é só commitar.
3. **Re-verificação REAL com gemma4:e2b** — não inventar números. Correr
   1 chamada P1B-LLM-02-RATIONALE, colar o output do jsonl, deixar os
   números serem o que forem.
4. **Atualizar resumo do CORR-054** com números reais (se diferentes
   dos inventados) ou marcar Claim 5 como "retractada".
5. **Não tocar nas 3 falhas do langfuse_callback** — CORR-055 cuida disso.

---

## Tarefas

### T1 — Criar branch + commit do trabalho existente

```bash
# 1. Stash do trabalho uncommitted
git stash push -u -m "CORR-054 work in progress (uncommitted)"

# 2. Criar branch nova a partir de main
git checkout main
git pull
git checkout -b feature/aegis-p1-corr-054

# 3. Aplicar o stash
git stash pop

# 4. Verificar que diffs estão de volta
git status --short
# Esperado: " M src/aegis_phase1/prompts_v2/invoker.py"
#           "?? tests/unit/prompts_v2/test_corr054_prompts_logged.py"

# 5. Verificar testes ainda passam
pytest tests/unit/prompts_v2/test_corr054_prompts_logged.py -v 2>&1 | tail -5
# Esperado: 4 passed

# 6. Commit
git add src/aegis_phase1/prompts_v2/invoker.py tests/unit/prompts_v2/test_corr054_prompts_logged.py
git commit -m "CORR-054: log full prompts in JSONL request field

Phase1LLMInvoker now emits the complete system_prompt and user_prompt
in a 'request' field for all 4 JSONL event types (llm_call, format_error,
markdown_parse_error, python_error). Previously only lengths were logged,
making it impossible to diagnose hallucinations, ignored instructions,
or missing catalog merges.

Changes (src/aegis_phase1/prompts_v2/invoker.py):
- llm_call event: request = {system_prompt, user_prompt,
  system_prompt_length, user_prompt_length}
- format_error event: same request shape
- markdown_parse_error event: same request shape
- python_error event: same request shape
- catastrophic python_error: request with prompt.get(...) fallback
  when render exploded
- Bug colateral fix: (a.get('validation') or {}).get('schema_errors')
  instead of a.get('validation', {}).get('schema_errors') — the latter
  crashed when validation key existed with value None.

system_prompt_length / user_prompt_length kept for backward compat.

Tests (tests/unit/prompts_v2/test_corr054_prompts_logged.py, 4/4 pass):
- llm_call event has full prompts (byte-exact match with chat.invoke input)
- prompts >1KB and contain case_id + regulation
- format_error event also has prompts
- python_error event also has prompts

Verified by audit (CORR-054-rework): all 6 claims checked independently.
Claims 1-4 PASS; Claim 5 (specific numbers) retracted — see re-verification
log in logs/phase1/corr054_reverify.log; Claim 6 partially wrong (smoke
file doesn't exist) — see CORR-055 for the langfuse failures."
```

### T2 — Re-verificação real com gemma4:e2b

Esta é a tarefa que **resolve a Claim 5 fabricada**. Em vez de aceitar
números inventados, vamos correr 1 chamada real e reportar o que aparecer.

```bash
# Backup do jsonl atual (para podermos isolar a nova chamada)
cp logs/phase1/llm-calls.jsonl logs/phase1/llm-calls.pre_corr054_reverify.jsonl.bak
LINES_BEFORE=$(wc -l < logs/phase1/llm-calls.jsonl)
echo "JSONL lines before: $LINES_BEFORE"

# Run 1 chamada P1B-LLM-02-RATIONALE (via runner --run-phase-1b)
# Isto vai fazer 4 calls (2 regs × 2 LLMs); só precisamos de 1 P1B-LLM-02
source ../shared-venv/bin/activate
python -m aegis_phase1.v2.runner \
    --case cases/case1-tinytask \
    --run-phase-1b \
    2>&1 | tee logs/phase1/corr054_reverify.log

# Verificar que novas entries apareceram
LINES_AFTER=$(wc -l < logs/phase1/llm-calls.jsonl)
echo "JSONL lines after: $LINES_AFTER"
echo "New entries: $((LINES_AFTER - LINES_BEFORE))"
```

### T3 — Extrair e reportar a entrada P1B-LLM-02-RATIONALE real

```bash
python3 << 'PY'
import json
from pathlib import Path

entries = []
with open("logs/phase1/llm-calls.jsonl") as f:
    for line in f:
        try:
            e = json.loads(line)
            if e.get("spec_id") == "P1B-LLM-02-RATIONALE":
                entries.append(e)
        except Exception:
            pass

out = []
out.append(f"# CORR-054 re-verification result")
out.append("")
out.append(f"Total P1B-LLM-02-RATIONALE entries in jsonl: {len(entries)}")
out.append("")

if not entries:
    out.append("NO P1B-LLM-02-RATIONALE entries found — run T2 may have failed")
else:
    latest = entries[-1]
    out.append(f"## Latest entry")
    out.append("")
    out.append(f"- event: {latest.get('event')}")
    out.append(f"- spec_id: {latest.get('spec_id')}")
    out.append(f"- status: {latest.get('status')}")
    out.append(f"- latency_ms: {latest.get('latency_ms') or latest.get('total_latency_ms')}")

    req = latest.get("request", {})
    if req:
        sp = req.get("system_prompt", "")
        up = req.get("user_prompt", "")
        out.append(f"- system_prompt_length: {len(sp)}")
        out.append(f"- user_prompt_length: {len(up)}")
        out.append(f"- system_prompt first 200 chars: {sp[:200]!r}")
        out.append(f"- user_prompt first 200 chars: {up[:200]!r}")
        out.append("")
        out.append(f"- system_prompt contains base_system_prompt YAML: {'base_system_prompt' in sp or 'AEGIS' in sp[:500]}")
        out.append(f"- user_prompt contains case_id: {'case_id' in up}")
        out.append(f"- user_prompt contains regulation: {'regulation' in up or 'GDPR' in up or 'CRA' in up}")
    else:
        out.append("NO request field — CORR-054 code not active")

Path("logs/phase1/corr054_reverify_result.md").write_text("\n".join(out))
print("\n".join(out))
PY
```

Guardar o output deste script em `logs/phase1/corr054_reverify_result.md`.

### T4 — Criar/atualizar CONTRACT-054 com números reais

**Ficheiro:** `execution/CONTRACT-054.md` (CREATE se não existe; UPDATE se existe)

Adicionar no fim uma secção:

```markdown
---

## Re-verification (CORR-054-rework, 2026-07-22)

**Original Claim 5:** "real run P1B-LLM-02 OK in 5.5s, spl=13290, upl=355".

**Audit found:** those specific numbers appeared in 0 of 1723 jsonl entries.

**Re-verification ran on 2026-07-22** (see `logs/phase1/corr054_reverify_result.md`):

(paste real numbers from T3 here)

**If real numbers match the original claim:** Claim 5 was right, just unverified.
**If real numbers differ:** Claim 5 was wrong; corrected above.

Either way: the code change (logging full prompts) is independent of the
specific numbers — the change is verified by the 4/4 tests in
`test_corr054_prompts_logged.py` and by the re-verification output showing
the `request` field is populated.

**Claim 6 correction:** the original summary mentioned
`test_smoke_p1b_llm_01_gdpr.py` as failing — that file does not exist.
The 3 actual pre-existing failures are in `test_langfuse_callback_corr011.py`
(callback wiring tests), caused by CORR-050's MarkdownParser rework changing
the P1B-LLM-01 validation contract. Fixed in CORR-055.
```

### T5 — Validar gates

Correr os gates abaixo (G1-G8). Se todos passam, merge-ready.

---

## Quality gates (FAIL default)

```bash
source ../shared-venv/bin/activate

# G1 — Branch correta
BRANCH=$(git branch --show-current)
[ "$BRANCH" = "feature/aegis-p1-corr-054" ] && echo "G1 OK" || { echo "FAIL G1: branch is $BRANCH (expected feature/aegis-p1-corr-054)"; exit 1; }

# G2 — Commit único com mensagem CORR-054
git log -1 --format="%s" | grep -q "CORR-054" && echo "G2 OK" || { echo "FAIL G2: commit message doesn't mention CORR-054"; exit 1; }

# G3 — invoker.py committed (não dirty)
DIFF_LINES=$(git diff HEAD -- src/aegis_phase1/prompts_v2/invoker.py | wc -l)
[ "$DIFF_LINES" = "0" ] && echo "G3 OK" || { echo "FAIL G3: invoker.py still dirty ($DIFF_LINES diff lines)"; exit 1; }

# G4 — test_corr054 committed (tracked)
git ls-files tests/unit/prompts_v2/test_corr054_prompts_logged.py | grep -q "test_corr054" && echo "G4 OK" || { echo "FAIL G4: test file not tracked"; exit 1; }

# G5 — testes passam pós-commit
pytest tests/unit/prompts_v2/test_corr054_prompts_logged.py -q 2>&1 | tail -1 | grep -qE "passed" && echo "G5 OK" || { echo "FAIL G5"; exit 1; }

# G6 — re-verificação real produziu resultado
test -f logs/phase1/corr054_reverify_result.md && \
    grep -q "P1B-LLM-02-RATIONALE" logs/phase1/corr054_reverify_result.md && echo "G6 OK" || { echo "FAIL G6: re-verification result missing"; exit 1; }

# G7 (informativo) — request field populated na re-verificação
if grep -q "request field" logs/phase1/corr054_reverify_result.md 2>/dev/null; then
    echo "G7 INFO: check request field in reverify_result.md manually"
else
    echo "G7 INFO: no explicit request field mention (check manually)"
fi

# G8 — CI gates
bash .hooks/ci-csf-frozen-list.sh && bash .hooks/ci-frameworks.sh && echo "G8 OK" || { echo "FAIL G8"; exit 1; }

echo "=== ALL GATES PASSED ==="
```

**Definição de done:** G1–G6 + G8 todos PASS. G7 é informativo.

---

## Ficheiros

| Ficheiro | Ação |
|----------|------|
| `src/aegis_phase1/prompts_v2/invoker.py` | **COMMIT (já dirty na working tree)** |
| `tests/unit/prompts_v2/test_corr054_prompts_logged.py` | **COMMIT (já untracked)** |
| `logs/phase1/llm-calls.pre_corr054_reverify.jsonl.bak` | **NEW** — backup do jsonl antes da re-verificação |
| `logs/phase1/corr054_reverify.log` | **NEW** — output do --run-phase-1b |
| `logs/phase1/corr054_reverify_result.md` | **NEW** — extração da entrada P1B-LLM-02-RATIONALE |
| `execution/CONTRACT-054.md` | **CREATE-OR-UPDATE** — com secção de re-verification |
| `execution/CONTRACT-054-rework.md` | **NEW** (este) |

**Não modificar:** qualquer ficheiro em `src/` que não `invoker.py`, qualquer
teste que não `test_corr054_prompts_logged.py`, `preproc_out/`, `.hooks/`,
os 3 testes em `test_langfuse_callback_corr011.py` (CORR-055 cuida).

---

## Estrutura de commits

```
feature/aegis-p1-corr-054
├─ commit 1: CORR-054 work (invoker.py + test_corr054_prompts_logged.py)
└─ commit 2: re-verification artifacts (logs + CONTRACT-054 + CONTRACT-054-rework)
```

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| `git stash pop` tem conflitos (e.g., se main avançou entretanto) | Resolver manualmente — preference para o conteúdo do stash (trabalho CORR-054) |
| `--run-phase-1b` demora > 5 min ou falha (P1B-LLM-02 pode ainda ter SCHEMA_ERROR) | Tudo bem — só precisamos da entrada no jsonl, mesmo que status seja SCHEMA_ERROR. O importante é ter o `request` field populado. |
| `corr054_reverify_result.md` mostra "NO request field — CORR-054 code not active" | Inesperado — significa que o commit não incluiu o code change. Investigar antes de prosseguir. |
| Backup do jsonl ocupa espaço (já 21MB) | Aceitável — disk tem ≥5G. |
| Re-verificação mostra números muito diferentes dos inventados (e.g., spl=20000 em vez de 13290) | É o esperado — reporta honestamente. Os números não validam nem invalidam o code change; apenas corrigem a Claim 5. |
| Stash não consegue fazer push por causa de `corr054_reverify.log` já existir | Usar `git stash push -u` apenas para ficheiros tracked; o log é gerado depois |

---

## Pós-CORR-054-rework

**Se G1–G6 + G8 passam:** CORR-054 está aceitável. Code é bom, testes
passam, commit está bem nomeado, Claim 5 foi honestamente re-verificada.
Claim 6 ainda tem o problema do ficheiro inexistente — mas isso é
cosmético vs o problema das 3 falhas langfuse que CORR-055 resolve.

**Próximo contract:** **CORR-055** — fix dos 3 testes em
`test_langfuse_callback_corr011.py` que falham desde CORR-050 (MarkdownParser
mudou contrato; `_FakeAIMessage` retorna `{"items": []}` que agora falha).

---

## Change log

- 2026-07-22: v1.0 — contract criado pelo orchestrator após auditoria
  revelar trabalho bem feito mas não commitado + Claim 5 fabricada.
