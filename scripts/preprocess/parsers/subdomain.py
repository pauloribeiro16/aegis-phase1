"""Parser for SubDomain ``D-XX.Y.md`` files.

A SubDomain file has 3 H2 sections (after the frontmatter):

  1. ``## 1. Cross-Regulation Analysis`` — CRDA pairs (free-form + tables)
  2. ``## 2. Hierarchical Security Objective`` — HL ``**Objective.**`` + per-reg sub-SOs
  3. ``## 3. Security Requirements`` — SR list (yaml bodies)

In addition to the H2 sections, the file contains H3 sub-sections like
``### D-10.1.1 — Sub-SO for GDPR`` inside the HL HSO section.

This parser is intentionally tolerant: it never raises, it always
returns a structured dict. If a section is unparseable, the parser
records a ``warnings`` list instead of aborting — the orchestrator
escalates to a build failure if any warn is present.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .frontmatter import parse_frontmatter
from .markdown import (
    extract_bullets,
    extract_fenced_blocks,
    find_h2_sections,
    heading_with_text,
    split_by_headings,
)

# ``### D-XX.Y — Sub-SO for <REG>``
_SUB_SO_RE = re.compile(
    r"^###\s+(D-\d{2}\.\d+\.\d+)\s*—\s*Sub-SO\s+for\s+([A-Za-z_0-9 ]+?)\s*$",
    re.MULTILINE,
)
# ``### D-XX.Y — High-level SecurityObjective``
_HL_H3_RE = re.compile(
    r"^###\s+(D-\d{2}\.\d+(?:\.0)?)\s*—\s*High-level SecurityObjective\s*$", re.MULTILINE
)
# ``**Objective.**`` paragraph (until next **Header.** or end-of-block)
_OBJECTIVE_RE = re.compile(
    r"\*\*Objective\.\*\*\s+(?P<text>.+?)(?=\n\n\*\*[A-Z][A-Za-z _]*\.\*\*|\n---\n|\Z)",
    re.DOTALL,
)
_CONSIDERATIONS_RE = re.compile(
    r"\*\*Considerations\.\*\*\s*\n(?P<bullets>(?:-\s+[^\n]+\n?)+)",
)
_ART_RE = re.compile(
    r"\bArt(?:\.|icle)?\s*[\dIVX]+(?:\([^)]+\))?",
)
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
_ANNEX_RE = re.compile(r"\bAnnex\s+[IVX]+(?:\s+Part\s+[IVX]+)?(?:\s*\([^\)]+\))?")
_SECTION_RE = re.compile(r"§\s*\d+")
_CLAUSE_ID_RE = re.compile(r"\b(GDPR|NIS2|CRA|DORA|AI_Act|AIACT)-CL\d+\b")


def _parse_yaml_block(body: str) -> dict[str, Any]:
    """Parse a ```yaml ...``` block. Returns empty dict on failure."""
    blocks = extract_fenced_blocks(body, lang="yaml")
    if not blocks:
        return {}
    try:
        parsed = yaml.safe_load(blocks[0][1])
        return parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError:
        return {}


def _extract_objective(text: str) -> str:
    m = _OBJECTIVE_RE.search(text)
    if not m:
        return ""
    return m.group("text").strip()


def _extract_considerations(text: str) -> list[str]:
    m = _CONSIDERATIONS_RE.search(text)
    if not m:
        return []
    return [b.strip() for b in extract_bullets(m.group("bullets")) if b.strip()]


def _extract_anchors(text: str) -> list[str]:
    anchors: set[str] = set()
    for m in _ART_RE.finditer(text):
        anchors.add(m.group(0).strip())
    for m in _ANNEX_RE.finditer(text):
        anchors.add(m.group(0).strip())
    for m in _SECTION_RE.finditer(text):
        anchors.add(m.group(0).strip())
    return sorted(anchors)


def _parse_sub_so(sub_so_id: str, regulation: str, body: str) -> dict[str, Any]:
    """Parse one ``### D-XX.Y.N — Sub-SO for <REG>`` block."""
    yaml_meta = _parse_yaml_block(body)
    objective = _extract_objective(body)
    considerations = _extract_considerations(body)
    reg_norm = _normalize_reg(regulation)
    return {
        "sub_so_id": f"SO-{sub_so_id}.{reg_norm}",
        "yaml_id": yaml_meta.get("id", f"SO-{sub_so_id}.{reg_norm}"),
        "regulation": reg_norm,
        "regulation_label_raw": regulation,
        "subdomain_id": sub_so_id,
        "applies_to": yaml_meta.get("applies_to", [reg_norm]),
        "inherits_from": yaml_meta.get("inherits_from"),
        "source_SR": yaml_meta.get("source_SR"),
        "activation": yaml_meta.get("activation"),
        "phase_1A_role": yaml_meta.get("phase_1A_role"),
        "verified_relationship": yaml_meta.get("verified_relationship"),
        "objective": objective,
        "considerations": considerations,
        "anchors": _extract_anchors(objective + "\n" + "\n".join(considerations)),
    }


