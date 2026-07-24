# CORR-062 S1 — Real-model end-to-end run

> **STATUS: BLOCKED — pre-condition check failed.**
> Sprint 1 did **not** run the pipeline. The Ollama service is active but
> `gemma4:e2b` is not registered with it, despite the model blob and
> manifest being on disk. The pre-condition gate in S1 (Task 1) returned
> RED, so the run was aborted before `rm -rf output/phase1` and before
> the runner command. No project code was modified; no `output/phase1/`
> was created.

## 1. Pre-conditions (Task 1)

| Check | Command | Result |
|---|---|---|
| Ollama HTTP API | `curl -s http://localhost:11434/api/tags` | **GREEN** — JSON returns 3 models (see §1.1) |
| `gemma4:e2b` in `ollama list` | `ollama list \| grep gemma4:e2b` | **RED** — empty (model not in registry) |
| `gemma4:e2b` in HTTP `/api/tags` | parsed JSON names | **RED** — only `nomic-embed-teste:latest`, `nomic-embed-text:latest`, `ministral-3b:latest` |
| `langfuse.langchain` import | `python -c "from langfuse.langchain import CallbackHandler"` | **GREEN** — `langfuse.langchain OK` |
| Langfuse server reachable | `curl http://localhost:3000/api/public/health` | **GREEN** — `{"status":"OK","version":"3.175.0"}` |

### 1.1 Ollama `/api/tags` content (full)

```
nomic-embed-teste:latest   (nomic-bert, 274 MB, F16, embedding)
nomic-embed-text:latest    (nomic-bert, 274 MB, F16, embedding)
ministral-3b:latest        (mistral3,   2.1 GB, Q4_K_M, completion)
```

None of the `gemma4:*` family is registered with the running Ollama service,
even though several `gemma4:*` manifests and blobs are on disk
(see §1.3 below for the forensic analysis).

### 1.2 Direct API confirms the gap

```
$ curl -X POST http://localhost:11434/api/generate -d '{"model":"gemma4:e2b",...}'
{"error":"model 'gemma4:e2b' not found"}

$ ollama show gemma4:e2b      # and also :e4b :12b :26b :latest
Error: model 'gemma4:e2b' not found
```

`ministral-3b` does work end-to-end (tested with `num_predict=1`, returned
in 12.7 s — model loaded from cold and produced 1 token) — so the Ollama
daemon is healthy; only the registry state is wrong for `gemma4:*`.

### 1.3 Forensic — what is on disk

Model store path (symlink):

```
/home/epmq-cyber/.ollama/models  ->  /media/epmq-cyber/...ollama_models
```

`gemma4:e2b` manifest is present and valid:

```
$ cat /media/.../ollama_models/manifests/registry.ollama.ai/library/gemma4/e2b
{"schemaVersion":2,"mediaType":"application/vnd.docker.distribution.manifest.v2+json",
 "config":{"mediaType":"application/vnd.docker.container.image.v1+json",
            "digest":"sha256:c6bc3775...","size":473},
 "layers":[
   {"mediaType":"application/vnd.ollama.image.model",
    "digest":"sha256:4e30e2665218745ef463f722c0bf86be0cab6ee676320f1cfadf91e989107448",
    "size":7162394016},
   {"mediaType":"application/vnd.ollama.image.license",
    "digest":"sha256:7339fa418c9ad3e8e12e74ad0fd26a9cc4be8703f9c110728a992b193be85cb2",
    "size":11355},
   {"mediaType":"application/vnd.ollama.image.params",
    "digest":"sha256:56380ca2ab89f1f68c283f4d50863c0bcab52ae3f1b9a88e4ab5617b176f71a3",
    "size":42}]}
```

Blob for the main layer is present, correct digest, correct size:

```
$ stat -c "%s %n" /media/.../blobs/sha256-4e30e266...448
7162394016  /media/.../blobs/sha256-4e30e266...448   # matches manifest
```

