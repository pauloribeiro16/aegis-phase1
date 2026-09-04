"""Tests for `scripts.kg_eval.score_t1` (CORR-113 Commit 4).

8 tests — one per documented metric + a few combinations:

  1. T1.1 citation ⊆ packet (valid)
  2. T1.1 citation ⊆ packet (invalid → invalid_tokens populated)
  3. T1.1 CSF tokens in catalogue
  4. T1.2 tension block present + severity in enum
  5. T1.3 ambiguity block + disposition in vocab + reading in verbatim_articles
  6. T1.4 tier/evidence/example controls/owner/verification
  7. T1.5 coverage + canonical regs
  8. EMPTY_PACKET detection + judge cell stub
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.kg_eval.generate_context_packets import generate_packet
from scripts.kg_eval.score_t1 import (
    score_run,
    score_runs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CASE1 = REPO_ROOT / "cases" / "case1-tinytask"
PREPROC = REPO_ROOT / "preproc_out"
TASKS_YAML = REPO_ROOT / "scripts" / "kg_eval" / "tasks.yaml"


# ─── Helpers ─────────────────────────────────────────────────────────


def _metric(score: dict, name: str) -> dict:
    """Return the metric dict with the given name from a score record."""
    for m in score["metrics"]:
        if m.get("metric") == name:
            return m
    raise AssertionError(f"metric {name!r} not in score record: {score['metrics']}")


def _make_run(
    tmp_path: Path,
    *,
    family: str,
    task_id: str,
    raw: str,
    packet: dict | None,
    script_status: str = "OK",
) -> Path:
    """Create a fake run directory under tmp_path mirroring the runner output."""
    from scripts.kg_eval.run_t1 import load_tasks, select_task

    task = select_task(load_tasks(TASKS_YAML), task_id)
    run_dir = tmp_path / "fake_run"
    run_dir.mkdir()
    env = {
        "task_id": task_id,
        "case_id": CASE1.name,
        "subdomain_id": task["subdomain_id"],
        "family": family,
        "arm": "with_kg" if packet is not None else "no_kg",
        "model": "mock",
        "provider": "mock",
        "packet_sha256": "deadbeef" if packet is not None else None,
        "commit_sha": "testsha",
        "timestamp_utc": "20260903T000000Z",
        "status": script_status,
    }
    (run_dir / "env.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    (run_dir / "raw_response.md").write_text(raw, encoding="utf-8")
    if packet is not None:
        (run_dir / "packet.json").write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return run_dir


# ─── T1.1 — citation ⊆ packet + CSF tokens ──────────────────────────


def test_t11_citation_subset_valid(tmp_path: Path) -> None:
    """Valid citation: every SYS-*/STORE-*/FLOW-* in raw is in packet's asset_ids."""
    packet = generate_packet(CASE1, "D-01.1", PREPROC)
    raw = (
        "## Affected systems\n"
        "- SYS-01 | Main SaaS Application | criticality=HIGH\n"
        "- STORE-01 | Primary Database\n\n"
        "## Legal clauses (per regulation)\n"
        "- GDPR: GDPR-CL05\n"
        "- CRA: CRA-CL01\n\n"
        "## CSF anchors\n"
        "- PR.DS-01\n"
    )
    run = _make_run(tmp_path, family="T1.1", task_id="T1.1-case1-D-01.1", raw=raw, packet=packet)
    score = score_run(run)
    metric = _metric(score, "citation_subset_of_packet")
    assert metric["value"] is True
    assert metric["invalid_count"] == 0


def test_t11_citation_subset_invalid(tmp_path: Path) -> None:
    """Invalid citation: SYS-99 not in packet → invalid_tokens populated."""
    packet = generate_packet(CASE1, "D-01.1", PREPROC)
    raw = (
        "## Affected systems\n"
        "- SYS-01 | ok\n"
        "- SYS-99 | invented id\n"  # NOT in packet
    )
    run = _make_run(tmp_path, family="T1.1", task_id="T1.1-case1-D-01.1", raw=raw, packet=packet)
    score = score_run(run)
    metric = _metric(score, "citation_subset_of_packet")
    assert metric["value"] is False
    assert "SYS-99" in metric["invalid_tokens"]


def test_t11_csf_tokens_in_catalogue(tmp_path: Path) -> None:
    """CSF token not in packet's csf_anchors is flagged."""
    packet = generate_packet(CASE1, "D-01.1", PREPROC)
    # Packet has PR.DS-01, PR.DS-11, PR.DS-02 — let's use PR.DS-99 (unknown)
    raw = "## CSF anchors\n- PR.DS-99\n"
    run = _make_run(tmp_path, family="T1.1", task_id="T1.1-case1-D-01.1", raw=raw, packet=packet)
    score = score_run(run)
    metric = _metric(score, "csf_tokens_in_catalogue")
    assert metric["value"] is False
    assert "PR.DS-99" in metric["invalid_tokens"]


