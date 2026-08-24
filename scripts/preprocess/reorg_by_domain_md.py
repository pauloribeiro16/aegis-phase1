#!/usr/bin/env python3
"""Reorganize methodology-00/PREPROCESSING/ into a domain-first layout.

Creates ``methodology-00/PREPROCESSING_by_domain/`` (a NEW location) with
regulation-scoped material and unified ``D-XX.Y.md`` files. The original
``PREPROCESSING/`` is never modified — this script only READS from it and
WRITES to the new location.

Layout produced::

    PREPROCESSING_by_domain/
    ├── README.md
    ├── _global/              # cross-cutting reference docs
    ├── _ambiguity/           # global ambiguity methodology
    ├── _templates/           # reusable templates
    ├── _archive/             # superseded / legacy monoliths
    ├── _archive_unmatched/   # unmatched ambiguity sections (preserved verbatim)
    │   ├── README.md         # index with 3 tables: archived / 100%-matched / filtered
    │   └── {REG}/             # one MD per source Ambiguity file WITH unmatched sections
    ├── _by_regulation/{REG}/ # top/ + Articles/ + Ambiguity/ (regulation-scoped)
    ├── audit/
    │   └── coverage_by_reg.md # ambiguity match coverage and limitations
    └── domains/D-XX_<name>/  # per-sub-subdomain unified folders
        └── D-XX.Y/
            ├── D-XX.Y.md     # Parts 1-4: definition, analyses, ambiguity
            └── articles/{REG}_Art_NN.md   # many-to-many duplication

Articles are hybrid: copied verbatim under _by_regulation/{REG}/Articles/ and
distributed under domains/D-XX.Y/articles/ using the Art->D-XX.Y mapping.
Ambiguity sections are mapped transitively from clause_id to sub-domain.

Usage::

    python reorg_by_domain_md.py [--src PATH] [--dst PATH] [--dry-run] [--clean]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REGULATIONS = ["GDPR", "CRA", "NIS2", "DORA", "AI_Act"]

CATEGORY_ORDER = [
    "false_positive_pattern3",
    "definition_section",
    "real_clause_no_sr",
    "no_clause_id_intro",
]

_NON_SECTION_MATCHES = {
    ("GDPR", "01_GDPR_Art4_Definitions.md", "R2-tightened"),
    ("CRA", "05_CRA_Art15-17_OtherReporting.md", "EU-CyCLONe"),
    ("NIS2", "02_NIS2_Art20_Governance.md", "RISK-MANAGEMENT"),
}

# Art -> D-XX.Y table row in Regulation/{REG}/Articles/README.md:
#   | [Art_4](Art_4.md) | D-01.1, D-01.2, ... | 22 |
# Capture the whole "Sub-domains" cell (everything up to the next " | "),
# then split it into individual D-XX.Y tokens afterwards.
ART_ROW_RE = re.compile(r"\|\s*\[Art_(\d+)\]\(Art_\d+\.md\)\s*\|\s*([^|]+?)\s*\|")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_article_map(src: Path) -> dict[str, list[tuple[str, str]]]:
    """Parse each Regulation/{REG}/Articles/README.md into a reverse map.

    Returns ``{D-XX.Y: [(reg, "Art_NN"), ...]}`` — for every sub-subdomain,
    which (regulation, article) pairs touch it.
    """
    article_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for reg in REGULATIONS:
        readme = src / "Regulation" / reg / "Articles" / "README.md"
        if not readme.exists():
            log(f"  WARN: {readme} not found — skipping article map for {reg}")
            continue
        text = readme.read_text(encoding="utf-8")
        n = 0
        for m in ART_ROW_RE.finditer(text):
            art_num = m.group(1)
            domains_field = m.group(2)
            for d in re.findall(r"D-\d+\.\d+", domains_field):
                article_map[d].append((reg, f"Art_{art_num}"))
                n += 1
        log(f"  article map: {reg} → {n} (reg,article)→sub-subdomain links")
    return article_map


def list_domain_dirs(parent: Path) -> list[Path]:
    """Return the 10 D-XX_<name> dirs under parent, sorted."""
    return sorted(p for p in parent.iterdir() if p.is_dir() and p.name.startswith("D-"))


def list_subsubdomain_files(domain_dir: Path) -> list[Path]:
    """Return D-XX.Y.md files inside a D-XX_<name> dir, sorted."""
    return sorted(p for p in domain_dir.glob("D-*.md") if re.match(r"D-\d+\.\d+\.md$", p.name))


def copy_file(src: Path, dst: Path, dry_run: bool, plan: list[str]) -> None:
    """Copy a single file (preserving metadata), logging to the plan."""
    plan.append(f"  {src} → {dst}")
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path, dry_run: bool, plan: list[str]) -> None:
    """Copy an entire subtree."""
    plan.append(f"  [tree] {src} → {dst}")
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _downgrade_headers(md_text: str) -> str:
    """Lower Markdown headers by one level."""
    output = []
    for line in md_text.split("\n"):
        if re.match(r"^#{1,6}(\s)", line):
            output.append("#" + line)
        else:
            output.append(line)
    return "\n".join(output)


def _normalize_article_ref(art: str) -> str:
    match = re.search(
        r"(?:Art\.\s*\d+(?:\([^)]+\))?(?:\s+sentence\s+\d+)?|"
        r"Annex\s+[IVX]+(?:\s+Part\s+[IVX]+)?)",
        art,
    )
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else ""


def parse_clause_to_subs(
    src: Path,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Map clause and article references to sub-domain IDs from security rules."""
    clause_to_subs: dict[str, set[str]] = defaultdict(set)
    article_to_subs: dict[str, set[str]] = defaultdict(set)
    for reg in REGULATIONS:
        sr_path = src / "Regulation" / reg / "02_SecurityRules_NIST.md"
        if not sr_path.exists():
            continue
        text = sr_path.read_text(encoding="utf-8")
        for block in re.findall(r"```yaml\n(.*?)\n```", text, re.DOTALL):
            clause_ids = re.findall(r"clause_id:\s*([A-Za-z0-9_]+-\w+)", block)
            article_refs = re.findall(r'article_ref:\s*"([^"]+)"', block)
            sub_match = re.search(r"sub_domain:\s*\[([^\]]*)\]", block)
            if not sub_match:
                continue
            sub_domains = re.findall(r"D-\d+\.\d+", sub_match.group(1))
            for clause_id in clause_ids:
                clause_to_subs[clause_id].update(sub_domains)
            for article_ref in article_refs:
                normalized = _normalize_article_ref(article_ref)
                if normalized:
                    article_to_subs[normalized].update(sub_domains)
    return clause_to_subs, article_to_subs