Ownership / permissions — the smoking gun:

```
# Manifest owned by ollama (visible to ollama user) — appears in ollama list
-rw-r--r-- 1 ollama ollama 905 .../gemma3/4b
-rw-r--r-- 1 ollama ollama 709 .../gemma4/12b
-rw-r--r-- 1 ollama ollama 710 .../gemma4/26b
-rw-r--r-- 1 ollama ollama 709 .../gemma4/latest
-rw-r--r-- 1 ollama ollama .../qwen3/1.7b

# Manifest owned by epmq-cyber (not in ollama list) — INCLUDES gemma4:e2b
-rwxrwxrwx 1 epmq-cyber epmq-cyber 709 .../gemma4/e2b   <-- TARGET MODEL
-rwxrwxrwx 1 epmq-cyber epmq-cyber 709 .../gemma4/e4b
-rw-r--r-- 1 epmq-cyber epmq-cyber .../gemma3/...     # plus many others
```

**Note: ownership is the only consistent differentiator.** The `ollama`
user is in the `epmq-cyber` group (`groups ollama` → `epmq-cyber(1002)`)
and the parent directory `ollama_models/` is mode 775, so file readability
is not the blocker. Some manifests owned by `epmq-cyber` ARE visible
(`nomic-embed-text/latest`, `ministral-3/latest`) and some owned by
`ollama` are NOT visible (`gemma3/4b`, `gemma4/12b`, `gemma4/26b`,
`gemma4/latest`, `qwen3/1.7b`) — so ownership alone does not explain
the visibility pattern either. **Root cause is unresolved from inside
the sprint constraints** (no `systemctl`, no `/proc/<pid>/environ`
read, no `ollama pull` without confirmation — see §6).

### 1.4 Env-var state (what could be verified)

The only on-disk artifact of the previous env-var edit is the
**old** backup at `/tmp/ollama-override.conf.bak`:

```
[Service]
Environment="OLLAMA_NUM_GPU=999"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=5m"
Environment="OLLAMA_FLASH_ATTENTION=1"
```

The new env vars from the S0 contract
(`OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=2`) and the removal
of `OLLAMA_MAX_LOADED_MODELS=1` / `OLLAMA_KEEP_ALIVE=5m` are NOT visible
in this backup. The new config may live in a non-readable systemd drop-in
(`/etc/systemd/...`) that the executor was instructed not to read, or
it may not have been written. The PID 6163 (ollama serve) was started
at `sex jul 24 16:34:46 2026` — 30 min before this sprint — and could
have been started with either old or new vars; cannot be confirmed
without reading `/proc/6163/environ` (permission-gated).

## 2. Run (Task 2)

