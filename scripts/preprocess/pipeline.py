"""Pipeline orchestrator: walk source, parse, write shards, write manifest."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parsers.article import parse_article
from .parsers.crossreg import parse_crossreg, parse_global
from .parsers.subdomain import parse_subdomain

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_default(o: Any) -> Any:
    """JSON encoder fallback for non-serializable types from PyYAML."""
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _write_json(path: Path, data: dict[str, Any]) -> tuple[int, str]:
    """Write ``data`` as pretty JSON. Returns ``(bytes, sha256)``."""
    text = json.dumps(
        data, indent=2, ensure_ascii=False, sort_keys=False, default=_json_default
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    raw = text.encode("utf-8")
    return len(raw), _sha256(raw)


def _process_subdomain(src: Path, out_root: Path) -> dict[str, Any] | None:
    """Parse one SubDomain ``D-XX.Y.md`` → write ``subdomains/D-XX.Y.json``.

    Returns the manifest entry, or None if the file is not a SubDomain.
    """
    if not src.stem.startswith("D-") or "." not in src.stem:
        return None
    parsed = parse_subdomain(src)
    shard_path = out_root / "subdomains" / f"{src.stem}.json"
    bytes_written, sha = _write_json(shard_path, parsed)
    return {
        "path": str(shard_path.relative_to(out_root)),
        "source_path": str(src),
        "sha256": sha,
        "bytes": bytes_written,
        "kind": "subdomain",
        "warnings": parsed.get("warnings", []),
    }


def _process_article(src: Path, out_root: Path, regulation: str) -> dict[str, Any] | None:
    """Parse one ``Art_NN.md`` → write ``regulation/{REG}/articles/Art_NN.json``.

    Also handles the per-regulation ``README.md`` (treated as a global
    shard, not as an article).
    """
    if src.stem == "README":
        # Per-articles-dir README → treat as a global shard under regulation
        parsed = parse_global(src)
        shard_path = out_root / "regulation" / regulation / "articles_README.json"
        bytes_written, sha = _write_json(shard_path, parsed)
        return {
            "path": str(shard_path.relative_to(out_root)),
            "source_path": str(src),
            "sha256": sha,
            "bytes": bytes_written,
            "kind": "regulation_root",
            "warnings": parsed.get("warnings", []),
        }
    if not src.stem.startswith("Art_"):
        return None
    parsed = parse_article(src)
    shard_path = out_root / "regulation" / regulation / "articles" / f"{src.stem}.json"
    bytes_written, sha = _write_json(shard_path, parsed)
    return {
        "path": str(shard_path.relative_to(out_root)),
        "source_path": str(src),
        "sha256": sha,
        "bytes": bytes_written,
        "kind": "article",
        "warnings": parsed.get("warnings", []),
    }


def _process_crossreg(src: Path, out_root: Path, root_dir: Path) -> dict[str, Any] | None:
    """Parse one CrossRegulation file → write ``crossregulation/.../<stem>.json``."""
    parsed = parse_crossreg(src, root_dir)
    rel = src.relative_to(root_dir)
    shard_path = out_root / "crossregulation" / rel.with_suffix(".json")
    bytes_written, sha = _write_json(shard_path, parsed)
    return {
        "path": str(shard_path.relative_to(out_root)),
        "source_path": str(src),
        "sha256": sha,
        "bytes": bytes_written,
        "kind": "crossreg",
        "warnings": parsed.get("warnings", []),
    }


def _process_global(src: Path, out_root: Path) -> dict[str, Any] | None:
    """Parse one top-level ``*.md`` → write ``global/<stem>.json``."""
    parsed = parse_global(src)
    shard_path = out_root / "global" / f"{src.stem}.json"
    bytes_written, sha = _write_json(shard_path, parsed)
    return {
        "path": str(shard_path.relative_to(out_root)),
        "source_path": str(src),
        "sha256": sha,
        "bytes": bytes_written,
        "kind": "global",
        "warnings": parsed.get("warnings", []),
    }


def _process_regulation_root(src: Path, out_root: Path, regulation: str) -> dict[str, Any] | None:
    """Parse one Regulation root file (``00_README``, ``01_SecurityObjectives``, etc.)."""
    if src.parent.name != regulation:  # not a direct child of Regulation/{REG}/
        return None
    parsed = parse_global(src)
    shard_path = out_root / "regulation" / regulation / f"{src.stem}.json"
    bytes_written, sha = _write_json(shard_path, parsed)
    return {
        "path": str(shard_path.relative_to(out_root)),
        "source_path": str(src),
        "sha256": sha,
        "bytes": bytes_written,
        "kind": "regulation_root",
        "warnings": parsed.get("warnings", []),
    }


def _process_ambiguity_clause(src: Path, out_root: Path, regulation: str) -> dict[str, Any] | None:
    """Parse one Regulation/Ambiguity/*.md clause file."""
    # Filenames look like "00_GDPR_Index", "01_AI_Act_Art9_RiskMgmt" — they
    # contain the regulation label somewhere in the stem (not necessarily
    # at the start, since they may be prefixed with a numeric index like
    # "00_" or "01_").
    reg_norm = regulation.replace("_", "")
    stem_norm = src.stem.replace("_", "")
    if reg_norm not in stem_norm:
        return None
    parsed = parse_global(src)
    shard_path = out_root / "regulation" / regulation / "ambiguity_clauses" / f"{src.stem}.json"
    bytes_written, sha = _write_json(shard_path, parsed)
    return {
        "path": str(shard_path.relative_to(out_root)),
        "source_path": str(src),
        "sha256": sha,
        "bytes": bytes_written,
        "kind": "ambiguity_clause",
        "warnings": parsed.get("warnings", []),
    }


def _process_ambiguity_analysis(src: Path, out_root: Path) -> dict[str, Any] | None:
    """Parse one top-level ``AMBIGUITY_ANALYSIS/*.md`` file."""
    parsed = parse_global(src)
    shard_path = out_root / "ambiguity_analysis" / f"{src.stem}.json"
    bytes_written, sha = _write_json(shard_path, parsed)
    return {
        "path": str(shard_path.relative_to(out_root)),
        "source_path": str(src),
        "sha256": sha,
        "bytes": bytes_written,
        "kind": "ambiguity_analysis",
        "warnings": parsed.get("warnings", []),
    }


def build(source_root: Path, output_root: Path) -> dict[str, Any]:
    """Run the full build. Returns the manifest dict.

    Strict mode (default): any per-shard warning is escalated to a
    build failure. The function returns the manifest; callers must
    check ``manifest["errors"]``.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "subdomains").mkdir(parents=True, exist_ok=True)

    manifest_shards: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    sd_dir = source_root / "SubDomains"
    if not sd_dir.is_dir():
        errors.append({"file": str(sd_dir), "error": "SubDomains directory not found"})
    else:
        # Top-level files inside SubDomains/ (Volere_shell.md, index.md)
        for src in sorted(sd_dir.glob("*.md")):
            try:
                parsed = parse_global(src)
                shard_path = output_root / "subdomains" / f"_meta_{src.stem}.json"
                bytes_written, sha = _write_json(shard_path, parsed)
                manifest_shards.append({
                    "path": str(shard_path.relative_to(output_root)),
                    "source_path": str(src),
                    "sha256": sha,
                    "bytes": bytes_written,
                    "kind": "subdomain_meta",
                    "warnings": parsed.get("warnings", []),
                })
                logger.info("wrote %s (%d bytes)", shard_path.relative_to(output_root), bytes_written)
            except Exception as exc:
                errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})

        for domain_dir in sorted(sd_dir.iterdir()):
            if not domain_dir.is_dir():
                continue
            for src in sorted(domain_dir.glob("*.md")):
                if not src.stem.startswith("D-"):
                    continue
                try:
                    entry = _process_subdomain(src, output_root)
                except Exception as exc:  # pragma: no cover — defensive
                    errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                    continue
                if entry is None:
                    continue
                # Strict: warnings are errors
                if entry["warnings"]:
                    for w in entry["warnings"]:
                        errors.append(
                            {"file": entry["source_path"], "error": f"warning: {w}"}
                        )
                manifest_shards.append(entry)
                logger.info("wrote %s (%d bytes)", entry["path"], entry["bytes"])

    # Regulation articles (per-article split files)
    reg_dir = source_root / "Regulation"
    if reg_dir.is_dir():
        for reg_dir_entry in sorted(reg_dir.iterdir()):
            if not reg_dir_entry.is_dir():
                continue
            regulation = reg_dir_entry.name
            articles_dir = reg_dir_entry / "Articles"
            if not articles_dir.is_dir():
                continue
            for src in sorted(articles_dir.glob("*.md")):
                try:
                    entry = _process_article(src, output_root, regulation)
                except Exception as exc:  # pragma: no cover — defensive
                    errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                    continue
                if entry is None:
                    continue
                if entry["warnings"]:
                    for w in entry["warnings"]:
                        errors.append(
                            {"file": entry["source_path"], "error": f"warning: {w}"}
                        )
                manifest_shards.append(entry)
                logger.info("wrote %s (%d bytes)", entry["path"], entry["bytes"])

            # Regulation root files (00_README, 01_SecurityObjectives, ...)
            for src in sorted(reg_dir_entry.glob("*.md")):
                try:
                    entry = _process_regulation_root(src, output_root, regulation)
                except Exception as exc:  # pragma: no cover — defensive
                    errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                    continue
                if entry is None:
                    continue
                if entry["warnings"]:
                    for w in entry["warnings"]:
                        errors.append(
                            {"file": entry["source_path"], "error": f"warning: {w}"}
                        )
                manifest_shards.append(entry)
                logger.info("wrote %s (%d bytes)", entry["path"], entry["bytes"])

            # Regulation/Ambiguity/ clause files
            ambig_dir = reg_dir_entry / "Ambiguity"
            if ambig_dir.is_dir():
                for src in sorted(ambig_dir.glob("*.md")):
                    try:
                        entry = _process_ambiguity_clause(src, output_root, regulation)
                    except Exception as exc:  # pragma: no cover — defensive
                        errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                        continue
                    if entry is None:
                        continue
                    if entry["warnings"]:
                        for w in entry["warnings"]:
                            errors.append(
                                {"file": entry["source_path"], "error": f"warning: {w}"}
                            )
                    manifest_shards.append(entry)
                    logger.info("wrote %s (%d bytes)", entry["path"], entry["bytes"])

    # CrossRegulation (DeepAnalysis + DomainAnalysis + index)
    cr_dir = source_root / "CrossRegulation"
    if cr_dir.is_dir():
        for src in sorted(cr_dir.rglob("*.md")):
            # Skip the _archive dir
            if "_archive" in src.parts:
                continue
            try:
                entry = _process_crossreg(src, output_root, cr_dir)
            except Exception as exc:  # pragma: no cover — defensive
                errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                continue
            if entry is None:
                continue
            if entry["warnings"]:
                for w in entry["warnings"]:
                    errors.append({"file": entry["source_path"], "error": f"warning: {w}"})
            manifest_shards.append(entry)
            logger.info("wrote %s (%d bytes)", entry["path"], entry["bytes"])

    # Top-level global files (NIST_CSF_2.0, Hierarchical_SecurityObjectives, etc.)
    for src in sorted(source_root.glob("*.md")):
        try:
            entry = _process_global(src, output_root)
        except Exception as exc:  # pragma: no cover — defensive
            errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
            continue
        if entry is None:
            continue
        if entry["warnings"]:
            for w in entry["warnings"]:
                errors.append({"file": entry["source_path"], "error": f"warning: {w}"})
        manifest_shards.append(entry)
        logger.info("wrote %s (%d bytes)", entry["path"], entry["bytes"])

    # AMBIGUITY_ANALYSIS/ (top-level, cross-regulation)
    ambig_dir = source_root / "AMBIGUITY_ANALYSIS"
    if ambig_dir.is_dir():
        for src in sorted(ambig_dir.glob("*.md")):
            try:
                entry = _process_ambiguity_analysis(src, output_root)
            except Exception as exc:  # pragma: no cover — defensive
                errors.append({"file": str(src), "error": f"unhandled: {exc!r}"})
                continue
            if entry is None:
                continue
            if entry["warnings"]:
                for w in entry["warnings"]:
                    errors.append({"file": entry["source_path"], "error": f"warning: {w}"})
            manifest_shards.append(entry)
            logger.info("wrote %s (%d bytes)", entry["path"], entry["bytes"])

    # Deterministic built_at: use max source mtime as the build epoch
    # so that re-builds from the same source tree are byte-identical (C3).
    src_mtime = max(
        (p.stat().st_mtime for p in source_root.rglob("*")),
        default=0.0,
    )
    built_at = datetime.fromtimestamp(src_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "built_at": built_at,
        "source_root": str(source_root),
        "method_version": "1.0",
        "shard_count": len(manifest_shards),
        "shards": manifest_shards,
        "errors": errors,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    build_info = {
        "schema_version": SCHEMA_VERSION,
        "built_at": built_at,
        "source_root": str(source_root),
        "method_version": "1.0",
        "shard_count": len(manifest_shards),
        "error_count": len(errors),
    }
    (output_root / "build_info.json").write_text(
        json.dumps(build_info, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest
