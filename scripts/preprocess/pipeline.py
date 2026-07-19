"""Pipeline orchestrator v2.

Walk → parse → write shards → build global indices → write manifest.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parsers.aggregated.security_objectives import parse_security_objectives
from .parsers.aggregated.security_rules import parse_security_rules
from .parsers.diagram import parse_diagram
from .parsers.entities.clause import parse_ambiguity_file
from .parsers.entities.csf import (
    parse_csf,
    parse_csf_authority_note_full,
    parse_csf_crossref_full,
    parse_csf_d_subdomain_hints,
    parse_csf_end_of_reference,
    parse_csf_function_structure,
    parse_csf_h1_title,
    parse_csf_special_tokens_full,
)
from .parsers.entities.csf_xlsx import build_shard, parse_csf2
from .parsers.entities.subdomain import parse_subdomain
from .parsers.frontmatter import parse_frontmatter
from .parsers.narrative import (
    parse_ambiguity_framework,
    parse_ambiguity_index,
    parse_crossregulation_brief_template,
    parse_crossregulation_index,
    parse_preproc_readme,
    parse_subagent_brief_template,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "2.0"


# ─── helpers ────────────────────────────────────────────────────────────


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _copy_preproc_readme(output_root: Path) -> None:
    """Copy scripts/preprocess/PREPROC_OUT_README.md → output_root/README.md.

    Keeps the preproc_out/ tree self-describing even when the output dir
    is gitignored. The source README lives next to the pipeline code so
    it is versioned with the rest of the preprocessing logic.
    """
    import shutil

    # __file__ = scripts/preprocess/pipeline.py → README is one level up + sibling
    src_readme = Path(__file__).parent / "PREPROC_OUT_README.md"
    dst_readme = output_root / "README.md"
    if src_readme.is_file():
        shutil.copy2(src_readme, dst_readme)


def _json_default(o: Any) -> Any:
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _write_json(path: Path, data: Any) -> tuple[int, str]:
    text = json.dumps(data, indent=2, ensure_ascii=False, default=_json_default) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    raw = text.encode("utf-8")
    return len(raw), _sha256(raw)


# ─── entity collectors ──────────────────────────────────────────────────


class EntityIndex:
    """Accumulates entities as they are parsed; flushes to per-entity shards
    and produces the 4 global index files at the end."""

    def __init__(self) -> None:
        # entity_id → entity_dict (with _source_path, _shard_path injected at write time)
        self.entities: dict[str, dict[str, Any]] = {}
        # entity_id → source file path
        self.sources: dict[str, str] = {}
        # shard_path (relative) → list of entity_ids it holds
        self.shard_contents: dict[str, list[str]] = defaultdict(list)
        # warnings accumulator
        self.warnings: list[dict[str, str]] = []
        # errors
        self.errors: list[dict[str, str]] = []

    def add(self, entity_id: str, entity: dict[str, Any], shard_path: str) -> None:
        if entity_id in self.entities:
            # Merge: keep the existing entity but record the additional
            # source. Cross-references (e.g. SO-GDPR-001 appearing in multiple
            # SubDomain hso_per_reg blocks) are NOT duplicates — they are
            # different occurrences of the same canonical ID. We track them
            # as references rather than warnings.
            self.sources[
                entity_id
                + "::ref::"
                + str(len([k for k in self.sources if k.startswith(entity_id + "::ref::")]))
            ] = entity.get("source", "?")
            return
        entity["_id"] = entity_id
        self.entities[entity_id] = entity
        self.sources[entity_id] = entity.get("source", "?")
        self.shard_contents[shard_path].append(entity_id)

    def add_warning(self, file: str, warning: str) -> None:
        self.warnings.append({"file": file, "warning": warning})


# ─── main build ─────────────────────────────────────────────────────────


def build(source_root: Path, output_root: Path) -> dict[str, Any]:
    """Run the full v2 build. Returns the manifest dict.

    Strict mode: any warning is escalated to an error. The function
    returns the manifest; callers check ``manifest["errors"]``.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    # v9: copy the README.md to the output root so the tree is
    # self-describing even when preproc_out/ is gitignored.
    _copy_preproc_readme(output_root)
    # v8: pre-create the entity subdirs.
    # "ambiguities" (proper plural — not "ambiguitys") is the v8 spelling.
    for kind in ("subdomain", "article", "clause", "so", "sr", "pair", "ambiguity", "csf"):
        dirname = "ambiguities" if kind == "ambiguity" else f"{kind}s"
        (output_root / "entities" / dirname).mkdir(parents=True, exist_ok=True)
    # CSF per-Function subfolders + _meta/
    for fn in ("GV", "ID", "PR", "DE", "RS", "RC"):
        (output_root / "entities" / "csfs" / fn).mkdir(parents=True, exist_ok=True)
    (output_root / "entities" / "csfs" / "_meta").mkdir(parents=True, exist_ok=True)
    # meta/ for manifest + build_info
    (output_root / "meta").mkdir(parents=True, exist_ok=True)
    # crossregulation/_templates/
    (output_root / "crossregulation" / "_templates").mkdir(parents=True, exist_ok=True)

    idx = EntityIndex()
    manifest_shards: list[dict[str, Any]] = []

    # 1. CSF (single source file → 106 subcategories + D-XX hint table)
    csf_hint = _process_csf(source_root, output_root, idx, manifest_shards)
    # Inject csf_hint into subdomain entities as we parse them
    # (held in closure; consumed in _process_subdomain below)

    # 2. SubDomains
    _process_subdomains(source_root, output_root, idx, manifest_shards, csf_hint)

    # 3. Regulation (articles, clauses, aggregated SO+SR, roots)
    _process_regulation(source_root, output_root, idx, manifest_shards)

    # 4. CrossRegulation (shallow: frontmatter + raw + participants)
    _process_crossregulation(source_root, output_root, idx, manifest_shards)

    # 5. Diagrams
    _process_diagrams(source_root, output_root, idx, manifest_shards)

    # 6. Global + ambiguity_analysis
    _process_global_and_ambiguity_analysis(source_root, output_root, idx, manifest_shards)

    # 7. Build global indices
    _build_indices(idx, output_root, manifest_shards)

    # 8. Manifest + build_info
    return _write_manifest(source_root, output_root, manifest_shards, idx.errors, idx.warnings)


# ─── section processors ────────────────────────────────────────────────


