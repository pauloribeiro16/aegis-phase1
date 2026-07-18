"""Aggregator: parse a regulation's ``02_SecurityRules_NIST.md``.

Format: each rule is a YAML record in a ``\\`\\`\\`yaml\\`\\`\\` block, following
the schema in ``TEMPLATE_subagent_brief.md`` §3. Multiple rules may share
a heading (e.g. ``### SO-GDPR-001 / SO-GDPR-014 (CIA + resilience)``).

We extract:
  - ``sr_id`` (canonical ID, e.g. ``SR-GDPR-029``)
  - ``title``
  - ``source_clauses``: ``[{clause_id, article_ref}]``
  - ``linked_objectives``: ``[SO-...]``
  - ``sub_domain``: ``[D-XX.Y]``
  - ``nist_csf_mapping``: ``[{id, title}]``
  - ``applies_to_role``: ``[CONTROLLER, PROCESSOR, ...]``
  - ``obligation_type``: ``[CONTINUOUS, ON_DEMAND, ...]``
  - ``regulatory_rationale``: full multiline string
  - ``security_rationale``: full multiline string
  - ``ambiguity_notes``: full multiline string
  - ``heading_under`` (the H3 the rule is grouped under, e.g. ``SO-GDPR-001/014``)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..frontmatter import parse_frontmatter
from ..markdown import extract_fenced_blocks, split_by_headings

_HEADING_RE = re.compile(r"^###\s+(?P<heading>.+?)\s*$", re.MULTILINE)


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _coerce_mapping(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            entry: dict[str, str] = {}
            for k, v in item.items():
                entry[str(k)] = "" if v is None else str(v)
            out.append(entry)
        elif isinstance(item, str):
            out.append({"id": item, "title": ""})
    return out


def _parse_source_clauses_in_sr(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            entry = {
                "clause_id": str(item.get("clause_id", "")),
                "article_ref": str(item.get("article_ref", "")),
            }
            if entry["clause_id"]:
                out.append(entry)
        elif isinstance(item, str):
            m = re.search(r"((?:GDPR|NIS2|CRA|DORA|AI_Act|AIACT)-CL\d+)", item)
            if m:
                out.append({"clause_id": m.group(1), "article_ref": item})
    return out


def _parse_sr_yaml_item(item: dict[str, Any], heading: str) -> dict[str, Any] | None:
    sr_id = str(item.get("sr_id", "")).strip()
    if not sr_id:
        return None
    return {
        "id": sr_id,
        "title": str(item.get("title", "")).strip(),
        "heading_under": heading,
        "source_clauses": _parse_source_clauses_in_sr(item.get("source_clauses")),
        "linked_objectives": _coerce_str_list(item.get("linked_objectives")),
        "sub_domain": _coerce_str_list(item.get("sub_domain")),
        "nist_csf_mapping": _coerce_mapping(item.get("nist_csf_mapping")),
        "applies_to_role": _coerce_str_list(item.get("applies_to_role")),
        "obligation_type": _coerce_str_list(item.get("obligation_type")),
        "regulatory_rationale": str(item.get("regulatory_rationale", "") or "").strip(),
        "security_rationale": str(item.get("security_rationale", "") or "").strip(),
        "ambiguity_notes": str(item.get("ambiguity_notes", "") or "").strip(),
    }


def parse_security_rules(path: Path, regulation: str) -> list[dict[str, Any]]:
    """Parse ``02_SecurityRules_NIST.md`` and return a list of SR dicts."""
    text = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    srs: list[dict[str, Any]] = []

    # Find all ### headings and their following yaml blocks
    matches = list(_HEADING_RE.finditer(body))
    for i, m in enumerate(matches):
        heading = m.group("heading").strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[m.end():end]
        for lang, yaml_body in extract_fenced_blocks(block, lang="yaml"):
            try:
                parsed = yaml.safe_load(yaml_body)
            except yaml.YAMLError:
                continue
            items: list[dict[str, Any]]
            if isinstance(parsed, list):
                items = [p for p in parsed if isinstance(p, dict)]
            elif isinstance(parsed, dict):
                items = [parsed]
            else:
                continue
            for item in items:
                sr = _parse_sr_yaml_item(item, heading)
                if sr:
                    sr["regulation"] = regulation
                    srs.append(sr)
    return srs