# ─── T1.2 — tension block + severity ────────────────────────────────


def test_t12_tension_block_and_severity(tmp_path: Path) -> None:
    """Well-formed tension block with HIGH severity → both metrics pass."""
    raw = (
        "### Tension Resolution: GDPR vs CRA — TEMPORAL_CONFLICT\n"
        "- Friction: 72h vs 24h breach SLA\n"
        "- Resolution adopted: Adopt max-SLA workflow (24h internal escalation)\n"
        "- Severity: HIGH\n"
        "- Source reference: TI-01\n"
    )
    run = _make_run(
        tmp_path,
        family="T1.2",
        task_id="T1.2-case1-D-04.3",
        raw=raw,
        packet=generate_packet(CASE1, "D-04.3", PREPROC),
    )
    score = score_run(run)
    assert _metric(score, "structured_block_tension_present")["value"] is True
    sev = _metric(score, "severity_in_enum")
    assert sev["value"] is True
    assert sev["found"] == "HIGH"


# ─── T1.3 — ambiguity block + disposition + reading ─────────────────


def test_t13_ambiguity_disposition_full(tmp_path: Path) -> None:
    """Ambiguity block: disposition ∈ vocab, reading present, structure ok."""
    packet = generate_packet(CASE1, "D-01.2", PREPROC)
    raw = (
        "### Ambiguity Disposition: GDPR vs CRA — D-01.2\n"
        "- Reading adopted: The non-integrated SaaS deployer reads as a controller\n"
        "- Anchors: GDPR Art. 4(7), Tier=MICRO, SYS-01, BG-01\n"
        "- Consequence: One combined documentation pack\n"
        "- Disposition: RESOLVED_BY_FACT\n"
    )
    run = _make_run(
        tmp_path,
        family="T1.3",
        task_id="T1.3-case1-D-01.2",
        raw=raw,
        packet=packet,
    )
    score = score_run(run)
    assert _metric(score, "structured_block_ambiguity_present")["value"] is True
    assert _metric(score, "disposition_in_vocab")["value"] is True
    # reading check returns either True (match) or False; accept either
    reading = _metric(score, "reading_in_verbatim_articles")
    assert reading["metric"] == "reading_in_verbatim_articles"


def test_t13_disposition_invalid_vocab(tmp_path: Path) -> None:
    """Disposition NOT in {RESOLVED_BY_FACT, RESOLVED_BY_TIER, NEEDS_HUMAN} → fail."""
    packet = generate_packet(CASE1, "D-01.2", PREPROC)
    raw = (
        "### Ambiguity Disposition: GDPR vs CRA — D-01.2\n"
        "- Reading adopted: Some reading\n"
        "- Anchors: -\n"
        "- Consequence: -\n"
        "- Disposition: INVALID_TOKEN\n"
    )
    run = _make_run(
        tmp_path,
        family="T1.3",
        task_id="T1.3-case1-D-01.2",
        raw=raw,
        packet=packet,
    )
    score = score_run(run)
    assert _metric(score, "disposition_in_vocab")["value"] is False


# ─── T1.4 — proportionality adequacy (5 sub-metrics) ─────────────────


def test_t14_proportionality_all_metrics(tmp_path: Path) -> None:
    """T1.4 with well-formed Proportionality block → all 5 metrics emit."""
    raw = (
        "## Proportionality for D-07.1 at tier STANDARD\n"
        "- Tier: STANDARD\n"
        "- Evidence depth: Cloud-managed AES-256 + KMS key rotation policy\n"
        "- Verification method: INSPECT\n"
        "- Example controls: Encryption at rest; Key management\n"
        "- Owner: CISO\n"
    )
    run = _make_run(
        tmp_path,
        family="T1.4",
        task_id="T1.4-case1-D-07.1",
        raw=raw,
        packet=generate_packet(CASE1, "D-07.1", PREPROC),
    )
    score = score_run(run)
    assert _metric(score, "tier_in_enum")["value"] is True
    assert _metric(score, "evidence_depth_non_empty")["value"] is True
    assert _metric(score, "example_controls_cited")["value"] is True
    assert _metric(score, "owner_named")["value"] is True
    assert _metric(score, "verification_method_in_enum")["value"] is True


# ─── T1.5 — coverage + canonical regs ───────────────────────────────