def _process_csf(
    src_root: Path, out_root: Path, idx: EntityIndex, shards: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Parse CSF 2.0 → 1 JSON per subcategory.

    **Source priority (CORR-024 v5):**

    1. ``csf2.xlsx`` (NIST CSF 2.0 Reference Tool) at the aegis-phase1 repo
       root — the **official** CSF 2.0 with 185 subcategories, Implementation
       Examples, and Informative References.
    2. ``PREPROCESSING/NIST_CSF_2.0_subcategories.md`` — legacy frozen list
       (98 edited subcategories; kept for traceability but NOT the source
       of truth).

    If the xlsx is present, it **replaces** the .md-derived shards entirely.
    The D-XX hint table is rebuilt from the xlsx by inverting the
    implementation_example / informative_reference content (the legacy
    .md cross-reference table is more authoritative for D-XX hints; for
    the v5 release we still derive hints from the .md file when present).
    """
    # The aegis-phase1 repo root is two levels above scripts/preprocess/.
    repo_root = Path(__file__).resolve().parents[2]
    xlsx_path = repo_root / "csf2.xlsx"
    csf_md_path = src_root / "PREPROCESSING" / "NIST_CSF_2.0_subcategories.md"

    if xlsx_path.is_file():
        return _process_csf_xlsx(xlsx_path, csf_md_path, out_root, idx, shards)
    if csf_md_path.is_file():
        return _process_csf_md(csf_md_path, out_root, idx, shards)
    idx.add_warning(str(csf_md_path), "CSF reference missing (neither csf2.xlsx nor .md)")
    return {}


def _process_csf_xlsx(
    xlsx_path: Path,
    csf_md_path: Path,
    out_root: Path,
    idx: EntityIndex,
    shards: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Parse csf2.xlsx (NIST CSF 2.0 Reference Tool) → 1 shard per **active**
    subcategory (CORR-024 v6).

    **Withdrawn subcategories (79 in the official CSF 2.0) are NOT
    materialized as per-subcategory shards.** They appear only in the
    aggregated ``global/NIST_CSF_2.0_subcategories.json`` under
    ``withdrawn_subcategories`` for audit traceability. Reason: a withdrawn
    subcategory has no Implementation Examples, no Informative References,
    and no actionable content — it is a historical marker, not a control.

    Counts after filtering:
      - 185 subcategories in xlsx
      - 79 withdrawn (skip per-subcategory shard, list in aggregated only)
      - 106 active (1 shard each, with full implementation_examples +
        informative_references)
    """
    logger.info(
        "csf2.xlsx detected → 185 subcategories (79 withdrawn + 106 active)" " (CORR-024 v6)"
    )
    parsed = parse_csf2(xlsx_path)
    intro = parsed["introduction"]

    n_written = 0
    n_skipped = 0
    for sc in parsed["subcategories"]:
        if sc["withdrawn"]:
            # Skip per-subcategory shard — withdrawn subs have no actionable
            # content. Their IDs are kept in the aggregated file for audit.
            n_skipped += 1
            continue
        shard_entity = build_shard(sc, intro, xlsx_path)
        eid = shard_entity["id"]
        # CORR-024 v7: organize shards by Function (GV, ID, PR, DE, RS, RC)
        # → entities/csfs/{FUNCTION}/{FUNC}_{CAT}_{NUM}.json
        fn = shard_entity["function"]
        fname = eid.replace(".", "_").replace("-", "_")
        shard_path = f"entities/csfs/{fn}/{fname}.json"
        idx.add(eid, shard_entity, shard_path)
        bytes_written, sha = _write_json(out_root / shard_path, shard_entity)
        shards.append(
            {
                "path": shard_path,
                "source_path": str(xlsx_path),
                "sha256": sha,
                "bytes": bytes_written,
                "kind": "csf",
                "entity_ids": [eid],
            }
        )
        n_written += 1
    logger.info("csf2.xlsx: wrote %d active shards, skipped %d withdrawn", n_written, n_skipped)

    # CORR-024 v7: write a retro-compat _index.json at entities/csfs/
    # mapping id → path. The v6 layout had flat files at
    # entities/csfs/<FUNC>_<CAT>_<NUM>.json; the v7 layout uses per-Function
    # subfolders. The index lets any consumer resolve a CSF id without
    # knowing the function code.
    id_to_path: dict[str, str] = {}
    for s in parsed["subcategories"]:
        if s["withdrawn"]:
            continue
        eid = s["id"]
        fn = s["function"]
        fname = eid.replace(".", "_").replace("-", "_")
        id_to_path[eid] = f"entities/csfs/{fn}/{fname}.json"
    per_function: dict[str, list[str]] = {}
    for s in parsed["subcategories"]:
        if s["withdrawn"]:
            continue
        per_function.setdefault(s["function"], []).append(s["id"])
    _write_json(
        out_root / "entities" / "csfs" / "_meta" / "_index.json",
        {
            "schema_version": "1.0",
            "kind": "csf_shard_index",
            "source": "csf2.xlsx",
            "layout": "per_function_subfolders",
            "function_order": ["GV", "ID", "PR", "DE", "RS", "RC"],
            "active_subcategory_count": len(id_to_path),
            "by_function": {
                fn: {"count": len(ids), "ids": sorted(ids)}
                for fn, ids in sorted(per_function.items())
            },
            "by_id": dict(sorted(id_to_path.items())),
        },
    )
    logger.info("csf2.xlsx: wrote _index.json with %d active subcategories", len(id_to_path))

    # Hint table: prefer the .md cross-reference if available (more
    # authoritative for AEGIS sub-domain → CSF mapping). The xlsx doesn't
    # carry a D-XX cross-reference.
    hint: dict[str, list[str]] = {}
    if csf_md_path.is_file():
        hint = parse_csf_d_subdomain_hints(csf_md_path)
    return hint


def _process_csf_md(
    csf_path: Path, out_root: Path, idx: EntityIndex, shards: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Legacy .md parser (98 subcategories). Used only if csf2.xlsx is absent."""
    logger.warning("csf2.xlsx NOT found; falling back to legacy .md (98 subcategories)")
    text = csf_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    body_start_in_source = text[: len(text) - len(body)].count("\n") + 1

    def shift_locus(locus: dict[str, int]) -> dict[str, int]:
        return {
            "start_line": locus["start_line"] + body_start_in_source - 1
            if locus.get("start_line", 0) > 0
            else 0,
            "end_line": locus["end_line"] + body_start_in_source - 1
            if locus.get("end_line", 0) > 0
            else 0,
        }

    subcats = parse_csf(csf_path)
    hint = parse_csf_d_subdomain_hints(csf_path)

    for sc in subcats:
        sc["schema_version"] = "1.1"
        sc["kind"] = "csf"
        sc["doc_id"] = sc.get("source_document", {}).get("document_id", "AEGIS-PREPROC-CSF-REF")
        sc["source_locus"] = shift_locus(sc["source_locus"])
        if sc.get("authority_note_locus"):
            sc["authority_note_locus"] = shift_locus(sc["authority_note_locus"])
        eid = sc["id"]
        fname = eid.replace(".", "_").replace("-", "_")
        # v8: per-Function subfolders
        fn = sc.get("function", "")
        shard_path = f"entities/csfs/{fn}/{fname}.json" if fn else f"entities/csfs/{fname}.json"
        idx.add(eid, sc, shard_path)
        bytes_written, sha = _write_json(out_root / shard_path, sc)
        shards.append(
            {
                "path": shard_path,
                "source_path": sc["source"],
                "sha256": sha,
                "bytes": bytes_written,
                "kind": "csf",
                "entity_ids": [eid],
            }
        )
    return hint


def _process_subdomains(
    src_root: Path,
    out_root: Path,
    idx: EntityIndex,
    shards: list[dict[str, Any]],
    csf_hint: dict[str, list[str]],
) -> None:
    sd_dir = src_root / "PREPROCESSING" / "SubDomains"
    if not sd_dir.is_dir():
        idx.errors.append({"file": str(sd_dir), "error": "SubDomains dir missing"})
        return
    for domain_dir in sorted(sd_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        for src in sorted(domain_dir.glob("*.md")):
            if not src.stem.startswith("D-"):
                # meta files (Volere_shell, index) — skip for now (already in global)
                continue
            try:
                parsed = parse_subdomain(src)
            except Exception as exc:
                idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                continue

            # Inject CSF hint for the subdomain
            hint = csf_hint.get(parsed["id"], [])
            if hint:
                parsed["csf_hint"] = hint

            # Schema warning tracking
            for w in parsed.get("warnings", []):
                idx.add_warning(str(src), w)

            # Add SubDomain entity
            sd_id = parsed["id"]
            sd_shard = f"entities/subdomains/{sd_id}.json"
            idx.add(sd_id, parsed, sd_shard)

            # Extract HL SO entity (if any)
            if parsed.get("hso_hl") and parsed["hso_hl"].get("id"):
                so_id = parsed["hso_hl"]["id"]
                # Attach subdomain ref
                so_entity = dict(parsed["hso_hl"])
                so_entity["regulation"] = "HL"
                so_entity["source_subdomain"] = sd_id
                idx.add(so_id, so_entity, f"entities/sos/{so_id.replace('.', '_')}.json")

            # Extract per-reg sub-SO entities
            for so in parsed.get("hso_per_reg", []):
                so_id = so["id"]
                so_entity = dict(so)
                so_entity["source_subdomain"] = sd_id
                idx.add(so_id, so_entity, f"entities/sos/{so_id.replace('.', '_')}.json")

            # Extract pair entities
            for pair in parsed.get("pairs", []):
                pair_id = pair["id"]
                pair_entity = dict(pair)
                pair_entity["source_subdomain"] = sd_id
                idx.add(pair_id, pair_entity, f"entities/pairs/{pair_id}.json")

            # Extract SR entities (from §3)
            for sr in parsed.get("security_requirements", []):
                sr_id = sr["id"]
                sr_entity = dict(sr)
                sr_entity["source_subdomain"] = sd_id
                # If yaml_body has linked_objectives, propagate
                yb = sr_entity.get("yaml_body") or {}
                if isinstance(yb, dict):
                    sr_entity["linked_objectives"] = yb.get("linked_objectives") or []
                    sr_entity["source_clauses"] = yb.get("source_clauses") or []
                    sr_entity["nist_csf_mapping"] = yb.get("nist_csf_mapping") or []
                    sr_entity["applies_to_role"] = yb.get("applies_to_role") or []
                    sr_entity["obligation_type"] = yb.get("obligation_type") or []
                    sr_entity["regulatory_rationale"] = yb.get("regulatory_rationale") or ""
                    sr_entity["security_rationale"] = yb.get("security_rationale") or ""
                    sr_entity["ambiguity_notes"] = yb.get("ambiguity_notes") or ""
                idx.add(sr_id, sr_entity, f"entities/srs/{sr_id.replace('.', '_')}.json")

            # Write the SubDomain shard
            bytes_written, sha = _write_json(out_root / sd_shard, parsed)
            shards.append(
                {
                    "path": sd_shard,
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": "subdomain",
                    "entity_ids": [sd_id],
                }
            )
            logger.info("wrote %s (%d bytes)", sd_shard, bytes_written)


def _process_regulation(
    src_root: Path, out_root: Path, idx: EntityIndex, manifest_shards: list[dict[str, Any]]
) -> None:
    reg_dir = src_root / "PREPROCESSING" / "Regulation"
    if not reg_dir.is_dir():
        idx.errors.append({"file": str(reg_dir), "error": "Regulation dir missing"})
        return
    for reg_dir_entry in sorted(reg_dir.iterdir()):
        if not reg_dir_entry.is_dir():
            continue
        regulation = reg_dir_entry.name

        # Roots (00_README, 01_SO, 02_SR_NIST, 03_validation, 04_deduction)
        # v8: under regulation/{reg}/_root/ instead of mixed at the root
        # v9: drop raw_md (the body content is also in
        # regulation/{reg}/aggregated/ for 01_SO/02_SR; for 00_README/
        # 03_validation/04_deduction the body is purely narrative and
        # not duplicated elsewhere — but frontmatter is enough for audit)
        for src in sorted(reg_dir_entry.glob("*.md")):
            shard_path = f"regulation/{regulation}/_root/{src.stem}.json"
            try:
                parsed = parse_root_md(src, include_raw_md=False)
                bytes_written, sha = _write_json(out_root / shard_path, parsed)
            except Exception as exc:
                idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                continue
            manifest_shards.append(
                {
                    "path": shard_path,
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": "regulation_root",
                    "entity_ids": [],
                }
            )

        # Per-article splits
        articles_dir = reg_dir_entry / "Articles"
        if articles_dir.is_dir():
            for src in sorted(articles_dir.glob("Art_*.md")):
                shard_path = f"regulation/{regulation}/articles/{src.stem}.json"
                try:
                    parsed = parse_article_split(src, regulation)
                    for w in parsed.get("warnings", []):
                        idx.add_warning(str(src), w)
                    article_id = parsed["id"]
                    parsed.pop("_id", None)
                    idx.add(article_id, parsed, shard_path)
                    bytes_written, sha = _write_json(out_root / shard_path, parsed)
                except Exception as exc:
                    idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                    continue
                manifest_shards.append(
                    {
                        "path": shard_path,
                        "source_path": str(src),
                        "sha256": sha,
                        "bytes": bytes_written,
                        "kind": "article",
                        "entity_ids": [parsed["id"]],
                    }
                )

        # Aggregated SO + SR (the canonical source files)
        for src_name, kind in [
            ("01_SecurityObjectives.md", "aggregated_SO"),
            ("02_SecurityRules_NIST.md", "aggregated_SR"),
        ]:
            src = reg_dir_entry / src_name
            if not src.is_file():
                continue
            shard_path = f"regulation/{regulation}/aggregated/{src.stem}.json"
            try:
                if kind == "aggregated_SO":
                    sos = parse_security_objectives(src, regulation)
                    # Add each SO as an entity too
                    for so in sos:
                        eid = so["id"]
                        idx.add(eid, so, f"entities/sos/{eid.replace('-', '_')}.json")
                    parsed: dict[str, Any] = {
                        "schema_version": "1.0",
                        "source": str(src),
                        "doc_id": f"AEGIS-PREPROC-{regulation}-SO-AGG",
                        "regulation": regulation,
                        "count": len(sos),
                        "sos": sos,
                    }
                else:
                    srs = parse_security_rules(src, regulation)
                    for sr in srs:
                        eid = sr["id"]
                        idx.add(eid, sr, f"entities/srs/{eid.replace('-', '_')}.json")
                    parsed = {
                        "schema_version": "1.0",
                        "source": str(src),
                        "doc_id": f"AEGIS-PREPROC-{regulation}-SR-AGG",
                        "regulation": regulation,
                        "count": len(srs),
                        "srs": srs,
                    }
                bytes_written, sha = _write_json(out_root / shard_path, parsed)
            except Exception as exc:
                idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                continue
            manifest_shards.append(
                {
                    "path": shard_path,
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": kind,
                    "entity_ids": [],
                }
            )

        # Per-clause (Ambiguity/{REG}/*.md) — universal v2 parser
        # v8: regulation/{reg}/clauses/ (was: ambiguity_clauses/)
        ambig_dir = reg_dir_entry / "Ambiguity"
        if ambig_dir.is_dir():
            reg_norm = regulation.replace("_", "")
            for src in sorted(ambig_dir.glob("*.md")):
                stem_norm = src.stem.replace("_", "")
                if reg_norm not in stem_norm:
                    continue
                # Per-file shard (always)
                file_shard_path = f"regulation/{regulation}/clauses/{src.stem}.json"
                try:
                    parsed = parse_ambiguity_file(src, regulation)
                    clauses = parsed.get("clauses", [])
                except Exception as exc:
                    idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                    continue
                # For AI_Act, the cross-article file 06_AI_Act.md (v0.1) is
                # **superseded by the per-article files 01..08 (v0.2)** —
                # skip its clause-shard generation to avoid duplicating every
                # AIA-Cxx shard. The file-shard itself is still written so
                # the v0.1 content is preserved for traceability.
                skip_clause_shards = regulation == "AI_Act" and src.stem == "06_AI_Act"
                # Write per-clause shards (1 JSON per clause_id) — only if
                # the file yielded per-clause entities. Cross-article v0.1
                # files (e.g. 06_AI_Act.md) overlap with v0.2 per-article
                # files; we dedup by ID so per-article wins.
                for clause in parsed.get("clauses", []):
                    eid = clause.get("id")
                    if not eid:
                        continue
                    if skip_clause_shards:
                        continue
                    # If the per-article source has already registered this
                    # clause (and this is a cross-article v0.1 overlap), skip
                    # to avoid duplicate clause shards.
                    if eid in idx.entities and parsed["kind"] == "cross_article":
                        continue
                    clause_shard = f"entities/clauses/{eid.replace('-', '_')}.json"
                    # Don't overwrite the file-shard with a clause-shard
                    if clause_shard == file_shard_path:
                        continue
                    try:
                        bytes_written, sha = _write_json(out_root / clause_shard, clause)
                        manifest_shards.append(
                            {
                                "path": clause_shard,
                                "source_path": str(src),
                                "sha256": sha,
                                "bytes": bytes_written,
                                "kind": "clause",
                                "entity_ids": [eid],
                            }
                        )
                        idx.add(eid, clause, clause_shard)
                    except Exception as exc:
                        idx.errors.append(
                            {"file": str(src), "error": f"clause shard {eid}: {exc!r}"}
                        )
                # Per-file shard
                try:
                    file_entity = parsed["file"]
                    file_entity["kind"] = parsed["kind"]
                    file_entity["clause_ids"] = [c["id"] for c in parsed.get("clauses", [])]
                    bytes_written, sha = _write_json(out_root / file_shard_path, file_entity)
                    manifest_shards.append(
                        {
                            "path": file_shard_path,
                            "source_path": str(src),
                            "sha256": sha,
                            "bytes": bytes_written,
                            "kind": f"ambiguity_{parsed['kind']}",
                            "entity_ids": [],
                        }
                    )
                    logger.info("wrote %s (%d bytes)", file_shard_path, bytes_written)
                except Exception as exc:
                    idx.errors.append({"file": str(src), "error": f"file shard: {exc!r}"})
                manifest_shards.append(
                    {
                        "path": shard_path,
                        "source_path": str(src),
                        "sha256": sha,
                        "bytes": bytes_written,
                        "kind": "ambiguity_clause_file",
                        "entity_ids": [c["id"] for c in clauses],
                    }
                )


def _process_crossregulation(
    src_root: Path, out_root: Path, idx: EntityIndex, shards: list[dict[str, Any]]
) -> None:
    cr_dir = src_root / "PREPROCESSING" / "CrossRegulation"
    if not cr_dir.is_dir():
        return
    for src in sorted(cr_dir.rglob("*.md")):
        if "_archive" in src.parts:
            continue
        rel = src.relative_to(cr_dir)
        # v8: root-level templates go to _templates/
        if rel.parent == Path("."):
            shard_path = f"crossregulation/_templates/{rel.with_suffix('.json').name}"
        else:
            shard_path = f"crossregulation/{rel.with_suffix('.json')}"
        try:
            text = src.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            participants_m = __import__("re").search(
                r"\*\*Participants\s+\(from\s+CRDA[^*]*\)\*\*:\s*([^\n]+)", body
            )
            participants: list[str] = []
            if participants_m:
                participants = [
                    r.strip().rstrip(",")
                    for r in __import__("re").split(r"[,/]", participants_m.group(1))
                    if r.strip()
                ]
            # v10: structured parsers for the 3 special filenames
            sub_kind = (
                "domain_analysis"
                if "DomainAnalysis" in rel.parts
                else "deep_analysis"
                if "DeepAnalysis" in rel.parts
                else "index"
            )
            if src.name == "index.md" and sub_kind in ("domain_analysis", "deep_analysis"):
                parsed = parse_crossregulation_index(src)
                parsed["sub_kind"] = sub_kind
            elif src.name == "TEMPLATE_crossreg_brief.md":
                parsed = parse_crossregulation_brief_template(src)
                parsed["sub_kind"] = "template"
            else:
                # Per-subdomain files (D-XX_*) — keep the v8 form for Fase 2
                parsed = {
                    "schema_version": "1.0",
                    "source": str(src),
                    "doc_id": fm.get("document_id", f"AEGIS-PREPROC-CRDA-{rel}"),
                    "sub_kind": sub_kind,
                    "macro_domain": fm.get("macro_domain", ""),
                    "sub_domain": fm.get("sub_domain", ""),
                    "title": fm.get("title", src.stem),
                    "status": fm.get("status", ""),
                    "frontmatter": fm,
                    "participants": participants,
                    "raw_md": body.strip(),
                }
            bytes_written, sha = _write_json(out_root / shard_path, parsed)
            bytes_written, sha = _write_json(out_root / shard_path, parsed)
            shards.append(
                {
                    "path": shard_path,
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": "crossreg",
                    "entity_ids": [],
                }
            )
        except Exception as exc:
            idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})


def _process_diagrams(
    src_root: Path, out_root: Path, idx: EntityIndex, shards: list[dict[str, Any]]
) -> None:
    diag_root = src_root / "diagrams"
    if not diag_root.is_dir():
        return
    for src in sorted(diag_root.rglob("*.md")):
        # Skip README and the (sometimes empty) class_models root README
        if src.name == "README.md":
            continue
        rel = src.relative_to(diag_root)
        shard_path = f"diagrams/{rel.with_suffix('.json')}"
        try:
            parsed = parse_diagram(src)
            bytes_written, sha = _write_json(out_root / shard_path, parsed)
            shards.append(
                {
                    "path": shard_path,
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": "diagram",
                    "entity_ids": [],
                }
            )
            logger.info("wrote %s (%d bytes)", shard_path, bytes_written)
        except Exception as exc:
            idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})


def _process_global_and_ambiguity_analysis(
    src_root: Path, out_root: Path, idx: EntityIndex, shards: list[dict[str, Any]]
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    xlsx_path = repo_root / "csf2.xlsx"
    # Top-level global files
    for src in sorted((src_root / "PREPROCESSING").glob("*.md")):
        shard_path = f"global/{src.stem}.json"
        try:
            # Special-case: NIST_CSF_2.0_subcategories.md is fully structured
            # (per-entity shards already written in _process_csf). The aggregated
            # top-level view must NOT carry raw_md.
            if src.name == "NIST_CSF_2.0_subcategories.md":
                if xlsx_path.is_file():
                    parsed = parse_root_csf_xlsx_structured(xlsx_path, src)
                else:
                    parsed = parse_root_csf_structured(src)
            elif src.name == "TEMPLATE_subagent_brief.md":
                # v10: structured parse (constraints[], bullet_lists[]) + raw_md
                parsed = parse_subagent_brief_template(src)
            elif src.name == "README.md":
                # v10: structured parse (sections[]) + raw_md
                parsed = parse_preproc_readme(src)
            elif src.name == "00_Hierarchical_SecurityObjectives.md":
                # v10: HSO is purely design rationale — keep parse_root_md
                # but the body is preserved verbatim (no info loss)
                parsed = parse_root_md(src)
                parsed["raw_md_kept_reason"] = "narrative_design_rationale_no_structured_form"
            else:
                parsed = parse_root_md(src)
            bytes_written, sha = _write_json(out_root / shard_path, parsed)
            shards.append(
                {
                    "path": shard_path,
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": "global",
                    "entity_ids": [],
                }
            )
        except Exception as exc:
            idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})

    # AMBIGUITY_ANALYSIS/
    ambig_dir = src_root / "PREPROCESSING" / "AMBIGUITY_ANALYSIS"
    if ambig_dir.is_dir():
        for src in sorted(ambig_dir.glob("*.md")):
            shard_path = f"ambiguity_analysis/{src.stem}.json"
            try:
                # v10: structured parsers per filename
                if src.name == "00_Index.md":
                    parsed = parse_ambiguity_index(src)
                elif src.name == "01_Framework.md":
                    parsed = parse_ambiguity_framework(src)
                else:
                    parsed = parse_root_md(src)
                bytes_written, sha = _write_json(out_root / shard_path, parsed)
                shards.append(
                    {
                        "path": shard_path,
                        "source_path": str(src),
                        "sha256": sha,
                        "bytes": bytes_written,
                        "kind": "ambiguity_analysis",
                        "entity_ids": [],
                    }
                )
            except Exception as exc:
                idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})


# ─── helpers (parsers reused from raw_md) ──────────────────────────────


def parse_root_md(path: Path, include_raw_md: bool = True) -> dict[str, Any]:
    """Parse a top-level ``.md`` into a structured dict (no full extraction).

    Used as a catch-all for narrative .md files where the body is not
    further parsed (regulation root files, global templates, etc.).

    **CORR-024 v9:** callers that have a structured counterpart for the
    body (e.g. ``regulation/{REG}/aggregated/``) should pass
    ``include_raw_md=False`` to drop the raw_md field — the body content
    is then only kept in frontmatter (for traceability) and the
    counterpart (for the structured form). This shrinks preproc_out by
    ~1.7 MB for regulation/_root/ (25 files) without losing audit info.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    out: dict[str, Any] = {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
    }
    if include_raw_md:
        out["raw_md"] = body.strip()
    return out


def parse_root_csf_xlsx_structured(xlsx_path: Path, md_path: Path | None) -> dict[str, Any]:
    """Aggregated top-level view of csf2.xlsx (CORR-024 v5 source of truth).

    The xlsx doesn't carry the D-XX cross-reference table — that comes from
    the legacy .md (still authoritative for AEGIS sub-domain mapping). All
    other fields are sourced from the xlsx:
      - introduction (Title, Read Me, Change Log, Generated Date)
      - function_structure (6 functions, with category + subcategory counts)
      - subcategories (185, with implementation_examples + informative_references)
      - categories (34 — function-grouped, with subcategory counts)
      - reference_families (21 families, sorted by count desc)
      - withdrawn_subcategories (79)
    """
    parsed = parse_csf2(xlsx_path)
    intro = parsed["introduction"]

    # Pull the D-XX cross-reference from the legacy .md if present — it's
    # the only place AEGIS sub-domain → CSF mapping lives.
    crossref_block = None
    if md_path is not None and md_path.is_file():
        try:
            crossref_block = parse_csf_crossref_full(md_path)
        except Exception:
            crossref_block = None

    return {
        "schema_version": "1.3",
        "source": str(xlsx_path),
        "source_md_legacy": str(md_path) if md_path else None,
        "doc_id": "AEGIS-PREPROC-CSF-2.0-REFTOOL",
        "title": intro.get("title", "NIST CSF 2.0 (Reference Tool export)"),
        "status": intro.get("change_log", ""),
        "kind": "csf_reference",
        "tool_metadata": {
            "title": intro.get("title", ""),
            "read_me": intro.get("read_me", ""),
            "change_log": intro.get("change_log", ""),
            "generated_date": intro.get("generated_date", ""),
        },
        "introduction": intro,
        "function_structure": {
            "title": "Function structure",
            "source": "csf2.xlsx (column A merged-cell aggregation)",
            "functions": parsed["functions"],
            "totals": {
                "function_count": len(parsed["functions"]),
                "category_count": sum(f["category_count"] for f in parsed["functions"]),
                "subcategory_count": sum(f["subcategory_count"] for f in parsed["functions"]),
                "withdrawn_count": sum(f["withdrawn_count"] for f in parsed["functions"]),
            },
        },
        "categories": parsed["categories"],
        "subcategories": [
            {
                "id": s["id"],
                "function": s["function"],
                "function_name": s["function_name"],
                "category_id": s["category_id_resolved"],
                "category_name": _category_name_only(s["category_name_text"]),
                "number": s["number"],
                "title": s["title"],
                "withdrawn": s["withdrawn"],
                "withdrawal_note": s["withdrawal_note"],
                "implementation_example_count": len(s["implementation_examples"]),
                "informative_reference_count": len(s["informative_references"]),
                "reference_families": s["reference_families"],
                "source_locus": s["source_locus"],
            }
            for s in parsed["subcategories"]
            if not s["withdrawn"]  # active subs only in the main list
        ],
        # All 185 subcategories (active + withdrawn) — full audit trail
        "all_subcategories": [
            {
                "id": s["id"],
                "function": s["function"],
                "category_id": s["category_id_resolved"],
                "title": s["title"],
                "withdrawn": s["withdrawn"],
                "withdrawal_note": s["withdrawal_note"],
            }
            for s in parsed["subcategories"]
        ],
        "reference_families": parsed["reference_families"],
        # Withdrawn subcategories are KEPT HERE for audit traceability,
        # but they are NOT materialized as per-subcategory shards (they
        # have no actionable content in the official xlsx).
        # Each entry has the parsed ``withdrawal_target_ids`` (the active
        # subcategories that absorbed the withdrawn one) extracted from
        # the withdrawal_note ("Incorporated into ID.AM-08, PR.PS-03"
        # → ["ID.AM-08", "PR.PS-03"]).
        "withdrawn_subcategories": [
            {
                **w,
                "withdrawal_target_ids": _extract_withdrawal_targets(w.get("withdrawal_note", "")),
            }
            for w in parsed["withdrawn_subcategories"]
        ],
        # Cross-reference is taken from the .md (advisory, AEGIS sub-domain
        # mapping is not in the xlsx).
        "cross_reference_aegis_subdomains": (
            {
                "title": crossref_block.get("title", "Cross-reference"),
                "table_header": crossref_block.get("table_header", []),
                "rows": crossref_block.get("rows", []),
                "csf_ids_by_d": crossref_block.get("csf_ids_by_d", {}),
                "advisory_blockquote": crossref_block.get("advisory_blockquote"),
                "source_locus": crossref_block.get("source_locus", {}),
            }
            if crossref_block
            else None
        ),
        "cross_reference_aegis_subdomains_advisory_only": True,
        "counts": parsed["counts"],
    }


def _category_name_only(text: str) -> str:
    """Strip ``(FUNC.CAT)`` and trailing description from a Category cell."""
    import re as _re

    txt = _re.sub(r"\s*\([A-Z]{2}\.[A-Z]{2,3}\)\s*", " ", text)
    if ":" in txt:
        txt = txt.rsplit(":", 1)[0]
    return txt.strip()


def _extract_withdrawal_targets(note: str) -> list[str]:
    """Extract target subcategory IDs from a withdrawal note.

    Example:
        ``"Incorporated into ID.AM-08, PR.PS-03"`` → ``["ID.AM-08", "PR.PS-03"]``
        ``"Moved to PR.IR-04"`` → ``["PR.IR-04"]``
        ``"Incorporated into ID.IM-03, ID.IM-04"`` → ``["ID.IM-03", "ID.IM-04"]``
    """
    import re as _re

    return _re.findall(r"[A-Z]{2}\.[A-Z]{2,3}-\d{2}", note or "")


def parse_root_csf_structured(path: Path) -> dict[str, Any]:
    """Structured (no raw_md) aggregate of NIST_CSF_2.0_subcategories.md.

    Maps every element of the source to a typed field. The per-subcategory
    shards are written by ``_process_csf``. All ``source_locus`` values are
    **source-file line numbers** (1-indexed) — the frontmatter offset is
    added on top of the body-relative indices returned by the parsers.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    # The body starts with the first character after the closing `---`
    # fence + a single newline. We need the 1-indexed line where body
    # starts in the source file so we can shift body-relative loci.
    body_start_in_source = text[: len(text) - len(body)].count("\n") + 1
    h1_title = parse_csf_h1_title(path)
    fn_struct = parse_csf_function_structure(path)
    crossref = parse_csf_crossref_full(path)
    special = parse_csf_special_tokens_full(path)
    authority = parse_csf_authority_note_full(path)
    end_ref = parse_csf_end_of_reference(path)
    subcats = parse_csf(path)

    def shift_locus(locus: dict[str, int]) -> dict[str, int]:
        return {
            "start_line": locus["start_line"] + body_start_in_source - 1
            if locus.get("start_line", 0) > 0
            else 0,
            "end_line": locus["end_line"] + body_start_in_source - 1
            if locus.get("end_line", 0) > 0
            else 0,
        }

    # Cross-reference loci (table_rows) are body-relative; shift to source.
    crossref_rows_shifted: list[dict[str, Any]] = []
    for row in crossref["rows"]:
        row = dict(row)
        row["source_locus"] = shift_locus(row["source_locus"])
        crossref_rows_shifted.append(row)

    # Advisory blockquote line is body-relative; shift.
    adv_bq = crossref["advisory_blockquote"]
    if adv_bq:
        adv_bq = dict(adv_bq)
        adv_bq["line"] = adv_bq["line"] + body_start_in_source - 1

    # Function structure locus
    fn_struct_shifted = dict(fn_struct)
    fn_struct_shifted["source_locus"] = shift_locus(fn_struct["source_locus"])

    # Special tokens locus
    special_shifted = dict(special)
    special_shifted["source_locus"] = shift_locus(special["source_locus"])

    # End-of-reference line is body-relative; shift.
    if end_ref:
        end_ref_shifted = dict(end_ref)
        end_ref_shifted["line"] = end_ref["line"] + body_start_in_source - 1
    else:
        end_ref_shifted = None

    return {
        "schema_version": "1.1",
        "source": str(path),
        "doc_id": fm.get("document_id", "AEGIS-PREPROC-CSF-REF"),
        "title": fm.get("title", "NIST CSF 2.0 Subcategory Reference (Frozen List)"),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "kind": "csf_reference",
        # YAML frontmatter — every key, parsed by PyYAML
        "frontmatter": fm,
        # H1 title (line 18 in source)
        "h1_title": h1_title,
        # Authority blockquote (line 20) — full text + source-relative locus
        "authority_note": {
            "text": authority["text"],
            "source_locus": shift_locus(
                {
                    "start_line": authority["start_line"],
                    "end_line": authority["end_line"],
                }
            ),
        },
        # Function structure table (source lines 24-36) — title + summary + table
        "function_structure": fn_struct_shifted,
        # Per-subcategory — 98 rows mapped 1:1 to source rows
        "subcategories": [
            {
                "id": s["id"],
                "function": s["function"],
                "function_name": s["function_name"],
                "category_id": s["category_id"],
                "category_name": s["category_name"],
                "number": s["number"],
                "title": s["title"],
                "source_locus": shift_locus(s["source_locus"]),
                "aegis_subdomain_back_refs": s.get("aegis_subdomain_back_refs", []),
            }
            for s in subcats
        ],
        # Per-category — H3 headers from source (deduplicated)
        "categories": sorted(
            {
                (
                    s["category_id"],
                    s["function"],
                    s["function_name"],
                    s["category_name"],
                ): {
                    "id": s["category_id"],
                    "function": s["function"],
                    "function_name": s["function_name"],
                    "name": s["category_name"],
                }
                for s in subcats
            }.values(),
            key=lambda c: c["id"],
        ),
        # Cross-reference table (source lines 267-310) — full H2 + table + advisory
        "cross_reference_aegis_subdomains": {
            "title": crossref["title"],
            "table_header": crossref["table_header"],
            "rows": crossref_rows_shifted,
            "csf_ids_by_d": crossref["csf_ids_by_d"],
            "advisory_blockquote": adv_bq,
            "source_locus": shift_locus(crossref["source_locus"]),
        },
        "cross_reference_aegis_subdomains_advisory_only": True,
        # Special tokens table — H2 + table header + rows
        "special_tokens": special_shifted,
        # Closing line "**End of reference.**" (source-relative line)
        "end_of_reference": end_ref_shifted,
        # Aggregate counts
        "counts": {
            "subcategories": len(subcats),
            "categories": len({s["category_id"] for s in subcats}),
            "functions": len({s["function"] for s in subcats}),
        },
    }


def parse_article_split(path: Path, regulation: str) -> dict[str, Any]:
    """Parse one ``Articles/Art_NN.md`` file into a structured Article entity."""
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    article_ref = str(fm.get("article", "UNKNOWN"))

    # Security Objectives table
    so_table_m = re.search(
        r"##\s+Security\s+Objectives[^\n]*\n(?P<body>.+?)(?=\n##\s+|\Z)",
        body,
        re.DOTALL,
    )
    so_list: list[dict[str, Any]] = []
    if so_table_m:
        from .parsers.markdown import extract_table_rows

        for row in extract_table_rows(so_table_m.group("body")):
            if len(row) < 4:
                continue
            so_id = row[0].strip()
            if not re.fullmatch(r"SO-[A-Z_0-9]+-\d{3}", so_id):
                continue
            so_list.append(
                {
                    "so_id": so_id,
                    "description": row[1].strip(),
                    "source_clauses": [s.strip() for s in row[2].split(";") if s.strip()],
                    "sub_domains": [s.strip() for s in row[3].split(",") if s.strip()],
                }
            )

    # Security Rules section: ### headers + ```yaml blocks
    sr_section_m = re.search(
        r"##\s+Security\s+Rules[^\n]*\n(?P<body>.+?)(?=\n##\s+|\Z)",
        body,
        re.DOTALL,
    )
    sr_list: list[dict[str, Any]] = []
    if sr_section_m:
        import yaml as _yaml

        from .parsers.markdown import extract_fenced_blocks

        sr_body = sr_section_m.group("body")
        for h_m in re.finditer(r"###\s+(.+)", sr_body):
            heading = h_m.group(1).strip()
            after = sr_body[h_m.end() :]
            nxt = re.search(r"^###\s+", after, re.MULTILINE)
            block = after[: nxt.start()] if nxt else after
            for lang, yaml_body in extract_fenced_blocks(block, lang="yaml"):
                try:
                    parsed = _yaml.safe_load(yaml_body)
                except _yaml.YAMLError:
                    continue
                items = (
                    parsed
                    if isinstance(parsed, list)
                    else [parsed]
                    if isinstance(parsed, dict)
                    else []
                )
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    sr_id = str(it.get("sr_id", "")).strip()
                    if not sr_id:
                        continue
                    sr_list.append(
                        {
                            "sr_id": sr_id,
                            "title": str(it.get("title", "")).strip(),
                            "heading_under": heading,
                            "source_clauses": it.get("source_clauses") or [],
                            "linked_objectives": it.get("linked_objectives") or [],
                            "sub_domain": it.get("sub_domain") or [],
                            "nist_csf_mapping": it.get("nist_csf_mapping") or [],
                            "applies_to_role": it.get("applies_to_role") or [],
                            "obligation_type": it.get("obligation_type") or [],
                            "regulatory_rationale": str(
                                it.get("regulatory_rationale", "") or ""
                            ).strip(),
                            "security_rationale": str(
                                it.get("security_rationale", "") or ""
                            ).strip(),
                            "ambiguity_notes": str(it.get("ambiguity_notes", "") or "").strip(),
                        }
                    )

    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{regulation}-ART-{article_ref}"),
        "id": f"{regulation}_{article_ref}",
        "regulation": regulation,
        "article_ref": article_ref,
        "title": str(fm.get("title", "")),
        "status": str(fm.get("status", "")),
        "frontmatter": fm,
        "security_objectives": so_list,
        "security_rules": sr_list,
    }


import re  # for the crossregulation regex

# ─── global indices ────────────────────────────────────────────────────


def _build_indices(idx: EntityIndex, out_root: Path, shards: list[dict[str, Any]]) -> None:
    entities_index: dict[str, str] = {}  # id → shard path
    for shard_path, ids in idx.shard_contents.items():
        for eid in ids:
            entities_index[eid] = shard_path

    # Write a standalone shard per entity (so consumers can load by id).
    for eid, entity in idx.entities.items():
        if "_id" in entity:
            del entity["_id"]
        # Find the canonical shard path for this entity
        kind = _entity_kind(entity)
        subdir_map = {
            "subdomain": "subdomains",
            "so": "sos",
            "so_hl": "sos",
            "sr": "srs",
            "pair": "pairs",
            "clause": "clauses",
            "csf": "csfs",
            "ambiguity": "ambiguities",
            "article": "articles",
        }
        sub = subdir_map.get(kind)
        if sub is None:
            continue
        fname = eid.replace(".", "_").replace("-", "_")
        # CORR-024 v7: CSF shards live in per-Function subfolders
        # entities/csfs/{FUNC}/{FUNC}_{CAT}_{NUM}.json
        if kind == "csf":
            fn = entity.get("function")
            if fn:
                entity_path = out_root / "entities" / sub / fn / f"{fname}.json"
            else:
                entity_path = out_root / "entities" / sub / f"{fname}.json"
        else:
            entity_path = out_root / "entities" / sub / f"{fname}.json"
        if entity_path.exists():
            continue  # already written by a per-section processor
        try:
            bytes_written, sha = _write_json(entity_path, entity)
            shards.append(
                {
                    "path": str(entity_path.relative_to(out_root)),
                    "source_path": entity.get("source", "?"),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": f"entity_{kind}",
                    "entity_ids": [eid],
                }
            )
        except Exception:  # pragma: no cover — defensive
            pass

    # by_regulation
    by_reg: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for eid, entity in idx.entities.items():
        reg = entity.get("regulation")
        kind = _entity_kind(entity)
        if reg:
            by_reg[reg][kind].append(eid)

    # by_subdomain
    by_sd: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for eid, entity in idx.entities.items():
        sd = entity.get("subdomain_id") or entity.get("source_subdomain")
        if not sd:
            if entity.get("id", "").startswith("D-") and entity.get("id", "").count(".") == 1:
                by_sd[entity["id"]]["self"] = [eid]
            continue
        kind = _entity_kind(entity)
        by_sd[sd][kind].append(eid)

    # cross_references (DAG of points_to / pointed_by)
    cross_refs: dict[str, dict[str, list[str]]] = {}
    for eid, entity in idx.entities.items():
        pts: set[str] = set()
        # SO → linked SOs (sub_so_id contains SO-...)
        for lo in entity.get("linked_objectives") or []:
            if lo.startswith("SO-"):
                pts.add(lo)
        # SO → SRs via source_SR
        for sr in entity.get("source_SR") or []:
            if sr.startswith("SR-"):
                pts.add(sr)
        # SO → sub_domains
        for sd in entity.get("sub_domains") or []:
            pts.add(sd)
        # SO → clauses
        for sc in entity.get("source_clauses") or []:
            if isinstance(sc, dict):
                if sc.get("clause_id"):
                    pts.add(sc["clause_id"])
        # SO → CSF
        for csf in entity.get("csf") or entity.get("nist_csf_mapping") or []:
            if isinstance(csf, str):
                pts.add(csf)
            elif isinstance(csf, dict) and csf.get("id"):
                pts.add(csf["id"])
        # SR → clauses / SOs / CSF
        for sc in entity.get("source_clauses") or []:
            if isinstance(sc, dict) and sc.get("clause_id"):
                pts.add(sc["clause_id"])
        # Pair → sub-SOs of reg_a and reg_b
        if entity.get("id", "").startswith("D-") and "-" in entity.get("pair", ""):
            # collect the per-reg SO ids this pair relates to
            sd_id = entity.get("source_subdomain")
            if sd_id:
                for so in by_sd.get(sd_id, {}).get("so", []):
                    pts.add(so)
        # Article → SOs / SRs
        for so in entity.get("security_objectives") or []:
            if isinstance(so, dict) and so.get("so_id"):
                pts.add(so["so_id"])
        for sr in entity.get("security_rules") or []:
            if isinstance(sr, dict) and sr.get("sr_id"):
                pts.add(sr["sr_id"])

        if pts:
            cross_refs[eid] = {"points_to": sorted(pts)}

    # invert: pointed_by (collect first, then mutate)
    edges: list[tuple[str, str]] = []
    for src, dest in cross_refs.items():
        for tgt in dest["points_to"]:
            edges.append((src, tgt))
    for src, tgt in edges:
        cross_refs.setdefault(tgt, {"points_to": []})
        cross_refs[tgt].setdefault("pointed_by", []).append(src)

    _write_json(
        out_root / "index" / "entities.json",
        {
            "schema_version": "2.0",
            "count": len(entities_index),
            "by_id": entities_index,
        },
    )
    _write_json(
        out_root / "index" / "by_regulation.json",
        {"schema_version": "2.0", "by_regulation": dict(by_reg)},
    )
    _write_json(
        out_root / "index" / "by_subdomain.json",
        {"schema_version": "2.0", "by_subdomain": dict(by_sd)},
    )
    _write_json(
        out_root / "index" / "cross_references.json",
        {"schema_version": "2.0", "count": len(cross_refs), "graph": cross_refs},
    )
    logger.info(
        "wrote indices: %d entities, %d regs, %d subdomains, %d cross-refs",
        len(entities_index),
        len(by_reg),
        len(by_sd),
        len(cross_refs),
    )


def _entity_kind(entity: dict[str, Any]) -> str:
    """Best-effort classification of an entity for index buckets."""
    eid = entity.get("id", "")
    # Pairs have a "pair" field (e.g. "GDPR ↔ CRA") AND id starts with "D-XX.Y_"
    if entity.get("pair") and "↔" in entity.get("pair", ""):
        return "pair"
    if entity.get("is_high_level") or eid.endswith(".HL"):
        return "so_hl"
    if eid.startswith("SO-"):
        return "so"
    if eid.startswith("SR-"):
        return "sr"
    if (
        eid.startswith("GDPR-CL")
        or eid.startswith("NIS2-CL")
        or eid.startswith("CRA-CL")
        or eid.startswith("DORA-CL")
        or eid.startswith("AI_Act-CL")
        or eid.startswith("AIACT-CL")
    ):
        return "clause"
    if re.match(r"^[A-Z]{2}\.[A-Z]{2}-\d{2}$", eid):
        return "csf"
    if eid.startswith("D-") and entity.get("id", "").count(".") == 1:
        return "subdomain"
    if "_" in eid and "ART" in entity.get("doc_id", ""):
        return "article"
    return "other"


def _write_manifest(
    src_root: Path,
    out_root: Path,
    shards: list[dict[str, Any]],
    parse_errors: list[dict[str, str]],
    parse_warnings: list[dict[str, str]],
) -> dict[str, Any]:
    # deterministic built_at = max source mtime
    src_mtime = max(
        (p.stat().st_mtime for p in src_root.rglob("*") if p.is_file()),
        default=0.0,
    )
    built_at = datetime.fromtimestamp(src_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Strict: any warning is an error
    errors = list(parse_errors)
    for w in parse_warnings:
        errors.append({"file": w["file"], "error": f"warning: {w['warning']}"})

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "built_at": built_at,
        "source_root": str(src_root),
        "method_version": "2.0",
        "shard_count": len(shards),
        "shards": shards,
        "errors": errors,
    }
    # v8: manifest + build_info live under meta/
    _write_json(out_root / "meta" / "manifest.json", manifest)
    _write_json(
        out_root / "meta" / "build_info.json",
        {
            "schema_version": SCHEMA_VERSION,
            "built_at": built_at,
            "source_root": str(src_root),
            "method_version": "2.0",
            "shard_count": len(shards),
            "error_count": len(errors),
        },
    )
    return manifest