def _ambiguity_parts(src: Path) -> list[tuple[str, str, str]]:
    parts_by_reg = []
    for reg in REGULATIONS:
        amb_dir = src / "Regulation" / reg / "Ambiguity"
        if not amb_dir.exists():
            continue
        for md_file in sorted(amb_dir.glob("*.md")):
            if re.match(r"^(00_|99_)", md_file.name):
                continue
            if re.match(r"^\d{2}_[A-Za-z_]+\.md$", md_file.name):
                continue
            text = md_file.read_text(encoding="utf-8")
            parts = re.split(r"(?=^####\s)", text, flags=re.MULTILINE)
            if len(parts) <= 1:
                parts = re.split(r"(?=^###\s)", text, flags=re.MULTILINE)
            parts_by_reg.extend((reg, md_file.name, part) for part in parts if part.strip())
    return parts_by_reg


def _ambiguity_match_inputs(part: str) -> tuple[str | None, str]:
    patterns = [
        re.compile(r"\*\*Clause:\s*([A-Za-z0-9_]+-[A-Za-z0-9]+)\*\*"),
        re.compile(r"\(([A-Z]+-D\d+)\)"),
        re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:_Act)?-[\w-]+)\b"),
    ]
    clause_id = next(
        (match.group(1) for pattern in patterns if (match := pattern.search(part))),
        None,
    )
    header = part.splitlines()[0] if part.splitlines() else ""
    return clause_id, _normalize_article_ref(header)


def ambiguity_totals(src: Path) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for reg, _, part in _ambiguity_parts(src):
        clause_id, article_ref = _ambiguity_match_inputs(part)
        if clause_id or article_ref:
            totals[reg] += 1
    return totals


def _categorize_unmatched(clause_id: str | None) -> str:
    if clause_id is None:
        return "no_clause_id_intro"
    if re.match(r"^(GDPR|CRA|NIS2|DORA|AI_Act)-D\d+$", clause_id):
        return "definition_section"
    if not re.match(r"^(GDPR|CRA|NIS2|DORA|AI_Act)-", clause_id):
        return "false_positive_pattern3"
    return "real_clause_no_sr"


