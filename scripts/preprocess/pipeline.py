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
from .parsers.entities.csf import parse_csf, parse_csf_d_subdomain_hints
from .parsers.entities.clause import parse_clause_file
from .parsers.entities.subdomain import parse_subdomain
from .parsers.frontmatter import parse_frontmatter
from .parsers.markdown import extract_fenced_blocks

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "2.0"


# ─── helpers ────────────────────────────────────────────────────────────


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            self.sources[entity_id + "::ref::" + str(len([k for k in self.sources if k.startswith(entity_id + "::ref::")]))] = entity.get("source", "?")
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
    # Pre-create the entity subdirs so we can sanity-check the layout
    for kind in (
        "subdomain", "article", "clause", "so", "sr", "pair", "ambiguity", "csf"
    ):
        (output_root / "entities" / f"{kind}s").mkdir(parents=True, exist_ok=True)

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
    return _write_manifest(
        source_root, output_root, manifest_shards, idx.errors, idx.warnings
    )


# ─── section processors ────────────────────────────────────────────────


def _process_csf(
    src_root: Path, out_root: Path, idx: EntityIndex, shards: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """Parse NIST_CSF_2.0_subcategories.md → 1 JSON per subcategory + D-XX hint table."""
    csf_path = src_root / "PREPROCESSING" / "NIST_CSF_2.0_subcategories.md"
    if not csf_path.is_file():
        idx.add_warning(str(csf_path), "CSF reference file missing")
        return {}
    subcats = parse_csf(csf_path)
    hint = parse_csf_d_subdomain_hints(csf_path)
    for sc in subcats:
        eid = sc["id"]
        shard_path = f"entities/csfs/{eid.replace('.', '_')}.json"
        idx.add(eid, sc, shard_path)
    for eid, entity in list(idx.entities.items()):
        if entity.get("id", "").startswith("GV.") or "/" in str(entity):
            continue
    # Write shards
    for eid, entity in list(idx.entities.items()):
        if entity.get("schema_version") != "1.0":
            continue
        if not (entity.get("id", "").count(".") == 2 and len(entity.get("id", "")) == 7):
            continue
        if entity.get("id", "").startswith("SO-") or entity.get("id", "").startswith("SR-"):
            continue
        shard_path = f"entities/csfs/{entity['id'].replace('.', '_')}.json"
        bytes_written, sha = _write_json(out_root / shard_path, entity)
        shards.append(
            {
                "path": shard_path,
                "source_path": entity["source"],
                "sha256": sha,
                "bytes": bytes_written,
                "kind": "csf",
                "entity_ids": [entity["id"]],
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
            sd_shard = f"subdomains/{sd_id}.json"
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
    src_root: Path, out_root: Path, idx: EntityIndex, shards: list[dict[str, Any]]
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
        for src in sorted(reg_dir_entry.glob("*.md")):
            shard_path = f"regulation/{regulation}/{src.stem}.json"
            try:
                parsed = parse_root_md(src)
                bytes_written, sha = _write_json(out_root / shard_path, parsed)
            except Exception as exc:
                idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                continue
            shards.append(
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
                shards.append(
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
            shards.append(
                {
                    "path": shard_path,
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": kind,
                    "entity_ids": [],
                }
            )

        # Per-clause (Ambiguity/{REG}-CLxx_*.md)
        ambig_dir = reg_dir_entry / "Ambiguity"
        if ambig_dir.is_dir():
            reg_norm = regulation.replace("_", "")
            for src in sorted(ambig_dir.glob("*.md")):
                stem_norm = src.stem.replace("_", "")
                if reg_norm not in stem_norm:
                    continue
                shard_path = (
                    f"regulation/{regulation}/ambiguity_clauses/{src.stem}.json"
                )
                try:
                    clauses = parse_clause_file(src, regulation)
                    for c in clauses:
                        for w in c.get("warnings", []):
                            idx.add_warning(str(src), w)
                        eid = c["id"]
                        c.pop("_id", None)
                        idx.add(eid, c, f"entities/clauses/{eid}.json")
                    bytes_written, sha = _write_json(
                        out_root / shard_path, {"clauses": clauses}
                    )
                except Exception as exc:
                    idx.errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                    continue
                shards.append(
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
            parsed = {
                "schema_version": "1.0",
                "source": str(src),
                "doc_id": fm.get("document_id", f"AEGIS-PREPROC-CRDA-{rel}"),
                "sub_kind": "domain_analysis"
                if "DomainAnalysis" in rel.parts
                else "deep_analysis"
                if "DeepAnalysis" in rel.parts
                else "index",
                "macro_domain": fm.get("macro_domain", ""),
                "sub_domain": fm.get("sub_domain", ""),
                "title": fm.get("title", src.stem),
                "status": fm.get("status", ""),
                "frontmatter": fm,
                "participants": participants,
                "raw_md": body.strip(),
            }
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
    # Top-level global files
    for src in sorted((src_root / "PREPROCESSING").glob("*.md")):
        shard_path = f"global/{src.stem}.json"
        try:
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


def parse_root_md(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    return {
        "schema_version": "1.0",
        "source": str(path),
        "doc_id": fm.get("document_id", f"AEGIS-PREPROC-{path.stem}"),
        "title": fm.get("title", path.stem),
        "status": fm.get("status", ""),
        "chain_version": fm.get("chain_version", ""),
        "frontmatter": fm,
        "raw_md": body.strip(),
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
                    "source_clauses": [
                        s.strip() for s in row[2].split(";") if s.strip()
                    ],
                    "sub_domains": [
                        s.strip() for s in row[3].split(",") if s.strip()
                    ],
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
            after = sr_body[h_m.end():]
            nxt = re.search(r"^###\s+", after, re.MULTILINE)
            block = after[: nxt.start()] if nxt else after
            for lang, yaml_body in extract_fenced_blocks(block, lang="yaml"):
                try:
                    parsed = _yaml.safe_load(yaml_body)
                except _yaml.YAMLError:
                    continue
                items = (
                    parsed if isinstance(parsed, list) else [parsed] if isinstance(parsed, dict) else []
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
                            "ambiguity_notes": str(
                                it.get("ambiguity_notes", "") or ""
                            ).strip(),
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


def _build_indices(
    idx: EntityIndex, out_root: Path, shards: list[dict[str, Any]]
) -> None:
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
            "so": "sos", "so_hl": "sos",
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
        except Exception as exc:  # pragma: no cover — defensive
            pass

    # by_regulation
    by_reg: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for eid, entity in idx.entities.items():
        reg = entity.get("regulation")
        kind = _entity_kind(entity)
        if reg:
            by_reg[reg][kind].append(eid)

    # by_subdomain
    by_sd: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
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
    if eid.startswith("GDPR-CL") or eid.startswith("NIS2-CL") or eid.startswith(
        "CRA-CL"
    ) or eid.startswith("DORA-CL") or eid.startswith("AI_Act-CL") or eid.startswith(
        "AIACT-CL"
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
    _write_json(out_root / "manifest.json", manifest)
    _write_json(
        out_root / "build_info.json",
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
