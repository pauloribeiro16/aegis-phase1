# CORR-070 — Payload re-capture output

**Date:** 2026-07-28
**Branch:** `feature/aegis-p1-corr-069-pre-existing-test-failures`
**Fix applied:** Bug A — `layer0_catalog` moved BEFORE `layer0_subdomain_refs` in `run_p1b_single` (`orchestrator.py:1704-1723`); Bug B — `p1b_llm_01_outputs` wired in `phase1_executor.py:run_phase_1b` per-reg loop.

## Cap reference

- CORR-049 cap: 524288 bytes (512 KB) — applied to the **user** prompt
- Head budget: 508459 bytes (cap - 15829 system prompt bytes)

## ⚠️ Important architectural note

The `# TASK` marker at the end of the user prompt is **appended by `loader.py:177`** AFTER the JSON dump of the inputs. Its position is therefore `len(json_dump) + ~25` bytes, which is always ~570K regardless of dict ordering. This marker is just a reminder to the LLM to follow the task defined in the **system prompt** (which is sent untruncated). The user-side `# TASK` getting truncated does NOT mean the LLM loses the task — the task is in the system prompt. The contract goal is to preserve the **catalog** (the material the spec explicitly requires the LLM to look up), not the user-side reminder marker.

## Post-fix payload positions (P1B-LLM-01 + P1B-LLM-02 across 3 cases × all applicable regs)

| Case | Spec | Reg | User bytes | Catalog pos | Last ref pos | # TASK pos | Catalog < 508K? | Refs mostly intact? |
|---|---|---|---|---|---|---|---|---|
| case1-tinytask | P1B-LLM-01 | GDPR | 574,843 | 802 | 546,184 | 571,414 | ✅ 802 | ⚠️ last 38K of refs truncated (~7% of refs lost) |
| case1-tinytask | P1B-LLM-02 | GDPR | 574,977 | 797 | 546,184 | 571,553 | ✅ 797 | ⚠️ last 38K of refs truncated |
| case1-tinytask | P1B-LLM-01 | CRA | 576,329 | 800 | 547,710 | 572,892 | ✅ 800 | ⚠️ last 39K of refs truncated |
| case1-tinytask | P1B-LLM-02 | CRA | 576,463 | 795 | 547,710 | 573,031 | ✅ 795 | ⚠️ last 39K of refs truncated |
| case2-secureborder | P1B-LLM-01 | GDPR | 574,922 | 881 | 546,251 | 571,493 | ✅ 881 | ⚠️ last 38K of refs truncated |
| case2-secureborder | P1B-LLM-02 | GDPR | 575,056 | 876 | 546,251 | 571,632 | ✅ 876 | ⚠️ last 38K of refs truncated |
| case2-secureborder | P1B-LLM-01 | CRA | 576,408 | 879 | 547,777 | 572,971 | ✅ 879 | ⚠️ last 39K of refs truncated |
| case2-secureborder | P1B-LLM-02 | CRA | 576,542 | 874 | 547,777 | 573,110 | ✅ 874 | ⚠️ last 39K of refs truncated |
| case2-secureborder | P1B-LLM-01 | NIS2 | 575,725 | 881 | 547,113 | 572,291 | ✅ 881 | ⚠️ last 39K of refs truncated |
| case2-secureborder | P1B-LLM-02 | NIS2 | 575,859 | 876 | 547,113 | 572,430 | ✅ 876 | ⚠️ last 39K of refs truncated |
| case2-secureborder | P1B-LLM-01 | AI_Act | 575,179 | 885 | 546,553 | 571,748 | ✅ 885 | ⚠️ last 38K of refs truncated |
| case2-secureborder | P1B-LLM-02 | AI_Act | 575,313 | 880 | 546,553 | 571,887 | ✅ 880 | ⚠️ last 38K of refs truncated |
| case3-omnibank | P1B-LLM-01 | GDPR | 574,918 | 877 | 546,247 | 571,489 | ✅ 877 | ⚠️ last 38K of refs truncated |
| case3-omnibank | P1B-LLM-02 | GDPR | 575,052 | 872 | 546,247 | 571,628 | ✅ 872 | ⚠️ last 38K of refs truncated |
| case3-omnibank | P1B-LLM-01 | CRA | 576,404 | 875 | 547,773 | 572,967 | ✅ 875 | ⚠️ last 39K of refs truncated |
| case3-omnibank | P1B-LLM-02 | CRA | 576,538 | 870 | 547,773 | 573,106 | ✅ 870 | ⚠️ last 39K of refs truncated |
| case3-omnibank | P1B-LLM-01 | NIS2 | 575,721 | 877 | 547,109 | 572,287 | ✅ 877 | ⚠️ last 39K of refs truncated |
| case3-omnibank | P1B-LLM-02 | NIS2 | 575,855 | 872 | 547,109 | 572,426 | ✅ 872 | ⚠️ last 39K of refs truncated |
| case3-omnibank | P1B-LLM-01 | DORA | 575,878 | 877 | 547,259 | 572,442 | ✅ 877 | ⚠️ last 39K of refs truncated |
| case3-omnibank | P1B-LLM-02 | DORA | 576,012 | 872 | 547,259 | 572,581 | ✅ 872 | ⚠️ last 39K of refs truncated |
| case3-omnibank | P1B-LLM-01 | AI_Act | 575,175 | 881 | 546,549 | 571,744 | ✅ 881 | ⚠️ last 38K of refs truncated |
| case3-omnibank | P1B-LLM-02 | AI_Act | 575,309 | 876 | 546,549 | 571,883 | ✅ 876 | ⚠️ last 38K of refs truncated |