def parse_ambiguity_sections(
    src: Path,
    clause_to_subs: dict[str, set[str]],
    article_to_subs: dict[str, set[str]],
) -> tuple[list[dict], list[dict]]:
    """Extract mapped and unmatched sections from regulation ambiguity files."""
    matched = []
    unmatched = []
    for reg, filename, part in _ambiguity_parts(src):
        clause_id, article_ref = _ambiguity_match_inputs(part)
        if (reg, filename, clause_id) in _NON_SECTION_MATCHES:
            continue
        category = _categorize_unmatched(clause_id)
        section_md = part.strip()
        first_line = section_md.splitlines()[0] if section_md.splitlines() else ""
        if not clause_id and not article_ref:
            unmatched.append(
                {
                    "reg": reg,
                    "file": filename,
                    "clause_id": clause_id,
                    "first_line": first_line,
                    "section_md": section_md,
                    "category": category,
                }
            )
            continue
        sub_domains = clause_to_subs.get(clause_id, set()) if clause_id else set()
        match_strategy = "clause_id"
        if not sub_domains and article_ref:
            sub_domains = set(article_to_subs.get(article_ref, set()))
            if not sub_domains:
                for yaml_key, yaml_sub_domains in article_to_subs.items():
                    if yaml_key.startswith(article_ref) or article_ref.startswith(yaml_key):
                        sub_domains.update(yaml_sub_domains)
            match_strategy = "article_ref"
        if not sub_domains:
            unmatched.append(
                {
                    "reg": reg,
                    "file": filename,
                    "clause_id": clause_id,
                    "first_line": first_line,
                    "section_md": section_md,
                    "category": category,
                }
            )
            continue
        matched.append(
            {
                "reg": reg,
                "clause_id": clause_id,
                "article_ref": article_ref,
                "match_strategy": match_strategy,
                "sub_domains": sub_domains,
                "section_md": section_md,
            }
        )
    return matched, unmatched


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def stage_globals(src: Path, dst: Path, dry_run: bool, plan: list[str]) -> None:
    """Cross-cutting reference docs, ambiguity methodology, templates, archive."""
    plan.append("\n== _global/ ==")
    gdir = dst / "_global"
    for fname in [
        "README.md",
        "00_Hierarchical_SecurityObjectives.md",
        "NIST_CSF_2.0_subcategories.md",
        "TEMPLATE_subagent_brief.md",
    ]:
        s = src / fname
        if s.exists():
            copy_file(s, gdir / fname, dry_run, plan)

    plan.append("\n== _ambiguity/ ==")
    adir = dst / "_ambiguity"
    amb_src = src / "AMBIGUITY_ANALYSIS"
    if amb_src.exists():
        for f in sorted(amb_src.glob("*.md")):
            copy_file(f, adir / f.name, dry_run, plan)

    plan.append("\n== _templates/ ==")
    tdir = dst / "_templates"
    for tmpl in [
        src / "CrossRegulation" / "TEMPLATE_crossreg_brief.md",
        src / "SubDomains" / "Volere_shell.md",
    ]:
        if tmpl.exists():
            copy_file(tmpl, tdir / tmpl.name, dry_run, plan)

    plan.append("\n== _archive/ ==")
    arcdir = dst / "_archive"
    # CrossRegulation legacy monoliths
    cr_archive = src / "CrossRegulation" / "_archive"
    if cr_archive.exists():
        copy_tree(cr_archive, arcdir / "CrossRegulation", dry_run, plan)
    # Legacy ambiguity NN_<REG>.md (v0.1, superseded per AMBIGUITY_ANALYSIS/00_Index.md)
    legacy_dir = arcdir / "legacy"
    for reg in REGULATIONS:
        for p in (src / "Regulation" / reg / "Ambiguity").glob("*.md"):
            # Legacy files are the bare NN_<REG>.md (no topic suffix).
            if re.match(r"^\d{2}_[A-Za-z_]+\.md$", p.name):
                copy_file(p, legacy_dir / f"{reg}_{p.name}", dry_run, plan)


def stage_by_regulation(src: Path, dst: Path, dry_run: bool, plan: list[str]) -> None:
    """Regulation-scoped content: top-level MDs + Articles/ + Ambiguity/."""
    plan.append("\n== _by_regulation/{REG}/ ==")
    for reg in REGULATIONS:
        reg_src = src / "Regulation" / reg
        if not reg_src.exists():
            log(f"  WARN: {reg_src} not found")
            continue
        reg_dst = dst / "_by_regulation" / reg

        # top/ — the 5 numbered top-level MDs
        for p in sorted(reg_src.glob("*.md")):
            copy_file(p, reg_dst / "top" / p.name, dry_run, plan)

        # Articles/ — verbatim copy (Art_NN.md + README.md)
        art_src = reg_src / "Articles"
        if art_src.exists():
            for p in sorted(art_src.glob("*.md")):
                copy_file(p, reg_dst / "Articles" / p.name, dry_run, plan)

        # Ambiguity/ — verbatim copy (topic files + index + synthesis;
        # legacy NN_<REG>.md excluded — goes to _archive/legacy/ instead)
        amb_src = reg_src / "Ambiguity"
        if amb_src.exists():
            for p in sorted(amb_src.glob("*.md")):
                if re.match(r"^\d{2}_[A-Za-z_]+\.md$", p.name):
                    continue  # legacy → _archive/legacy/
                copy_file(p, reg_dst / "Ambiguity" / p.name, dry_run, plan)


