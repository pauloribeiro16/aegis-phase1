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
    """Build per-regulation summary + raw MD from Methodology-main/README + 01/02/03/04 + aggregated SOs/SRs.

    CORR-079 (WS1): extend to embed the 5 top-level MD files and aggregated
    SecurityObjectives/SecurityRules arrays so the Markdown and JSON tabs
    surface every bit of methodology context per regulation.
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

        # CORR-079 (WS1): read the 5 top-level methodology MDs (graceful fallback to "").
        method_reg_dir = METHODOLOGY_DIR / reg
        raw_readme = _read_text(method_reg_dir / "00_README.md")
        raw_01 = _read_text(method_reg_dir / "01_SecurityObjectives.md")
        raw_02 = _read_text(method_reg_dir / "02_SecurityRules_NIST.md")
        raw_validation = _read_text(method_reg_dir / "03_validation_report.md")
        raw_audit = _read_text(method_reg_dir / "04_deduction_audit.md")

        # CORR-079 (WS1): aggregated SOs/SRs are full dicts (vs the §4/§5 which only
        # render the headline fields). Embed them so the JSON tab exposes the same
        # payload the clause-shards and SR-shards have.
        aggregated_sos = sobj.get("sos", []) or []
        aggregated_srs = srobj.get("srs", []) or []

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
            "raw01": raw_01,
            "raw02": raw_02,
            "rawValidation": raw_validation,
            "rawAudit": raw_audit,
            "aggregatedSos": aggregated_sos,
            "aggregatedSrs": aggregated_srs,
            "stats": {
                "articles": article_count,
                "clauses": clause_count,
                "sos": sobj.get("count", len(aggregated_sos)),
                "srs": srobj.get("count", len(aggregated_srs)),
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

    CORR-079 (WS1): additionally preserve ``securityRules`` (full SR dicts),
    ``securityObjectivesFull`` (full SO dicts), ``source`` (path),
    ``inScopeArticlesReferenced``, ``rawMd`` (Articles/Art_NN.md content).
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

        # CORR-079 (WS1): preserve full SR / SO dicts (was stripped to IDs only)
        full_srs = list(arts) if isinstance(arts, list) else []
        full_sos = list(d.get("security_objectives") or [])

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
            "securityObjectivesFull": full_sos,
            "securityRuleCount": len(arts),
            "securityRuleIds": [sr.get("sr_id") for sr in arts],
            "securityRules": full_srs,
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
) -> str:
    """Build the full HTML string for the given data slices.

    CORR-078 (C11): supports programmatic invocation by tests — pass any
    subset of entity lists and an empty/inferred view is produced. Useful
    for unit-testing the §3 table layout without writing to disk.

    When invoked with ``articles=[]`` etc., the HTML still contains the
    column headers (``<th>VAG</th>`` etc.), which is what the C11 test
    command asserts against.
    """
    data = {
        "regulations": regulations if regulations is not None else [],
        "articles": articles if articles is not None else [],
        "clauses": clauses if clauses is not None else [],
        "sos": sos if sos is not None else [],
        "srs": srs if srs is not None else [],
        "stats": {
            "regulations": len(regulations or []),
            "articles": len(articles or []),
            "clauses": len(clauses or []),
            "sos": len(sos or []),
            "srs": len(srs or []),
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

    html = HTML_TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size / 1024
    print(f"Wrote {OUT_HTML} ({size_kb:.1f} KB)")
    print(f"  regs={len(regulations or [])} arts={len(articles or [])} "
          f"clauses={len(clauses or [])} sos={len(sos or [])} srs={len(srs or [])}")
    return html


def main():
    """CLI entry point — reads preproc_out/ shards and writes the HTML."""
    regs = load_regulations()
    articles = load_articles()
    clauses = load_clauses()
    sos = load_sos()
    srs = load_srs()
    build_html(
        regulations=regs,
        articles=articles,
        clauses=clauses,
        sos=sos,
        srs=srs,
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
    .detail-tabs { display: flex; gap: 4px; margin-bottom: 8px; border-bottom: 1px solid var(--border); }
    .detail-tab-btn { background: transparent; border: 1px solid transparent; border-bottom: none; color: var(--fg-dim); padding: 6px 12px; cursor: pointer; font-size: 12px; border-radius: 4px 4px 0 0; transition: background 0.15s, color 0.15s; }
    .detail-tab-btn:hover { background: var(--panel-2); color: var(--fg); }
    .detail-tab-btn.active { background: var(--panel); color: var(--accent); border-color: var(--border); }
    .detail-tab-body { padding: 0 4px; overflow-y: auto; max-height: calc(100vh - 240px); }
    .tab-pane[hidden] { display: none; }
    .raw-json { white-space: pre-wrap; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; background: var(--panel-2); padding: 8px; border-radius: 4px; max-height: 60vh; overflow: auto; }
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
    .type-badge.HL { background: rgba(249,244,157,0.20); border-color: var(--hl); color: var(--hl); }
    .type-badge.canonical { background: var(--panel-2); border-color: var(--border); color: var(--fg-dim); }
    .type-badge.VAG { color: var(--warn); }
    .type-badge.POLY { color: var(--accent-2); }
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
    <button class="tab-btn" data-tab="regulations">Regulations <span class="badge-count">5</span></button>
    <button class="tab-btn" data-tab="articles">Articles <span class="badge-count">140</span></button>
    <button class="tab-btn" data-tab="clauses">Clauses <span class="badge-count">498</span></button>
    <button class="tab-btn" data-tab="sos">SOs <span class="badge-count">328</span></button>
    <button class="tab-btn" data-tab="srs">SRs <span class="badge-count">282</span></button>
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
          <h2>§1 Regulations <small>5 cards</small></h2>
          <div class="section-meta">Per-reg preproc manifest: README + SecurityObjectives + SecurityRules_NIST. Click a card to inspect.</div>
          <div id="regs-cards"></div>
        </div>
      </div>

      <div id="tab-articles" class="tab-pane" data-pane="articles" style="display:none">
        <div id="section-2" data-section="2">
          <h2>§2 Articles <small>140 articles</small></h2>
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
          <h2>§3 Clauses <small>498 clauses (many skeleton)</small></h2>
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
          <h2>§4 SecurityObjectives <small>328 SOs (3 formats)</small></h2>
          <div class="section-meta">
            <span class="type-badge HL">HL</span> High-level (cross-reg) ·
            <span class="type-badge per-reg">per-reg</span> Per-reg subdomain ·
            <span class="type-badge canonical">canonical</span> Canonical
          </div>
          <table class="entity" id="table-sos">
            <thead>
              <tr>
                <th>ID</th><th>Type</th><th>Reg</th><th>Subdomain</th><th>Description</th>
              </tr>
            </thead>
            <tbody id="tbody-sos"></tbody>
          </table>
        </div>
      </div>

      <div id="tab-srs" class="tab-pane" data-pane="srs" style="display:none">
        <div id="section-5" data-section="5">
          <h2>§5 SecurityRules <small>282 SRs</small></h2>
          <div class="section-meta">Regulatory duties mapped to NIST CSF 2.0 controls. Click any row for full raw data (incl. regulatory_rationale, security_rationale, ambiguity_notes).</div>
          <table class="entity" id="table-srs">
            <thead>
              <tr>
                <th>ID</th><th>Title</th><th>Reg</th><th>Sub-domains</th><th>CSF</th><th>Role</th>
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
          addFilterGroup(sb, 'REGULATION', DATA.regulations.map(r => [r.id, r.displayName || r.id]), 'regulation');
          addFilterGroup(sb, 'SO TYPE', [
            ['HL', 'High-Level'],
            ['per-reg', 'Per-Reg'],
            ['canonical', 'Canonical'],
          ], 'soType');
          const sdSet = new Set();
          DATA.sos.forEach(s => s.subDomains && s.subDomains.forEach(x => sdSet.add(x)));
          const subs = [...sdSet].sort((a,b) => a.localeCompare(b, undefined, {numeric:true}));
          addFilterGroup(sb, 'SUBDOMAIN', subs.map(s => [s, s]), 'subdomain');
          break;
        case 'srs':
          addFilterGroup(sb, 'REGULATION', DATA.regulations.map(r => [r.id, r.displayName || r.id]), 'regulation');
          const srSd = new Set();
          DATA.srs.forEach(s => s.sub_domain && s.sub_domain.forEach(x => srSd.add(x)));
          const srsubs = [...srSd].sort((a,b) => a.localeCompare(b, undefined, {numeric:true}));
          addFilterGroup(sb, 'SUBDOMAIN', srsubs.map(s => [s, s]), 'subdomain');
          addFilterGroup(sb, 'CSF FUNCTION', [['GV','GV'],['ID','ID'],['PR','PR'],['DE','DE'],['RS','RS'],['RC','RC']], 'csfFunction');
          const roles = new Set();
          DATA.srs.forEach(s => s.applies_to_role && s.applies_to_role.forEach(r => roles.add(r)));
          addFilterGroup(sb, 'ROLE', [...roles].sort().map(r => [r, r]), 'role');
          const obls = new Set();
          DATA.srs.forEach(s => s.obligation_type && s.obligation_type.forEach(o => obls.add(o)));
          addFilterGroup(sb, 'OBLIGATION', [...obls].sort().map(o => [o, o]), 'obligation');
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
      let dataArr = [];
      switch (STATE.activeTab) {
        case 'regulations': dataArr = DATA.regulations; break;
        case 'articles':    dataArr = DATA.articles; break;
        case 'clauses':     dataArr = DATA.clauses; break;
        case 'sos':         dataArr = DATA.sos; break;
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
      const rows = DATA.sos.map(s => {
        const sub = (s.subDomains && s.subDomains.length) ? s.subDomains.join(', ')
                   : (s.subdomainId || s.sourceSubdomain || '');
        const preview = s.description || s.objective || '';
        return `
          <tr data-detail-kind="so" data-detail-id="${s.id}" data-entity-id="${s.id}">
            <td><span class="cell-id">${s.id}</span></td>
            <td><span class="type-badge ${s.soType}">${s.soType}</span></td>
            <td><span class="reg-tag" style="background:${DATA.regColors[s.regulation] || '#888'}">${s.regulation}</span></td>
            <td>${escapeHtml(sub || '')}</td>
            <td><div class="preview">${escapeHtml(shortText(preview, 100))}</div></td>
          </tr>`;
      }).join('');
      document.getElementById('tbody-sos').innerHTML = rows;
    }

    function renderSrs() {
      const rows = DATA.srs.map(sr => {
        const csfChips = (sr.nist_csf_mapping || []).map(c => {
          const fn = csfFunctionOf(c.id);
          return `<span class="csf-chip" style="background:${DATA.csfColors[fn] || '#888'}" data-csf-id="${c.id}">${c.id}</span>`;
        }).join('');
        const subs = (sr.sub_domain || []).join(', ');
        return `
          <tr data-detail-kind="sr" data-detail-id="${sr.id}" data-entity-id="${sr.id}">
            <td><span class="cell-id">${sr.id}</span></td>
            <td><div class="preview">${escapeHtml(sr.title || '')}</div></td>
            <td><span class="reg-tag" style="background:${DATA.regColors[sr.regulation]}">${sr.regulation}</span></td>
            <td>${escapeHtml(subs)}</td>
            <td><div class="chip-list">${csfChips}</div></td>
            <td>${escapeHtml((sr.applies_to_role || []).join(', '))}</td>
          </tr>`;
      }).join('');
      document.getElementById('tbody-srs').innerHTML = rows;
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
      h = h.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>');
      h = h.replace(/^###### (.+)$/gm, '<h6>$1</h6>');
      h = h.replace(/^##### (.+)$/gm, '<h5>$1</h5>');
      h = h.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
      h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
      h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
      h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
      h = h.replace(/^---+$/gm, '<hr>');
      h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
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
      const mdFields = [
        ['rawReadme', '00_README.md'],
        ['raw01', '01_SecurityObjectives.md'],
        ['raw02', '02_SecurityRules_NIST.md'],
        ['rawValidation', '03_validation_report.md'],
        ['rawAudit', '04_deduction_audit.md'],
      ];
      const mdItems = mdFields.filter(([f]) => (obj[f] || '').length > 0);
      if (mdItems.length > 0) {
        parts.push('<h4>Methodology MD files</h4>');
        parts.push('<ul>');
        for (const [f, label] of mdItems) {
          const size = (obj[f] || '').length;
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
      } else if (kind === 'so') {
        obj = DATA.sos.find(s => s.id === id);
      } else if (kind === 'sr') {
        obj = DATA.srs.find(s => s.id === id);
      } else if (kind === 'csf') {
        obj = { id: id, kind: 'csf', title: 'NIST CSF 2.0 subcategory', csfColors: DATA.csfColors, csfId: id, function: csfFunctionOf(id) };
      }
      if (!obj) {
        el.innerHTML = `<div class="empty">Entity "${id}" not found.</div>`;
        return;
      }
      const kindLabel = ({regulation: 'Regulation', article: 'Article', clause: 'Clause', so: 'SO', sr: 'SR', csf: 'CSF'})[kind] || kind;
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

      jsonPane.innerHTML = `<pre class="raw-json">${escapeHtml(JSON.stringify(obj, null, 2))}</pre>`;

      const md = obj.rawMd || obj.rawRow || obj.raw_md || obj.rawReadme || obj.raw01 || '';
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
