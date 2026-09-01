# Digest — qwen3.5:27b run-all (JOB 1847659)

**Judge:** GLM-5.3-Flash via ZCode (2026-09-01, this session)
**Commit:** a710efd4fc309f72d54b0bc49b499a277e56e4e3
**Case:** case1-tinytask
**Run dir:** `Deucalion/results/qwen35_runall_1847659/`
**Walltime:** ~53 min total, started 2026-08-24 14:49:10 WEST

---

## L1–L5 summary

| Spec | L1 | L2 | L3 | L4 | L5 |
|------|----|----|----|----|----|
| P1B-LLM-01-INTERPRETATION | PASS | n/a | 4/5 | n/a | 318s/125k tok; 260s/125k; 207s/93k; 152s/92k |
| P1B-LLM-02-RATIONALE      | PASS | n/a | 3/5 | n/a | see above |
| P1C-LLM-01-OVERLAP-CLASSIFICATION | PASS (header `## Status`); **0 activations extracted** | n/a | 1/5 | REDUCE-LLM SKIPPED | 142–212s/call; 27–53k tok |
| P1C-LLM-02-COMPOUND-EVENT         | FAIL (no LLM response) | n/a | n/a | REDUCE-LLM SKIPPED | n/a |
| P1C-LLM-03-STRATEGIC-SYNTHESIS    | FAIL (no LLM response) | n/a | n/a | REDUCE-LLM SKIPPED | n/a |

---

## Faz bem (com evidência)

- **Per-regulation rationale is grounded.** The CRA rationale
  correctly identifies `TIPO2-CRA-ART14-DUAL-FLOW` and the GDPR rationale
  explains why `TIPO3-GDPR-HOUSEHOLD` is `NOT_ACTIVATED`.
  > "derogations TIPO3-CRA-NON-PLACED and TIPO3-CRA-OPEN-SOURCE are
  > explicitly NOT_ACTIVATED because TinyTask is a commercial entity
  > placing proprietary software on the market" — Doc 05 §6.1b CRA
  > rationale (2 142 chars)
- **All P1B-01 interpretations cite DOC04 facts by key.**
  > "TinyTask's sector ('Technology/Software') does not match this
  > list (DOC04:FACTS-sector)" — Doc 05 §6.1b GDPR
- **Output deterministic stage delivered 6 artefacts + xlsx**
  (Doc 04/04a/04b/04c/05/06/07/07b) in ~5 min after REDUCE skipped —
  proves the renderers do not depend on REDUCE-LLM output.

## Faz mal (com evidência)

- **P1C-01 emits `## Pair classifications` bullets — the parser extracts 0 activations.**
  > "qwen3.5 emits a `## Pair classifications` section with
  > `- D-XX.Y : REG ↔ REG (VERDICT): …` bullets — a completely
  > different shape from the contract's `## Sub-domain Activations`
  > + `### D-XX.Y` subsections." — scout report §2.7
- **P1B-02 implications/gaps end up empty even though rationale prose is solid (2.1k chars).**
  > "P1B-02: emits `## Findings` with loose bullets instead of the
  > 5-section Status/Rationale/Implications/Gaps/Notes contract;
  > `implications`/`gaps` end up empty (the rationale prose itself
  > is high quality — 2.1k chars of grounded analysis per regulation)."
  > — scout report §2.6
- **Doc 04b maturity is `1/1/1/1/1/1/1/1/1/1`** for all 10 domains.
  No variance means the maturity scorer is not differentiating
  (or the model is conservatively flat). Flag: signal of either model
  weakness or scorer over-collapse.
- **P1C-02 and P1C-03 are absent.** Doc 05 §6.1b explicitly records
  > "_(no LLM response for this spec)_" for both, which is the
  > downstream symptom of `aggregated_activations` being empty.

## Verdict

A solid **P1B** runner whose output is good enough to drive Doc 05
verbatim, but it never reaches the **P1C** REDUCE stage because the
P1C-01 parser gate produces 0 activations. **Use qwen3.5 for P1B
exploration; it is not a candidate for full-pipeline validation.**

## Confidence

High — based on 1 805 s of MAP calls across 10 lanes and the full
deterministic-output render (8 artefacts + xlsx).