def stage_domains(
    src: Path,
    dst: Path,
    article_map: dict[str, list[tuple[str, str]]],
    ambiguity_sections: list[dict],
    dry_run: bool,
    plan: list[str],
) -> dict[str, dict[str, int]]:
    """Build merged four-part files in the domains tree."""
    plan.append("\n== domains/D-XX_<name>/D-XX.Y/ ==")
    sub_src = src / "SubDomains"
    da_src = src / "CrossRegulation" / "DomainAnalysis"
    de_src = src / "CrossRegulation" / "DeepAnalysis"
    sub_to_sections: dict[str, list[dict]] = defaultdict(list)
    for section in ambiguity_sections:
        for sub_domain in section["sub_domains"]:
            sub_to_sections[sub_domain].append(section)
    stats: dict[str, dict[str, int]] = {}
    for ddir in list_domain_dirs(sub_src):
        domain_name = ddir.name
        domain_dst = dst / "domains" / domain_name
        d_stats = {"subsubdomains": 0, "articles": 0, "files": 0, "ambiguity_sections": 0}
        for ss_file in list_subsubdomain_files(ddir):
            ss_id = ss_file.stem
            ss_dst = domain_dst / ss_id
            sub_md = ss_file.read_text(encoding="utf-8")
            da_file = da_src / domain_name / ss_file.name
            de_file = de_src / domain_name / ss_file.name
            da_md = da_file.read_text(encoding="utf-8") if da_file.exists() else ""
            de_md = de_file.read_text(encoding="utf-8") if de_file.exists() else ""
            relevant = sub_to_sections.get(ss_id, [])
            d_stats["ambiguity_sections"] += len(relevant)
            sections_by_reg: dict[str, list[dict]] = defaultdict(list)
            for section in relevant:
                sections_by_reg[section["reg"]].append(section)
            part4 = []
            for reg in REGULATIONS:
                sections = sections_by_reg.get(reg, [])
                if sections:
                    body = "\n\n".join(
                        _downgrade_headers(section["section_md"]) for section in sections
                    )
                    part4.append(f"## {reg}\n\n{body}")
                else:
                    part4.append(f"## {reg}\n\n_No applicable {reg} ambiguity._")
            title_match = re.search(r"^#\s+(.+)$", sub_md, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else ss_id
            part4_md = "\n\n".join(part4)
            merged = f"""# {ss_id} — {title}

> Unified view: Sub-domain definition + Domain Analysis + Deep Analysis + relevant Ambiguity.
> Generated by reorg_by_domain_md.py from PREPROCESSING/.

---

# Part 1 — Sub-domain definition

{_downgrade_headers(sub_md)}

---

# Part 2 — Domain Analysis (cross-regulation)

{_downgrade_headers(da_md) if da_md else "_Domain Analysis source not found._"}

---

# Part 3 — Deep Analysis (per-pair)

{_downgrade_headers(de_md) if de_md else "_Deep Analysis source not found._"}

---

# Part 4 — Relevant Ambiguity (by regulation)

{part4_md}
"""
            merged_path = ss_dst / f"{ss_id}.md"
            plan.append(f"  [merge] {ss_id} -> {merged_path}")
            if not dry_run:
                merged_path.parent.mkdir(parents=True, exist_ok=True)
                merged_path.write_text(merged, encoding="utf-8")
            for reg, art_name in sorted(article_map.get(ss_id, [])):
                article_src = src / "Regulation" / reg / "Articles" / f"{art_name}.md"
                if article_src.exists():
                    copy_file(
                        article_src, ss_dst / "articles" / f"{reg}_{art_name}.md", dry_run, plan
                    )
                    d_stats["articles"] += 1
            d_stats["subsubdomains"] += 1
            d_stats["files"] += 1
        stats[domain_name] = d_stats
        log(
            f"  {domain_name}: {d_stats['subsubdomains']} sub-subdomains, "
            f"{d_stats['articles']} article copies, "
            f"{d_stats['ambiguity_sections']} ambiguity sections"
        )
    return stats


# ---------------------------------------------------------------------------
# Generated indexes + README
# ---------------------------------------------------------------------------


def write_unmatched_archive(dst: Path, unmatched: list[dict], dry_run: bool) -> None:
    if dry_run:
        return
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for section in unmatched:
        grouped[(section["reg"], section["file"])].append(section)
    for (reg, filename), sections in grouped.items():
        if not sections:
            continue
        categories = [
            category
            for category in CATEGORY_ORDER
            if any(section["category"] == category for section in sections)
        ]
        lines = [
            f"<!-- archive_id: {reg}-{filename} -->",
            f"<!-- source: methodology-00/PREPROCESSING/Regulation/{reg}/Ambiguity/{filename} -->",
            f"<!-- unmatched_count: {len(sections)} -->",
            f"<!-- categories: [{', '.join(categories)}] -->",
            "<!-- generated_by: reorg_by_domain_md.py -->",
            "",
            f"# Unmatched ambiguity sections — {reg} / {filename}",
            "",
            "> Archived because these sections could not be mapped to a security rule",
            "> while preserving the source content for audit and future re-parsing.",
            "> Categories: false_positive_pattern3, definition_section,",
            "> real_clause_no_sr, no_clause_id_intro.",
            "",
        ]
        for number, section in enumerate(sections, start=1):
            lines.append(f"## Section {number} — {section['first_line']}")
            lines.append(section["section_md"])
            if number < len(sections):
                lines.extend(["", "---", ""])
        archive_file = dst / "_archive_unmatched" / reg / filename
        archive_file.parent.mkdir(parents=True, exist_ok=True)
        archive_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_unmatched_index(dst: Path, unmatched: list[dict], dry_run: bool) -> None:
    if dry_run:
        return
    unmatched_grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for section in unmatched:
        unmatched_grouped[(section["reg"], section["file"])].append(section)
    source_root = dst.parent / "PREPROCESSING" / "Regulation"
    archived: list[tuple[str, str, list[str]]] = []
    matched_full: list[tuple[str, str]] = []
    filtered: list[tuple[str, str, str]] = []
    for reg in REGULATIONS:
        amb_dir = source_root / reg / "Ambiguity"
        if not amb_dir.exists():
            continue
        for md_file in sorted(amb_dir.glob("*.md")):
            key = (reg, md_file.name)
            if re.match(r"^(00_|99_)", md_file.name):
                filtered.append((reg, md_file.name, "Index/Synthesis"))
            elif re.match(r"^\d{2}_[A-Za-z_]+\.md$", md_file.name):
                filtered.append((reg, md_file.name, "Legacy NN_<REG>.md"))
            elif key in unmatched_grouped:
                cats = sorted({s["category"] for s in unmatched_grouped[key]})
                archived.append((reg, md_file.name, cats))
            else:
                matched_full.append((reg, md_file.name))
    category_descriptions = {
        "false_positive_pattern3": "Pattern 3 captured a fragment rather than a canonical clause identifier.",
        "definition_section": "The section is a regulation definition without a SecurityRule mapping.",
        "real_clause_no_sr": "The section has a real clause identifier with no SecurityRule in the corpus.",
        "no_clause_id_intro": "The section is an introductory or aggregate section without a clause identifier.",
    }
    lines = [
        "# Archived unmatched ambiguity sections",
        "",
        "This archive preserves unmatched ambiguity sections as an audit trail and for future re-parsing with improved heuristics.",
        "",
        "Source files fall into three categories:",
        "1. **Archived** (>=1 unmatched section): section content preserved verbatim in `_archive_unmatched/<REG>/<file>.md`.",
        "2. **100% matched** (processed by Parser B, all sections matched): no unmatched content; source preserved in `_by_regulation/<REG>/Ambiguity/`.",
        "3. **Filtered out** (Index/Synthesis/Legacy): Parser B skips these; source preserved in `_by_regulation/<REG>/Ambiguity/` (or `_archive/legacy/` for v0.1 monoliths).",
        "",
        "## Categories of unmatched sections",
        "",
    ]
    lines.extend(
        f"- **{category}**: {category_descriptions[category]}" for category in CATEGORY_ORDER
    )
    lines.extend(
        [
            "",
            f"## Archived files ({len(archived)} files, {sum(len(c) for _, _, c in archived)} categories listed)",
            "",
            "| Regulation | File | Archive | Source | Categories |",
            "|---|---|---|---|---|",
        ]
    )
    for reg, filename, cats in archived:
        cats_str = ", ".join(cats)
        lines.append(
            f"| {reg} | {filename} | [archive]({reg}/{filename}) | "
            f"[source](../_by_regulation/{reg}/Ambiguity/{filename}) | {cats_str} |"
        )
    lines.extend(
        [
            "",
            f"## Files 100% matched ({len(matched_full)} files)",
            "",
            "| Regulation | File | Source |",
            "|---|---|---|",
        ]
    )
    for reg, filename in matched_full:
        lines.append(
            f"| {reg} | {filename} | [source](../_by_regulation/{reg}/Ambiguity/{filename}) |"
        )
    lines.extend(
        [
            "",
            f"## Files filtered out by Parser B ({len(filtered)} files)",
            "",
            "| Regulation | File | Source | Reason |",
            "|---|---|---|---|",
        ]
    )
    for reg, filename, reason in filtered:
        lines.append(
            f"| {reg} | {filename} | [source](../_by_regulation/{reg}/Ambiguity/{filename}) | {reason} |"
        )
    readme = dst / "_archive_unmatched" / "README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_coverage_report(
    dst: Path,
    totals_by_reg: dict[str, int],
    matched: list[dict],
    unmatched: list[dict],
    dry_run: bool,
) -> None:
    if dry_run:
        return
    matched_clause: dict[str, int] = defaultdict(int)
    matched_article: dict[str, int] = defaultdict(int)
    for section in matched:
        target = matched_clause if section["match_strategy"] == "clause_id" else matched_article
        target[section["reg"]] += 1
    total_extracted = (
        sum(totals_by_reg.values())
        + sum(1 for section in unmatched if section["category"] == "no_clause_id_intro")
        - len(_NON_SECTION_MATCHES)
    )
    extracted_by_reg = {
        reg: totals_by_reg[reg]
        + sum(
            1
            for section in unmatched
            if section["reg"] == reg and section["category"] == "no_clause_id_intro"
        )
        - sum(1 for item in _NON_SECTION_MATCHES if item[0] == reg)
        for reg in REGULATIONS
    }
    total_clause = sum(matched_clause.values())
    total_article = sum(matched_article.values())
    lines = [
        "# Ambiguity coverage by regulation",
        "",
        "## Total stats",
        "",
        f"- totals_by_reg: {total_extracted} extracted",
        f"- matched_clause: {total_clause}",
        f"- matched_article: {total_article}",
        f"- unmatched: {len(unmatched)}",
        "",
        "## Per-regulation coverage",
        "",
        "| Regulation | Extracted | Matched | by_clause_id | by_article_ref | Unmatched | Rate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for reg in REGULATIONS:
        extracted = extracted_by_reg[reg]
        by_clause = matched_clause[reg]
        by_article = matched_article[reg]
        matched = by_clause + by_article
        rate = matched / extracted if extracted else 0
        lines.append(
            f"| {reg} | {extracted} | {matched} | {by_clause} | {by_article} | "
            f"{extracted - matched} | {rate:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Known limitations",
            "",
            "1. **Limitation — NIS2 short-form** `NIS2-CNN`: T3-mapping narrative has no SecurityRule equivalent.",
            "2. **Limitation — CRA `CRA-DNN`**: definitions are Ambiguity-only.",
            "3. **Limitation — DORA articles** without SecurityRule include Ch. II Sec. I governance and Ch. III incident reporting.",
            "4. **Limitation — Many-to-many via article_ref**: one section intentionally maps to multiple sub_domains.",
            "5. **Limitation — False positives from pattern 3 fallback**: `Cross-clause` and `Berry-relief` cause no harm.",
        ]
    )
    unmatched_by_category: dict[str, int] = defaultdict(int)
    unmatched_by_reg: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for section in unmatched:
        category = section["category"]
        unmatched_by_category[category] += 1
        unmatched_by_reg[category][section["reg"]] += 1
    lines.extend(
        [
            "",
            f"## Unmatched archived ({len(unmatched)} sections)",
            "",
            "| Category | Count | Per-reg breakdown |",
            "|---|---:|---|",
        ]
    )
    for category in CATEGORY_ORDER:
        breakdown = ", ".join(
            f"{reg} {unmatched_by_reg[category][reg]}"
            for reg in REGULATIONS
            if unmatched_by_reg[category][reg]
        )
        lines.append(f"| {category} | {unmatched_by_category[category]} | {breakdown} |")
    lines.extend(
        [
            "",
            "Archive: _archive_unmatched/README.md — full index.",
        ]
    )
    report = dst / "audit" / "coverage_by_reg.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_index_per_domain(dst: Path, stats: dict[str, dict[str, int]], dry_run: bool) -> None:
    for domain_name, d_stats in stats.items():
        idx = dst / "domains" / domain_name / "_index.md"
        if dry_run:
            continue
        idx.parent.mkdir(parents=True, exist_ok=True)
        # Derive sub-subdomain list from the folders actually created.
        ss_dirs = sorted(
            p.name for p in idx.parent.iterdir() if p.is_dir() and re.match(r"D-\d+\.\d+$", p.name)
        )
        lines = [
            f"# {domain_name}",
            "",
            f"- Sub-subdomains: {len(ss_dirs)}",
            f"- Merged files (Parts 1-4): {d_stats['files']}",
            f"- Article copies (many-to-many): {d_stats['articles']}",
            f"- Ambiguity sections: {d_stats['ambiguity_sections']}",
            "",
            "## Sub-subdomains",
            "",
        ]
        for ss in ss_dirs:
            lines.append(f"- [{ss}]({ss}/)")
        idx.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_global_index(dst: Path, stats: dict[str, dict[str, int]], dry_run: bool) -> None:
    idx = dst / "domains" / "index.md"
    if dry_run:
        return
    idx.parent.mkdir(parents=True, exist_ok=True)
    total_ss = sum(s["subsubdomains"] for s in stats.values())
    total_files = sum(s["files"] for s in stats.values())
    total_articles = sum(s["articles"] for s in stats.values())
    total_ambiguity = sum(s["ambiguity_sections"] for s in stats.values())
    lines = [
        "# Domains index (by-domain reorganization)",
        "",
        f"- Domains: {len(stats)}",
        f"- Sub-subdomains: {total_ss}",
        f"- Merged files (Parts 1-4): {total_files}",
        f"- Article copies (many-to-many): {total_articles}",
        f"- Ambiguity sections: {total_ambiguity}",
        "",
        "| Domain | Sub-subdomains | Merged files | Article copies | Ambiguity sections |",
        "|---|---|---|---|---|",
    ]
    for name, s in stats.items():
        lines.append(
            f"| [{name}]({name}/_index.md) | {s['subsubdomains']} | "
            f"{s['files']} | {s['articles']} | {s['ambiguity_sections']} |"
        )
    idx.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(dst: Path, stats: dict[str, dict[str, int]], dry_run: bool) -> None:
    readme = dst / "README.md"
    if dry_run:
        return
    total_ss = sum(s["subsubdomains"] for s in stats.values())
    total_files = sum(s["files"] for s in stats.values())
    total_articles = sum(s["articles"] for s in stats.values())
    total_ambiguity = sum(s["ambiguity_sections"] for s in stats.values())
    content = f"""# PREPROCESSING_by_domain

Domain-first reorganization of `methodology-00/PREPROCESSING/`.

Generated by `scripts/preprocess/reorg_by_domain_md.py`. The original
`PREPROCESSING/` is the source of truth and is never modified.

## Why

The original tree organizes content by **kind** (SubDomains/, CrossRegulation/,
Regulation/). This copy reorganizes by **domain** so that everything touching a
given sub-subdomain `D-XX.Y` lives in one folder — easier to browse when you
ask "show me everything about D-04.3".

## Layout

```
_global/            # cross-cutting reference (HSO, NIST CSF, README)
_ambiguity/         # global ambiguity methodology (00_Index, 01_Framework)
_templates/         # reusable templates (cross-reg brief, Volere shell)
_archive/           # superseded / legacy monoliths + ambiguity v0.1
_by_regulation/     # regulation-scoped: top/ + Articles/ + Ambiguity/ per reg
domains/D-XX_<name>/D-XX.Y/
                     # UNIFIED per sub-subdomain (Parts 1-4):
                     #   D-XX.Y.md        ← definition + analyses + ambiguity
                     #   articles/        ← Art_NN mapped to this D-XX.Y

```

## Stats

- Domains: {len(stats)}
- Sub-subdomains: {total_ss}
- Merged files (Parts 1-4): {total_files}
- Article copies distributed by sub-subdomain (many-to-many): {total_articles}
- Ambiguity sections distributed by sub-subdomain: {total_ambiguity}

## Notes

- **Articles are hybrid**: kept verbatim under `_by_regulation/{{REG}}/Articles/`
  AND distributed under `domains/D-XX.Y/articles/` (prefixed with the regulation
  to avoid name collisions). An article touching N sub-subdomains is copied N
  times — this is intentional (many-to-many).
- **Ambiguity** is extracted by clause and distributed into Part 4 of each
  applicable merged domain file. The regulation-scoped source remains under
  `_by_regulation/{{REG}}/Ambiguity/`.
- **Legacy files** (CrossRegulation monoliths + ambiguity v0.1 `NN_<REG>.md`)
  are parked under `_archive/`.
"""
    readme.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--src",
        type=Path,
        default=Path("methodology-00/PREPROCESSING"),
        help="source PREPROCESSING/ folder (default: methodology-00/PREPROCESSING)",
    )
    ap.add_argument(
        "--dst",
        type=Path,
        default=Path("methodology-00/PREPROCESSING_by_domain"),
        help="destination folder (default: methodology-00/PREPROCESSING_by_domain)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="show the copy plan without writing anything"
    )
    ap.add_argument("--clean", action="store_true", help="remove dst before writing (idempotent)")
    args = ap.parse_args()

    src: Path = args.src.resolve()
    dst: Path = args.dst.resolve()

    if not src.exists() or not src.is_dir():
        log(f"ERROR: source not found: {src}")
        return 2

    log(f"Source : {src}")
    log(f"Dest   : {dst}")
    log(f"Dry-run: {args.dry_run}")

    # Safety: refuse to overwrite the source, and refuse a dst inside the src.
    if dst == src:
        log("ERROR: destination equals source — aborting.")
        return 2
    try:
        dst.relative_to(src)
        log("ERROR: destination is inside source — aborting.")
        return 2
    except ValueError:
        pass

    if args.clean and dst.exists() and not args.dry_run:
        log(f"Cleaning existing {dst} ...")
        shutil.rmtree(dst)

    # 1. Parse the Art → D-XX.Y map from the 5 Articles READMEs.
    log("\nParsing Art → D-XX.Y map ...")
    article_map = parse_article_map(src)
    log(f"  total sub-subdomains with article links: {len(article_map)}")
    total_links = sum(len(v) for v in article_map.values())
    log(f"  total (reg,article)→sub-subdomain links: {total_links}")

    log("\nParsing clause_id and article_ref → sub_domain maps ...")
    clause_to_subs, article_to_subs = parse_clause_to_subs(src)

    log("\nParsing ambiguity sections ...")
    matched, unmatched = parse_ambiguity_sections(src, clause_to_subs, article_to_subs)
    totals_by_reg = ambiguity_totals(src)
    matched_clause: dict[str, int] = defaultdict(int)
    matched_article: dict[str, int] = defaultdict(int)
    for section in matched:
        target = matched_clause if section["match_strategy"] == "clause_id" else matched_article
        target[section["reg"]] += 1
    total_clause = sum(matched_clause.values())
    total_article = sum(matched_article.values())
    log(f"  total ambiguity sections extracted: {sum(totals_by_reg.values())}")
    log(
        f"  total matched: {total_clause + total_article} "
        f"(by clause_id={total_clause}, by article_ref={total_article})"
    )
    for reg in REGULATIONS:
        reg_matched = matched_clause[reg] + matched_article[reg]
        log(
            f"  {reg}: extracted={totals_by_reg[reg]} matched={reg_matched} "
            f"(clause_id={matched_clause[reg]}, article_ref={matched_article[reg]})"
        )
    unmatched_counts = defaultdict(int)
    for section in unmatched:
        unmatched_counts[section["category"]] += 1
    log(f"  total unmatched sections: {len(unmatched)}")
    log(
        "  unmatched by category: "
        + " ".join(f"{category}={unmatched_counts[category]}" for category in CATEGORY_ORDER)
    )
    log(f"  total article_refs mapped: {len(article_to_subs)}")
    log(f"  total clause_ids mapped: {len(clause_to_subs)}")

    # 2. Build the copy plan (and execute unless --dry-run).
    plan: list[str] = []
    stage_globals(src, dst, args.dry_run, plan)
    stage_by_regulation(src, dst, args.dry_run, plan)
    stats = stage_domains(
        src,
        dst,
        article_map,
        matched,
        args.dry_run,
        plan,
    )
    write_coverage_report(dst, totals_by_reg, matched, unmatched, args.dry_run)
    write_unmatched_archive(dst, unmatched, args.dry_run)
    write_unmatched_index(dst, unmatched, args.dry_run)

    # 3. Generated indexes + README.
    if not args.dry_run:
        write_index_per_domain(dst, stats, args.dry_run)
        write_global_index(dst, stats, args.dry_run)
        write_readme(dst, stats, args.dry_run)

    # 4. Summary.
    log("\n=== SUMMARY ===")
    total_ss = sum(s["subsubdomains"] for s in stats.values())
    total_files = sum(s["files"] for s in stats.values())
    total_articles = sum(s["articles"] for s in stats.values())
    total_ambiguity = sum(s["ambiguity_sections"] for s in stats.values())
    log(f"Domains         : {len(stats)}")
    log(f"Sub-subdomains  : {total_ss}")
    log(f"Merged files    : {total_files}")
    log(f"Article copies  : {total_articles}")
    log(f"Ambiguity refs  : {total_ambiguity}")

    if args.dry_run:
        log(f"\n[dry-run] {len(plan)} copy operations planned — nothing written.")
    else:
        log(f"\nDone. Wrote {len(plan)} items to {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
