"""CORR-024 preprocessor v2 — converts 00_METHODOLOGY/ into structured JSON.

Scope (per user decision 2026-07-18): PREPROCESSING/ + diagrams/.

Output structure (preproc_out/):
  entities/
    subdomains/D-XX.Y.json
    articles/Art_NN.json
    clauses/{REG}-CLxx.json
    sos/SO-{REG}-NNN.json
    srs/SR-{REG}-NNN.json
    pairs/{D-XX.Y}_{a}-{b}.json
    ambiguities/{REG}-CLxx.json
    csf/{FUNCTION}.{CAT}-{NN}.json
  regulation/
    {REG}/
      articles/Art_NN.json          (root + per-article split)
      aggregated/01_SecurityObjectives.json  (full SO list)
      aggregated/02_SecurityRules_NIST.json  (full SR list)
      clauses/{REG}-CLxx.json
      ambiguity_clauses/{REG}-*.json
      roots/{00_README,01_SO,02_SR_NIST,03_validation,04_deduction}.json
  crossregulation/  (DeepAnalysis + DomainAnalysis shards)
  diagrams/  (per-flux-diagram steps list)
  global/  (NIST_CSF, HSO, README, subagent_brief)
  ambiguity_analysis/  (00_Index, 01_Framework)
  index/
    entities.json         (entity_id → shard_path)
    by_regulation.json    (regulation → {articles, sos, srs, clauses, ambiguities})
    by_subdomain.json     (D-XX.Y → {hl, sub_sos, pairs, applicable_*})
    cross_references.json (entity_id → {points_to, pointed_by})
  manifest.json
  build_info.json
"""

from __future__ import annotations

__version__ = "2.0.0"