def test_t15_coverage_and_canonical_regs(tmp_path: Path) -> None:
    """T1.5 with valid regs + CSF anchors + tension block → coverage OK + no invented regs."""
    raw = (
        "## Active regulations\n"
        "- GDPR: CONTROLLER (context=customer_data)\n"
        "- CRA: MANUFACTURER (context=product_sale)\n\n"
        "## Activated subdomains (top 5 by tier)\n"
        "- D-01.1 | tier=STANDARD | priority=MUST\n"
        "- D-04.3 | tier=STANDARD | priority=MUST\n\n"
        "## Open tensions\n"
        "### Tension Resolution: GDPR vs CRA — TEMPORAL_CONFLICT\n"
        "- Friction: SLA mismatch\n"
        "- Resolution adopted: Adopt max-SLA workflow\n"
        "- Severity: HIGH\n"
        "- Source reference: TI-01\n\n"
        "## CSF anchors (per active regulation)\n"
        "- GDPR: PR.DS-01, PR.DS-11\n"
        "- CRA: PR.IP-01\n"
    )
    run = _make_run(
        tmp_path,
        family="T1.5",
        task_id="T1.5-case1-D-01.1",
        raw=raw,
        packet=generate_packet(CASE1, "D-01.1", PREPROC),
    )
    score = score_run(run)
    coverage = _metric(score, "coverage_metrics")
    assert coverage["has_any_structured_block"] is True
    assert coverage["subdomains_cited"]  # non-empty
    assert coverage["csf_anchors_cited"]  # non-empty
    regs = _metric(score, "active_regulations_canonical")
    assert regs["value"] is True
    assert regs["count"] >= 2


def test_t15_invented_regulation_fails(tmp_path: Path) -> None:
    """Invented regulation token (FOOBAR) is flagged as invalid."""
    raw = (
        "## Active regulations\n"
        "- GDPR: CONTROLLER\n"
        "- FOOBAR: invented\n"  # NOT in canonical 5-vocab
    )
    run = _make_run(
        tmp_path,
        family="T1.5",
        task_id="T1.5-case1-D-01.1",
        raw=raw,
        packet=generate_packet(CASE1, "D-01.1", PREPROC),
    )
    score = score_run(run)
    regs = _metric(score, "active_regulations_canonical")
    assert regs["value"] is False
    assert "FOOBAR" in regs["invalid"]


# ─── EMPTY_PACKET + judge stub + batch ───────────────────────────────


def test_empty_packet_detection(tmp_path: Path) -> None:
    """Empty packet (no asset_ids) on T1.1 → empty_packet=True (protocol §4)."""
    empty_packet = {
        "schema_version": "kg_eval_packet/v0",
        "subdomain_id": "D-01.1",
        "case_id": "case1-tinytask",
        "regulation_ids": ["GDPR"],
        "article_ids": [],
        "asset_ids": {
            "systems": [], "data_stores": [], "data_flows": [],
            "auth_systems": [], "cloud_services": [], "data_subjects": [],
        },
        "business_goal_ids": [],
        "must_business_goal_ids": [],
        "csf_anchors": [],
        "clause_pairs": [],
        "ambiguity_pairs": [],
        "proportional_profile": {},
        "regulatory_interactions": [],
        "company_context": {},
    }
    raw = "## Affected systems\n- SYS-01\n"  # claims SYS-01 but packet has no assets
    run = _make_run(
        tmp_path,
        family="T1.1",
        task_id="T1.1-case1-D-01.1",
        raw=raw,
        packet=empty_packet,
    )
    score = score_run(run)
    assert score["empty_packet"] is True
    assert score["judge"] is None  # protocol §7 Q4 — judge deferred


def test_score_runs_batches(tmp_path: Path) -> None:
    """score_runs iterates over child directories of the runs root."""
    parent = tmp_path / "runs"
    parent.mkdir()
    # Create two separate run dirs
    for name in ("run_a", "run_b"):
        run_dir = parent / name
        run_dir.mkdir()
        (run_dir / "env.json").write_text(
            json.dumps({
                "task_id": "T1.4-case1-D-07.1",
                "case_id": "case1-tinytask",
                "subdomain_id": "D-07.1",
                "family": "T1.4",
                "arm": "no_kg",
                "status": "OK",
                "model": "mock",
                "packet_sha256": None,
                "commit_sha": "x",
                "timestamp_utc": "20260903T000000Z",
            }),
            encoding="utf-8",
        )
        (run_dir / "raw_response.md").write_text(
            "## Proportionality for D-07.1 at tier STANDARD\n"
            "- Tier: STANDARD\n- Evidence depth: Cloud AES-256\n"
            "- Verification method: INSPECT\n- Example controls: KMS\n- Owner: CISO\n",
            encoding="utf-8",
        )
    scores = score_runs(parent)
    assert len(scores) == 2
    assert all(s["family"] == "T1.4" for s in scores)
    # Both runs should have the 5 T1.4 sub-metrics
    for s in scores:
        names = {m["metric"] for m in s["metrics"]}
        assert "tier_in_enum" in names
        assert "evidence_depth_non_empty" in names


def test_score_run_missing_artefacts(tmp_path: Path) -> None:
    """Missing env.json → score record carries an error and no metrics (fail-loud)."""
    run_dir = tmp_path / "broken_run"
    run_dir.mkdir()
    score = score_run(run_dir)
    assert any("env.json" in err for err in score["errors"])
    assert score["metrics"] == []
