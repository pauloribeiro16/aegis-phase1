"""CORR-024 preprocessor v2 — converts 00_METHODOLOGY/ into structured JSON.

Scope (per user decision 2026-07-18): PREPROCESSING/ + diagrams/.

Output structure (preproc_out/, v8 layout):
  meta/                              build metadata
    manifest.json                    (full shard inventory + errors)
    build_info.json                  (counts + summary)

  README.md                          (this layout, human-readable)

  global/                            top-level aggregated references
    NIST_CSF_2.0_subcategories.json  (185 × CSF 2.0 official, schema 1.3)
    00_Hierarchical_SecurityObjectives.json
    README.json
    TEMPLATE_subagent_brief.json

  index/                             lookup indices
    entities.json                    (entity_id → shard_path)
    by_regulation.json               (regulation → entity lists)
    by_subdomain.json                (D-XX.Y → entity lists)
    cross_references.json            (entity_id → {points_to, pointed_by})

  entities/                          ALL entity shards (8 kinds)
    csfs/                            NIST CSF 2.0 subcategories (106 active)
      _meta/_index.json              (id → path map)
      GV/  (31 shards — Govern)
      ID/  (21 shards — Identify)
      PR/  (22 shards — Protect)
      DE/  (11 shards — Detect)
      RS/  (13 shards — Respond)
      RC/  ( 8 shards — Recover)
    subdomains/  D-XX.Y.json         (38 subdomains)
    articles/    {REG}_Art_NN.json   (per-article splits, 140)
    clauses/     {REG}-CLxx.json     (per-clause entities, 578)
    sos/         SO-{REG}-NNN.json   (per-SO entities, 338)
    srs/         SR-{REG}-NNN.json   (per-SR entities, 282)
    pairs/       {D-XX.Y}_{a}-{b}.json (per-pair entities, 196)
    ambiguities/                     (reserved; v8 spelling)

  regulation/                        per-regulation tree
    {REG}/
      _root/                         (00_README, 01_SO, 02_SR, 03_validation, 04_deduction)
      articles/                      (per-article splits)
      clauses/                       (per-Ambiguity clause files)
      aggregated/                    (full SO + SR lists per regulation)

  crossregulation/                   cross-regulation analysis
    _templates/                      (TEMPLATE_crossreg_brief.json, etc.)
    DomainAnalysis/D-XX_*/           (per-domain analysis)
    DeepAnalysis/D-XX_*/             (per-domain deep analysis)

  diagrams/                          flux + class diagrams
    Class_Models/
    fluxdiagram/{phase1,phase2,phase3}/

  ambiguity_analysis/                ambiguity framework (top-level)
    00_Index.json
    01_Framework.json
"""

from __future__ import annotations

__version__ = "2.0.0"