def _parse_hl_hso(subdomain_id: str, body: str) -> dict[str, Any]:
    """Parse the ``### D-XX.Y — High-level SecurityObjective`` block."""
    yaml_meta = _parse_yaml_block(body)
    objective = _extract_objective(body)
    considerations = _extract_considerations(body)
    return {
        "sub_so_id": f"SO-{subdomain_id}.HL",
        "yaml_id": yaml_meta.get("id", f"SO-{subdomain_id}.HL"),
        "is_high_level": True,
        "applies_to": ["ALL"],
        "subdomain_id": subdomain_id,
        "derivation_source": yaml_meta.get("derivation_source"),
        "verified_relationship_basis": yaml_meta.get("verified_relationship_basis"),
        "emergent_tensions": yaml_meta.get("emergent_tensions"),
        "objective": objective,
        "considerations": considerations,
        "anchors": _extract_anchors(objective + "\n" + "\n".join(considerations)),
    }


def _parse_cross_reg_pairs(body: str) -> list[dict[str, Any]]:
    """Parse the Cross-Regulation Analysis section.

    Strategy: each ``#### Pair: A ↔ B`` starts a pair block. We capture
    the text up to the next ``####`` or end-of-section. Then we extract
    a few structured fields by regex (classification, scope overlap,
    layer2 flag) and store the raw text alongside.
    """
    pairs: list[dict[str, Any]] = []
    pair_pat = re.compile(
        r"^####\s+Pair:\s*(?P<a>[^\s↔]+)\s*↔\s*(?P<b>[^\s]+)\s*$",
        re.MULTILINE,
    )
    matches = list(pair_pat.finditer(body))
    for i, m in enumerate(matches):
        a = m.group("a").strip()
        b = m.group("b").strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.end():end]

        # Classification: "Verified relationship: **SAME — COMPLEMENTARY**"
        cls_m = re.search(
            r"Verified relationship[^:]*:\s*\*\*([^*]+)\*\*", block
        )
        classification = cls_m.group(1).strip() if cls_m else None

        # Layer 2 flag (any "Layer 2" or "GENUINE TENSION" mention in block)
        layer2_flag = bool(
            re.search(r"Layer\s*2\s+(?:OJ-level\s+)?(?:review|resolution)", block, re.IGNORECASE)
            or re.search(r"GENUINE\s+TENSION", block, re.IGNORECASE)
        )

        # Scope-disjoint test
        sdt_m = re.search(r"Scope-disjoint test:\s*(.+?)(?:\n|$)", block)
        scope_disjoint = sdt_m.group(1).strip() if sdt_m else None

        # Verbatim article quotes
        verbatim: dict[str, str] = {}
        for va_m in re.finditer(
            r"\*\*(?P<reg>[A-Za-z_0-9 ]+)\s+article\s+\(verbatim[^*]*\)\*\*:\s*>\s*\"(?P<text>.+?)\"",
            block,
            re.DOTALL,
        ):
            verbatim[va_m.group("reg").strip()] = va_m.group("text").strip()[:500]

        pairs.append(
            {
                "pair": f"{a} ↔ {b}",
                "reg_a": a,
                "reg_b": b,
                "classification": classification,
                "layer2_flag": layer2_flag,
                "scope_disjoint_test": scope_disjoint,
                "verbatim_articles": verbatim,
                "raw_text": block.strip()[:2000],
            }
        )
    return pairs


def _parse_security_requirements(body: str, domain_id: str) -> list[dict[str, Any]]:
    """Parse the Security Requirements section into per-SR dicts.

    Each SR lives under a ``### NN.NN.N — <title>`` heading followed by
    a ``\\`\\`\\`yaml\\`\\`\\` block with the SR metadata. The numeric
    prefix is the sub-domain relative index (e.g. ``10.1.1`` for
    D-10.1) and is prefixed with the domain id to form the canonical
    sr_id (e.g. ``D-10.1.1``).
    """
    srs: list[dict[str, Any]] = []
    sr_pat = re.compile(
        r"^###\s+(?P<id>\d+\.\d+(?:\.\d+)?)\s*—\s*(?P<title>.+?)\s*$", re.MULTILINE
    )
    matches = list(sr_pat.finditer(body))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.end():end]
        yaml_meta = _parse_yaml_block(block)
        srs.append(
            {
                "sr_id": f"{domain_id}.{m.group('id').strip()}",
                "sr_short": m.group("id").strip(),
                "title": m.group("title").strip(),
                "yaml_body": yaml_meta,
                "anchors": _extract_anchors(block),
            }
        )
    return srs


def _numbered_section(body: str, level: int, section_num: int) -> tuple[str, str] | None:
    """Return the H{level} body of the numbered section ``## N. <title>``.

    The body extends until the next H{level} numbered ``> N`` (or EOF).
    Sub-sections with H{level} headings that do NOT start with a number
    (e.g. "## Participating regulations") are included — they are
    LOGICALLY part of section N.
    """
    pat = re.compile(
        r"^" + "#" * level + r"\s+(?P<num>\d+)\.\s+(?P<title>.+?)\s*$",
        re.MULTILINE,
    )
    matches = list(pat.finditer(body))
    start_idx = None
    for i, m in enumerate(matches):
        if int(m.group("num")) == section_num:
            start_idx = i
            break
    if start_idx is None:
        return None
    start = matches[start_idx].start()
    end = len(body)
    for j in range(start_idx + 1, len(matches)):
        if int(matches[j].group("num")) > section_num:
            end = matches[j].start()
            break
    return matches[start_idx].group("title"), body[start:end]


