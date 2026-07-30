"""CORR-078 WS1 — Regression tests for the 5 preprocessor parser fixes.

Covers:
  C1 — `_SO_ID_RE` accepts mixed-case prefixes (SO-AI_Act-013)
  C2 — `parse_article_split` returns ≥1 `security_objectives` for AI_Act Art_3
  C3 — `parse_ambiguity_file` (AI_Act Art9) returns clauses with non-empty
       `instances[]`
  C4 — `parse_ambiguity_file` (GDPR Ch3 Rights) returns GDPR-RT01 with
       `instances[0].label` in the Berry set
  C5 — GDPR Ch3 clauses have populated `type` + `obligated_party`
  C6 — GDPR Ch3 RT01 title contains 'Transparency modalities', no 'Verbatim'
  C13 — REGRESSION: CRA Art13 CL14 still has `instances[0].label == 'POLY'`
  C14 — REGRESSION: DORA + NIS2 parsers still populate `instances[]`

Methodology-main must be present; tests are skipped if not.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "src"))

METHODOLOGY = REPO_ROOT.parent / "Methodology-main" / "00_METHODOLOGY"
PREPROC_OUT = REPO_ROOT / "preproc_out"

requires_methodology = pytest.mark.skipif(
    not METHODOLOGY.is_dir(),
    reason="Methodology-main not mounted; CORR-078 contract tests need real MD sources",
)


# ─── C1: regex fix ───────────────────────────────────────────────────────


@requires_methodology
def test_c1_so_id_re_accepts_mixed_case() -> None:
    """_SO_ID_RE accepts SO-AI_Act-013 etc."""
    from scripts.preprocess.parsers.aggregated.security_objectives import (
        _SO_ID_RE as SO_PAT,
    )
    assert SO_PAT.fullmatch("SO-AI_Act-013")
    assert SO_PAT.fullmatch("SO-GDPR-001")
    assert SO_PAT.fullmatch("SO-CRA-001")
    assert SO_PAT.fullmatch("SO-DORA-001")
    assert SO_PAT.fullmatch("SO-NIS2-001")
    assert SO_PAT.fullmatch("SO-a-013")  # all-lowercase alpha prefix is OK
    assert not SO_PAT.fullmatch("SO--013")  # empty prefix not OK


# ─── C2: Art_3.md parses SOs ─────────────────────────────────────────────


@requires_methodology
def test_c2_ai_act_art3_security_objectives_populated() -> None:
    """parse_article_split('Art_3.md') returns ≥1 security_objectives."""
    from scripts.preprocess.pipeline import parse_article_split

    r = parse_article_split(
        METHODOLOGY / "PREPROCESSING/Regulation/AI_Act/Articles/Art_3.md",
        "AI_Act",
    )
    assert r.get("article_ref") == "Art. 3"
    assert len(r.get("security_objectives", [])) >= 1
    assert len(r.get("security_rules", [])) >= 1
    # Inner linked_objectives survive:
    inner = r["security_rules"][0].get("linked_objectives", [])
    assert inner, "inner linked_objectives lost"


# ─── C3: AI_Act Art9 has non-empty instances[] ──────────────────────────


@requires_methodology
def test_c3_ai_act_art9_clauses_have_instances() -> None:
    """parse_ambiguity_file('01_AI_Act_Art9_RiskMgmt.md') returns ≥1 non-skeleton
    clause with `instances[0].label` populated."""
    from scripts.preprocess.parsers.entities.clause import parse_ambiguity_file

    r = parse_ambiguity_file(
        METHODOLOGY / "PREPROCESSING/Regulation/AI_Act/Ambiguity/01_AI_Act_Art9_RiskMgmt.md",
        "AI_Act",
    )
    clauses = r.get("clauses", [])
    assert len(clauses) >= 4
    non_skel = [c for c in clauses if not c.get("is_skeleton", False)]
    assert len(non_skel) >= 1
    labeled = [c for c in clauses if any(i.get("label") for i in c.get("instances", []))]
    assert len(labeled) >= 1
    # First labeled clause has at least one instance with a Berry label
    first_labeled = labeled[0]
    assert first_labeled["instances"]
    assert first_labeled["instances"][0].get("label") in {
        "VAG", "POLY", "COORD", "SCOPE-Q", "Compound", "Independent"
    }


# ─── C4/C5/C6: GDPR Ch3 Rights ───────────────────────────────────────────


@requires_methodology
def test_c4_gdpr_rt01_first_instance_label_valid() -> None:
    """GDPR-RT01 has `instances[0].label` in Berry set."""
    from scripts.preprocess.parsers.entities.clause import parse_ambiguity_file

    r = parse_ambiguity_file(
        METHODOLOGY / "PREPROCESSING/Regulation/GDPR/Ambiguity/03_GDPR_Ch3_Rights.md",
        "GDPR",
    )
    rt01 = next((c for c in r["clauses"] if c.get("id") == "GDPR-RT01"), None)
    assert rt01 is not None
    assert rt01["instances"], "GDPR-RT01 has no instances"
    label = rt01["instances"][0].get("label", "")
    assert label in {"VAG", "POLY", "COORD", "SCOPE-Q", "Compound", "Independent"}


@requires_methodology
def test_c5_gdpr_ch3_populated_metadata() -> None:
    """GDPR Ch3 clauses have populated `type`, `obligated_party`."""
    from scripts.preprocess.parsers.entities.clause import parse_ambiguity_file

    r = parse_ambiguity_file(
        METHODOLOGY / "PREPROCESSING/Regulation/GDPR/Ambiguity/03_GDPR_Ch3_Rights.md",
        "GDPR",
    )
    populated = [c for c in r["clauses"] if c.get("type") and c.get("obligated_party")]
    assert len(populated) >= 10
    rt01 = next((c for c in r["clauses"] if c.get("id") == "GDPR-RT01"), None)
    assert rt01 is not None
    assert rt01.get("type") == "data-subject-facing"
    assert rt01.get("obligated_party") == "CONTROLLER"


@requires_methodology
def test_c6_gdpr_rt01_title_uses_h4() -> None:
    """GDPR-RT01 title contains 'Transparency modalities', no 'Verbatim'."""
    from scripts.preprocess.parsers.entities.clause import parse_ambiguity_file

    r = parse_ambiguity_file(
        METHODOLOGY / "PREPROCESSING/Regulation/GDPR/Ambiguity/03_GDPR_Ch3_Rights.md",
        "GDPR",
    )
    rt01 = next((c for c in r["clauses"] if c.get("id") == "GDPR-RT01"), None)
    assert rt01 is not None
    title = rt01.get("title", "")
    assert "Transparency modalities" in title
    assert "Verbatim" not in title


# ─── C13: CRA regression ─────────────────────────────────────────────────


@requires_methodology
def test_c13_cra_cl14_polylabel_first() -> None:
    """REGRESSION: CRA-CL14 still has `instances[0].label == 'POLY'`."""
    from scripts.preprocess.parsers.entities.clause import parse_ambiguity_file

    r = parse_ambiguity_file(
        METHODOLOGY / "PREPROCESSING/Regulation/CRA/Ambiguity/03_CRA_Art13_Manufacturers.md",
        "CRA",
    )
    cl14 = next((c for c in r["clauses"] if c.get("id") == "CRA-CL14"), None)
    assert cl14 is not None
    assert cl14["instances"], "CRA-CL14 has no instances"
    assert cl14["instances"][0]["label"] == "POLY"


# ─── C14: DORA + NIS2 regression ─────────────────────────────────────────


@requires_methodology
def test_c14_dora_nis2_instances_populated() -> None:
    """REGRESSION: DORA + NIS2 parsers still populate `instances[]` for their
    clauses (≥73 DORA, ≥50 NIS2 clauses after full preprocessor regen).

    This test exercises the *parsers* directly (preproc_out will be regen'd
    by WS4); the corresponding JSON file check runs against preproc_out/.
    """
    from scripts.preprocess.parsers.entities.clause import parse_ambiguity_file

    dora_total = 0
    for f in sorted(
        (METHODOLOGY / "PREPROCESSING/Regulation/DORA/Ambiguity").glob("*.md")
    ):
        r = parse_ambiguity_file(f, "DORA")
        dora_total += sum(1 for c in r["clauses"] if c.get("instances"))
    assert dora_total >= 73, f"DORA regression: only {dora_total} clauses have instances"

    nis2_total = 0
    for f in sorted(
        (METHODOLOGY / "PREPROCESSING/Regulation/NIS2/Ambiguity").glob("*.md")
    ):
        r = parse_ambiguity_file(f, "NIS2")
        nis2_total += sum(1 for c in r["clauses"] if c.get("instances"))
    assert nis2_total >= 50, f"NIS2 regression: only {nis2_total} clauses have instances"


# ─── Inline regex unit tests (defence-in-depth) ──────────────────────────


def test_instance_re_accepts_both_formats() -> None:
    """_INSTANCE_RE matches both em-dash and slash-separated Instance labels."""
    from scripts.preprocess.parsers.entities.clause import _INSTANCE_RE

    em = _INSTANCE_RE.search("**Instance 1 — POLY — S2 — `risk management system`**")
    assert em and em.group("label") == "POLY" and em.group("sev") == "2"

    slash = _INSTANCE_RE.search(
        "**Instance 1 — VAG / S3 / six adjectives on information form**"
    )
    assert slash and slash.group("label") == "VAG" and slash.group("sev") == "3"


def test_ai_act_h3_re_accepts_canonical_ids() -> None:
    """_AI_ACT_H3_RE matches AI_Act-CLxx (not just AIA-Cxx)."""
    from scripts.preprocess.parsers.entities.clause import _AI_ACT_H3_RE

    m = _AI_ACT_H3_RE.search(
        "### 3.1 AI_Act-CL01 — Art. 9(1) Risk management system"
    )
    assert m and m.group("id") == "AI_Act-CL01"

    m = _AI_ACT_H3_RE.search("### 3.1 AIA-C01 — Art. 9(1) Risk management system")
    assert m and m.group("id") == "AIA-C01"

    m = _AI_ACT_H3_RE.search(
        "### 3.1 AIACT-CL01 — Art. 9(1) Risk management system"
    )
    assert m and m.group("id") == "AIACT-CL01"


def test_v01_h3_re_accepts_one_or_two_emdashes() -> None:
    """_V01_H3_CLAUSE_RE accepts both 1 and 2 em-dashes."""
    from scripts.preprocess.parsers.entities.clause import _V01_H3_CLAUSE_RE

    m = _V01_H3_CLAUSE_RE.search(
        "### 2.1 GDPR-C01 — Art. 5(1)(c) Data minimisation"
    )
    assert m and m.group("id") == "GDPR-C01"

    m = _V01_H3_CLAUSE_RE.search(
        "### 2.1 GDPR-C01 — Art. 5(1)(c) — Data minimisation"
    )
    assert m and m.group("id") == "GDPR-C01"
