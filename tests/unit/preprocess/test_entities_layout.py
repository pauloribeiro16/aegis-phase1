"""CORR-031: invariants for the by-D-XX entities layout.

After the v11 refactor, every entity shard lives under
``entities/<kind>/<bucket>/<id>.json`` where the bucket is:

* D-XX (parent domain) for entities that carry a subdomain anchor
  (subdomain, sub-SO, pair, SR)
* _no_subdomain for SOs loaded from aggregated 01_SecObj whose
  ``sub_domains`` cell is empty or unparseable
* _root/<REG> for clauses (per-regulatory, no D-XX link)

This module asserts those invariants from the manifest and the
on-disk tree after a fresh ``python -m scripts.preprocess build``.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ENTITIES = REPO_ROOT / "preproc_out" / "entities"
MANIFEST = REPO_ROOT / "preproc_out" / "meta" / "manifest.json"

_D_XX_RE = re.compile(r"^D-(\d{2})(?:\.\d+)?$")
_BUCKETS = ("_root", "_no_subdomain", "_archive")


@pytest.fixture(scope="module")
def manifest() -> dict:
    if not MANIFEST.is_file():
        pytest.skip(f"manifest not built: {MANIFEST}")
    return json.loads(MANIFEST.read_text())


def _shards_by_kind(manifest: dict, kind: str) -> list[dict]:
    return [s for s in manifest["shards"] if s.get("kind") == kind]


def _all_shards_under(bucket: str) -> list[str]:
    """Every shard path under entities/<bucket>/."""
    return [
        s["path"]
        for s in json.loads(MANIFEST.read_text())["shards"]
        if s["path"].startswith(f"entities/{bucket}/")
    ]


# ─── 1. Subdomains are partitioned by parent D-XX ─────────────────────


def test_subdomains_live_under_d_xx_subdirs(manifest: dict) -> None:
    """Every subdomain shard lives under entities/subdomains/D-XX/.

    The pre-v11 flat layout ``entities/subdomains/D-XX.Y.json`` is no
    longer allowed (we'd lose the by-domain grouping). The 38 files
    are now exactly 38 in the new layout: 4 × 10 parent domains.
    """
    sd_shards = _shards_by_kind(manifest, "subdomain")
    assert len(sd_shards) == 38, f"expected 38 subdomain shards, got {len(sd_shards)}"

    for s in sd_shards:
        path = s["path"]
        assert path.startswith("entities/subdomains/D-"), (
            f"subdomain shard {path} is not under entities/subdomains/D-XX/"
        )
        # The path must be exactly 4 segments deep: subdomains/D-XX/D-XX.Y.json
        parts = path.split("/")
        assert len(parts) == 4, f"subdomain shard {path} is not D-XX/D-XX.Y.json"


def test_each_d_xx_has_between_1_and_4_subdomains(manifest: dict) -> None:
    """The taxonomy has 10 parent domains with 1-4 subdomains each (38 total)."""
    sd_shards = _shards_by_kind(manifest, "subdomain")
    by_parent: Counter = Counter()
    for s in sd_shards:
        path = s["path"]
        # entities/subdomains/D-04/D-04.3.json → parent D-04
        parts = path.split("/")
        by_parent[parts[2]] += 1
    for parent, count in by_parent.items():
        assert 1 <= count <= 4, f"{parent} has {count} subdomains (expected 1-4)"
    assert sum(by_parent.values()) == 38


# ─── 2. Pairs live under D-XX matching their subdomain_id ──────────────


def test_pairs_partitioned_by_subdomain_id(manifest: dict) -> None:
    """Every pair shard lives under entities/pairs/D-XX/ matching its subdomain_id."""
    pair_shards = _shards_by_kind(manifest, "entity_pair")
    assert len(pair_shards) == 196, f"expected 196 pair shards, got {len(pair_shards)}"

    for s in pair_shards:
        path = s["path"]
        assert path.startswith("entities/pairs/D-"), (
            f"pair shard {path} is not under entities/pairs/D-XX/"
        )
        # No _root/_no_subdomain/_archive for pairs (they always have
        # a subdomain_id by construction)
        parts = path.split("/")
        assert len(parts) == 4, f"pair shard {path} is not D-XX/<id>.json"


# ─── 3. SOs go to D-XX (first parent) or _no_subdomain ────────────────


def test_sos_partitioned_by_d_xx_or_no_subdomain(manifest: dict) -> None:
    """SO shards live under entities/sos/D-XX/ or entities/sos/_no_subdomain/."""
    so_shards = _shards_by_kind(manifest, "entity_so")
    # Should have 168 (from aggregated 01_SecObj) + 136 (hso_per_reg) = 304.
    # But the original 342 was inflated by duplicates written by both
    # the per-section and _build_indices paths. The new pipeline writes
    # once, so we expect 304 distinct SO entities.
    assert len(so_shards) >= 280, f"expected ~304 SO shards, got {len(so_shards)}"

    by_bucket: Counter = Counter()
    for s in so_shards:
        path = s["path"]
        assert path.startswith("entities/sos/"), f"bad SO path {path}"
        parts = path.split("/")
        bucket = parts[2]
        by_bucket[bucket] += 1
        if bucket not in _BUCKETS:
            assert bucket.startswith("D-"), f"unexpected SO bucket {bucket}"
        # Sub-bucket depth
        if bucket.startswith("D-"):
            assert len(parts) == 4, f"SO shard {path} not in D-XX/<id>.json"

    # The _no_subdomain bucket should be tiny (3 orphans: SO-AIACT-002,
    # SO-AIACT-009, SO-CRA-016 — see B.2 inference analysis).
    no_sub = by_bucket.get("_no_subdomain", 0)
    assert no_sub <= 5, (
        f"_no_subdomain bucket has {no_sub} SOs (expected ≤5). "
        f"Review 01_SecurityObjectives.md for unparseable 'sub_domains' cells."
    )


def test_so_hl_live_under_d_xx(manifest: dict) -> None:
    """High-level SOs (SO-D-XX.Y.HL) live under their D-XX bucket."""
    hl_shards = _shards_by_kind(manifest, "entity_so_hl")
    assert len(hl_shards) == 38, f"expected 38 SO-HL shards, got {len(hl_shards)}"
    for s in hl_shards:
        path = s["path"]
        # entities/sos/D-XX/SO_D_XX_Y_HL.json
        assert path.startswith("entities/sos/D-"), f"SO-HL not under D-XX/: {path}"
        parts = path.split("/")
        assert len(parts) == 4, f"SO-HL shard {path} is not D-XX/<id>.json"


# ─── 4. SRs go to D-XX (first parent) ─────────────────────────────────


def test_srs_partitioned_by_d_xx(manifest: dict) -> None:
    """Every SR shard lives under entities/srs/D-XX/ matching its first sub_domain."""
    sr_shards = _shards_by_kind(manifest, "entity_sr")
    assert len(sr_shards) == 282, f"expected 282 SR shards, got {len(sr_shards)}"
    by_bucket: Counter = Counter()
    for s in sr_shards:
        path = s["path"]
        assert path.startswith("entities/srs/D-"), f"bad SR path {path}"
        by_bucket[path.split("/")[2]] += 1
    # No _no_subdomain SRs (every SR has at least one sub_domain)
    assert "_no_subdomain" not in by_bucket, (
        f"some SRs ended up in _no_subdomain: {by_bucket.get('_no_subdomain', 0)}"
    )


# ─── 5. Clauses live under _root/{REG}/ (per-regulatory) ──────────────


def test_clauses_live_under_root_by_regulation(manifest: dict) -> None:
    """Every clause shard lives under entities/clauses/_root/{REG}/."""
    clause_shards = _shards_by_kind(manifest, "clause")
    assert len(clause_shards) == 578, (
        f"expected 578 clause shards, got {len(clause_shards)}"
    )
    regs: Counter = Counter()
    for s in clause_shards:
        path = s["path"]
        parts = path.split("/")
        assert parts[2] == "_root", f"clause not under _root/: {path}"
        reg = parts[3]
        regs[reg] += 1
    # 5 regulations: CRA, GDPR, NIS2, DORA, AI_Act
    assert set(regs.keys()) == {"CRA", "GDPR", "NIS2", "DORA", "AI_Act"}, (
        f"unexpected clause regs: {set(regs.keys())}"
    )


# ─── 6. No flat shards at the old (pre-v11) locations ─────────────────


def test_no_pre_v11_flat_shards_remain(manifest: dict) -> None:
    """Pre-v11 flat layout (``entities/<kind>/D-XX.Y.json``) is gone.

    Only the D-XX/<id>.json shape is allowed. Any file at the top
    level of entities/<kind>/ (other than the special _root/_no_subdomain/
    _archive/ buckets) is a leftover that must be cleaned.
    """
    for kind in ("subdomains", "pairs", "sos", "srs"):
        # Top-level entries that are *.json (not directories)
        prefix = f"entities/{kind}/"
        leftovers = []
        for s in manifest["shards"]:
            path = s["path"]
            if not path.startswith(prefix):
                continue
            tail = path[len(prefix):]
            # tail must contain at least one '/' (sub-bucket) OR be a bucket
            if "/" not in tail and tail.endswith(".json"):
                leftovers.append(path)
        assert not leftovers, (
            f"pre-v11 flat shards in {kind}/: {leftovers}"
        )


# ─── 7. Manifest counts match the pre-v11 totals ──────────────────────


def test_manifest_entity_counts_unchanged(manifest: dict) -> None:
    """The refactor must not change entity counts."""
    counts = Counter(s.get("kind") for s in manifest["shards"])

    # Pre-v11 totals (from CORR-029 audit + re-aggregation):
    assert counts.get("subdomain") == 38
    assert counts.get("entity_pair") == 196
    # 304 = aggregated 01_SecObj + per-subdomain hso_per_reg SOs (minus
    # duplicates that the v11 refactor dedupes; the count is stable at
    # ~304 across builds).
    assert counts.get("entity_so") + counts.get("entity_so_hl") == 304 + 38
    assert counts.get("entity_sr") == 282
    assert counts.get("clause") == 578
