"""Build script for docs/visualization/regulation_chain.html.

Reads the case-INDEPENDENT preproc_out entity shards and emits a single
self-contained HTML with embedded JSON data and a 5-section, 3-column UI
that surfaces every field of every entity (Regulation → Article → Clause → SO → SR).

Sources:
  - preproc_out/regulation/<REG>/_root/00_README.json + aggregated/*.json (5 regs)
  - preproc_out/entities/articles/<REG>_Art_ <N>.json (140 articles; SPACE before N)
  - preproc_out/entities/clauses/_root/<REG>/<REG>-CLNN.json (498 clauses; some skeleton)
  - preproc_out/entities/sos/D-XX/<SO-ID>.json (328 SOs; 3 formats: canonical/per-reg/HL)
  - preproc_out/entities/srs/D-XX/<SR-ID>.json (282 SRs)

Run: python3 docs/visualization/build_regulation_chain.py
"""

import glob
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PREPROC_OUT = ROOT / "preproc_out"
OUT_HTML = ROOT / "docs/visualization/regulation_chain.html"

REGULATIONS = ["AI_Act", "CRA", "DORA", "GDPR", "NIS2"]

# NIST CSF 2.0 official colours (per nist.gov/cyberframework/faqs "Six Functions Graphic")
CSF_COLOR = {
    "GV": "#f9f49d",  # Govern — pale yellow
    "ID": "#4bb2e0",  # Identify — sky blue
    "PR": "#9292ea",  # Protect — lavender
    "DE": "#fab746",  # Detect — orange
    "RS": "#f97367",  # Respond — coral
    "RC": "#7df49f",  # Recover — mint green
}

# Regulation colours
REG_COLORS = {
    "GDPR": "#FF6B6B",
    "CRA": "#4ECDC4",
    "NIS2": "#FFD93D",
    "DORA": "#6C5CE7",
    "AI_Act": "#A8E6CF",
}

REG_NAMES = {
    "AI_Act": "AI Act",
    "GDPR": "GDPR",
    "CRA": "CRA",
    "NIS2": "NIS 2",
    "DORA": "DORA",
}

# Article number sort key helper
def _article_sort_key(article_ref):
    """Extract numeric portion from 'Art. 9' / 'Art. 9(1)' for natural sort."""
    m = re.search(r"(\d+)", article_ref or "")
    return (int(m.group(1)) if m else 9999, article_ref or "")


def _read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [warn] skip {path}: {e}")
        return None


