"""Parser for SubDomain ``D-XX.Y.md`` files.

A SubDomain file has 3 numbered H2 sections (after the frontmatter):

  1. ``## 1. Cross-Regulation Analysis`` — CRDA pairs (free-form + tables)
  2. ``## 2. Hierarchical Security Objective`` — HL ``**Objective.**`` + per-reg sub-SOs
  3. ``## 3. Security Requirements`` — SR list (yaml bodies)

In addition to the H2 sections, the file contains H3 sub-sections like
``### D-10.1.1 — Sub-SO for GDPR`` inside the HL HSO section, and
``### 10.1.1 — <title>`` for SRs.

Output entity shape (one SubDomain = one entity):
  {
    "id": "D-10.1", "domain_id": "D-10", "title": ..., "status": ..., "chain_version": ...,
    "participating_regulations": [...],
    "hso_hl": { "objective", "considerations", "anchors", "emergent_tensions" },
    "hso_per_reg": [ { "regulation", "sub_so_id", "objective", "considerations",
                        "anchors", "inherits_from", "source_SR", "activation" } ],
    "pairs": [ { "id", "pair", "reg_a", "reg_b", "classification", "verified_relationship",
                  "layer2_flag", "scope_overlap", "scope_disjoint_test",
                  "downstream_implication", "verbatim_articles": {reg: text},
                  "participating_so_ids": {a: [so_ids...], b: [so_ids...]} } ],
    "security_requirements": [ { "sr_id", "title", "yaml_body": {...} } ],
    "csf_hint": [ "DE.CM-01", ... ]  (looked up from NIST_CSF_2.0_subcategories.md D-XX table)
  }
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..frontmatter import parse_frontmatter
from ..markdown import (
    extract_bullets,
    extract_fenced_blocks,
    numbered_section,
)

_PAIR_H4_RE = re.compile(
    r"^####\s+Pair:\s*(?P<a>[^\s↔]+)\s*↔\s*(?P<b>[^\s]+)\s*$",
    re.MULTILINE,
)
_SUB_SO_H3_RE = re.compile(
    r"^###\s+(D-\d{2}\.\d+\.\d+)\s*—\s*Sub-SO\s+for\s+([A-Za-z_0-9 ]+?)\s*$",
    re.MULTILINE,
)
_HL_H3_RE = re.compile(
    r"^###\s+(D-\d{2}\.\d+(?:\.0)?)\s*—\s*High-level SecurityObjective\s*$",
    re.MULTILINE,
)
_SR_H3_RE = re.compile(
    r"^###\s+(?P<id>\d+\.\d+(?:\.\d+)?)\s*—\s*(?P<title>.+?)\s*$",
    re.MULTILINE,
)
_OBJECTIVE_RE = re.compile(
    r"\*\*Objective\.\*\*\s+(?P<text>.+?)(?=\n\n\*\*[A-Z][A-Za-z _]*\.\*\*|\n---\n|\Z)",
    re.DOTALL,
)
_CONSIDERATIONS_RE = re.compile(
    r"\*\*Considerations\.\*\*\s*\n(?P<bullets>(?:-\s+[^\n]+\n?)+)",
)
_PARTICIPANTS_RE = re.compile(
    r"\*\*Participants\s+\(from\s+CRDA[^*]*\)\*\*:\s*(?P<regs>[^\n]+)",
)
_CLASSIFIED_RE = re.compile(
    r"Verified relationship[^:]*:\s*\*\*([^*]+)\*\*",
)
_SCOPE_DISJOINT_RE = re.compile(r"Scope-disjoint test:\s*(.+?)(?:\n|$)")
_VERBATIM_ARTICLE_RE = re.compile(
    r"\*\*(?P<reg>[A-Za-z_0-9 ]+)\s+article\s+\(verbatim[^*]*\)\*\*:\s*>\s*\"(?P<text>.+?)\"",
    re.DOTALL,
)
_DOWNSTREAM_RE = re.compile(
    r"Downstream implication[^:]*:\s*(?P<text>.+?)(?=\n---|\n####|\Z)",
    re.DOTALL,
)
_SCOPE_OVERLAP_RE = re.compile(
    r"Scope overlap:\s*\*\*(?P<v>[^*]+)\*\*",
)
_ART_RE = re.compile(r"\bArt(?:\.|icle)?\s*[\dIVX]+(?:\([^)]+\))?")
_ANNEX_RE = re.compile(r"\bAnnex\s+[IVX]+(?:\s+Part\s+[IVX]+)?(?:\s*\([^\)]+\))?")
_SECTION_RE = re.compile(r"§\s*\d+")
_CSF_RE = re.compile(r"\b([A-Z]{2}\.[A-Z]{2}-\d{2})\b")

_REG_NORMALIZE = {
    "GDPR": "GDPR",
    "NIS 2": "NIS2",
    "NIS2": "NIS2",
    "CRA": "CRA",
    "DORA": "DORA",
    "AI Act": "AI_Act",
    "AI_Act": "AI_Act",
}


def _normalize_reg(label: str) -> str:
    return _REG_NORMALIZE.get(label.strip(), label.strip())


def _extract_anchors(text: str) -> list[str]:
    anchors: set[str] = set()
    for m in _ART_RE.finditer(text):
        anchors.add(m.group(0).strip())
    for m in _ANNEX_RE.finditer(text):
        anchors.add(m.group(0).strip())
    for m in _SECTION_RE.finditer(text):
        anchors.add(m.group(0).strip())
    return sorted(anchors)


def _extract_csf(text: str) -> list[str]:
    return sorted(set(m.group(1) for m in _CSF_RE.finditer(text)))


def _extract_objective(text: str) -> str:
    m = _OBJECTIVE_RE.search(text)
    return m.group("text").strip() if m else ""


def _extract_considerations(text: str) -> list[str]:
    m = _CONSIDERATIONS_RE.search(text)
    if not m:
        return []
    return [b.strip() for b in extract_bullets(m.group("bullets")) if b.strip()]


def _parse_yaml_block(body: str) -> dict[str, Any]:
    blocks = extract_fenced_blocks(body, lang="yaml")
    if not blocks:
        return {}
    try:
        parsed = yaml.safe_load(blocks[0][1])
        return parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError:
        return {}


def _parse_pair(block: str, subdomain_id: str, a: str, b: str) -> dict[str, Any]:
    a_norm = _normalize_reg(a)
    b_norm = _normalize_reg(b)
    pair_id = f"{subdomain_id}_{a_norm}-{b_norm}".replace(" ", "")

    cls_m = _CLASSIFIED_RE.search(block)
    classification = cls_m.group(1).strip() if cls_m else None

    sdt_m = _SCOPE_DISJOINT_RE.search(block)
    scope_disjoint = sdt_m.group(1).strip() if sdt_m else None

    so_m = _SCOPE_OVERLAP_RE.search(block)
    scope_overlap = so_m.group("v").strip() if so_m else None

    down_m = _DOWNSTREAM_RE.search(block)
    downstream = down_m.group("text").strip()[:500] if down_m else None

    layer2_flag = bool(
        re.search(r"Layer\s*2\s+(?:OJ-level\s+)?(?:review|resolution)", block, re.IGNORECASE)
        or re.search(r"GENUINE\s+TENSION", block, re.IGNORECASE)
    )

    verbatim: dict[str, str] = {}
    for va_m in _VERBATIM_ARTICLE_RE.finditer(block):
        verbatim[va_m.group("reg").strip()] = va_m.group("text").strip()[:500]

    return {
        "id": pair_id,
        "subdomain_id": subdomain_id,
        "pair": f"{a_norm} ↔ {b_norm}",
        "reg_a": a_norm,
        "reg_b": b_norm,
        "classification": classification,
        "verified_relationship": classification,
        "layer2_flag": layer2_flag,
        "scope_overlap": scope_overlap,
        "scope_disjoint_test": scope_disjoint,
        "downstream_implication": downstream,
        "verbatim_articles": verbatim,
    }


def _parse_hl_hso(subdomain_id: str, body: str) -> dict[str, Any]:
    yaml_meta = _parse_yaml_block(body)
    objective = _extract_objective(body)
    considerations = _extract_considerations(body)
    full = objective + "\n" + "\n".join(considerations)
    return {
        "id": f"SO-{subdomain_id}.HL",
        "subdomain_id": subdomain_id,
        "is_high_level": True,
        "applies_to": ["ALL"],
        "derivation_source": yaml_meta.get("derivation_source"),
        "verified_relationship_basis": yaml_meta.get("verified_relationship_basis"),
        "emergent_tensions": yaml_meta.get("emergent_tensions"),
        "objective": objective,
        "considerations": considerations,
        "anchors": _extract_anchors(full),
        "csf": _extract_csf(full),
        "inherits_from": None,
        "source_SR": None,
        "activation": yaml_meta.get("applies_to"),
    }


def _parse_sub_so(sub_so_id: str, regulation: str, body: str) -> dict[str, Any]:
    yaml_meta = _parse_yaml_block(body)
    objective = _extract_objective(body)
    considerations = _extract_considerations(body)
    full = objective + "\n" + "\n".join(considerations)
    reg_norm = _normalize_reg(regulation)
    return {
        "id": f"SO-{sub_so_id}.{reg_norm}",
        "yaml_id": yaml_meta.get("id", f"SO-{sub_so_id}.{reg_norm}"),
        "regulation": reg_norm,
        "subdomain_id": sub_so_id,
        "applies_to": yaml_meta.get("applies_to", [reg_norm]),
        "inherits_from": yaml_meta.get("inherits_from"),
        "source_SR": yaml_meta.get("source_SR"),
        "activation": yaml_meta.get("activation"),
        "phase_1A_role": yaml_meta.get("phase_1A_role"),
        "verified_relationship": yaml_meta.get("verified_relationship"),
        "objective": objective,
        "considerations": considerations,
        "anchors": _extract_anchors(full),
        "csf": _extract_csf(full),
    }


def _parse_cross_reg_pairs(body: str, subdomain_id: str) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    matches = list(_PAIR_H4_RE.finditer(body))
    for i, m in enumerate(matches):
        a = m.group("a")
        b = m.group("b")
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.end():end]
        pairs.append(_parse_pair(block, subdomain_id, a, b))
    return pairs


def _parse_security_requirements(body: str, domain_id: str) -> list[dict[str, Any]]:
    srs: list[dict[str, Any]] = []
    matches = list(_SR_H3_RE.finditer(body))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.end():end]
        yaml_meta = _parse_yaml_block(block)
        sr_id = f"{domain_id}.{m.group('id').strip()}"
        srs.append(
            {
                "id": sr_id,
                "sr_short": m.group("id").strip(),
                "title": m.group("title").strip(),
                "yaml_body": yaml_meta,
                "anchors": _extract_anchors(block),
                "csf": _extract_csf(block),
            }
        )
    return srs


def parse_subdomain(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    warnings: list[str] = []

    stem = path.stem
    subdomain_id = stem
    domain_id = ".".join(stem.split(".")[:1])
    title = str(frontmatter.get("title", stem))
    status = str(frontmatter.get("status", ""))
    chain_version = str(frontmatter.get("chain_version", ""))

    # Section 1
    cross_section = numbered_section(body, 2, 1)
    cross_reg_pairs: list[dict[str, Any]] = []
    cross_reg_raw = ""
    if cross_section is None:
        warnings.append("missing '## 1. Cross-Regulation Analysis' section")
    else:
        cross_reg_raw = cross_section[1].strip()
        cross_reg_pairs = _parse_cross_reg_pairs(cross_section[1], subdomain_id)

    # Section 2
    hso_section = numbered_section(body, 2, 2)
    hso_raw = ""
    hl_hso: dict[str, Any] = {}
    sub_sos: list[dict[str, Any]] = []
    if hso_section is None:
        warnings.append("missing '## 2. Hierarchical Security Objective' section")
    else:
        hso_raw = hso_section[1].strip()
        hl_match = _HL_H3_RE.search(hso_section[1])
        if hl_match:
            hl_start = hl_match.start()
            next_sub_so = _SUB_SO_H3_RE.search(hso_section[1], hl_start + 1)
            hl_end = next_sub_so.start() if next_sub_so else len(hso_section[1])
            hl_hso = _parse_hl_hso(subdomain_id, hso_section[1][hl_start:hl_end])
        else:
            warnings.append(
                f"no '### {subdomain_id}(.0)? — High-level SecurityObjective' block found"
            )

        for m in _SUB_SO_H3_RE.finditer(hso_section[1]):
            sid_full = m.group(1)  # e.g. "D-10.1.1"
            # Normalize to 2-segment subdomain_id (D-10.1) for canonical
            # SO IDs (matches the format used in per-Article aggregated SO IDs)
            parts = sid_full.split(".")
            sid = ".".join(parts[:2])  # "D-10.1"
            reg = m.group(2)
            start = m.end()
            nxt = _SUB_SO_H3_RE.search(hso_section[1], start)
            end = nxt.start() if nxt else len(hso_section[1])
            sub_sos.append(_parse_sub_so(sid, reg, hso_section[1][start:end]))

    # Section 3
    sr_section = numbered_section(body, 2, 3)
    sr_raw = ""
    srs: list[dict[str, Any]] = []
    if sr_section is None:
        warnings.append("missing '## 3. Security Requirements' section")
    else:
        sr_raw = sr_section[1].strip()
        srs = _parse_security_requirements(sr_section[1], domain_id)

    # Participating regulations
    participants: list[str] = []
    parts_m = _PARTICIPANTS_RE.search(cross_reg_raw)
    if parts_m:
        participants = [
            _normalize_reg(r.strip().rstrip(","))
            for r in re.split(r"[,/]", parts_m.group("regs"))
            if r.strip()
        ]

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": frontmatter.get("document_id", f"AEGIS-PREPROC-SD-{subdomain_id}"),
        "id": subdomain_id,
        "domain_id": domain_id,
        "title": title,
        "status": status,
        "chain_version": chain_version,
        "participating_regulations": participants,
        "hso_hl": hl_hso,
        "hso_per_reg": sub_sos,
        "pairs": cross_reg_pairs,
        "security_requirements": srs,
        "sections": {
            "cross_reg_analysis": {"raw_md": cross_reg_raw},
            "hso": {"raw_md": hso_raw},
            "security_requirements": {"raw_md": sr_raw},
        },
        "warnings": warnings,
    }
