"""CORR-032: invariants for the canonical entity ID format.

After the v12 refactor, every entity ID must use the canonical form
defined in AGENTS.md §11. This module scans both:

* the source MDs under Methodology-main/00_METHODOLOGY/ (executed
  only if that directory is available — the test is skipped otherwise
  so the unit suite stays runnable from the aegis-phase1-only env)
* the preproc_out/entities/ shards (always checked)

and asserts the absence of every legacy / drift form. New drift is
caught here before it can propagate.
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
METHODOLOGY = REPO_ROOT.parent / "Methodology-main" / "00_METHODOLOGY"


# ─── 1. Preproc-level invariants (always checked) ──────────────────────


def _load_clause_ids_from_manifest() -> list[str]:
    m = json.loads(MANIFEST.read_text())
    return [
        eid
        for s in m["shards"]
        if s.get("kind") == "clause"
        for eid in s.get("entity_ids", [])
    ]


def test_no_aia_c_clauses_in_preproc() -> None:
    """AIA-C{NN} (legacy) must not appear in preproc_out/clauses."""
    eids = _load_clause_ids_from_manifest()
    drift = [eid for eid in eids if re.match(r"^AIA-C\d+", eid)]
    assert not drift, (
        f"AIA-C legacy clauses in preproc_out: {drift[:5]}. "
        f"Run the Methodology-main migration script to fix."
    )


def test_no_aiact_in_so_sr_or_clauses() -> None:
    """AIACT prefix (legacy) must not appear in any preproc entity id."""
    m = json.loads(MANIFEST.read_text())
    drift = []
    for s in m["shards"]:
        for eid in s.get("entity_ids", []):
            if "AIACT" in eid:
                drift.append((s.get("kind"), eid))
    assert not drift, (
        f"AIACT legacy prefix in preproc_out: {drift[:5]}. "
        f"Run the Methodology-main migration script to fix."
    )


def test_clauses_use_reg_cl_format() -> None:
    """Every clause id must match the canonical {REG}-CL{NN} format.

    Accepted regexes:
      - CRA-CL01, NIS2-CL01, GDPR-CL01, DORA-CL01, AI_Act-CL01
      - DORA-CL{NN}-{M} for multi-clause articles
    Anything else (bare CL-N-M without DORA-, GDPR-C without -L, etc.)
    is a drift that must be fixed at source.
    """
    eids = _load_clause_ids_from_manifest()
    # Per-REG chapter-specific prefix map. The base form is CL{NN};
    # GDPR uses additional prefixes for its Chapter III (RT = Rights),
    # Chapter IV (CP = Controller-Processor), and Chapter V (TR =
    # Transfers). NIS2 may use a v0.1 cross-article CN form (no -L) for
    # historical mapping tables — see AGENTS.md §11.3 for the
    # GDPR/RT/CP/TR rationale.
    canon_re = re.compile(
        r"^(CRA|GDPR|NIS2|DORA|AI_Act)-"
        r"(CL\d{1,3}[a-z]?|CL\d{1,3}-\d+"        # generic CL form
        r"|RT\d{1,3}[a-z]?"                       # GDPR Ch III (Rights)
        r"|CP\d{1,3}[a-z]?"                       # GDPR Ch IV (Ctrl-Proc)
        r"|TR\d{1,3}[a-z]?"                       # GDPR Ch V (Transfers)
        r")$"
    )
    drift = [eid for eid in eids if not canon_re.match(eid)]
    # Report
    counter: Counter = Counter()
    for eid in drift:
        counter[eid.split("-")[0]] += 1
    assert not drift, (
        f"non-canonical clause ids in preproc_out ({len(drift)} total, "
        f"by reg prefix: {dict(counter)}). "
        f"Sample: {drift[:10]}"
    )


def test_sos_use_aiact_or_aia_act_form() -> None:
    """All AI_Act master SOs must use the AI_Act prefix (not AIACT)."""
    m = json.loads(MANIFEST.read_text())
    so_master_eids = [
        eid
        for s in m["shards"]
        for eid in s.get("entity_ids", [])
        if re.match(r"^SO-[A-Z_0-9]+-\d+$", eid) and not eid.startswith("SO-D-")
    ]
    ai_act_drift = [
        eid for eid in so_master_eids if eid.startswith("SO-AIACT-")
    ]
    assert not ai_act_drift, (
        f"SO-AIACT- legacy master SOs: {ai_act_drift}. "
        f"Run the migration: SO-AIACT-NNN → SO-AI_Act-NNN."
    )


def test_srs_use_aiact_or_aia_act_form() -> None:
    """All AI_Act master SRs must use the AI_Act prefix (not AIACT)."""
    m = json.loads(MANIFEST.read_text())
    sr_master_eids = [
        eid
        for s in m["shards"]
        for eid in s.get("entity_ids", [])
        if re.match(r"^SR-[A-Z_0-9]+-\d+$", eid)
    ]
    ai_act_drift = [
        eid for eid in sr_master_eids if eid.startswith("SR-AIACT-")
    ]
    assert not ai_act_drift, (
        f"SR-AIACT- legacy master SRs: {ai_act_drift}. "
        f"Run the migration: SR-AIACT-NNN → SR-AI_Act-NNN."
    )


def test_subdomain_sub_so_have_underscored_ai_act() -> None:
    """Sub-SOs (hso_per_reg) for AI_Act must use AI_Act (not AIACT)."""
    m = json.loads(MANIFEST.read_text())
    drift = []
    for s in m["shards"]:
        if s.get("kind") != "subdomain":
            continue
        # s["path"] is relative to preproc_out/ (which is REPO_ROOT/preproc_out)
        sd = json.loads((REPO_ROOT / "preproc_out" / s["path"]).read_text())
        for hso in sd.get("hso_per_reg", []):
            eid = hso.get("id", "")
            if "AIACT" in eid:
                drift.append(eid)
    assert not drift, (
        f"Sub-SO entities with AIACT in their id: {drift[:5]}. "
        f"Sub-SO id format is SO-D-XX.Y.AI_Act (post-CORR-032)."
    )


# ─── 2. Source-level invariants (Methodology-main only) ────────────────


@pytest.mark.skipif(
    not METHODOLOGY.is_dir(),
    reason=f"Methodology-main not found at {METHODOLOGY} (run from a CI env that has it)",
)
def test_no_legacy_drift_in_active_source_mds() -> None:
    """No legacy ID forms in the active source tree (excluding _archive/).

    The exact patterns AGENTS.md §11.4 lists as forbidden.
    """
    forbidden = [
        r"\bAIA-C\d+",          # AIA-C01, AIA-CL01
        r"\bAIA-CL\d+",         # AIA-CL01
        r"\bAI-CL\d+",          # AI-CL01
        r"\bAIACT-C\d+",        # AIACT-C01
        r"\bAIACT-CL\d+",       # AIACT-CL01
        r"\bSO-AIACT-\d+",      # SO-AIACT-001
        r"\bSR-AIACT-\d+",      # SR-AIACT-001
        r"\bGDPR-C\d+",         # GDPR-C01 (must be GDPR-CL01)
        r"\bDORA-C\d+",         # DORA-C01 (must be DORA-CL01)
    ]
    bad_files: list[tuple[str, str]] = []
    for fp in METHODOLOGY.rglob("*.md"):
        if "_archive" in fp.parts or "_build" in fp.parts:
            continue
        text = fp.read_text(encoding="utf-8")
        for pat in forbidden:
            m = re.search(pat, text)
            if m:
                bad_files.append((str(fp.relative_to(METHODOLOGY)), m.group(0)))
                break
    assert not bad_files, (
        f"legacy ID forms in active source MDs (first 10): "
        f"{bad_files[:10]}. "
        f"Re-run the migration script in Methodology-main/."
    )


@pytest.mark.skipif(
    not METHODOLOGY.is_dir(),
    reason=f"Methodology-main not found at {METHODOLOGY}",
)
def test_ai_act_dora_orphan_clauses_have_prefix() -> None:
    """DORA cross-article orphan clauses `CL{NN}-{M}` must be `DORA-CL{NN}-{M}`."""
    bad_files: list[tuple[str, str]] = []
    for fp in METHODOLOGY.rglob("*.md"):
        if "_archive" in fp.parts:
            continue
        # Only in DORA dir
        if "/DORA/" not in str(fp):
            continue
        text = fp.read_text(encoding="utf-8")
        for m in re.finditer(r"\bCL\d+-\d+\b", text):
            # Must have DORA- prefix
            start = m.start()
            prefix = text[max(0, start - 5):start]
            if "DORA-" not in prefix:
                bad_files.append((str(fp.relative_to(METHODOLOGY)), m.group(0)))
                break
    assert not bad_files, (
        f"unprefixed DORA orphan clauses (CL{NN}-{M} without DORA-): "
        f"{bad_files[:5]}. "
        f"Re-run the migration: CL{NN}-{M} → DORA-CL{NN}-{M}."
    )