def parse_subdomain(path: Path) -> dict[str, Any]:
    """Parse a SubDomain ``D-XX.Y.md`` into a JSON-ready dict."""
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    warnings: list[str] = []

    # Extract domain/subdomain IDs from filename (e.g. D-10.1.md)
    stem = path.stem
    subdomain_id = stem
    domain_id = ".".join(stem.split(".")[:1])  # "D-10" from "D-10.1"

    # Title from frontmatter (or fall back to first H1)
    title = str(frontmatter.get("title", stem))
    status = str(frontmatter.get("status", ""))
    chain_version = str(frontmatter.get("chain_version", ""))

    # Section 1: Cross-Regulation Analysis
    cross_section = _numbered_section(body, 2, 1)
    if cross_section is None:
        warnings.append("missing '## 1. Cross-Regulation Analysis' section")
        cross_reg_pairs: list[dict[str, Any]] = []
        cross_reg_raw = ""
    else:
        cross_reg_pairs = _parse_cross_reg_pairs(cross_section[1])
        cross_reg_raw = cross_section[1].strip()

    # Section 2: Hierarchical Security Objective (contains HL + per-reg sub-SOs)
    hso_section = _numbered_section(body, 2, 2)
    if hso_section is None:
        warnings.append("missing '## 2. Hierarchical Security Objective' section")
        hl_hso: dict[str, Any] = {}
        sub_sos: list[dict[str, Any]] = []
        hso_raw = ""
    else:
        hso_raw = hso_section[1].strip()
        # HL block: ### D-XX.Y(.0)? — High-level SecurityObjective
        hl_match = _HL_H3_RE.search(hso_section[1])
        if hl_match:
            hl_start = hl_match.start()
            # HL ends at the first "### D-XX.Y.N — Sub-SO for <REG>" (the
            # first per-reg sub-SO), NOT at any random H3 inside the HL
            # (e.g. "### Sub-domain scope structure" which is metadata
            # belonging to the HL block).
            next_sub_so = _SUB_SO_RE.search(hso_section[1], hl_start + 1)
            hl_end = next_sub_so.start() if next_sub_so else len(hso_section[1])
            hl_hso = _parse_hl_hso(subdomain_id, hso_section[1][hl_start:hl_end])
        else:
            warnings.append(
                f"no '### {subdomain_id}(.0)? — High-level SecurityObjective' block found"
            )
            hl_hso = {}

        sub_sos = []
        for m in _SUB_SO_RE.finditer(hso_section[1]):
            sid = m.group(1)
            reg = m.group(2)
            start = m.end()
            nxt = _SUB_SO_RE.search(hso_section[1], start)
            nxt_h3 = re.search(
                r"^###\s+D-\d{2}\.\d+(\.\d+)?\s*—", hso_section[1][start:], re.MULTILINE
            )
            candidates = [c for c in (nxt.start() if nxt else None,
                                      (start + nxt_h3.start()) if nxt_h3 else None) if c is not None]
            end = min(candidates) if candidates else len(hso_section[1])
            sub_sos.append(_parse_sub_so(sid, reg, hso_section[1][start:end]))

    # Section 3: Security Requirements
    sr_section = _numbered_section(body, 2, 3)
    if sr_section is None:
        warnings.append("missing '## 3. Security Requirements' section")
        srs: list[dict[str, Any]] = []
        sr_raw = ""
    else:
        srs = _parse_security_requirements(sr_section[1], domain_id)
        sr_raw = sr_section[1].strip()

    # Participating regulations (from "Participants (from CRDA):" in section 1)
    participants_m = re.search(
        r"\*\*Participants\s+\(from\s+CRDA[^*]*\)\*\*:\s*(?P<regs>[^\n]+)",
        cross_reg_raw,
    )
    participating_regulations: list[str] = []
    if participants_m:
        participating_regulations = [
            r.strip().rstrip(",")
            for r in re.split(r"[,/]", participants_m.group("regs"))
            if r.strip()
        ]

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": frontmatter.get("document_id", f"AEGIS-PREPROC-SD-{subdomain_id}"),
        "domain_id": domain_id,
        "subdomain_id": subdomain_id,
        "title": title,
        "status": status,
        "chain_version": chain_version,
        "frontmatter": frontmatter,
        "participating_regulations": participating_regulations,
        "sections": {
            "cross_reg_analysis": {
                "raw_md": cross_reg_raw,
                "pairs": cross_reg_pairs,
            },
            "hso": {
                "raw_md": hso_raw,
                "hl": hl_hso,
                "sub_sos": sub_sos,
            },
            "security_requirements": {
                "raw_md": sr_raw,
                "srs": srs,
            },
        },
        "warnings": warnings,
    }