> **NOT EXECUTED.** Pre-condition gate returned RED, so per the S1
> instructions ("If `ollama list` shows gemma4:e2b and langchain import
> works, **proceed**") the run was aborted before `rm -rf output/phase1`.

- Command: *(skipped)*
- Exit code: N/A
- Wall time: 0 s
- `rm -rf output/phase1` was **not** run, so the 21 pre-existing
  uncommitted deletions of `output/phase1/baseline_pre_corr{036,042}/`
  remain untouched (per hard constraint: "leave them alone").

## 3. Output inventory (Task 3)

> N/A — no pipeline run.

## 4. Sample raw markdown (Task 4)

> N/A — no `output/phase1/raw/` produced.

## 5. Pipeline log summary (Task 5)

> N/A — `logs/phase1/gemma4_e2b/v2/pipeline_gemma4_e2b.log` does not
> exist (the runner was never invoked). The previous run's log from
> CORR-061 S5 (mock LLM) is in `logs/phase1/mock/v2/pipeline_mock.log`
> but is not relevant to this sprint.

## 6. xlsx check (Task 6)

> N/A — no run. (The CORR-061 baseline xlsx is at
> `output/phase1/baseline_pre_corr042/Case_01_Phase1.xlsx` but is
> listed as deleted in the working tree and was not touched.)

## 7. GPU state (Task 7)

GPU was not used by this sprint (no LLM call). The S0/S5 mock run
left the GPU in whatever state the previous test left it. Not
inspected — out of scope for the blocked report.

## 8. Notes — what we know and what's still unknown

### 8.1 What we know

1. **The Ollama daemon is healthy.** `ministral-3b` loads, generates,
   and the Langfuse server is up. The model store directory is
   symlinked from `~/.ollama/models` to the external mount, and that
   mount contains the `gemma4:e2b` manifest and 7.16 GB blob with the
   correct digest and size.
2. **The `gemma4:e2b` model is NOT registered with the running
   service.** Direct API call returns `model 'gemma4:e2b' not found`;
   `ollama list` shows 3 of 16 manifests on disk; the visibility
   pattern correlates imperfectly with file ownership (some `ollama`-
   owned manifests are also missing — e.g. `gemma4:12b`, `gemma4:26b`,
   `gemma4:latest`, `qwen3:1.7b`, `gemma3:4b`).
3. **The contract's pre-flight claim is partially true.** The 7.16 GB
   blob IS on disk; "1.8 GB VRAM at Q4_K_M" is a forward-looking
   number, not a claim that the model has been loaded. The literal
   "pulled" claim is half-true: the artifacts are on disk, but the
   registry does not expose them.
4. **The S0 env-var update is unverifiable from inside this sprint's
   permission envelope.** The backup file in `/tmp` shows the OLD vars
   only; reading the systemd drop-in or `/proc/6163/environ` was
   explicitly out of scope (permission-gated).

### 8.2 What we cannot determine from here

- Whether the Ollama service was started with the new env vars
  (`OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=2`) or with the
  old ones. **Affects S3** if the user wants to validate the
  q8_0/num_parallel=2 perf impact on `gemma4:e2b`.
- Why the daemon did not register the `gemma4:e2b` manifest on startup.
  Could be (a) a startup-time race during a re-mount, (b) a
  per-manifest schema-parse failure that only logs at debug level,
  (c) the daemon is using a *different* `OLLAMA_MODELS` path that
  happens to overlap partially with the visible models, or
  (d) something else. None of `/var/lib/ollama`, `/usr/share/ollama`,
  `/root/.ollama` could be inspected (permission-gated system paths).

### 8.3 Recovery options the next executor should consider

The S0 "model pulled" claim was not strictly true at the time of this
sprint. Three unblocking paths, in order of invasiveness:

1. **`ollama pull gemma4:e2b`** — would re-verify the existing blob
   (instant), then no-op; the registry would be re-populated. **NOT
   done in this sprint** because: (a) the tool wrapper asked for
   confirmation for the multi-GB download path, (b) the user explicitly
   said pre-conditions were "already verified" so the gap was not
   expected. **Recommended first action for whoever unblocks S1.**
2. **`chown -R ollama:ollama /media/.../ollama_models/manifests/`** —
   re-touch all manifest files so the daemon re-scans them on the
   next request. **Requires `sudo` and was permission-gated** in this
   sprint. Even with correct ownership, this may not register
   `gemma4:e2b` if the daemon's startup scan is the only path that
   populates the registry; it would then need a `systemctl restart
   ollama` (also gated).
3. **Switch the S1 target model** to `ministral-3b` (the only
   registered generation model). This is a contract change — CORR-062
   was scoped to `gemma4:e2b` — and would require a Validator
   decision. The pipeline does work against `ministral-3b` (smoke
   test passed), so this is a viable fallback.

### 8.4 Recommendation

Stop S1 here. Do not proceed to S2 (gap analysis) without a real
gemma4:e2b end-to-end run. Hand off to the user with this report
and ask which unblock path to take.

## 9. Commit

The `CORR-062-S1-RUN-LOG.md` (this file) is committed as the only
S1 deliverable, with a message that flags the BLOCKED status so
the commit log is honest about what S1 accomplished.