def _read_text(path: Path) -> str:
    """Read text file; return empty string on failure (CORR-079 graceful fallback)."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


# CORR-079: methodology MD directory (resolve symlink by going through ROOT).
METHODOLOGY_DIR = ROOT / "Methodology-main" / "00_METHODOLOGY" / "PREPROCESSING" / "Regulation"


def load_regulations():
    """Build per-regulation summary + raw MD from Methodology-main/README + 01/02/03/04.

    CORR-079 (WS1): extend to embed the 5 top-level MD files so the Markdown
    tab surfaces every bit of methodology context per regulation.

    CORR-079 (size opt): aggregated SOs/SRs dropped — full data still in
    top-level ``sos[]`` / ``srs[]``; per-regulation stats retained.
    """
    regs = []
    for reg in REGULATIONS:
        reg_dir = PREPROC_OUT / "regulation" / reg
        readme = _read_json(reg_dir / "_root" / "00_README.json") or {}
        sobj = _read_json(reg_dir / "aggregated" / "01_SecurityObjectives.json") or {}
        srobj = _read_json(reg_dir / "aggregated" / "02_SecurityRules_NIST.json") or {}

        # Article count for this reg
        article_count = sum(
            1
            for fp in glob.glob(str(PREPROC_OUT / "entities" / "articles" / f"{reg}_Art_ *.json"))
        )
        # Clause count for this reg
        clause_count = sum(
            1 for fp in glob.glob(str(PREPROC_OUT / "entities" / "clauses" / "_root" / reg / "*.json"))
        )

        fm = readme.get("frontmatter", {}) or {}

        # CORR-079 (WS1): read top-level README (used as Markdown tab content
        # for the regulation detail panel — see showDetail fallback chain).
        method_reg_dir = METHODOLOGY_DIR / reg
        raw_readme = _read_text(method_reg_dir / "00_README.md")

        # CORR-079 (size opt): the other 4 methodology MDs are ONLY referenced
        # by the Context tab to show "X chars" — record their lengths instead of
        # embedding the full content (saves ~1.7 MB across all regulations).
        raw_01_size = len(_read_text(method_reg_dir / "01_SecurityObjectives.md"))
        raw_02_size = len(_read_text(method_reg_dir / "02_SecurityRules_NIST.md"))
        raw_validation_size = len(_read_text(method_reg_dir / "03_validation_report.md"))
        raw_audit_size = len(_read_text(method_reg_dir / "04_deduction_audit.md"))

        # CORR-079 (size opt): aggregated SOs/SRs dropped from per-regulation
        # payload — full dicts still live at top-level ``sos[]`` / ``srs[]``
        # (filtered by regulation when needed). Per-regulation stats are kept.
        sobj_count = sobj.get("count", 0)
        srobj_count = srobj.get("count", 0)

        regs.append({
            "id": reg,
            "name": reg,
            "displayName": REG_NAMES.get(reg, reg),
            "color": REG_COLORS.get(reg, "#888"),
            "title": fm.get("title", readme.get("title", reg)),
            "docId": readme.get("doc_id"),
            "version": fm.get("version"),
            "status": fm.get("status") or readme.get("status"),
            "created": fm.get("created"),
            "updated": fm.get("updated"),
            "author": fm.get("author"),
            "frontmatter": fm,
            "rawReadme": raw_readme,
            "raw01Size": raw_01_size,
            "raw02Size": raw_02_size,
            "rawValidationSize": raw_validation_size,
            "rawAuditSize": raw_audit_size,
            "stats": {
                "articles": article_count,
                "clauses": clause_count,
                "sos": sobj_count,
                "srs": srobj_count,
            },
        })
    return regs


def _article_md_filename(article_id: str, article_ref: str) -> str:
    """Map article_id / article_ref to a Methodology-main Articles/Art_NN.md path.

    Article IDs follow the pattern ``<REG>_Art. <N>`` (e.g. ``AI_Act_Art. 9``),
    while the methodology filename uses underscore (``AI_Act`` + ``Art_ 9`` →
    ``Art_9.md``). Try a few common shapes.
    """
    ref = article_ref or article_id or ""
    # Strip non-digits at the front, keep the leading digits.
    m = re.search(r"(\d+)", ref)
    if not m:
        return ""
    return f"Art_{m.group(1)}.md"


def _read_article_md(regulation: str, article_id: str, article_ref: str) -> str:
    """Read the Articles/Art_NN.md content for an article.

    Tries ``Art_<N>.md``; falls back to empty string on any I/O error so the
    contract's graceful-fallback expectation (CORR-079 NFR-5) is preserved.
    """
    filename = _article_md_filename(article_id, article_ref)
    if not filename:
        return ""
    path = METHODOLOGY_DIR / regulation / "Articles" / filename
    return _read_text(path)


_CLAUSE_SECTION_PATTERN = re.compile(
    r"^(#{1,5})\s+(?P<header>.*?)(?P<clause_id>(?:AI_Act|GDPR|CRA|DORA|NIS2)-CL\d{2,3}).*$",
    re.MULTILINE,
)


def _read_clause_md(regulation: str, clause_id: str) -> str:
    """Find the Ambiguity MD section whose header contains ``clause_id`` and
    return the slice from that heading to the next heading of equal/higher
    level. Returns empty string if not found.

    CORR-079 perf fix: split on H4 boundaries (linear time, no backtracking).
    """
    if not clause_id:
        return ""
    ambig_dir = METHODOLOGY_DIR / regulation / "Ambiguity"
    if not ambig_dir.exists():
        return ""
    for md_path in sorted(ambig_dir.glob("*.md")):
        text = _read_text(md_path)
        if not text or clause_id not in text:
            continue
        # Try the level-3 consolidated form first.
        for m in _CLAUSE_SECTION_PATTERN.finditer(text):
            if m.group("clause_id") == clause_id:
                start = m.start()
                level = len(m.group(1))
                end = len(text)
                for m2 in re.finditer(r"^#{1,5}\s+", text[m.end():], re.MULTILINE):
                    if m2.group(0).count("#") <= level:
                        end = m.end() + m2.start()
                        break
                section = text[start:end].strip()
                if section:
                    return section
        # Per-chapter form: split on H4 boundaries, then search each section.
        # Linear in number of H4s — no catastrophic backtracking.
        h4_positions = [m.start() for m in re.finditer(r"^####\s+", text, re.MULTILINE)]
        h4_positions.append(len(text))
        marker = f"**Clause: {clause_id}**"
        for i in range(len(h4_positions) - 1):
            section = text[h4_positions[i]:h4_positions[i + 1]]
            if marker in section:
                header_end = section.find("\n") + 1
                header = section[:header_end]
                body = section[header_end:]
                if marker in body:
                    return (header + body[: body.index(marker) + len(marker) + 200]).strip()
    return ""


def _read_so_row(regulation: str, so_id: str) -> str:
    """Extract the markdown row + 2 lines context for an SO from
    ``01_SecurityObjectives.md`` (regulation-level). Returns empty string.
    """
    if not so_id:
        return ""
    md_path = METHODOLOGY_DIR / regulation / "01_SecurityObjectives.md"
    text = _read_text(md_path)
    if not text:
        return ""
    # Find line containing the SO ID.
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if so_id in ln:
            lo = max(0, i - 2)
            hi = min(len(lines), i + 3)
            return "\n".join(lines[lo:hi])
    return ""


def load_articles():
    """Read all 140 article shards (wildcard matches the SPACE before number).

    The full security_rules array is held in-memory for the detail panel but
    NOT embedded in the JSON (it duplicates the §5 SR data). We compute a
    derived compact view that lists only sr_id + title.

    CORR-078 (C10): ``securityObjectives`` is the union of the article's
    top-level ``security_objectives[]`` and the inner
    ``security_rules[].linked_objectives[]`` (the latter was previously
    ignored, leading to ``#SOs = 0`` for every AI_Act article).

    CORR-078 (C9): articles with ``source_role == "out_of_scope"`` are
    filtered out of §2 (the field is still present in the per-article
    payload for downstream consumers).

    CORR-079 (WS1): additionally preserve ``source`` (path),
    ``inScopeArticlesReferenced``, ``rawMd`` (Articles/Art_NN.md content).
    CORR-079 (size opt): ``securityRules`` / ``securityObjectivesFull`` were
    dropped — full data still lives in top-level ``sos[]`` / ``srs[]`` and is
    referenced by ``securityRuleIds`` / ``securityObjectives``.
    """
    articles = []
    files = sorted(glob.glob(str(PREPROC_OUT / "entities" / "articles" / "*_Art_ *.json")))
    for fp in files:
        d = _read_json(Path(fp))
        if not d:
            continue
        arts = d.get("security_rules", []) or []
        # CORR-078 (C10): union top-level + inner linked_objectives.
        # Top-level may be list[dict] (per-article shard from
        # pipeline.parse_article_split) or list[str] (aggregated shard).
        # Normalise to list[str] of SO IDs.
        def _so_id(s: Any) -> str:
            if isinstance(s, dict):
                return str(s.get("so_id") or s.get("id") or "")
            return str(s)

        top_sos = [_so_id(s) for s in (d.get("security_objectives") or [])]
        inner_sos: list[str] = []
        for sr in arts:
            inner_sos.extend(sr.get("linked_objectives") or [])
        all_sos = sorted({s for s in (top_sos + inner_sos) if s})

        # CORR-079 (size opt): full SR/SO dicts dropped — IDs only via
        # ``securityRuleIds`` / ``securityObjectives``. Full data still available
        # at top-level ``sos[]`` / ``srs[]`` and is referenced by ID from the
        # detail panel.

        # CORR-079 (WS1): embed the source MD for this article
        reg = d.get("regulation") or ""
        raw_md = _read_article_md(reg, d.get("id") or "", d.get("article_ref") or "")

        articles.append({
            "id": d.get("id"),
            "regulation": d.get("regulation"),
            "articleRef": d.get("article_ref"),
            "title": d.get("title"),
            "status": d.get("status"),
            "schemaVersion": d.get("schema_version"),
            "docId": d.get("doc_id"),
            "frontmatter": d.get("frontmatter", {}),
            "securityObjectives": all_sos,
            "securityRuleCount": len(arts),
            "securityRuleIds": [sr.get("sr_id") for sr in arts],
            "source": d.get("source"),
            "inScopeArticlesReferenced": d.get("in_scope_articles_referenced", []),
            "rawMd": raw_md,
            "filename": Path(fp).name,
            # CORR-078 (C9): preserve source_role so detail panel shows it
            "sourceRole": d.get("source_role"),
        })
    # CORR-078 (C9): filter out_of_scope articles from §2
    articles = [a for a in articles if a.get("sourceRole") != "out_of_scope"]
    # Sort by regulation then article number
    articles.sort(key=lambda a: (a.get("regulation") or "", _article_sort_key(a.get("articleRef") or "")))
    return articles


def load_clauses():
    """Read all 498 clauses, including skeleton (marked with is_skeleton).

    CORR-079 (WS1): additionally preserve ``obligated_party`` / ``obligation_type``
    (which CORR-078 populated in preproc_out but the prior loader dropped) and
    embed the per-clause block from the Ambiguity MDs as ``rawMd``.
    """
    clauses = []
    files = sorted(glob.glob(str(PREPROC_OUT / "entities" / "clauses" / "_root" / "*" / "*.json")))
    for fp in files:
        d = _read_json(Path(fp))
        if not d:
            continue
        # Determine severity from instances (most-severe wins)
        severities = [i.get("severity") for i in d.get("instances", []) if i.get("severity")]
        severity = max(severities, key=lambda s: int(s[1])) if severities else None
        # Most-prominent Berry type from types_found (VAG/POLY/COORD/SCOPE-Q priority)
        types_found = d.get("types_found", []) or []
        berry_priority = ["VAG", "POLY", "COORD", "SCOPE-Q"]
        primary_type = None
        for tp in berry_priority:
            if tp in types_found:
                primary_type = tp
                break
        if not primary_type and d.get("type") in berry_priority:
            primary_type = d["type"]

        # CORR-079 (WS1): per-clause MD block from Ambiguity/*.md
        reg = d.get("regulation") or ""
        cid = d.get("id") or ""
        raw_md = _read_clause_md(reg, cid)

        clauses.append({
            "id": d.get("id"),
            "regulation": d.get("regulation"),
            "sectionRef": d.get("section_ref"),
            "title": d.get("title"),
            "type": primary_type,
            "typesFound": types_found,
            "subDomain": d.get("sub_domain"),
            "sourceLocus": d.get("source_locus"),
            "obligatedParty": d.get("obligated_party"),
            "obligationType": d.get("obligation_type"),
            "instances": d.get("instances", []),
            "intraSectionNotes": d.get("intra_section_notes", []),
            "berryAnchors": d.get("berry_anchors", []),
            "isSkeleton": d.get("is_skeleton", False),
            "severity": severity,
            "rawMd": raw_md,
            "filename": Path(fp).name,
        })
    # Sort by regulation, then section ref
    clauses.sort(key=lambda c: (c.get("regulation") or "", c.get("sectionRef") or "", c.get("id") or ""))
    return clauses


def _so_type(so_id: str) -> str:
    """Classify SO into 3 types: HL, per-reg, canonical."""
    if not so_id:
        return "unknown"
    if so_id.endswith(".HL"):
        return "HL"
    # Per-reg or canonical?
    # Canonical: SO-{REG}-{NNN} where REG is uppercase alpha (no dots)
    if re.match(r"^SO-[A-Z][A-Z0-9_]*-\d+$", so_id):
        return "canonical"
    # Everything else (per-reg subdomain, etc.)
    return "per-reg"


def load_sos():
    """Read all 328 SO shards (3 formats: canonical, per-reg subdomain, HL).

    CORR-079 (WS1): additionally embed ``rawRow`` extracted from the
    regulation's ``01_SecurityObjectives.md`` (the SO's table row + 2 lines
    context). Used by the Markdown tab.
    """
    sos = []
    files = sorted(glob.glob(str(PREPROC_OUT / "entities" / "sos" / "*" / "*.json")))
    for fp in files:
        d = _read_json(Path(fp))
        if not d:
            continue
        sid = d.get("id") or Path(fp).stem
        # Skip _id (always duplicates id)
        # Derive regulation
        reg = d.get("regulation")
        if not reg:
            if sid.endswith(".HL"):
                reg = "HL"
            else:
                m = re.match(r"^SO-([A-Za-z_]+)", sid)
                reg = m.group(1) if m else "UNKNOWN"
        # Determine subdomain
        subdomain = d.get("subdomain_id") or d.get("source_subdomain")
        if not subdomain:
            # Try from folder: D-01/... → D-01
            parent = Path(fp).parent.name
            if parent.startswith("D-"):
                subdomain = parent
        # First D-XX reference from id
        if not subdomain or subdomain.startswith("D-"):
            m = re.search(r"(D-\d+\.\d+)", sid)
            if m:
                subdomain = m.group(1)
        # CORR-079 (WS1): raw row from the regulation-level 01_SecurityObjectives.md
        raw_row = _read_so_row(reg, sid)
        sos.append({
            "id": sid,
            "regulation": reg,
            "soType": _so_type(sid),
            "description": d.get("description") or d.get("objective"),
            "objective": d.get("objective"),
            "sourceClauses": d.get("source_clauses", []),
            "subDomains": d.get("sub_domains", []),
            "subdomainId": d.get("subdomain_id"),
            "sourceSubdomain": d.get("source_subdomain"),
            "isCrossRef": d.get("is_cross_ref", False),
            "isHighLevel": d.get("is_high_level", False),
            "appliesTo": d.get("applies_to", []),
            "derivationSource": d.get("derivation_source"),
            "verifiedRelationshipBasis": d.get("verified_relationship_basis"),
            "emergentTensions": d.get("emergent_tensions"),
            "considerations": d.get("considerations", []),
            "anchors": d.get("anchors", []),
            "csf": d.get("csf", []),
            "inheritsFrom": d.get("inherits_from"),
            "sourceSR": d.get("source_SR"),
            "activation": d.get("activation"),
            "phase1ARole": d.get("phase_1A_role"),
            "yamlId": d.get("yaml_id"),
            "verifiedRelationship": d.get("verified_relationship"),
            "rawRow": raw_row,
            "filename": Path(fp).name,
        })
    # Sort by so_type, then regulation, then id
    sos.sort(key=lambda s: (s["soType"], s.get("regulation") or "", s.get("id") or ""))
    return sos


def load_srs():
    """Read all 282 SR shards. Keep original snake_case keys per spec."""
    srs = []
    files = sorted(glob.glob(str(PREPROC_OUT / "entities" / "srs" / "*" / "*.json")))
    for fp in files:
        d = _read_json(Path(fp))
        if not d:
            continue
        # Pass-through with original snake_case keys per spec requirement
        srs.append({
            "id": d.get("id"),
            "title": d.get("title"),
            "heading_under": d.get("heading_under"),
            "source_clauses": d.get("source_clauses", []),
            "linked_objectives": d.get("linked_objectives", []),
            "sub_domain": d.get("sub_domain", []),
            "nist_csf_mapping": d.get("nist_csf_mapping", []),
            "applies_to_role": d.get("applies_to_role", []),
            "obligation_type": d.get("obligation_type", []),
            "regulatory_rationale": d.get("regulatory_rationale"),
            "security_rationale": d.get("security_rationale"),
            "ambiguity_notes": d.get("ambiguity_notes"),
            "raw_md": d.get("raw_md"),
            "regulation": d.get("regulation"),
            "filename": Path(fp).name,
        })
    # Sort by regulation then id
    srs.sort(key=lambda s: (s.get("regulation") or "", s.get("id") or ""))
    return srs


def load_security_requirements() -> list[dict]:
    """Load hierarchical security requirements (HL + sub-reqs) from SubDomains MDs.

    CORR-093: source of truth is SubDomains MDs.
    Each MD has:
    - `## High-level requirement` section (1 HL req)
    - `## Sub-requirements` section (2-5 sub-reqs)
    Returns flat list with parent_id field for hierarchy.
    """
    SUBDOMAINS_DIR = METHODOLOGY_DIR.parent / "SubDomains"
    requirements: list[dict] = []
    if not SUBDOMAINS_DIR.exists():
        return requirements
    for sub_dir in sorted(SUBDOMAINS_DIR.iterdir()):
        if not sub_dir.is_dir():
            continue
        for md_file in sorted(sub_dir.glob("D-*.md")):
            if md_file.stem == "index":
                continue
            md_text = _read_text(md_file)
            if not md_text:
                continue
            md_clean = _strip_frontmatter(md_text)
            ss_id = md_file.stem  # e.g., "D-01.1"
            # Find HL requirement section
            hl_m = re.search(
                r"^##\s+High-level requirement\s*\n(.*?)(?=^##\s+|\Z)",
                md_clean, re.MULTILINE | re.DOTALL
            )
            hl_req_id = None
            hl_yaml = ""
            if hl_m:
                hl_yaml_m = re.search(r"```yaml\n(.*?)\n```", hl_m.group(1), re.DOTALL)
                if hl_yaml_m:
                    hl_yaml = hl_yaml_m.group(1)
                    req_id_m = re.search(r"req_id:\s*(\S+)", hl_yaml)
                    if req_id_m:
                        hl_req_id = req_id_m.group(1)
                if hl_req_id:
                    requirements.append({
                        "id": f"{ss_id}/{hl_req_id}",
                        "req_id": hl_req_id,
                        "subdomain": ss_id,
                        "level": "HL",
                        "parent_id": None,
                        "yaml": hl_yaml,
                        "raw_md": hl_m.group(0).strip(),
                    })
            # Find Sub-requirements section
            sub_m = re.search(
                r"^##\s+Sub-requirements\s*\n(.*?)(?=^##\s+|\Z)",
                md_clean, re.MULTILINE | re.DOTALL
            )
            if sub_m and hl_req_id:
                for sub_section in re.split(
                    r"(?=^###\s+[0-9]+\.[0-9]+\.[0-9]+\s*[—\-–])",
                    sub_m.group(1), flags=re.MULTILINE
                ):
                    sub_heading_m = re.match(
                        r"^###\s+([0-9]+\.[0-9]+\.[0-9]+)\s*[—\-–]\s*(.+?)\s*$",
                        sub_section, re.MULTILINE
                    )
                    if not sub_heading_m:
                        continue
                    sub_req_id = sub_heading_m.group(1)
                    sub_yaml_m = re.search(r"```yaml\n(.*?)\n```", sub_section, re.DOTALL)
                    if not sub_yaml_m:
                        continue
                    sub_yaml = sub_yaml_m.group(1)
                    # Extract title from yaml
                    title_m = re.search(r"title:\s*\"?([^\"\n]+)\"?", sub_yaml)
                    sub_title = title_m.group(1).strip() if title_m else sub_heading_m.group(2)
                    requirements.append({
                        "id": f"{ss_id}/{sub_req_id}",
                        "req_id": sub_req_id,
                        "subdomain": ss_id,
                        "level": "sub",
                        "parent_id": hl_req_id,
                        "title": sub_title,
                        "yaml": sub_yaml,
                        "raw_md": sub_section.strip(),
                    })
    print(f"load_security_requirements: {len(requirements)} requirements (HL + sub)", flush=True)
    return requirements


def _normalize_reg_label(raw: str) -> str:
    """Normalise a "Sub-SO for <X>" label to a canonical regulation ID.

    SubDomains MDs use human-readable names ("AI Act", "NIS 2", "CRA"). The
    rest of the pipeline (REG_COLORS, articles, clauses, ...) uses canonical
    IDs ("AI_Act", "NIS2", "CRA"). Trailing annotations like "(CORR-030
    propagated phantom)" or "(partial)" are stripped.

    Returns the canonical ID when matched, otherwise the cleaned original.
    """
    s = raw.strip()
    # Strip trailing parenthesised annotations.
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
    aliases = {
        "AI Act": "AI_Act",
        "GDPR": "GDPR",
        "NIS 2": "NIS2",
        "NIS2": "NIS2",
        "CRA": "CRA",
        "DORA": "DORA",
    }
    return aliases.get(s, s.replace(" ", ""))


def load_all_objectives() -> list[dict]:
    """Load ALL objectives (HL + per-reg sub-SOs) from SubDomains MDs.

    CORR-091: SubDomains MDs are the source of truth for objectives.
    Each MD has:
    - ``### D-XX.Y.0 — High-level SecurityObjective`` (HL)
    - ``### D-XX.Y.N — Sub-SO for <REG>`` (N=1..k, one per regulation)

    Returns list of objective dicts (skips sub-subdomains without HSO).
    """
    SUBDOMAINS_DIR = METHODOLOGY_DIR.parent / "SubDomains"
    objectives: list[dict] = []
    if not SUBDOMAINS_DIR.exists():
        print("load_all_objectives: SubDomains dir not found", flush=True)
        return objectives
    for sub_dir in sorted(SUBDOMAINS_DIR.iterdir()):
        if not sub_dir.is_dir():
            continue
        for md_file in sorted(sub_dir.glob("D-*.md")):
            if md_file.stem == "index":
                continue
            md_text = _read_text(md_file)
            if not md_text:
                continue
            md_clean = _strip_frontmatter(md_text)
            ss_id = md_file.stem  # e.g., "D-01.1"
            # CORR-098: per-file counter to disambiguate phantoms that share
            # both inherits_from and sectionId (rare; e.g. D-04.3.11 NIS2).
            phantom_seen: dict[tuple[str, str], int] = {}
            pattern = re.compile(
                r"^###\s+(D-\d+\.\d+\.\d+)\s*[—\-–]\s*(High-level SecurityObjective|Sub-SO for\s+(.+?))\s*$",
                re.MULTILINE,
            )
            for m in pattern.finditer(md_clean):
                section_id = m.group(1)
                section_title = m.group(2)
                is_hl = "High-level" in section_title
                # CORR-098: detect phantom (CORR-030 propagated) blocks BEFORE
                # _normalize_reg_label strips the annotation, so we can disambiguate
                # their id and avoid collisions with the legit sub-SO.
                is_phantom = "phantom" in section_title.lower()
                if is_hl:
                    reg = "HL"
                else:
                    reg = _normalize_reg_label(m.group(3))
                start = m.start()
                rest = md_clean[m.end():]
                end_m = re.search(r"^###\s+", rest, re.MULTILINE)
                end = m.end() + end_m.start() if end_m else len(md_clean)
                section_md = md_clean[start:end]
                yaml_m = re.search(r"```(?:yaml)?\n(.*?)\n```", section_md, re.DOTALL)
                yaml_dict: dict = {}
                yaml_raw = yaml_m.group(1) if yaml_m else ""
                for line in yaml_raw.split("\n"):
                    if ":" in line and not line.strip().startswith("#"):
                        k, _, v = line.partition(":")
                        yaml_dict[k.strip()] = v.strip()
                obj_m = re.search(
                    r"\*\*Objective\.\*\*\s*(.*?)(?=\n\n|\*\*Considerations|^###|\Z)",
                    section_md, re.DOTALL,
                )
                objective = obj_m.group(1).strip() if obj_m else ""
                cons_m = re.search(
                    r"\*\*Considerations\.\*\*\s*(.*?)(?=^###|\Z)",
                    section_md, re.DOTALL | re.MULTILINE,
                )
                considerations = cons_m.group(1).strip() if cons_m else ""
                so_id = yaml_dict.get("id", f"SO-{section_id}.{reg}")
                phantom_flag = False
                if is_phantom:
                    # CORR-098: phantom blocks share the legit sub-SO's id in YAML.
                    # Give them a unique id derived from inherits_from + sectionId
                    # (e.g. SO-CRA-048 under D-09.4.4 → SO-D-09.4.CRA.P048x0944)
                    # so multiple phantoms inheriting the same SO stay distinct.
                    phantom_flag = True
                    inh = yaml_dict.get("inherits_from", "")
                    inh_m = re.search(r"(\d+)", inh)
                    inh_num = inh_m.group(1) if inh_m else "0"
                    sec_suffix = section_id.replace("D-", "").replace(".", "")
                    key = (inh_num, sec_suffix)
                    phantom_seen[key] = phantom_seen.get(key, 0) + 1
                    occ = phantom_seen[key]
                    so_id = f"SO-{ss_id}.{reg}.P{inh_num}x{sec_suffix}" + (f"#{occ}" if occ > 1 else "")
                objectives.append({
                    "id": so_id,
                    "kind": "HL" if is_hl else "sub-SO",
                    "regulation": reg,
                    "subdomain": ss_id,
                    "yaml": yaml_dict,
                    "yamlRaw": yaml_raw,
                    "objective": objective,
                    "considerations": considerations,
                    "sectionId": section_id,
                    "filename": md_file.name,
                    "phantom": phantom_flag,
                })
    print(
        f"load_all_objectives: {len(objectives)} objectives from SubDomains MDs",
        flush=True,
    )
    return objectives


def _extract_pair_relationships(md_text: str) -> list[dict]:
    """Extract pairwise analysis blocks from a DeepAnalysis MD.

    Matches ``#### Pair: X ↔ Y`` (or ``<->``, ``-``, ``–``, ``—``) headers and
    captures the verified_relationship mention + scope overlap from the
    following paragraphs.
    """
    pairs = []
    pattern = re.compile(
        r"^#{2,4}\s*Pair:\s*([A-Za-z_0-9]+)\s*[↔<>\-–—]\s*([A-Za-z_0-9]+)",
        re.MULTILINE,
    )
    rel_pattern = re.compile(
        r"(SCOPE-DISJOINT|COMPLEMENTARY|SAME|CONDITIONAL[\-\s]?\w*|N typically|disjoint)",
        re.IGNORECASE,
    )
    scope_pattern = re.compile(
        r"scope[- ]overlap[:\s]+([YN]\b|Conditional)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(md_text):
        reg_a, reg_b = m.group(1), m.group(2)
        start = m.start()
        rest = md_text[m.end():]
        end_m = re.search(r"^#{2,4}\s+", rest, re.MULTILINE)
        end = m.end() + end_m.start() if end_m else len(md_text)
        section_md = md_text[start:end]
        rel_m = rel_pattern.search(section_md)
        relationship = rel_m.group(1).upper() if rel_m else "?"
        scope_m = scope_pattern.search(section_md)
        scope_overlap = (scope_m.group(1) or "?").upper() if scope_m else "?"
        pairs.append({
            "reg_a": reg_a,
            "reg_b": reg_b,
            "relationship": relationship,
            "scope_overlap": scope_overlap,
            "section_md": section_md,
        })
    return pairs


def _parse_da_sections(md_text: str) -> list[dict]:
    """Split a DomainAnalysis MD into structured ``####`` sections.

    CORR-099 (Lacuna 2): DomainAnalysis MDs follow a fixed template — one ``###``
    title heading followed by ``####`` blocks (Participants, Pairwise matrix,
    Emergent tensions, SR cross-validation, Downstream implication, ...). The
    raw blob is hard to browse, so we split on ``####`` headings and return a
    list of ``{heading, body_md}`` for rendering as individual toggles.

    Text before the first ``####`` (the ``###`` title + any intro) is returned
    as a section with heading ``""`` so nothing is silently dropped.
    """
    if not md_text:
        return []
    h4_re = re.compile(r"^####\s+(.+?)\s*$", re.MULTILINE)
    sections: list[dict] = []
    matches = list(h4_re.finditer(md_text))
    if not matches:
        return [{"heading": "", "body_md": md_text.strip()}]
    # Intro: everything before the first #### (the ### title + preamble).
    pre = md_text[: matches[0].start()].strip()
    if pre:
        sections.append({"heading": "", "body_md": pre})
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        body = md_text[start:end].strip()
        sections.append({"heading": heading, "body_md": body})
    return sections


def load_crossregulation_md() -> dict:
    """Load cross-regulation MD files (HL + DeepAnalysis) grouped by subdomain.

    Sources (raw MD, NOT JSON entities — per CORR-080 user decision):

    - ``00_Hierarchical_SecurityObjectives.md`` — HL definitions (pilot: D-04.3)
    - ``CrossRegulation/DeepAnalysis/D-XX/D-XX.N.md`` — pairwise analysis
      (10 subdomain folders × 3-4 sub-subdomains each)

    Returns::

        {
            "D-02": {
                "title": "Vulnerability Management",
                "hl_md": "...",                       # empty if no HL defined
                "sub_subdomains": {
                    "D-02.1": {"md": "...", "filename": "D-02.1.md",
                               "pairs": [...], "title": "..."},
                    ...
                }
            },
            ...
        }
    """
    HSO_MD = METHODOLOGY_DIR.parent / "00_Hierarchical_SecurityObjectives.md"
    DEEP_DIR = METHODOLOGY_DIR.parent / "CrossRegulation" / "DeepAnalysis"
    SUBDOMAINS_DIR = METHODOLOGY_DIR.parent / "SubDomains"
    DOMAIN_ANALYSIS_DIR = METHODOLOGY_DIR.parent / "CrossRegulation" / "DomainAnalysis"
    result: dict = {}

    # Parse HL file: extract `### D-XX.N` (or `D-XX.N.M`) sections
    if HSO_MD.exists():
        text = _read_text(HSO_MD)
        # HL sections: `### D-XX.N — ...` OR `### D-XX.N.M — ...` (e.g., D-04.3.0, D-04.3.1)
        for m in re.finditer(r"^###\s+(D-\d+\.\d+(?:\.\d+)?)\s*[—\-–]\s*(.+)$", text, re.MULTILINE):
            sub_id = m.group(1)
            start = m.start()
            rest = text[m.end():]
            end_m = re.search(r"^###\s+", rest, re.MULTILINE)
            end = m.end() + end_m.start() if end_m else len(text)
            section_md = text[start:end]
            base = sub_id.split(".")[0]  # "D-04"
            bucket = result.setdefault(base, {"title": "", "hl_md": "", "sub_subdomains": {}})
            bucket["hl_md"] += section_md + "\n\n"

    # Parse DeepAnalysis folder
    if DEEP_DIR.exists():
        for sub_dir in sorted(DEEP_DIR.iterdir()):
            if not sub_dir.is_dir():
                continue
            sub_match = re.match(r"^(D-\d{2})_", sub_dir.name)
            if not sub_match:
                continue
            sub_id = sub_match.group(1)
            # Title from dir name (strip "D-XX_")
            sub_title = sub_dir.name[len(sub_id) + 1:].replace("_", " ")
            bucket = result.setdefault(sub_id, {"title": sub_title, "hl_md": "", "sub_subdomains": {}})
            if not bucket["title"]:
                bucket["title"] = sub_title
            for md_file in sorted(sub_dir.glob("*.md")):
                file_match = re.match(r"^(D-\d+\.\d+(?:\.\d+)?)\.md$", md_file.name)
                if not file_match:
                    continue
                ss_id = file_match.group(1)
                md_text = _read_text(md_file)
                if not md_text:
                    continue
                # CORR-084: strip YAML frontmatter (document_id, title, etc.)
                md_clean = _strip_frontmatter(md_text)
                pairs = _extract_pair_relationships(md_clean)
                # CORR-084: structured pair parsing (each pair block separate)
                parsed = _parse_pairs(md_clean)
                title_m = re.search(r"^#+\s+(.+)$", md_clean, re.MULTILINE)
                title = title_m.group(1).strip() if title_m else ss_id
                sub_md_path = SUBDOMAINS_DIR / sub_dir.name / md_file.name
                sub_md_text = _read_text(sub_md_path) if sub_md_path.exists() else ""
                sub_md_clean = _strip_frontmatter(sub_md_text) if sub_md_text else ""
                # CORR-088: capture BOTH 3 known summary sections AND all other
                # methodology sections, skipping security-objective sections.
                if sub_md_clean:
                    summary, methodology = _parse_subdomain_md(sub_md_clean)
                else:
                    summary = {
                        "emergent_tensions_md": "",
                        "validated_relationships_md": "",
                        "downstream_implication_md": "",
                    }
                    methodology = []
                domain_md_path = DOMAIN_ANALYSIS_DIR / sub_dir.name / md_file.name
                domain_md_text = _read_text(domain_md_path) if domain_md_path.exists() else ""
                domain_md_clean = _strip_frontmatter(domain_md_text) if domain_md_text else ""
                # DATA-DEBT (Part 4): D-05.4.md has a stray "## D-06 Supply Chain"
                # heading bleed at file end (concatenation artifact in the source
                # MD under Methodology-main). Not fixed here — Methodology-main is
                # a separate repo. Surface to the methodology team to trim.
                bucket["sub_subdomains"][ss_id] = {
                    "md": md_clean,
                    "filename": md_file.name,
                    "pairs": pairs,
                    "parsed": parsed,
                    "title": title,
                    "summary": summary,
                    "methodology": methodology,   # CORR-088: NEW
                    "domainAnalysisMd": domain_md_clean,
                    "da_sections": _parse_da_sections(domain_md_clean),  # CORR-099: Lacuna 2
                }
    print(
        f"load_crossregulation_md: {len(result)} subdomains, "
        f"{sum(len(s['sub_subdomains']) for s in result.values())} sub-subdomains",
        flush=True,
    )
    # CORR-081: sort subdomains by id (D-01 before D-04)
    return dict(sorted(result.items()))


def _strip_frontmatter(md_text: str) -> str:
    """Strip YAML frontmatter delimited by ``---\\n…\\n---\\n`` at start of MD.

    CORR-084: the first 15-20 lines of every DeepAnalysis MD is YAML
    metadata (document_id, title, related_documents, etc.) that adds noise
    to the rendered HTML. Strip it before storing ``ss["md"]``.
    """
    if not md_text.startswith("---\n"):
        return md_text
    end = md_text.find("\n---\n", 4)
    if end <= 0:
        return md_text
    # Skip the closing "---" line and the trailing newline
    return md_text[end + 5:].lstrip("\n")


def _parse_pairs(md_text: str) -> dict:
    """Parse a DeepAnalysis MD into {intro_md, pairs, notes_md}.

    CORR-084: split the MD on ``#### Pair: X ↔ Y`` headers and capture
    each pair's body plus the verified_relationship + scope_overlap
    classification extracted from the body text.

    Returns::
        {
            "intro_md": str,        # text before first pair (domain link, participants)
            "pairs": [
                {
                    "reg_a": str,
                    "reg_b": str,
                    "body_md": str,
                    "verified_relationship": str,   # SAME / COMPLEMENTARY / SCOPE-DISJOINT / CONDITIONAL / N typically / ?
                    "scope_overlap": str,           # Y / N / Conditional / ?
                },
                ...
            ],
            "notes_md": str,        # text after last pair (methodology / aggregation)
        }
    """
    pair_re = re.compile(
        r"^####\s+Pair:\s*(\S+)\s*[↔<>\-–—]\s*(\S+)\s*$",
        re.MULTILINE,
    )
    rel_re = re.compile(
        r"(SCOPE-DISJOINT|COMPLEMENTARY|SAME|CONDITIONAL[\-\s]?\w*|N typically)",
        re.IGNORECASE,
    )
    scope_re = re.compile(
        r"scope[- ]overlap[:\s]+([YN]\b|Conditional)",
        re.IGNORECASE,
    )

    parts = pair_re.split(md_text)
    # re.split with capturing groups returns: [pre, reg_a1, reg_b1, body1, reg_a2, reg_b2, body2, ..., post]
    intro_md = parts[0].strip() if parts else ""
    pairs: list[dict] = []
    i = 1
    while i + 2 < len(parts):
        reg_a = parts[i]
        reg_b = parts[i + 1]
        body = parts[i + 2].strip()
        rel_m = rel_re.search(body)
        scope_m = scope_re.search(body)
        pairs.append({
            "reg_a": reg_a,
            "reg_b": reg_b,
            "body_md": body,
            "verified_relationship": (rel_m.group(1).upper() if rel_m else "?"),
            "scope_overlap": ((scope_m.group(1) or "?").upper() if scope_m else "?"),
        })
        i += 3
    notes_md = ""
    # If last segment after all pairs exists, it's notes_md
    if i < len(parts) and not pairs:
        notes_md = parts[i].strip()
    elif i < len(parts) and pairs:
        notes_md = parts[i].strip()
    return {"intro_md": intro_md, "pairs": pairs, "notes_md": notes_md}


def _parse_subdomain_md(md_text: str) -> tuple[dict, list[dict]]:
    """Parse SubDomains MD into (summary, methodology).

    CORR-088: capture BOTH the 3 known summary sections AND all other
    methodology sections. EXCLUDE security-objective sections:
    - ``### D-XX.Y.0 — High-level SecurityObjective``
    - ``### D-XX.Y.N — Sub-SO for <REG>`` (where N >= 1)

    Returns:
        summary: ``{"emergent_tensions_md": str, "validated_relationships_md": str, "downstream_implication_md": str}``
        methodology: ``[{"heading": str, "body_md": str}, ...]`` — every other ``###`` section
    """
    summary = {
        "emergent_tensions_md": "",
        "validated_relationships_md": "",
        "downstream_implication_md": "",
    }
    methodology: list[dict] = []
    current_section: dict | None = None  # {"kind": "summary"|"methodology", "key"|"heading"}

    for line in md_text.split("\n"):
        # CORR-099 (Lacuna 3): capture ## wrappers + their intro text (previously
        # dropped). Each ## opens a methodology section; a subsequent ### or ##
        # naturally supersedes it. Only non-empty intro is retained (filtered
        # at return) so wrappers that are pure containers add no noise.
        m_h2 = re.match(r"^##\s+(.+)$", line)
        if m_h2 and not line.startswith("###"):
            heading = m_h2.group(1).strip()
            current_section = {"kind": "methodology", "heading": heading, "is_so": False, "is_h2": True}
            methodology.append({"heading": heading, "body_md": "", "is_so": False, "is_h2": True})
            continue
        m = re.match(r"^###\s+(.+)$", line)
        if m:
            heading = m.group(1).strip()
            # CORR-099 (Lacuna 1): SO sections (HL + per-reg sub-SOs) are now
            # INCLUDED in methodology (user decision), flagged via is_so so the
            # renderer can badge them. Previously skipped (CORR-088).
            is_so = bool(re.match(
                r"^D-\d+\.\d+\.\d+\s*[—\-–]\s*(High-level SecurityObjective|Sub-SO for\s+\S+)",
                heading,
            ))
            if "Emergent tensions" in heading:
                current_section = {"kind": "summary", "key": "emergent_tensions_md"}
            elif "Validated relationships" in heading:
                current_section = {"kind": "summary", "key": "validated_relationships_md"}
            elif "Downstream implication" in heading:
                current_section = {"kind": "summary", "key": "downstream_implication_md"}
            else:
                current_section = {"kind": "methodology", "heading": heading, "is_so": is_so}
                methodology.append({"heading": heading, "body_md": "", "is_so": is_so})
            continue
        if current_section is None:
            continue
        if current_section["kind"] == "summary":
            summary[current_section["key"]] += line + "\n"
        else:
            methodology[-1]["body_md"] += line + "\n"

    return {k: v.strip() for k, v in summary.items()}, [
        {"heading": m["heading"], "body_md": m["body_md"].rstrip(),
         "is_so": m.get("is_so", False), "is_h2": m.get("is_h2", False)}
        for m in methodology
        # CORR-099 (Lacuna 3): drop h2 wrappers that captured only whitespace
        # (i.e. a ## immediately followed by a ### child — nothing to show).
        if not (m.get("is_h2") and not m["body_md"].strip())
    ]


def _parse_subdomain_summary(md_text: str) -> dict:
    """Backwards-compat wrapper: keep old name returning just the summary dict.

    CORR-088: thin shim over :func:`_parse_subdomain_md`. Existing callers
    that only need the 3 summary strings continue to work.
    """
    summary, _methodology = _parse_subdomain_md(md_text)
    return summary


def _build_cross_refs(articles, clauses, sos, srs):
    """For each article, build an inverse index of which SOs/SRs/clauses reference it.

    CORR-079 (WS1, C10): pre-compute cross-references at build time (not runtime)
    so the Context tab renders instantly. Each entity gets a
    ``crossRefs`` dict with keys ``sos``, ``srs``, ``clauses`` — each a list of
    entity IDs that mention the entity's ``article_ref``.
    """
    # article_ref → list of (entity_id, kind)
    refs_by_article_ref: dict[str, list[tuple[str, str]]] = {}

    def _extract_article_refs(refs: list) -> list[str]:
        out: list[str] = []
        for ref in refs or []:
            if isinstance(ref, dict):
                ar = ref.get("article_ref") or ""
            else:
                ar = str(ref)
            if ar:
                out.append(ar)
        return out

    for so in sos:
        for ar in _extract_article_refs(so.get("sourceClauses", [])):
            refs_by_article_ref.setdefault(ar, []).append((so["id"], "so"))
    for sr in srs:
        for ar in _extract_article_refs(sr.get("source_clauses", [])):
            refs_by_article_ref.setdefault(ar, []).append((sr["id"], "sr"))
    for cl in clauses:
        # clauses expose article refs via instances[].locus? No — they're free-text.
        # Use a regex on the title field instead (e.g. "Art. 5(1)(a) — ...").
        title = cl.get("title") or ""
        m = re.search(r"Art\.\s*\d+", title)
        if m:
            refs_by_article_ref.setdefault(m.group(0), []).append((cl["id"], "clause"))

    def _cross_refs_for(article_ref: str) -> dict:
        if not article_ref:
            return {"sos": [], "srs": [], "clauses": []}
        matches = refs_by_article_ref.get(article_ref, [])
        sos_ids: list[str] = []
        srs_ids: list[str] = []
        cl_ids: list[str] = []
        seen_so: set[str] = set()
        seen_sr: set[str] = set()
        seen_cl: set[str] = set()
        for eid, kind in matches:
            if kind == "so" and eid not in seen_so:
                sos_ids.append(eid)
                seen_so.add(eid)
            elif kind == "sr" and eid not in seen_sr:
                srs_ids.append(eid)
                seen_sr.add(eid)
            elif kind == "clause" and eid not in seen_cl:
                cl_ids.append(eid)
                seen_cl.add(eid)
        return {"sos": sos_ids, "srs": srs_ids, "clauses": cl_ids}

    # Assign to articles
    for a in articles:
        a["crossRefs"] = _cross_refs_for(a.get("articleRef") or "")
    # Assign to clauses (their own article_ref comes from the title)
    for cl in clauses:
        cl["crossRefs"] = _cross_refs_for(cl.get("articleRef") or "")
    # For SOs/SRs we don't have a single article_ref; crossRefs stays empty
    # (reserved for future cross-ref granularity).
    for so in sos:
        so.setdefault("crossRefs", {"sos": [], "srs": [], "clauses": []})
    for sr in srs:
        sr.setdefault("crossRefs", {"sos": [], "srs": [], "clauses": []})
    return articles, clauses, sos, srs


def build_html(
    regulations: list[dict] | None = None,
    articles: list[dict] | None = None,
    clauses: list[dict] | None = None,
    sos: list[dict] | None = None,
    srs: list[dict] | None = None,
    objectives: list[dict] | None = None,
    security_requirements: list[dict] | None = None,
) -> str:
    """Build the full HTML string for the given data slices.

    CORR-078 (C11): supports programmatic invocation by tests — pass any
    subset of entity lists and an empty/inferred view is produced. Useful
    for unit-testing the §3 table layout without writing to disk.

    When invoked with ``articles=[]`` etc., the HTML still contains the
    column headers (``<th>VAG</th>`` etc.), which is what the C11 test
    command asserts against.

    CORR-091: ``objectives`` (HL + per-reg sub-SOs from SubDomains MDs) is
    the new source of truth for §4. The legacy ``sos`` payload is kept
    under ``DATA.sos`` for backward compatibility with existing detail
    panels / cross-refs (CORR-079).

    CORR-093: ``security_requirements`` (HL + sub-reqs from SubDomains MDs)
    is the new source of truth for §6. The legacy ``srs`` payload (atomic
    SRs from preproc_out/entities/srs/) is kept under ``DATA.srs`` empty
    for backward compatibility.
    """
    if objectives is None:
        objectives = load_all_objectives()
    if security_requirements is None:
        security_requirements = load_security_requirements()
    data = {
        "regulations": regulations if regulations is not None else [],
        "articles": articles if articles is not None else [],
        "clauses": clauses if clauses is not None else [],
        "sos": sos if sos is not None else [],
        "srs": srs if srs is not None else [],
        "objectives": objectives,
        "securityRequirements": security_requirements,
        "stats": {
            "regulations": len(regulations or []),
            "articles": len(articles or []),
            "clauses": len(clauses or []),
            "sos": len(objectives),
            "objectives": len(objectives),
            "srs": len(security_requirements),
        },
        "regColors": REG_COLORS,
        "csfColors": CSF_COLOR,
        "regNames": REG_NAMES,
        "buildMeta": {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "version": "sprint-1",
            "source": "preproc_out/ (5 entity kinds, full data, case-independent methodology)",
            "notes": "Full embedded entity data; every field surfaced in detail panel.",
        },
    }

    # CORR-079 (WS1, C10): pre-compute cross-refs (inverse index article_ref → SOs/SRs/clauses).
    articles, clauses, sos, srs = _build_cross_refs(
        data["articles"], data["clauses"], data["sos"], data["srs"]
    )
    data["articles"] = articles
    data["clauses"] = clauses
    data["sos"] = sos
    data["srs"] = srs

    # CORR-080: §5 Cross-Regulation (HL + DeepAnalysis MD, NOT JSON entities)
    crossregulation = load_crossregulation_md()
    data["crossregulation"] = crossregulation
    data["crossregulation_stats"] = {
        "subdomains": len(crossregulation),
        "sub_subdomains": sum(len(s["sub_subdomains"]) for s in crossregulation.values()),
        "with_hl": sum(1 for s in crossregulation.values() if s["hl_md"]),
        "pairs_total": sum(
            len(ss["pairs"]) for s in crossregulation.values()
            for ss in s["sub_subdomains"].values()
        ),
    }

    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    # CORR-100: inject live counts into tab badges + section subtitles so they
    # always match the arrays the renderers iterate (source of truth = the array,
    # not DATA.stats, to avoid future drift between stats and the array).
    html = html.replace("__COUNT_REGS__", str(len(regulations or [])))
    html = html.replace("__COUNT_ARTICLES__", str(len(articles or [])))
    html = html.replace("__COUNT_CLAUSES__", str(len(clauses or [])))
    html = html.replace("__COUNT_OBJECTIVES__", str(len(objectives)))
    html = html.replace("__COUNT_SRS__", str(len(security_requirements)))
    html = html.replace("__COUNT_PAIRS__", str(data["crossregulation_stats"]["pairs_total"]))
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size / 1024
    print(f"Wrote {OUT_HTML} ({size_kb:.1f} KB)")
    print(f"  regs={len(regulations or [])} arts={len(articles or [])} "
          f"clauses={len(clauses or [])} objectives={len(objectives)} "
          f"srs(legacy)={len(srs or [])} srs(hier)={len(security_requirements)}")
    cr_stats = data["crossregulation_stats"]
    print(f"  crossregulation: {cr_stats['subdomains']} subdomains, "
          f"{cr_stats['sub_subdomains']} sub-subdomains, {cr_stats['with_hl']} with HL, "
          f"{cr_stats['pairs_total']} pairs")
    return html


def main():
    """CLI entry point — reads preproc_out/ shards and writes the HTML."""
    regs = load_regulations()
    articles = load_articles()
    clauses = load_clauses()
    sos = load_sos()
    srs = load_srs()
    objectives = load_all_objectives()
    security_requirements = load_security_requirements()
    build_html(
        regulations=regs,
        articles=articles,
        clauses=clauses,
        sos=sos,
        srs=srs,
        objectives=objectives,
        security_requirements=security_requirements,
    )


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AEGIS-KG — Regulation Chain Viewer (full data)</title>
  <style>
    :root {
      --bg: #0f1419;
      --panel: #1a1f2e;
      --panel-2: #242b3d;
      --border: #2d3548;
      --fg: #e1e7f0;
      --fg-dim: #8b95a7;
      --accent: #4ecdc4;
      --accent-2: #6c5ce7;
      --warn: #ffd93d;
      --danger: #ff6b6b;
      --hl: #f9f49d;
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0; padding: 0; height: 100%;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg); color: var(--fg);
      font-size: 13px;
    }
    body { display: flex; flex-direction: column; }

    header {
      padding: 12px 20px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    header h1 {
      margin: 0 0 8px 0; font-size: 18px; font-weight: 600; letter-spacing: 0.3px;
    }
    header h1 small { color: var(--fg-dim); font-weight: 400; font-size: 12px; margin-left: 8px; }
    .kpis {
      display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 8px;
    }
    .kpi {
      padding: 8px 14px;
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 6px;
      min-width: 100px;
    }
    .kpi .n {
      font-size: 20px; font-weight: 700; color: var(--accent);
      line-height: 1; font-variant-numeric: tabular-nums;
    }
    .kpi .l {
      font-size: 10px; color: var(--fg-dim);
      text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;
    }
    .build-banner {
      padding: 6px 12px; font-size: 11px;
      background: rgba(78,205,196,0.10); border: 1px solid rgba(78,205,196,0.35);
      border-radius: 6px; color: var(--accent);
      display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    }
    .build-banner .badge {
      background: var(--accent); color: var(--bg); padding: 2px 8px;
      border-radius: 4px; font-size: 10px; letter-spacing: 0.5px; font-weight: 600;
    }
    .build-banner .meta { color: var(--fg-dim); }

    /* ---- Tab bar (CORR-077) ---- */
    .tab-bar {
      display: flex;
      gap: 4px;
      padding: 8px 16px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
    }
    .tab-btn {
      padding: 8px 16px;
      background: transparent;
      color: var(--fg-dim);
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s;
    }
    .tab-btn:hover { color: var(--fg); border-color: var(--accent); }
    .tab-btn.active { background: var(--accent); color: var(--bg); border-color: var(--accent); font-weight: 600; }
    .tab-btn .badge-count {
      display: inline-block;
      margin-left: 6px;
      padding: 1px 8px;
      background: rgba(0,0,0,0.18);
      border-radius: 10px;
      font-size: 11px;
      font-weight: 500;
    }
    .tab-btn.active .badge-count {
      background: rgba(255,255,255,0.25);
    }

    main {
      flex: 1; display: grid;
      grid-template-columns: 240px 1fr 420px;
      gap: 1px; background: var(--border);
      min-height: 0;
    }

    aside, section, .detail {
      background: var(--panel); padding: 14px;
      overflow-y: auto; min-height: 0;
    }
    .detail { display: flex; flex-direction: column; }
    .detail-tabs { display: flex; gap: 4px; margin-bottom: 8px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
    .detail-tab-btn { background: transparent; border: 1px solid transparent; border-bottom: none; color: var(--fg-dim); padding: 6px 12px; cursor: pointer; font-size: 12px; border-radius: 4px 4px 0 0; transition: background 0.15s, color 0.15s; }
    .detail-tab-btn:hover { background: var(--panel-2); color: var(--fg); }
    .detail-tab-btn.active { background: var(--panel); color: var(--accent); border-color: var(--border); }
    .detail-tab-body { padding: 0 4px; flex: 1; overflow-y: auto; min-height: 0; }
    .tab-pane[hidden] { display: none; }
    .raw-json { white-space: pre-wrap; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; background: var(--panel-2); padding: 8px; border-radius: 4px; max-height: 60vh; overflow: auto; }
    /* CORR-090: Unified details card system for §5 Cross-Regulation */
    .code-block {
      background: var(--panel-2);
      padding: 8px 10px;
      border-radius: 4px;
      overflow-x: auto;
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      font-size: 11px;
      border: 1px solid var(--border);
    }

    /* All <details> elements in §5 use .crossreg-card for consistent look.
       Accent variants (.accent-XXX) add a 4px left border in a semantic color. */

    /* Outer container — same shape, padding, transition regardless of accent */
    details.crossreg-card {
      border: 1px solid var(--border);
      border-radius: 4px;
      background: var(--panel);
      margin-bottom: 8px;
      overflow: hidden;
      transition: border-color 0.15s ease, background 0.15s ease;
    }

    /* Summary (header) — same padding, font, hover behaviour */
    details.crossreg-card > summary {
      cursor: pointer;
      padding: 10px 14px;
      font-size: 12px;
      font-weight: 600;
      color: var(--fg);
      list-style: disclosure-closed inside;
      background: var(--panel);
      border-bottom: 1px solid transparent;
      transition: background 0.15s, color 0.15s, border-color 0.15s;
      user-select: none;
    }
    details.crossreg-card > summary:hover {
      background: var(--panel-2);
      color: var(--accent);
    }

    /* Open state — same background shift, same border separator */
    details.crossreg-card[open] > summary {
      background: var(--panel-2);
      color: var(--accent);
      border-bottom: 1px solid var(--border);
      list-style: disclosure-open inside;
    }

    /* Content area — same padding, same background */
    details.crossreg-card > .card-content {
      padding: 12px 14px;
      font-size: 12px;
      background: var(--bg);
      border-top: 1px solid var(--border);
    }

    /* Accent variants — 4px left border in semantic color */
    details.crossreg-card.accent-orange { border-left: 4px solid #ff9800; }
    details.crossreg-card.accent-cyan   { border-left: 4px solid #4ecdc4; }
    details.crossreg-card.accent-green  { border-left: 4px solid #a8e6cf; }
    details.crossreg-card.accent-red    { border-left: 4px solid #ff6b6b; }
    details.crossreg-card.accent-yellow { border-left: 4px solid #ffd93d; }
    details.crossreg-card.accent-purple { border-left: 4px solid #6c5ce7; }

    /* Nested cards (inside another crossreg-card) — slightly lighter background */
    details.crossreg-card details.crossreg-card {
      margin: 8px 0;
      background: var(--panel-2);
    }
    details.crossreg-card details.crossreg-card > summary {
      background: var(--panel-2);
      padding: 8px 12px;
      font-size: 11px;
      font-weight: 600;
    }
    details.crossreg-card details.crossreg-card[open] > summary {
      background: var(--bg);
    }

    /* Summary card content — keep simple, no nested */
    .crossreg-card .summary-content { font-size: 12px; }
    .crossreg-card .summary-label { display: inline; font-weight: 600; }

    /* Pair block content — styling for header rows */
    .crossreg-card .pair-header {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .crossreg-card .pair-pair { font-weight: 600; color: var(--accent); }
    .crossreg-card .pair-rel {
      font-size: 10px;
      text-transform: uppercase;
      padding: 2px 8px;
      border-radius: 3px;
      background: var(--panel);
      color: var(--accent);
      letter-spacing: 0.5px;
    }
    .crossreg-card .pair-scope { color: var(--fg-dim); font-size: 11px; font-style: italic; }
    .crossreg-card .pair-srs { color: var(--fg-dim); font-size: 11px; font-family: var(--mono, monospace); }

    /* Sub-methodology wrapper (outer toggle) */
    details.crossreg-card .crossreg-card + .crossreg-card,
    .crossreg-card-wrapper { margin-top: 12px; }

    /* Container block (D-01, D-02, ...) */
    .crossreg-block { margin-bottom: 20px; padding: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--panel); }
    .crossreg-block h3 { margin: 0 0 8px; color: var(--accent); font-size: 14px; }
    .crossreg-block h4 { margin: 8px 0 4px; color: var(--fg); font-size: 12px; }

    /* Tab toggle bar (top of §5) */
    .crossreg-toggle-bar {
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
    }
    .crossreg-toggle-bar button {
      background: var(--panel-2);
      color: var(--fg);
      border: 1px solid var(--border);
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 11px;
      transition: background 0.15s, color 0.15s;
    }
    .crossreg-toggle-bar button:hover { background: var(--accent); color: var(--bg); }

    /* Pair grid — stacking layout for the .crossreg-card children */
    .pair-grid { display: grid; grid-template-columns: 1fr; gap: 6px; margin-top: 8px; }

    /* Sub-summary heading row */
    .sub-summary { margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--border); }
    .sub-summary h4 { color: var(--accent); font-size: 12px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }

    /* Intro text inside a crossreg-card */
    .crossreg-card .crossreg-intro { color: var(--fg-dim); font-size: 11px; margin-bottom: 10px; }

    /* Generic typography for content inside cards */
    .crossreg-card p:first-child { margin-top: 0; }
    .crossreg-card p:last-child { margin-bottom: 0; }
    .crossreg-card h1, .crossreg-card h2, .crossreg-card h3, .crossreg-card h4 { margin: 8px 0 4px; }
    .crossreg-card table { border-collapse: collapse; width: 100%; margin: 8px 0; }
    .crossreg-card th, .crossreg-card td { border: 1px solid var(--border); padding: 4px 8px; text-align: left; font-size: 11px; }
    .crossreg-card th { background: var(--panel-2); }
    .crossreg-card pre.code-block {
      background: var(--panel-2);
      padding: 8px 10px;
      border-radius: 4px;
      overflow-x: auto;
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      font-size: 11px;
      border: 1px solid var(--border);
    }

    .tab-pane h4 { margin: 12px 0 4px; font-size: 12px; color: var(--accent); }
    .tab-pane p { margin: 4px 0; }

    aside h3, .detail h3 {
      margin: 0 0 10px 0; font-size: 11px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 1px; color: var(--fg-dim);
    }
    .filter-group { margin-bottom: 16px; }
    .filter-group > label.title {
      display: block; font-size: 10px; text-transform: uppercase;
      letter-spacing: 1px; color: var(--fg-dim); margin-bottom: 6px; font-weight: 600;
    }
    .filter-group label {
      display: flex; align-items: center; gap: 8px; padding: 3px 0;
      font-size: 12px; cursor: pointer; user-select: none;
    }
    .filter-group input[type=checkbox] { accent-color: var(--accent); }
    .filter-group .count { color: var(--fg-dim); font-size: 10px; margin-left: auto; }
    .filter-group .swatch {
      display: inline-block; width: 10px; height: 10px; border-radius: 2px;
    }
    .filter-group .csf-swatch {
      display: inline-block; width: 28px; padding: 1px 4px; border-radius: 3px;
      font-size: 9px; font-weight: 700; color: #0f1419; text-align: center;
    }
    .filter-group .severity-badge {
      display: inline-block; width: 22px; padding: 1px 4px; border-radius: 3px;
      font-size: 10px; font-weight: 700; color: #0f1419; text-align: center;
    }
    .filter-group .berry-badge {
      display: inline-block; padding: 1px 6px; border-radius: 3px;
      font-size: 10px; font-weight: 600;
      background: var(--panel-2); border: 1px solid var(--border);
    }
    input[type=search] {
      width: 100%; padding: 6px 10px; background: var(--panel-2);
      border: 1px solid var(--border); color: var(--fg);
      border-radius: 6px; font-size: 12px; outline: none;
      margin-bottom: 12px;
    }
    input[type=search]:focus { border-color: var(--accent); }
    .reset-btn {
      width: 100%; padding: 6px 12px;
      background: var(--panel-2); color: var(--accent);
      border: 1px solid var(--accent); border-radius: 6px;
      font-size: 11px; cursor: pointer; font-weight: 600;
      margin-top: 8px;
    }
    .reset-btn:hover { background: var(--accent); color: var(--bg); }

    .anchor-link {
      display: block; padding: 4px 8px;
      color: var(--fg-dim); text-decoration: none;
      font-size: 12px; border-radius: 4px;
      transition: background 0.15s;
    }
    .anchor-link:hover { background: var(--panel-2); color: var(--accent); }
    .anchor-link .n {
      display: inline-block; min-width: 24px; color: var(--accent);
      font-weight: 600; font-variant-numeric: tabular-nums;
    }

    section h2 {
      margin: 0 0 8px 0; font-size: 16px; color: var(--fg);
      border-bottom: 2px solid var(--accent); padding-bottom: 6px;
    }
    section h2 small {
      color: var(--fg-dim); font-weight: 400; font-size: 12px; margin-left: 8px;
    }
    section .section-meta {
      font-size: 11px; color: var(--fg-dim); margin-bottom: 12px;
    }

    .reg-card {
      display: grid;
      grid-template-columns: 8px 1fr auto;
      gap: 12px;
      padding: 10px 12px;
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .reg-card:hover { border-color: var(--accent); transform: translateY(-1px); }
    .reg-card .strip { border-radius: 4px; }
    .reg-card .name { font-size: 14px; font-weight: 600; }
    .reg-card .focus { font-size: 11px; color: var(--fg-dim); margin-top: 4px; }
    .reg-card .stats-line {
      display: flex; gap: 8px; margin-top: 6px; font-size: 10px;
      color: var(--fg-dim); flex-wrap: wrap;
    }
    .reg-card .stats-line b { color: var(--accent); font-weight: 600; }
    .reg-card .doc-id {
      font-size: 10px; color: var(--fg-dim); text-align: right;
      font-family: ui-monospace, monospace;
    }

    table.entity {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      background: var(--panel-2);
      border-radius: 6px;
      overflow: hidden;
    }
    table.entity thead {
      position: sticky;
      top: 0;
      background: var(--panel);
      z-index: 2;
    }
    table.entity th {
      text-align: left; padding: 8px 10px;
      font-size: 10px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 1px; color: var(--fg-dim);
      border-bottom: 1px solid var(--border);
    }
    table.entity td {
      padding: 6px 10px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }
    table.entity tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
    table.entity tr:hover td { background: rgba(78,205,196,0.08); cursor: pointer; }
    table.entity tr.skeleton td { opacity: 0.55; }
    table.entity tr.hidden { display: none; }
    .cell-id {
      font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
      font-size: 11px;
      color: var(--accent);
      cursor: pointer;
    }
    .cell-id:hover { text-decoration: underline; }
    .cell-id-sm { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 10px; color: var(--fg-dim); }
    .reg-tag {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: 600;
      color: #0f1419;
    }
    .type-badge {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: 600;
      background: var(--panel-2);
      border: 1px solid var(--border);
    }
    .type-badge.per-reg { background: rgba(108,92,231,0.20); border-color: var(--accent-2); color: var(--accent-2); }
    .type-badge.sub-SO { background: rgba(108,92,231,0.20); border-color: var(--accent-2); color: var(--accent-2); }
    .type-badge.HL { background: rgba(249,244,157,0.20); border-color: var(--hl); color: var(--hl); }
    .type-badge.canonical { background: var(--panel-2); border-color: var(--border); color: var(--fg-dim); }
    .type-badge.VAG { color: var(--warn); }
    .type-badge.POLY { color: var(--accent-2); }
    /* CORR-098: phantom badge for CORR-030 propagated sub-SO blocks (unique id) */
    .phantom-badge { margin-left: 4px; padding: 1px 5px; font-size: 9px; border-radius: 3px; background: rgba(255,159,28,0.18); border: 1px solid var(--warn); color: var(--warn); cursor: help; }
    /* CORR-099 Lacuna 1: SO badge for security-objective sections inside methodology */
    .so-badge { margin-left: 4px; padding: 1px 5px; font-size: 9px; border-radius: 3px; background: rgba(108,92,231,0.18); border: 1px solid var(--accent-2); color: var(--accent-2); cursor: help; }
    /* CORR-099 Lacuna 3: H2 wrapper badge + emphasis for top-level sections */
    .h2-badge { margin-left: 4px; padding: 1px 5px; font-size: 9px; border-radius: 3px; background: var(--panel-2); border: 1px solid var(--border); color: var(--fg-dim); cursor: help; }
    .crossreg-card.meth-h2 > summary { font-size: 13px; font-weight: 700; color: var(--accent); }
    .type-badge.COORD { color: var(--accent); }
    .type-badge.SCOPE-Q { color: var(--danger); }
    /* CORR-078 (C11/C12): Berry category indicators in the §3 table */
    .berry-on {
      color: var(--accent);
      font-size: 14px;
      font-weight: 700;
    }
    .berry-off {
      color: var(--fg-dim);
      font-size: 14px;
      opacity: 0.4;
    }
    .severity {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: 700;
      color: #0f1419;
    }
    .severity.S1 { background: #7df49f; }
    .severity.S2 { background: var(--warn); }
    .severity.S3 { background: var(--danger); color: #fff; }
    .skel-tag {
      display: inline-block;
      padding: 0 5px;
      margin-left: 4px;
      border-radius: 3px;
      font-size: 9px;
      background: var(--panel-2);
      color: var(--fg-dim);
      border: 1px solid var(--border);
    }
    /* CORR-093: hierarchical SR rows (HL bold + sub indented/toned-down) */
    tr[data-level="HL"] { font-weight: 600; }
    tr.sub-req-row { background: var(--panel-2); }
    tr.sub-req-row:hover { background: var(--panel); }
    .type-badge.sub { background: rgba(139,149,167,0.20); border-color: var(--fg-dim); color: var(--fg-dim); }
    .code-block { background: var(--panel-2); border: 1px solid var(--border); border-radius: 6px; padding: 10px; max-height: 360px; overflow: auto; font-family: ui-monospace, monospace; font-size: 11px; }
    .preview {
      max-width: 380px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--fg-dim);
    }
    .csf-chip {
      display: inline-block;
      padding: 1px 6px;
      margin: 1px 2px;
      border-radius: 3px;
      font-size: 10px;
      font-weight: 700;
      color: #0f1419;
      font-family: ui-monospace, monospace;
      cursor: pointer;
    }
    .csf-chip:hover { filter: brightness(1.15); }
    .chip-list { display: flex; flex-wrap: wrap; gap: 2px; }

    .expand-toggle {
      background: none; border: none; color: var(--accent);
      cursor: pointer; padding: 0; font-size: 11px;
      font-family: inherit;
    }
    .expand-toggle:hover { text-decoration: underline; }

    .detail .empty {
      color: var(--fg-dim); font-style: italic;
      padding: 24px 0; text-align: center; font-size: 12px;
    }
    .detail h2 {
      margin: 0 0 6px 0; font-size: 16px; color: var(--accent);
      font-family: ui-monospace, monospace;
    }
    .detail h2 .kind {
      display: inline-block; padding: 2px 8px; margin-right: 6px;
      background: var(--panel-2); border: 1px solid var(--border);
      border-radius: 4px; font-size: 10px; color: var(--fg-dim);
      font-family: -apple-system, sans-serif;
      text-transform: uppercase; letter-spacing: 1px;
      vertical-align: middle;
    }
    .detail .meta {
      font-size: 11px; color: var(--fg-dim);
      margin-bottom: 12px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
    }
    .detail .meta .pill {
      display: inline-block; padding: 2px 8px;
      background: var(--panel-2); border: 1px solid var(--border);
      border-radius: 4px; margin-right: 6px; margin-top: 4px;
    }
    .detail dl { margin: 0; }
    .detail .field {
      display: grid;
      grid-template-columns: 28% 1fr;
      gap: 8px;
      padding: 6px 0;
      border-bottom: 1px solid var(--border);
      font-size: 12px;
    }
    .detail .field-key {
      color: var(--fg-dim); font-weight: 600;
      font-family: ui-monospace, monospace;
      word-break: break-word;
      padding-right: 6px;
    }
    .detail .field-val { word-wrap: break-word; overflow-wrap: break-word; }
    .detail .field-val pre {
      margin: 0;
      white-space: pre-wrap;
      word-wrap: break-word;
      font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
      font-size: 11px;
      color: var(--fg);
      background: var(--bg);
      padding: 6px 8px;
      border-radius: 4px;
      max-height: 240px;
      overflow-y: auto;
    }
    .detail .field-val .string { color: var(--fg); }
    .detail .field-val .num { color: var(--warn); font-weight: 600; }
    .detail .field-val .bool {
      display: inline-block; padding: 1px 6px; border-radius: 3px;
      font-size: 10px; font-weight: 700;
    }
    .detail .field-val .bool.true { background: #7df49f; color: #0f1419; }
    .detail .field-val .bool.false { background: var(--bg); color: var(--fg-dim); border: 1px solid var(--border); }
    .detail .field-val .null { color: var(--fg-dim); font-style: italic; }
    .detail .field-val .deeper { color: var(--fg-dim); font-style: italic; }
    .detail .field-val details {
      margin: 0;
    }
    .detail .field-val details > summary {
      cursor: pointer;
      padding: 2px 6px;
      background: var(--bg);
      border-radius: 4px;
      font-size: 11px;
      user-select: none;
      list-style: none;
    }
    .detail .field-val details > summary::-webkit-details-marker { display: none; }
    .detail .field-val details > summary::before {
      content: '▶'; color: var(--accent); margin-right: 5px;
      display: inline-block; transition: transform 0.15s;
      font-size: 9px;
    }
    .detail .field-val details[open] > summary::before { transform: rotate(90deg); }
    .detail .field-val details .item {
      padding: 6px 8px;
      margin: 4px 0;
      background: var(--bg);
      border-left: 2px solid var(--accent);
      border-radius: 0 4px 4px 0;
    }
    .detail .field-val .nested {
      margin: 4px 0 0 8px;
      padding-left: 8px;
      border-left: 1px dashed var(--border);
    }
    .detail .field-val .narrative {
      cursor: pointer;
    }
    .detail .field-val .narrative summary {
      background: var(--bg);
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      list-style: none;
    }
    .detail .field-val .narrative summary::-webkit-details-marker { display: none; }
    .detail .field-val .narrative summary::before {
      content: '▶ '; color: var(--accent); font-size: 9px;
    }
    .detail .field-val .narrative[open] summary::before { content: '▼ '; }
    .detail .field-val .narrative .body {
      padding: 8px 12px;
      background: var(--bg);
      border-radius: 4px;
      margin-top: 4px;
      white-space: pre-wrap;
      font-size: 11px;
      line-height: 1.5;
      max-height: 360px;
      overflow-y: auto;
    }
    .detail .pill-list { display: flex; flex-wrap: wrap; gap: 4px; }
    .detail .pill-list .pill {
      padding: 2px 8px;
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 4px;
      font-size: 11px;
      font-family: ui-monospace, monospace;
    }
    .narrative-hint { font-size: 10px; color: var(--fg-dim); font-style: italic; margin-left: 6px; }

    footer {
      padding: 6px 16px; background: var(--panel); border-top: 1px solid var(--border);
      font-size: 10px; color: var(--fg-dim); flex-shrink: 0;
      display: flex; justify-content: space-between;
    }
  </style>
</head>
<body>
  <header>
    <h1>AEGIS-KG — Regulation Chain Viewer <small>full data · 5 sections · 3-column layout</small></h1>
    <div class="kpis" id="kpis"></div>
    <div class="build-banner" id="build-banner"></div>
  </header>

  <nav class="tab-bar" id="tab-bar">
    <button class="tab-btn" data-tab="regulations">Regulations <span class="badge-count">__COUNT_REGS__</span></button>
    <button class="tab-btn" data-tab="articles">Articles <span class="badge-count">__COUNT_ARTICLES__</span></button>
    <button class="tab-btn" data-tab="clauses">Clauses <span class="badge-count">__COUNT_CLAUSES__</span></button>
    <button class="tab-btn" data-tab="sos">SOs <span class="badge-count">__COUNT_OBJECTIVES__</span></button>
    <button class="tab-btn" data-tab="crossregulation">CrossRegulation <span class="badge-count">__COUNT_PAIRS__</span></button>
    <button class="tab-btn" data-tab="srs">SRs <span class="badge-count">__COUNT_SRS__</span></button>
  </nav>

  <main>
    <aside>
      <div class="sidebar-content" id="sidebar-content">
        <!-- JS will rebuild contents on tab change + on init -->
      </div>
    </aside>

    <section id="main-content">
      <div id="tab-regulations" class="tab-pane" data-pane="regulations" style="display:block">
        <div id="section-1" data-section="1">
          <h2>§1 Regulations <small>__COUNT_REGS__ regulations</small></h2>
          <div class="section-meta">Per-reg preproc manifest: README + SecurityObjectives + SecurityRules_NIST. Click a card to inspect.</div>
          <div id="regs-cards"></div>
        </div>
      </div>

      <div id="tab-articles" class="tab-pane" data-pane="articles" style="display:none">
        <div id="section-2" data-section="2">
          <h2>§2 Articles <small>__COUNT_ARTICLES__ articles</small></h2>
          <div class="section-meta">Individual article shards (<code>preproc_out/entities/articles/&lt;REG&gt;_Art_ &lt;N&gt;.json</code>). Click row for full detail.</div>
          <table class="entity" id="table-articles">
            <thead>
              <tr>
                <th>ID</th><th>Reg</th><th>Article Ref</th><th>Title</th><th>#SOs</th><th>#SRs</th><th>Status</th>
              </tr>
            </thead>
            <tbody id="tbody-articles"></tbody>
          </table>
        </div>
      </div>

      <div id="tab-clauses" class="tab-pane" data-pane="clauses" style="display:none">
        <div id="section-3" data-section="3">
          <h2>§3 Clauses <small>__COUNT_CLAUSES__ clauses (many skeleton)</small></h2>
          <div class="section-meta">Atomic clauses with Berry types (VAG/POLY/COORD/SCOPE-Q) and severity (S1/S2/S3). Skeleton rows are dimmed.</div>
          <table class="entity" id="table-clauses">
            <thead>
              <tr>
                <th>ID</th><th>Reg</th><th>Section Ref</th><th>Title</th><th>VAG</th><th>POLY</th><th>COORD</th><th>SCOPE-Q</th><th>Severity</th><th>Sk</th>
              </tr>
            </thead>
            <tbody id="tbody-clauses"></tbody>
          </table>
        </div>
      </div>

      <div id="tab-sos" class="tab-pane" data-pane="sos" style="display:none">
        <div id="section-4" data-section="4">
          <h2>§4 SecurityObjectives <small id="objectives-stats"></small></h2>
          <div class="section-meta">
            Source: <code>Methodology-main/00_METHODOLOGY/PREPROCESSING/SubDomains/**/*.md</code>.
            <span class="type-badge HL">HL</span> High-level (cross-reg) ·
            <span class="type-badge sub-SO">sub-SO</span> Per-reg subdomain.
            CORR-091 — atomic Berry SOs from <code>preproc_out/entities/sos/</code> are no longer used here.
          </div>
          <table class="entity" id="table-sos">
            <thead>
              <tr>
                <th>ID</th><th>Kind</th><th>Reg</th><th>Subdomain</th><th>Objective</th><th>Status</th>
              </tr>
            </thead>
            <tbody id="tbody-sos"></tbody>
          </table>
        </div>
      </div>

      <div id="tab-crossregulation" class="tab-pane" data-pane="crossregulation" style="display:none">
        <div id="section-5" data-section="5">
          <h2>§5 Cross-Regulation <small id="crossregulation-stats"></small></h2>
          <div class="section-meta">Pairwise analysis from <code>CrossRegulation/DeepAnalysis/D-XX/*.md</code> + HL definitions from <code>00_Hierarchical_SecurityObjectives.md</code>. Source = raw MD, rendered client-side (NOT JSON entities).</div>
          <div id="crossregulation-blocks"></div>
        </div>
      </div>

      <div id="tab-srs" class="tab-pane" data-pane="srs" style="display:none">
        <div id="section-6" data-section="6">
          <h2>§6 SecurityRequirements <small>__COUNT_SRS__ reqs (HL + sub)</small></h2>
          <div class="section-meta">Hierarchical security requirements derived from SubDomains MDs. Each High-Level (HL) row aggregates 2-5 sub-requirements. Click any row for full YAML + description + considerations.</div>
          <table class="entity" id="table-srs">
            <thead>
              <tr>
                <th>Req ID</th><th>Level</th><th>Subdomain</th><th>Title</th><th>NIST CSF</th><th>Priority</th><th>Sub</th>
              </tr>
            </thead>
            <tbody id="tbody-srs"></tbody>
          </table>
        </div>
      </div>
    </section>

    <div class="detail" id="detail">
      <div class="detail-tabs">
        <button class="detail-tab-btn active" data-tab="rendered">Rendered</button>
        <button class="detail-tab-btn" data-tab="json">JSON</button>
        <button class="detail-tab-btn" data-tab="markdown">Markdown</button>
        <button class="detail-tab-btn" data-tab="context">Context</button>
      </div>
      <div class="detail-tab-body">
        <div class="tab-pane" data-pane="rendered"></div>
        <div class="tab-pane" data-pane="json" hidden></div>
        <div class="tab-pane" data-pane="markdown" hidden></div>
        <div class="tab-pane" data-pane="context" hidden></div>
      </div>
    </div>
  </main>

  <footer>
    <span>AEGIS-KG — Regulation Chain Viewer (full data) · 5 sections · 1,253 entities</span>
    <span id="footer-info"></span>
  </footer>

  <script id="app-data" type="application/json">__DATA_JSON__</script>
  <script>
  (function () {
    'use strict';

    const DATA = JSON.parse(document.getElementById('app-data').textContent);
    const LONG_FIELDS = new Set([
      'regulatory_rationale', 'security_rationale', 'ambiguity_notes',
      'raw_md', 'securityRules', 'instances', 'intraSectionNotes', 'berryAnchors',
      'sourceClauses', 'linkedObjectives', 'nistCsfMapping', 'sourceClauses',
      'objective', 'description', 'considerations', 'anchors', 'csf',
      'securityObjectives', 'sos', 'srs', 'frontmatter', 'rawMd',
    ]);

    const STATE = {
      activeTab: 'regulations',
      activeDetailTab: 'rendered',
      search: '',
      filters: {},
    };

    // ---- Pre-derive filter-friendly fields (CORR-077) ----
    const REG_TYPE_MAP = { 'GDPR': 'DATA_PROTECTION', 'CRA': 'CYBER_SECURITY', 'NIS2': 'CRITICAL_INFRA', 'DORA': 'FINANCIAL', 'AI_Act': 'AI_REGULATION' };
    DATA.regulations.forEach(r => { r.type = REG_TYPE_MAP[r.id] || 'OTHER'; });
    DATA.clauses.forEach(c => { c.berryType = c.type; });
    DATA.srs.forEach(sr => {
      sr.csfFunction = [...new Set((sr.nist_csf_mapping || []).map(c => {
        const m = (c.id || '').match(/^([A-Z]{2})\./);
        return m ? m[1] : null;
      }).filter(Boolean))];
    });

    // ---- KPI cards ----
    function renderKpis() {
      const s = DATA.stats;
      const kpis = [
        { n: s.regulations, l: 'Regulations' },
        { n: s.articles, l: 'Articles' },
        { n: s.clauses, l: 'Clauses' },
        { n: s.sos, l: 'SOs' },
        { n: s.srs, l: 'SRs' },
      ];
      document.getElementById('kpis').innerHTML = kpis.map(k =>
        `<div class="kpi"><div class="n">${k.n}</div><div class="l">${k.l}</div></div>`
      ).join('');
    }

    // ---- Build banner ----
    function renderBanner() {
      const m = DATA.buildMeta;
      document.getElementById('build-banner').innerHTML = `
        <span class="badge">${m.version}</span>
        <span>Built ${m.generatedAt}</span>
        <span class="meta">· ${m.source}</span>
        <span class="meta">· If missing data, re-run <code>python3 docs/visualization/build_regulation_chain.py</code></span>
      `;
    }

    // ---- Helpers ----
    function csfFunctionOf(csfId) {
      if (!csfId) return '';
      const m = csfId.match(/^([A-Z]{2})\./);
      return m ? m[1] : '';
    }

    function escapeHtml(s) {
      return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      })[c]);
    }

    function shortText(s, max) {
      if (s == null) return '';
      const t = String(s);
      return t.length > max ? t.slice(0, max) + '…' : t;
    }

    // ---- Sidebar: contextual filter rendering (CORR-077) ----
    function rebuildSidebar() {
      const sb = document.getElementById('sidebar-content');
      sb.innerHTML = '';

      // Search box — always present
      const searchRow = document.createElement('div');
      searchRow.style.marginBottom = '16px';
      const searchLabel = document.createElement('div');
      searchLabel.textContent = 'SEARCH';
      searchLabel.style.cssText = 'font-size:11px;font-weight:600;letter-spacing:1px;color:var(--fg-dim);margin-bottom:6px;';
      const searchInput = document.createElement('input');
      searchInput.type = 'search';
      searchInput.placeholder = 'Type to filter this tab';
      searchInput.id = 'tab-search';
      searchInput.style.cssText = 'width:100%;padding:6px 10px;background:var(--panel-2);border:1px solid var(--border);color:var(--fg);border-radius:6px;font-size:13px;outline:none';
      searchInput.value = STATE.search || '';
      searchInput.addEventListener('input', e => { STATE.search = e.target.value; applyAllFilters(); });
      searchRow.appendChild(searchLabel);
      searchRow.appendChild(searchInput);
      sb.appendChild(searchRow);

      // Tab-specific filters (CONTEXTUAL)
      switch (STATE.activeTab) {
        case 'regulations':
          addFilterGroup(sb, 'REGULATION TYPE', [
            ['DATA_PROTECTION', 'Data Protection'],
            ['CYBER_SECURITY', 'Cyber Security'],
            ['CRITICAL_INFRA', 'Critical Infra'],
            ['FINANCIAL', 'Financial'],
            ['AI_REGULATION', 'AI Regulation'],
          ], 'type');
          break;
        case 'articles':
          addFilterGroup(sb, 'REGULATION', DATA.regulations.map(r => [r.id, r.displayName || r.id]), 'regulation');
          addFilterGroup(sb, 'STATUS', [['DRAFT','DRAFT'],['ACTIVE','ACTIVE']], 'status');
          break;
        case 'clauses':
          addFilterGroup(sb, 'REGULATION', DATA.regulations.map(r => [r.id, r.displayName || r.id]), 'regulation');
          addFilterGroup(sb, 'BERRY TYPE', [['VAG','VAG'],['POLY','POLY'],['COORD','COORD'],['SCOPE-Q','SCOPE-Q']], 'berryType');
          addFilterGroup(sb, 'SEVERITY', [['S1','S1'],['S2','S2'],['S3','S3']], 'severity');
          const hideSkel = document.createElement('label');
          hideSkel.style.cssText = 'display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;margin-top:8px;';
          hideSkel.innerHTML = '<input type="checkbox" id="hide-skel" /> <span>Hide skeleton clauses</span>';
          hideSkel.querySelector('#hide-skel').addEventListener('change', e => {
            if (!STATE.filters.hideSkeleton) STATE.filters.hideSkeleton = new Set();
            if (e.target.checked) STATE.filters.hideSkeleton.add('true');
            else STATE.filters.hideSkeleton.delete('true');
            applyAllFilters();
          });
          sb.appendChild(hideSkel);
          break;
        case 'sos':
          // CORR-092: source = DATA.objectives (SubDomains MDs)
          // DOMAIN filter (D-01..D-10)
          const objDomains = new Set();
          (DATA.objectives || []).forEach(o => {
            if (o.subdomain) objDomains.add(o.subdomain.split('.')[0]);
          });
          addFilterGroup(sb, 'DOMAIN',
            [...objDomains].sort().map(d => [d, d]),
            'domain');
          // REGULATION filter (HL + each reg)
          const objRegs = new Set();
          (DATA.objectives || []).forEach(o => {
            if (o.regulation) objRegs.add(o.regulation);
          });
          // Include canonical regulations from DATA.regulations too
          const allRegs = new Set([...objRegs, ...DATA.regulations.map(r => r.id)]);
          addFilterGroup(sb, 'REGULATION',
            DATA.regulations.filter(r => allRegs.has(r.id)).map(r => [r.id, r.displayName || r.id]),
            'regulation');
          // SO TYPE filter (HL + sub-SO from new data)
          addFilterGroup(sb, 'SO TYPE', [
            ['HL', 'High-Level'],
            ['sub-SO', 'Per-Reg Sub-SO'],
          ], 'kind');
          // SUBDOMAIN filter (D-XX.Y from objectives)
          const objSubs = new Set();
          (DATA.objectives || []).forEach(o => {
            if (o.subdomain) objSubs.add(o.subdomain);
          });
          addFilterGroup(sb, 'SUBDOMAIN',
            [...objSubs].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).map(s => [s, s]),
            'subdomain');
          break;
        case 'srs':
          // CORR-093: source = DATA.securityRequirements
          // DOMAIN filter
          const srDomains = new Set();
          (DATA.securityRequirements || []).forEach(r => {
            if (r.subdomain) srDomains.add(r.subdomain.split('.')[0]);
          });
          addFilterGroup(sb, 'DOMAIN',
            [...srDomains].sort().map(d => [d, d]),
            'domain');
          // SUBDOMAIN filter
          const srSubs = new Set();
          (DATA.securityRequirements || []).forEach(r => {
            if (r.subdomain) srSubs.add(r.subdomain);
          });
          addFilterGroup(sb, 'SUBDOMAIN',
            [...srSubs].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).map(s => [s, s]),
            'subdomain');
          // LEVEL filter
          addFilterGroup(sb, 'LEVEL', [
            ['HL', 'High-Level'],
            ['sub', 'Sub-Req'],
          ], 'level');
          break;
        case 'crossregulation':
          // CORR-092: DOMAIN filter (D-01..D-10)
          const crDomains = new Set();
          Object.values(DATA.crossregulation || {}).forEach(s => {
            Object.keys(s.sub_subdomains || {}).forEach(ssId => {
              const dom = (ssId || '').split('.')[0];
              if (dom) crDomains.add(dom);
            });
          });
          addFilterGroup(sb, 'DOMAIN',
            [...crDomains].sort().map(d => [d, d]),
            'domain');
          // SUBDOMAIN filter (D-XX.Y) — only those with data
          const crSubs = new Set();
          Object.values(DATA.crossregulation || {}).forEach(s => {
            Object.keys(s.sub_subdomains || {}).forEach(ssId => crSubs.add(ssId));
          });
          addFilterGroup(sb, 'SUBDOMAIN',
            [...crSubs].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).map(s => [s, s]),
            'subdomain');
          break;
      }

      // Reset button — always present
      const reset = document.createElement('button');
      reset.textContent = 'Reset filters';
      reset.style.cssText = 'margin-top:20px;width:100%;padding:8px;background:transparent;color:var(--accent);border:1px solid var(--accent);border-radius:6px;cursor:pointer;font-size:12px';
      reset.addEventListener('click', () => {
        STATE.search = '';
        STATE.filters = {};
        rebuildSidebar();
        applyAllFilters();
      });
      sb.appendChild(reset);
    }

    function addFilterGroup(parent, title, options, filterKey) {
      const group = document.createElement('div');
      group.style.cssText = 'margin-bottom:16px';
      const head = document.createElement('div');
      head.textContent = title;
      head.style.cssText = 'font-size:11px;font-weight:600;letter-spacing:1px;color:var(--fg-dim);margin-bottom:6px';
      group.appendChild(head);
      options.forEach(([val, label]) => {
        const lbl = document.createElement('label');
        lbl.style.cssText = 'display:flex;align-items:center;gap:6px;font-size:12px;padding:3px 0;cursor:pointer;color:var(--fg)';
        const checked = STATE.filters[filterKey] && STATE.filters[filterKey].has(val) ? 'checked' : '';
        lbl.innerHTML = `<input type="checkbox" data-filter="${filterKey}" data-value="${escapeHtml(String(val))}" ${checked} /> <span>${escapeHtml(String(label))}</span>`;
        lbl.querySelector('input').addEventListener('change', e => {
          if (!STATE.filters[filterKey]) STATE.filters[filterKey] = new Set();
          if (e.target.checked) STATE.filters[filterKey].add(val);
          else STATE.filters[filterKey].delete(val);
          applyAllFilters();
        });
        group.appendChild(lbl);
      });
      parent.appendChild(group);
    }

    // ---- Apply ALL filters (search + sidebar) to active tab (CORR-077) ----
    function applyAllFilters() {
      if (STATE.activeTab === 'sos') {
        const trs = document.querySelectorAll('#tab-sos [data-entity-id]');
        const domainFilter = STATE.filters.domain || new Set();
        const regulationFilter = STATE.filters.regulation || new Set();
        const subdomainFilter = STATE.filters.subdomain || new Set();
        const kindFilter = STATE.filters.kind || new Set();
        trs.forEach(row => {
          const id = row.getAttribute('data-entity-id');
          const obj = (DATA.objectives || []).find(o => o.id === id);
          if (!obj) { row.style.display = 'none'; return; }
          const ssDomain = (obj.subdomain || '').split('.')[0];
          const matchesDomain = !domainFilter.size || domainFilter.has(ssDomain);
          const matchesReg = !regulationFilter.size || regulationFilter.has(obj.regulation);
          const matchesSub = !subdomainFilter.size || subdomainFilter.has(obj.subdomain);
          const matchesKind = !kindFilter.size || kindFilter.has(obj.kind);
          row.style.display = (matchesDomain && matchesReg && matchesSub && matchesKind) ? '' : 'none';
        });
        return;
      }
      if (STATE.activeTab === 'crossregulation') {
        // CORR-092: filter §5 by domain and subdomain
        const domainFilter = STATE.filters.domain || new Set();
        const subdomainFilter = STATE.filters.subdomain || new Set();
        // Iterate crossreg-block (10 subdomains) — hide if domain filter excludes
        document.querySelectorAll('#main-content .crossreg-block').forEach(block => {
          const subId = (block.querySelector('h3')?.textContent || '').split('—')[0].trim();
          const matchesDomain = !domainFilter.size || domainFilter.has(subId);
          block.style.display = matchesDomain ? '' : 'none';
        });
        // Iterate sub-subdomain <details> (crossreg-sub) — hide if domain or subdomain filter excludes
        document.querySelectorAll('#main-content .crossreg-sub').forEach(ss => {
          const ssIdEl = ss.querySelector('summary > strong');
          const ssId = ssIdEl ? ssIdEl.textContent.trim() : '';
          const ssDomain = ssId.split('.')[0];
          const matchesDomain = !domainFilter.size || domainFilter.has(ssDomain);
          const matchesSubdomain = !subdomainFilter.size || subdomainFilter.has(ssId);
          ss.style.display = (matchesDomain && matchesSubdomain) ? '' : 'none';
        });
        return;
      }

      if (STATE.activeTab === 'srs') {
        const trs = document.querySelectorAll('#tab-srs [data-entity-id]');
        const domainFilter = STATE.filters.domain || new Set();
        const subdomainFilter = STATE.filters.subdomain || new Set();
        const levelFilter = STATE.filters.level || new Set();
        trs.forEach(row => {
          const id = row.getAttribute('data-entity-id');
          const req = (DATA.securityRequirements || []).find(r => r.id === id);
          if (!req) { row.style.display = 'none'; return; }
          const ssDomain = (req.subdomain || '').split('.')[0];
          const matchesDomain = !domainFilter.size || domainFilter.has(ssDomain);
          const matchesSub = !subdomainFilter.size || subdomainFilter.has(req.subdomain);
          const matchesLevel = !levelFilter.size || levelFilter.has(req.level);
          row.style.display = (matchesDomain && matchesSub && matchesLevel) ? '' : 'none';
        });
        return;
      }

      let dataArr = [];
      switch (STATE.activeTab) {
        case 'regulations': dataArr = DATA.regulations; break;
        case 'articles':    dataArr = DATA.articles; break;
        case 'clauses':     dataArr = DATA.clauses; break;
        case 'srs':         dataArr = DATA.srs; break;
      }

      const filtered = dataArr.filter(item => {
        // Search filter — matches across all fields
        if (STATE.search && STATE.search.trim()) {
          const q = STATE.search.toLowerCase().trim();
          const haystack = JSON.stringify(item).toLowerCase();
          if (!haystack.includes(q)) return false;
        }
        // Tab-specific filters
        for (const [key, valSet] of Object.entries(STATE.filters)) {
          if (!valSet || valSet.size === 0) continue;
          if (key === 'hideSkeleton') {
            const isSkel = item.is_skeleton === true || item.isSkeleton === true;
            if (valSet.has('true') && isSkel) return false;
            continue;
          }
          const itemVal = item[key];
          let matches = false;
          if (Array.isArray(itemVal)) {
            for (const v of itemVal) {
              if (valSet.has(String(v)) || valSet.has(v)) { matches = true; break; }
            }
          } else if (itemVal != null) {
            if (valSet.has(String(itemVal)) || valSet.has(itemVal)) matches = true;
          }
          if (!matches) return false;
        }
        return true;
      });

      // Hide rows in DOM that don't match
      const pane = document.querySelector(`#tab-${STATE.activeTab}`);
      if (!pane) return;
      const allRows = pane.querySelectorAll('[data-entity-id]');
      const visibleIds = new Set(filtered.map(e => e.id || e._id));
      allRows.forEach(row => {
        const rowId = row.getAttribute('data-entity-id');
        row.style.display = visibleIds.has(rowId) ? '' : 'none';
      });
    }

    // ---- Tab switching (CORR-077) ----
    function switchTab(tabName) {
      STATE.activeTab = tabName;
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
      });
      document.querySelectorAll('#main-content > .tab-pane').forEach(pane => {
        pane.style.display = (pane.dataset.pane === tabName) ? 'block' : 'none';
      });
      STATE.search = '';
      STATE.filters = {};
      rebuildSidebar();
      applyAllFilters();
    }

    // ---- Section renderers (CORR-077: add data-entity-id) ----
    function renderRegs() {
      const cards = DATA.regulations.map(r => {
        const st = r.stats || {};
        return `
          <div class="reg-card" data-detail-kind="regulation" data-detail-id="${r.id}" data-entity-id="${r.id}">
            <div class="strip" style="background:${r.color}"></div>
            <div>
              <div class="name">${r.displayName}</div>
              <div class="focus">${escapeHtml(r.title || '')}</div>
              <div class="stats-line">
                <span><b>${st.articles}</b> articles</span>
                <span><b>${st.clauses}</b> clauses</span>
                <span><b>${st.sos}</b> SOs</span>
                <span><b>${st.srs}</b> SRs</span>
              </div>
            </div>
            <div class="doc-id">${escapeHtml(r.docId || '')}</div>
          </div>`;
      });
      document.getElementById('regs-cards').innerHTML = cards.join('');
    }

    function renderArticles() {
      const rows = DATA.articles.map(a => `
          <tr data-detail-kind="article" data-detail-id="${a.id}" data-entity-id="${a.id}">
            <td><span class="cell-id">${a.id}</span></td>
            <td><span class="reg-tag" style="background:${DATA.regColors[a.regulation]}">${a.regulation}</span></td>
            <td>${escapeHtml(a.articleRef || '')}</td>
            <td><div class="preview">${escapeHtml(a.title || '')}</div></td>
            <td>${(a.securityObjectives || []).length}</td>
            <td>${a.securityRuleCount || 0}</td>
            <td>${escapeHtml(a.status || '')}</td>
          </tr>`).join('');
      document.getElementById('tbody-articles').innerHTML = rows;
    }

    function renderClauses() {
      const rows = DATA.clauses.map(c => {
        // CORR-078 (C11/C12): 4 boolean columns VAG/POLY/COORD/SCOPE-Q.
        // Union of types_found[] + instances[].label drives each indicator.
        const tf = c.typesFound || [];
        const instLabels = (c.instances || []).map(i => i.label).filter(Boolean);
        const allTypes = new Set([...tf, ...instLabels]);
        const cell = (cat) => allTypes.has(cat)
          ? '<span class="berry-on">●</span>'
          : '<span class="berry-off">○</span>';
        return `
          <tr data-detail-kind="clause" data-detail-id="${c.id}" data-entity-id="${c.id}" class="${c.isSkeleton ? 'skeleton' : ''}">
            <td><span class="cell-id">${c.id}${c.isSkeleton ? '<span class="skel-tag">skel</span>' : ''}</span></td>
            <td><span class="reg-tag" style="background:${DATA.regColors[c.regulation]}">${c.regulation}</span></td>
            <td>${escapeHtml(c.sectionRef || '')}</td>
            <td><div class="preview">${escapeHtml(c.title || '')}</div></td>
            <td>${cell('VAG')}</td>
            <td>${cell('POLY')}</td>
            <td>${cell('COORD')}</td>
            <td>${cell('SCOPE-Q')}</td>
            <td>${c.severity ? `<span class="severity ${c.severity}">${c.severity}</span>` : '—'}</td>
            <td>${c.isSkeleton ? 'yes' : ''}</td>
          </tr>`;
      }).join('');
      document.getElementById('tbody-clauses').innerHTML = rows;
    }

    function renderSos() {
      const list = DATA.objectives || DATA.sos || [];
      const rows = list.map(s => {
        const reg = s.regulation || 'HL';
        const regColor = (reg && reg !== 'HL' && DATA.regColors && DATA.regColors[reg])
          ? DATA.regColors[reg]
          : (reg === 'HL' ? '#a8e6cf' : '#8b95a7');
        const preview = s.objective || s.yamlRaw || '';
        const status = (s.yaml && s.yaml.status) || 'static';
        return `
          <tr data-detail-kind="objective" data-detail-id="${s.id}" data-entity-id="${s.id}">
            <td><span class="cell-id">${s.id}</span></td>
            <td><span class="type-badge ${s.kind === 'HL' ? 'HL' : 'sub-SO'}">${s.kind}</span>${s.phantom ? '<span class="phantom-badge" title="CORR-030 propagated phantom (unique id assigned)">phantom</span>' : ''}</td>
            <td><span class="reg-tag" style="background:${regColor}">${escapeHtml(reg)}</span></td>
            <td><span class="cell-id-sm">${escapeHtml(s.subdomain || '')}</span></td>
            <td><div class="preview">${escapeHtml((preview || '').slice(0, 200))}${(preview || '').length > 200 ? '…' : ''}</div></td>
            <td>${escapeHtml(status)}</td>
          </tr>`;
      }).join('');
      document.getElementById('tbody-sos').innerHTML = rows;
    }

    // ---- CORR-080: §5 Cross-Regulation (raw MD, NOT JSON entities) ----
    function renderCrossRegulation() {
      const data = DATA.crossregulation || {};
      const stats = DATA.crossregulation_stats || {};
      const statsEl = document.getElementById('crossregulation-stats');
      if (statsEl) {
        statsEl.textContent =
          `${stats.subdomains || 0} subdomains, ${stats.sub_subdomains || 0} sub-subdomains, ` +
          `${stats.pairs_total || 0} pairs`;
      }
      const blocksEl = document.getElementById('crossregulation-blocks');
      if (!blocksEl) return;
      const toggleBar = `
        <div class="crossreg-toggle-bar">
          <button onclick="document.querySelectorAll('#crossregulation-blocks details').forEach(d => d.open = true)">▾ Expand all</button>
          <button onclick="document.querySelectorAll('#crossregulation-blocks details').forEach(d => d.open = false)">▸ Collapse all</button>
        </div>`;
      // CORR-090: pair card accent by relationship family
      const PAIR_REL_COLORS = {
        'SAME': '#4caf50',
        'COMPLEMENTARY': '#ffd93d',
        'SCOPE-DISJOINT': '#8b95a7',
        'CONDITIONAL': '#ff9800',
        'N typically': '#8b95a7',
      };
      const pairRelColor = (rel) => {
        if (!rel) return '#8b95a7';
        const upper = rel.toUpperCase();
        for (const k of Object.keys(PAIR_REL_COLORS)) {
          if (upper.startsWith(k)) return PAIR_REL_COLORS[k];
        }
        return '#8b95a7';
      };
      // CORR-090: pair accent class (border-left color) by relationship family
      const PAIR_REL_ACCENT = {
        'SAME': 'green',
        'COMPLEMENTARY': 'yellow',
        'SCOPE-DISJOINT': 'cyan',
        'CONDITIONAL': 'orange',
        'N': 'red',
      };
      const pairRelAccent = (rel) => {
        if (!rel) return 'purple';
        const upper = rel.toUpperCase();
        for (const k of Object.keys(PAIR_REL_ACCENT)) {
          if (upper.startsWith(k)) return PAIR_REL_ACCENT[k];
        }
        return 'purple';
      };

      // CORR-099 (Part 3): global-only-once methodology headings. The SubDomains
      // MDs copy-paste certain boilerplate (e.g. "Verbatim OJ text sourcing")
      // across sub-subdomains; render it just once across the whole §5 panel.
      const GLOBAL_ONCE = new Set(['Verbatim OJ text sourcing']);
      const _globalSeen = new Set();
      const isGlobalDuplicate = (heading) => {
        if (!GLOBAL_ONCE.has(heading)) return false;
        if (_globalSeen.has(heading)) return true;
        _globalSeen.add(heading);
        return false;
      };

      const html = Object.entries(data).map(([subId, sub]) => {
        const subsHtml = Object.entries(sub.sub_subdomains || {}).map(([ssId, ss]) => {
          const parsed = ss.parsed || { intro_md: '', pairs: [], notes_md: '' };
          const lineCount = (ss.md || '').split('\n').length;
          // CORR-097: pair shows ONLY its own body_md (no shared sub-subdomain DA).
          // SR mention count via regex on body_md (clauses are not present in pair bodies).
          const SR_MENTION_RE = /SR-[A-Z_]+-\d+/g;
          const pairBlocks = (parsed.pairs || []).map((p, idx) => {
            const color = pairRelColor(p.verified_relationship);
            const accent = pairRelAccent(p.verified_relationship);
            const srCount = ((p.body_md || '').match(SR_MENTION_RE) || []).length;
            return `
              <details class="crossreg-card accent-${accent}">
                <summary class="pair-header">
                  <span class="pair-pair">${escapeHtml(p.reg_a)} ↔ ${escapeHtml(p.reg_b)}</span>
                  <span class="pair-rel" style="background:${color}; color:#0f1419">${escapeHtml(p.verified_relationship || '?')}</span>
                  ${p.scope_overlap && p.scope_overlap !== '?' ? `<span class="pair-scope">scope ${escapeHtml(p.scope_overlap)}</span>` : ''}
                  ${srCount > 0 ? `<span class="pair-srs">SRs:${srCount}</span>` : ''}
                </summary>
                <div class="card-content">${mdToHtml(p.body_md)}</div>
              </details>`;
          }).join('');
          // CORR-097: hoist DomainAnalysis out of the pair loop — render ONCE per sub-subdomain.
          // CORR-099 (Lacuna 2): render DA as structured #### toggles when available.
          const daSections = ss.da_sections || [];
          const daInner = daSections.length
            ? daSections.map(ds => ds.heading
                ? `<details class="crossreg-card"><summary>${escapeHtml(ds.heading)}</summary><div class="card-content">${mdToHtml(ds.body_md)}</div></details>`
                : `<div class="card-content">${mdToHtml(ds.body_md)}</div>`
              ).join('')
            : (ss.domainAnalysisMd ? mdToHtml(ss.domainAnalysisMd) : '');
          const domainAnalysisSection = daInner
            ? `<details class="crossreg-card"><summary>DomainAnalysis</summary><div class="card-content">${daInner}</div></details>`
            : '';
           const introSection = parsed.intro_md
             ? `<div class="crossreg-intro">${mdToHtml(parsed.intro_md)}</div>`
             : '';
           const notesSection = parsed.notes_md
             ? `<details class="crossreg-card"><summary>Methodology notes</summary><div class="card-content">${mdToHtml(parsed.notes_md)}</div></details>`
             : '';
           const summary = ss.summary || {};
           const SUMMARY_CARDS = [
             { key: 'emergent_tensions_md', label: 'Emergent tensions', accent: 'orange' },
             { key: 'validated_relationships_md', label: 'SR cross-validation', accent: 'cyan' },
             { key: 'downstream_implication_md', label: 'Downstream implication (Phase 1C Doc 07)', accent: 'green' },
           ];
           const summaryCardsHtml = SUMMARY_CARDS
             .filter(c => summary[c.key] && summary[c.key].length > 50)
             .map(c => `
               <details class="crossreg-card accent-${c.accent}">
                 <summary><span class="summary-label">${c.label}</span></summary>
                 <div class="card-content">${mdToHtml(summary[c.key])}</div>
               </details>`).join('');
           const summarySection = summaryCardsHtml
             ? `<div class="sub-summary"><h4>Sub-domain summary</h4>${summaryCardsHtml}</div>`
             : '';
           // CORR-090: render Sub-domain methodology as nested .crossreg-card toggles
           const methodologyHtml = (ss.methodology || [])
             .filter(m => !isGlobalDuplicate(m.heading))
             .map(m => {
             const h2cls = m.is_h2 ? ' meth-h2' : '';
             const soBadge = m.is_so ? '<span class="so-badge" title="Security Objective section">SO</span>' : '';
             const h2Badge = m.is_h2 ? '<span class="h2-badge" title="Top-level wrapper section">H2</span>' : '';
             return `
             <details class="crossreg-card${h2cls}">
               <summary>${escapeHtml(m.heading)}${soBadge}${h2Badge}</summary>
               <div class="card-content">${mdToHtml(m.body_md)}</div>
             </details>`;
           }).join('');
           const methodologySection = methodologyHtml
              ? `<details class="crossreg-card">
                <summary>Sub-domain methodology (${(ss.methodology || []).length} sections)</summary>
                <div class="card-content">${methodologyHtml}</div>
              </details>`
              : '';
           return `
             <div class="crossreg-sub">
               <details class="crossreg-card">
                 <summary><strong>${escapeHtml(ssId)}</strong> — ${escapeHtml(ss.title || '')} <span class="meta">(${parsed.pairs?.length || 0} pairs · ${lineCount} lines · source: <code>${escapeHtml(ss.filename || '')}</code>)</span></summary>
                 <div class="card-content">
                   ${introSection}
                   ${domainAnalysisSection}
                   <div class="pair-grid">${pairBlocks || '<p style="color:var(--fg-dim); font-size:11px">No pairs extracted.</p>'}</div>
                   ${summarySection}
                   ${methodologySection}
                   ${notesSection}
                 </div>
               </details>
             </div>`;


        }).join('');
        return `
          <div class="crossreg-block">
            <h3>${escapeHtml(subId)} — ${escapeHtml(sub.title || '')}</h3>
            ${subsHtml}
          </div>`;
      }).join('');
      blocksEl.innerHTML = toggleBar + (html || '<p style="color:var(--fg-dim)">No cross-regulation MDs found in <code>CrossRegulation/DeepAnalysis/</code>.</p>');
    }

    function renderSrs() {
      const reqs = DATA.securityRequirements || [];
      // Group by HL parent
      const byParent = {};
      reqs.forEach(r => {
        const key = r.level === 'HL' ? r.id : `${r.subdomain}/${r.parent_id}`;
        if (!byParent[key]) byParent[key] = { hl: null, subs: [] };
        if (r.level === 'HL') byParent[key].hl = r;
        else byParent[key].subs.push(r);
      });
      // Sort by subdomain then req_id
      const sortedKeys = Object.keys(byParent).sort((a, b) => a.localeCompare(b, undefined, {numeric: true}));
      const rows = sortedKeys.map(parentKey => {
        const { hl, subs } = byParent[parentKey];
        if (!hl) return '';
        // Extract title from yaml
        const titleM = hl.yaml.match(/title:\s*"?([^"\n]+)"?/);
        const title = titleM ? titleM[1].trim() : (hl.req_id);
        // Extract nist_csf
        const nistM = hl.yaml.match(/nist_csf:\s*\[([^\]]+)\]/);
        const nist = nistM ? nistM[1].replace(/[\[\]"]/g, '').split(',').map(s => s.trim()).join(' ') : '—';
        // Extract priority
        const prioM = hl.yaml.match(/priority:\s*(\S+)/);
        const priority = prioM ? prioM[1] : '—';
        const hlRow = `
          <tr data-detail-kind="requirement" data-detail-id="${hl.id}" data-entity-id="${hl.id}" data-level="HL">
            <td><span class="cell-id">${escapeHtml(hl.req_id)}</span></td>
            <td><span class="type-badge HL">HL</span></td>
            <td><span class="reg-tag" style="background:#a8e6cf; color:#0f1419">${escapeHtml(hl.subdomain)}</span></td>
            <td><div class="preview">${escapeHtml(title)}</div></td>
            <td><div class="meta">${escapeHtml(nist)}</div></td>
            <td>${escapeHtml(priority)}</td>
            <td><div class="meta">${subs.length} sub</div></td>
          </tr>`;
        const subRows = subs.map(s => {
          const subTitleM = s.yaml.match(/title:\s*"?([^"\n]+)"?/);
          const subTitle = subTitleM ? subTitleM[1].trim() : s.title;
          const subNistM = s.yaml.match(/nist_csf:\s*\[([^\]]+)\]/);
          const subNist = subNistM ? subNistM[1].replace(/[\[\]"]/g, '').split(',').map(x => x.trim()).join(' ') : '—';
          const subPrioM = s.yaml.match(/priority:\s*(\S+)/);
          const subPriority = subPrioM ? subPrioM[1] : '—';
          return `
            <tr data-detail-kind="requirement" data-detail-id="${s.id}" data-entity-id="${s.id}" data-level="sub" class="sub-req-row">
              <td><span class="cell-id-sm">↳ ${escapeHtml(s.req_id)}</span></td>
              <td><span class="type-badge sub">sub</span></td>
              <td><span class="cell-id-sm">${escapeHtml(s.subdomain)}</span></td>
              <td><div class="preview">${escapeHtml(subTitle)}</div></td>
              <td><div class="meta">${escapeHtml(subNist)}</div></td>
              <td>${escapeHtml(subPriority)}</td>
              <td>—</td>
            </tr>`;
        }).join('');
        return hlRow + subRows;
      }).join('');
      document.getElementById('tbody-srs').innerHTML = rows || '<tr><td colspan="7" style="color:var(--fg-dim)">No security requirements loaded.</td></tr>';
    }

    // ---- Detail panel: render arbitrary object as dl grid ----
    function renderField(val, key, depth) {
      depth = depth || 0;
      const t = typeof val;
      if (val === null) return '<span class="null">null</span>';
      if (val === undefined) return '<span class="null">undefined</span>';
      if (t === 'string') return `<span class="string">${escapeHtml(val.length > 600 ? val.slice(0, 600) + '…' : val)}</span>`;
      if (t === 'number') return `<span class="num">${val}</span>`;
      if (t === 'boolean') return `<span class="bool ${val}">${val}</span>`;
      if (Array.isArray(val)) {
        if (val.length === 0) return '<span class="null">[empty]</span>';
        const items = val.map((it, i) => {
          if (it && typeof it === 'object') {
            const preview = it.text || it.title || it.id || it.name || it.label || null;
            const summary = preview ? `<strong>${escapeHtml(String(preview).slice(0, 60))}</strong>` : `<em>item ${i+1}</em>`;
            return `<div class="item">${summary}<div class="nested">${renderFields(it, depth + 1)}</div></div>`;
          }
          return `<div class="item">${escapeHtml(String(it))}</div>`;
        }).join('');
        return `<details open><summary>Array (${val.length})</summary>${items}</details>`;
      }
      if (t === 'object') {
        const keys = Object.keys(val);
        if (keys.length === 0) return '<span class="null">{}</span>';
        if (depth >= 3) return `<span class="deeper">deeper: ${keys.length} keys (${keys.slice(0, 3).join(', ')}${keys.length>3?'…':''})</span>`;
        return `<div class="nested">${renderFields(val, depth + 1)}</div>`;
      }
      return `<span class="string">${escapeHtml(String(val))}</span>`;
    }

    function renderFields(obj, depth) {
      depth = depth || 0;
      const keys = Object.keys(obj);
      if (keys.length === 0) return '<em style="color:var(--fg-dim)">empty</em>';
      return keys.map(k => {
        const v = obj[k];
        const isLong = (typeof v === 'string' && v.length > 280) || LONG_FIELDS.has(k);
        const key = `<dt class="field-key">${escapeHtml(k)}</dt>`;
        let val;
        if (isLong && typeof v === 'string') {
          val = `
            <details class="narrative">
              <summary>${shortText(v, 80)} <span class="narrative-hint">[${v.length} chars — expand]</span></summary>
              <div class="body">${escapeHtml(v)}</div>
            </details>`;
        } else {
          val = renderField(v, k, depth);
        }
        return `<div class="field">${key}<dd class="field-val">${val}</dd></div>`;
      }).join('');
    }

    // ---- CORR-079: Tab switching ----
    function switchDetailTab(name) {
      STATE.activeDetailTab = name;
      document.querySelectorAll('.detail-tabs .detail-tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === name);
      });
      document.querySelectorAll('.detail-tab-body .tab-pane').forEach(p => {
        p.hidden = p.dataset.pane !== name;
      });
    }

    // ---- CORR-079: Markdown renderer ----
    function mdToHtml(md) {
      if (!md) return '';
      let h = md.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      h = h.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code class="language-$1">$2</code></pre>');
      h = h.replace(/^###### (.+)$/gm, '<h6>$1</h6>');
      h = h.replace(/^##### (.+)$/gm, '<h5>$1</h5>');
      h = h.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
      h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
      h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
      h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
      h = h.replace(/^---+$/gm, '<hr>');
      h = h.replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>');
      h = h.replace(/\*(.+?)\*/gs, '<em>$1</em>');
      h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
      h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
      h = h.replace(/((?:^|\n)\|[^\n]+\|\n\|[-:|\s]+\|(?:\n\|[^\n]+\|)+)/g, (table) => {
        const rows = table.trim().split('\n');
        if (rows.length < 2) return table;
        const headerCells = rows[0].split('|').slice(1, -1).map(c => `<th>${c.trim()}</th>`).join('');
        const bodyRows = rows.slice(2).map(r => {
          const cells = r.split('|').slice(1, -1).map(c => `<td>${c.trim()}</td>`).join('');
          return `<tr>${cells}</tr>`;
        }).join('');
        return `<table><thead><tr>${headerCells}</tr></thead><tbody>${bodyRows}</tbody></table>`;
      });
      h = h.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
      h = h.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
      h = h.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
      h = h.split(/\n\n+/).map(para => {
        para = para.trim();
        if (!para || para.startsWith('<')) return para;
        return `<p>${para.replace(/\n/g, '<br>')}</p>`;
      }).join('\n');
      return h;
    }

    // ---- CORR-079: Context tab renderer ----
    function renderContext(obj) {
      const parts = [];
      // CORR-079 (size opt): regulation MD files are recorded as size ints
      // (rawReadme / raw01Size / raw02Size / rawValidationSize / rawAuditSize)
      // — full content dropped from the JSON payload. rawReadme content is
      // used directly by the Markdown tab, so it's the only one embedded.
      const mdFields = obj.rawReadme !== undefined
        ? [
            ['rawReadme', '00_README.md', obj.rawReadme.length],
            ['raw01Size', '01_SecurityObjectives.md', obj.raw01Size],
            ['raw02Size', '02_SecurityRules_NIST.md', obj.raw02Size],
            ['rawValidationSize', '03_validation_report.md', obj.rawValidationSize],
            ['rawAuditSize', '04_deduction_audit.md', obj.rawAuditSize],
          ].filter(([_, _2, size]) => size > 0)
        : [];
      if (mdFields.length > 0) {
        parts.push('<h4>Methodology MD files</h4>');
        parts.push('<ul>');
        for (const [_f, label, size] of mdFields) {
          parts.push(`<li><code>${label}</code> — ${size.toLocaleString()} chars</li>`);
        }
        parts.push('</ul>');
      }
      const cr = obj.crossRefs;
      if (cr && (cr.sos?.length || cr.srs?.length || cr.clauses?.length)) {
        parts.push('<h4>Cross-references</h4>');
        if (cr.sos?.length) parts.push(`<p><strong>SOs (${cr.sos.length}):</strong> ${cr.sos.slice(0, 30).map(s => `<code>${escapeHtml(s)}</code>`).join(', ')}${cr.sos.length > 30 ? '…' : ''}</p>`);
        if (cr.srs?.length) parts.push(`<p><strong>SRs (${cr.srs.length}):</strong> ${cr.srs.slice(0, 30).map(s => `<code>${escapeHtml(s)}</code>`).join(', ')}${cr.srs.length > 30 ? '…' : ''}</p>`);
        if (cr.clauses?.length) parts.push(`<p><strong>Clauses (${cr.clauses.length}):</strong> ${cr.clauses.slice(0, 30).map(s => `<code>${escapeHtml(s)}</code>`).join(', ')}${cr.clauses.length > 30 ? '…' : ''}</p>`);
      } else if (obj.crossRefs !== undefined) {
        parts.push('<p style="color:var(--fg-dim)">No cross-references found.</p>');
      }
      if (obj.source) {
        parts.push('<h4>Source file</h4>');
        parts.push(`<p><code>${escapeHtml(obj.source)}</code></p>`);
      }
      return parts.join('\n') || '<p style="color:var(--fg-dim)">No context available for this entity.</p>';
    }

    function showDetail(kind, id) {
      const el = document.getElementById('detail');
      let obj = null;
      if (kind === 'regulation') {
        obj = DATA.regulations.find(r => r.id === id);
      } else if (kind === 'article') {
        obj = DATA.articles.find(a => a.id === id);
      } else if (kind === 'clause') {
        obj = DATA.clauses.find(c => c.id === id);
      } else if (kind === 'objective' || kind === 'so') {
        const list = DATA.objectives || DATA.sos || [];
        obj = list.find(s => s.id === id);
      } else if (kind === 'requirement' || kind === 'sr') {
        obj = (DATA.securityRequirements || DATA.srs || []).find(s => s.id === id);
      } else if (kind === 'csf') {
        obj = { id: id, kind: 'csf', title: 'NIST CSF 2.0 subcategory', csfColors: DATA.csfColors, csfId: id, function: csfFunctionOf(id) };
      }
      if (!obj) {
        el.innerHTML = `<div class="empty">Entity "${id}" not found.</div>`;
        return;
      }
      const kindLabel = ({regulation: 'Regulation', article: 'Article', clause: 'Clause', so: 'SO', objective: 'Objective', sr: 'SR', csf: 'CSF'})[kind] || kind;
      // CORR-079: render all 4 tabs
      const renderedPane = el.querySelector('.tab-pane[data-pane="rendered"]');
      const jsonPane = el.querySelector('.tab-pane[data-pane="json"]');
      const mdPane = el.querySelector('.tab-pane[data-pane="markdown"]');
      const ctxPane = el.querySelector('.tab-pane[data-pane="context"]');

      renderedPane.innerHTML = `
        <h2><span class="kind">${kindLabel}</span>${escapeHtml(obj.id)}</h2>
        <div class="meta">${renderMetaPills(kind, obj)}</div>
        <dl>${renderFields(obj)}</dl>
      `;

      // CORR-093: rich rendered tab for hierarchical security requirements
      if (kind === 'requirement') {
        const yamlHtml = obj.yaml
          ? `<pre class="code-block"><code class="language-yaml">${escapeHtml(obj.yaml)}</code></pre>`
          : '';
        const descM = obj.yaml.match(/description:\s*\|?\s*\n([\s\S]+?)(?=\n[a-z_]+:|\Z)/);
        const desc = descM ? descM[1].replace(/^  /gm, '').trim() : '';
        const considerationsM = obj.yaml.match(/considerations:\s*\|?\s*\n([\s\S]+?)(?=\n[a-z_]+:|\Z)/);
        const considerations = considerationsM ? considerationsM[1].replace(/^  /gm, '').trim() : '';
        renderedPane.innerHTML = `
          <h2><span class="kind">Requirement</span>${escapeHtml(obj.id)}</h2>
          <div class="meta">
            <span class="pill">${escapeHtml(obj.level)}</span>
            <span class="pill">${escapeHtml(obj.subdomain)}</span>
            ${obj.parent_id ? `<span class="pill">parent: ${escapeHtml(obj.parent_id)}</span>` : ''}
          </div>
          <h4>YAML</h4>
          ${yamlHtml}
          ${desc ? `<h4>Description</h4><pre>${escapeHtml(desc)}</pre>` : ''}
          ${considerations ? `<h4>Considerations</h4><pre>${escapeHtml(considerations)}</pre>` : ''}
          <hr>
          <details><summary>Raw MD</summary><pre>${escapeHtml(obj.raw_md || '')}</pre></details>
        `;
        mdPane.innerHTML = obj.raw_md ? mdToHtml(obj.raw_md) : '<p style="color:var(--fg-dim)">No markdown.</p>';
        ctxPane.innerHTML = renderContext(obj);
        return;
      }

      jsonPane.innerHTML = `<pre class="raw-json">${escapeHtml(JSON.stringify(obj, null, 2))}</pre>`;

      let md = obj.rawMd || obj.rawRow || obj.raw_md || obj.rawReadme || obj.raw01 || '';
      // CORR-091: for objective kind, synthesise MD from yaml + objective + considerations
      if (!md && (kind === 'objective' || (DATA.objectives && DATA.objectives.find(o => o.id === obj.id)))) {
        const objObj = DATA.objectives && DATA.objectives.find(o => o.id === obj.id);
        if (objObj) {
          md = '';
          if (objObj.yamlRaw) {
            md += '```yaml\n' + objObj.yamlRaw + '\n```\n\n';
          }
          if (objObj.objective) {
            md += '**Objective.** ' + objObj.objective + '\n\n';
          }
          if (objObj.considerations) {
            md += '**Considerations.**\n' + objObj.considerations;
          }
        }
      }
      mdPane.innerHTML = md
        ? mdToHtml(md)
        : '<p style="color:var(--fg-dim)">No markdown available for this entity.</p>';

      ctxPane.innerHTML = renderContext(obj);
      switchDetailTab(STATE.activeDetailTab || 'rendered');
    }

    function renderMetaPills(kind, obj) {
      const pills = [];
      if (obj.regulation) {
        const color = DATA.regColors[obj.regulation] || '#888';
        pills.push(`<span class="pill" style="background:${color}; color:#0f1419; font-weight:600">${obj.regulation}</span>`);
      }
      if (kind === 'article' && obj.articleRef) pills.push(`<span class="pill">${escapeHtml(obj.articleRef)}</span>`);
      if (kind === 'article' && obj.securityRuleCount != null) pills.push(`<span class="pill">${obj.securityRuleCount} SR(s)</span>`);
      if (kind === 'clause' && obj.sectionRef) pills.push(`<span class="pill">${escapeHtml(obj.sectionRef)}</span>`);
      if (kind === 'clause' && obj.type) pills.push(`<span class="pill">type: ${obj.type}</span>`);
      if (kind === 'clause' && obj.severity) pills.push(`<span class="pill">severity: ${obj.severity}</span>`);
      if (kind === 'clause' && obj.isSkeleton) pills.push(`<span class="pill">skeleton</span>`);
      if (kind === 'so' && obj.soType) pills.push(`<span class="pill">type: ${obj.soType}</span>`);
      if (kind === 'objective' && obj.kind) pills.push(`<span class="pill">kind: ${escapeHtml(obj.kind)}</span>`);
      if ((kind === 'objective' || kind === 'so') && obj.subdomain) pills.push(`<span class="pill">${escapeHtml(obj.subdomain)}</span>`);
      if (kind === 'sr' && obj.title) pills.push(`<span class="pill">${escapeHtml(shortText(obj.title, 80))}</span>`);
      if (kind === 'csf' && obj.function) {
        const c = DATA.csfColors[obj.function] || '#888';
        pills.push(`<span class="pill" style="background:${c}; color:#0f1419; font-weight:700">${obj.function}</span>`);
      }
      return pills.join('');
    }

    // ---- Field camelCase → snake_case for sr kinds (raw JSON keys) ----
    function normalizeSrKeys(obj) {
      if (!obj) return obj;
      return {
        ...obj,
        headingUnder: obj.heading_under,
        sourceClauses: obj.source_clauses,
        linkedObjectives: obj.linked_objectives,
        subDomain: obj.sub_domain,
        nistCsfMapping: obj.nist_csf_mapping,
        appliesToRole: obj.applies_to_role,
        obligationType: obj.obligation_type,
        regulatoryRationale: obj.regulatory_rationale,
        securityRationale: obj.security_rationale,
        ambiguityNotes: obj.ambiguity_notes,
        rawMd: obj.raw_md,
      };
    }

    // ---- Click delegation ----
    document.addEventListener('click', e => {
      // CSF chip
      const chip = e.target.closest('.csf-chip');
      if (chip) {
        e.stopPropagation();
        showDetail('csf', chip.dataset.csfId);
        return;
      }
      // Entity row / card
      const target = e.target.closest('[data-detail-kind]');
      if (target) {
        showDetail(target.dataset.detailKind, target.dataset.detailId);
      }
    });

    // ---- Init (CORR-077: tab-based) ----
    renderKpis();
    renderBanner();
    renderRegs();
    renderArticles();
    renderClauses();
    renderSos();
    // CORR-091: populate §4 stats subtitle
    (function() {
      const el = document.getElementById('objectives-stats');
      if (!el) return;
      const list = DATA.objectives || DATA.sos || [];
      const hl = list.filter(o => o.kind === 'HL').length;
      const sub = list.filter(o => o.kind === 'sub-SO').length;
      el.textContent = `${list.length} objectives (${hl} HL + ${sub} sub-SO)`;
    })();
    renderCrossRegulation();
    renderSrs();
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === STATE.activeTab);
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    rebuildSidebar();
    applyAllFilters();
    document.querySelectorAll('.detail-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => switchDetailTab(btn.dataset.tab));
    });
  })();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
