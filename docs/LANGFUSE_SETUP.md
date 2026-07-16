# Langfuse Setup (Self-Hosted)

This file documents how to bring up the shared Langfuse stack used by `aegis-phase1` for LLM observability.

## Architecture

The Langfuse stack lives in `~/Área de Trabalho/projects/aegis-kg/docker-compose.yml` and is shared across AEGIS projects. It runs:

- `langfuse-web` (langfuse:3) — UI + API on `localhost:3000`
- `langfuse-worker` — async event processor
- `clickhouse` — analytics store (`localhost:8123`)
- `postgres` — control plane (`localhost:5432`)
- `redis` — queue (`localhost:6379`)
- `minio` — S3-compatible blob store (`localhost:9090`/`9001`)

## Start

```bash
cd ~/Área\ de\ Trabalho/projects/aegis-kg
docker compose up -d
```

## Stop

```bash
cd ~/Área\ de\ Trabalho/projects/aegis-kg
docker compose down
```

## Verify

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:3000
# expect 200 or 302
```

UI: open <http://localhost:3000> in browser.

## aegis-phase1 env wiring

This repo's `.env` (gitignored — local only) has 4 Langfuse keys, mirroring `aegis-kg/.env`:

| Var | Purpose |
|---|---|
| `LANGFUSE_ENABLED` | Master switch. Default `false`. When `false`, all code paths run as if Langfuse were absent. |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public API key (`pk-lf-...`). Safe to commit placeholders. |
| `LANGFUSE_SECRET_KEY` | Langfuse secret API key (`sk-lf-...`). **Treated as secret — never commit.** |
| `LANGFUSE_BASE_URL` | Where the Langfuse SDK points. Self-hosted default: `http://localhost:3000`. |

`.env.example` (tracked) carries placeholders (`pk-lf-CHANGEME`, `sk-lf-CHANGEME`) for fresh clones.

### How to populate `.env` on a fresh clone

1. Copy template: `cp .env.example .env`
2. Pull the real keys from `~/Área de Trabalho/projects/aegis-kg/.env`:
   - `LANGFUSE_PUBLIC_KEY=pk-lf-...` (line 2)
   - `LANGFUSE_SECRET_KEY=sk-lf-...` (line 1)
3. Leave `LANGFUSE_ENABLED=false` unless actively debugging traces.

## Master switch semantics

`LANGFUSE_ENABLED=false` is the safe default:

- Pipeline runs identically to pre-CORR-009.
- `scripts/test-quick.sh` passes 222.
- No network traffic to Langfuse.
- `get_langfuse_callback()` returns `(client, handler)` where both are `None` — all tracing code paths become no-ops.

Set `LANGFUSE_ENABLED=true` to enable. Re-run pipeline; traces appear in <http://localhost:3000>.

## Smoke test (CORR-009 verification)

```bash
LANGFUSE_ENABLED=true .venv/bin/python -c "
import os
from dotenv import load_dotenv
load_dotenv(override=True)
from aegis_phase1.llm.tracing import get_langfuse_callback
client, handler = get_langfuse_callback()
print('auth:', client.auth_check())
with client.start_as_current_observation(as_type='span', name='corr009-smoke') as span:
    print('trace_id:', span.trace_id)
client.flush()
"
```

Expected: `auth: True`, `trace_id: <hex>`. Then verify via API:

```bash
curl -sS -u "$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY" \
  "http://localhost:3000/api/public/traces?limit=1"
```

Expected: HTTP 200, latest trace name `corr009-smoke`.

> **Note on `get_langfuse_callback()` return order:** the function returns `(client, handler)` (not `(handler, client)` as some LangChain docs suggest). The `client` is the `Langfuse` instance; `handler` is the `LangchainCallbackHandler`.

## Cost

Free (self-hosted, all data local). No budget gates in CORR-009. Per-case budgets to follow in CORR-011 or later.

## See also

- `docs/SPEC-observability.md` — full CORR-009 → CORR-015 plan.
- `aegis-kg/core/agent/tracing.py` — reference Langfuse wrapper.
- `AGENTS.md §10` — Branch Policy + Pre-flight Check.
