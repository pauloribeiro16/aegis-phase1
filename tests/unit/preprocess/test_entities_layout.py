"""CORR-031 (post-CORR-032): filesystem layout invariants.

This module asserts the by-D-XX filesystem layout directly from
``preproc_out/entities/<kind>/<bucket>/<id>.json`` (rather than from
the manifest, which only carries a subset of the shards). The
filesystem is the source of truth for downstream consumers that
load by path glob.

Layout contract:

  entities/subdomains/D-XX/D-XX.Y.json      (38 shards, 10 parent domains)
  entities/pairs/D-XX/D-XX.Y_REG_A-REG_B.json (per-subdomain lanes)
  entities/sos/D-XX/SO-XXX.json            (sub-SOs + master SOs)
  entities/sos/_no_subdomain/SO-XXX.json   (orphans, ≤5)
  entities/srs/D-XX/SR-REG-NNN.json        (282 shards, first sub_domain)
  entities/clauses/_root/{REG}/CLAUSE_ID.json (per-regulatory, 543 shards)
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ENTITIES = REPO_ROOT / "preproc_out" / "entities"


def _list_shards(kind: str, bucket: str | None = None) -> list[Path]:
    d = ENTITIES / kind
    if not d.is_dir():
        return []
    if bucket is None:
        return sorted(p for p in d.rglob("*.json") if p.is_file())
    return sorted((d / bucket).rglob("*.json"))


# ─── 1. Subdomains are partitioned by parent D-XX ─────────────────────


def test_subdomains_partitioned_by_d_xx() -> None:
    """Every subdomain lives under entities/subdomains/D-XX/."""
    sd_files = _list_shards("subdomains")
    # Exclude _archive
    sd_files = [p for p in sd_files if "_archive" not in p.parts]
    assert len(sd_files) == 38, f"expected 38 subdomain files, got {len(sd_files)}"
    by_parent: Counter = Counter()
    for p in sd_files:
        # entities/subdomains/D-04/D-04.3.json → D-04
        rel = p.relative_to(ENTITIES / "subdomains")
        by_parent[rel.parts[0]] += 1
    for parent, count in by_parent.items():
        assert parent.startswith("D-"), f"non-D-XX parent: {parent}"
        assert 1 <= count <= 4, f"{parent} has {count} subdomains"
    assert sum(by_parent.values()) == 38


# ─── 2. Pairs live under D-XX matching their subdomain_id ──────────────


def test_pairs_partitioned_by_subdomain_id() -> None:
    """Every pair shard lives under entities/pairs/D-XX/."""
    pair_files = _list_shards("pairs")
    assert len(pair_files) >= 100, f"expected ≥100 pair files, got {len(pair_files)}"
    for p in pair_files:
        rel = p.relative_to(ENTITIES / "pairs")
        assert rel.parts[0].startswith("D-"), f"pair {p} not under D-XX/"


# ─── 3. SOs go to D-XX (first parent) or _no_subdomain ────────────────


def test_sos_partitioned_by_d_xx_or_no_subdomain() -> None:
    """SO shards live under entities/sos/D-XX/ or entities/sos/_no_subdomain/."""
    so_files = _list_shards("sos")
    assert len(so_files) >= 100, f"expected ≥100 SO files, got {len(so_files)}"
    by_bucket: Counter = Counter()
    for p in so_files:
        rel = p.relative_to(ENTITIES / "sos")
        by_bucket[rel.parts[0]] += 1
    # All D-XX buckets
    for bucket in by_bucket:
        assert bucket.startswith("D-") or bucket in ("_no_subdomain", "_root"), (
            f"unexpected SO bucket {bucket}"
        )
    no_sub = by_bucket.get("_no_subdomain", 0)
    assert no_sub <= 5, (
        f"_no_subdomain bucket has {no_sub} SOs (expected ≤5)"
    )


# ─── 4. SRs go to D-XX (first parent) ─────────────────────────────────


def test_srs_partitioned_by_d_xx() -> None:
    """Every SR shard lives under entities/srs/D-XX/."""
    sr_files = _list_shards("srs")
    assert len(sr_files) >= 200, f"expected ≥200 SR files, got {len(sr_files)}"
    for p in sr_files:
        rel = p.relative_to(ENTITIES / "srs")
        assert rel.parts[0].startswith("D-"), f"SR {p} not under D-XX/"


# ─── 5. Clauses live under _root/{REG}/ (per-regulatory) ──────────────


def test_clauses_live_under_root_by_regulation() -> None:
    """Every clause lives under entities/clauses/_root/{REG}/."""
    clause_files = _list_shards("clauses")
    assert len(clause_files) >= 400, (
        f"expected ≥400 clause files, got {len(clause_files)}"
    )
    regs: Counter = Counter()
    for p in clause_files:
        rel = p.relative_to(ENTITIES / "clauses")
        assert rel.parts[0] == "_root", f"clause {p} not under _root/"
        regs[rel.parts[1]] += 1
    assert {"CRA", "GDPR", "NIS2", "DORA", "AI_Act"}.issubset(set(regs.keys())), (
        f"missing regulation in clauses: {set(regs.keys())}"
    )


# ─── 6. Canonical clause-id format on disk (CORR-032) ───────────────


def test_clause_filenames_match_canonical_pattern() -> None:
    """All clause filenames match the canonical {REG}-CL{NN} pattern.

    Filename form: {REG}_CL{NN}.json (dot→underscore for filesystem
    safety). Multi-clause articles use the DORA-CL{NN}-{M} form.
    The dash in the id becomes an underscore in the filename
    (filesystem convention), so ``DORA-CL10-1`` → ``DORA_CL10_1.json``.
    """
    clause_files = _list_shards("clauses")
    canon_re = re.compile(
        r"^(CRA|GDPR|NIS2|DORA|AI_Act)_"
        r"(CL\d{1,3}[a-z]?|CL\d{1,3}[-_]\d+"      # generic CL form (dash or underscore separator)
        r"|RT\d{1,3}[a-z]?"                       # GDPR Ch III (Rights)
        r"|CP\d{1,3}[a-z]?"                       # GDPR Ch IV (Ctrl-Proc)
        r"|TR\d{1,3}[a-z]?"                       # GDPR Ch V (Transfers)
        r")$"
    )
    drift = [
        p.name for p in clause_files if not canon_re.match(p.stem)
    ]
    assert not drift, (
        f"non-canonical clause filenames (first 10): {drift[:10]}"
    )


# ─── 7. SO/SR filenames use AI_Act prefix ────────────────────────────


def test_so_filenames_use_ai_act_not_aiact() -> None:
    """No SO file uses the legacy AIACT prefix."""
    so_files = _list_shards("sos")
    drift = [p.name for p in so_files if "AIACT" in p.name]
    assert not drift, f"SO files with AIACT: {drift[:5]}"


def test_sr_filenames_use_ai_act_not_aiact() -> None:
    """No SR file uses the legacy AIACT prefix."""
    sr_files = _list_shards("srs")
    drift = [p.name for p in sr_files if "AIACT" in p.name]
    assert not drift, f"SR files with AIACT: {drift[:5]}"


# ─── 8. Total entity counts are stable ──────────────────────────────


def test_total_clause_count_in_expected_range() -> None:
    """Clauses ≥400 (CORR-032 may shift within this range)."""
    clause_files = _list_shards("clauses")
    assert 400 <= len(clause_files) <= 700, (
        f"clause count {len(clause_files)} outside [400, 700]"
    )


def test_total_sr_count_is_282() -> None:
    """SR count unchanged from CORR-029 (282)."""
    sr_files = _list_shards("srs")
    assert len(sr_files) == 282, f"expected 282 SRs, got {len(sr_files)}"