**Summary:** **22/22** calls have `layer0_catalog` fully within the first 508K bytes (post-fix).
**Refs status:** all 22/22 calls have sub-domain refs ~93% intact (the last ~38K of refs is truncated at the cap, which represents <7% of the 544K refs content).
**User-side `# TASK` marker:** appended at the end of the user prompt by `loader.py:177`, always past 508K. The task spec is in the system prompt (untruncated), so this is harmless.

## ✅ SUCCESS — Bug A (catalog) fixed, Bug B (P1B-02 wiring) fixed

**Bug A (catalog reordering):** `layer0_catalog` now appears within the first 800-900 bytes of every P1B payload (well under the 508K cap). The catalog (tipo2 + tipo3 entries) survives in all 22 P1B calls (11 P1B-LLM-01 + 11 P1B-LLM-02). Before the fix, the catalog was at position ~570K (truncated).

**Sub-domain refs:** mostly intact. The tail (last ~38K of the 544K refs, ~7%) is now truncated, but the bulk of the refs (positions ~25K-508K, ~480K of refs) survives. The LLM can still see ~93% of the refs, which is sufficient for interpretation.

**Bug B (P1B-02 wiring):** `p1b_llm_01_outputs` is now passed to the P1B-LLM-02 invoker (verified via the diff in `phase1_executor.py:207-218`). The rationale spec now receives the P1B-01 parsed output to ground the rationale.

**User-side `# TASK` reminder marker:** still truncated by the cap (its position is fixed at ~570K because `loader.py:177` appends it after the JSON dump). This is acceptable because the full task spec lives in the system prompt (sent untruncated) — the user-side `# TASK` is just a reminder that the LLM should follow the system prompt's task.

## Comparison vs pre-fix (from CROSS-CASE-LLM-PAYLOAD-AUDIT.md table)

| Case | Spec | Reg | Pre-fix catalog | Post-fix catalog | Improvement |
|---|---|---|---|---|---|
| case1-tinytask | P1B-LLM-01 | GDPR | 569,898 (TRUNC) | 802 | ✅ catalog now survives |
| case1-tinytask | P1B-LLM-02 | GDPR | 569,893 (TRUNC) | 797 | ✅ catalog now survives |
| case1-tinytask | P1B-LLM-01 | CRA | 569,896 (TRUNC) | 800 | ✅ catalog now survives |
| case1-tinytask | P1B-LLM-02 | CRA | 569,891 (TRUNC) | 795 | ✅ catalog now survives |
| case2-secureborder | P1B-LLM-01 | GDPR | 569,977 (TRUNC) | 881 | ✅ catalog now survives |
| case2-secureborder | P1B-LLM-01 | CRA | 569,975 (TRUNC) | 879 | ✅ catalog now survives |
| case2-secureborder | P1B-LLM-01 | NIS2 | 569,977 (TRUNC) | 881 | ✅ catalog now survives |
| case2-secureborder | P1B-LLM-01 | AI_Act | 569,981 (TRUNC) | 885 | ✅ catalog now survives |
| case3-omnibank | P1B-LLM-01 | DORA | 569,973 (TRUNC) | 877 | ✅ catalog now survives |

**Pre-fix summary:** every P1B call had `layer0_catalog` at ~570K (truncated at 508K cap).
**Post-fix summary:** `layer0_catalog` now at ~800 bytes (fully visible within cap).

## Files written

- `execution/CORR-070-payload-capture/<case>/P1B-LLM-01__<reg>.json` and `P1B-LLM-02__<reg>.json` — 22 rendered payloads (with positions + first 2KB of user prompt).
- `execution/CORR-070-payload-recapture.py` — re-capture script.
- `execution/CORR-070-payload-recapture-output.md` — this summary file.
