# CORR-045 — Fix P1C-LLM-01 prompt: catalogs merge + helper + lane filter

**Status:** Recriado a partir do report (`execution/reports/corr045_report.md`)
porque o contract doc original foi perdido em transições de branch.

---

## Verdict pós-CORR-049 (2026-07-22)

**Status:** PASS (cascade-merged into feature/aegis-p1-corr-049).

**CORR-049 integrou este contract num branch cascade. Detalhes em
`execution/CONTRACT-049.md` §FASE 1 e `logs/phase1/corr049_parity_report.md`.**

**Evidence:** 15/16 quality gates pass; only G11 (concatenate: 0 domains)
fails, and that is a model-side issue (gemma4:e2b not following schema),
not a contract-045 fix issue. The 045 work (catalogs merge in invoker,
helper `_build_layer0_subdomain_refs`, per-lane filter in
`run_phase_1c_map`) is permanent and 100% effective — the prompt
no longer has 211K-token echo (now 2.5K-4K), 10/10 P1C-LLM-01 lanes
return OK in 177s, and the 3-call-site bug (`'str' object has no
attribute 'get'`) is fully resolved.

The merge into 049 (commit 1, T1) is `git merge --no-ff
feature/aegis-p1-corr-045` — no conflicts, suite green
(623 → 625 passed, 0 failed).
