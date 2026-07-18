"""Load clause-level ambiguity analyses for applicable regulations.

The ambiguity corpus (``Regulation/<REG>/Ambiguity/*.md``) carries
Berry-linguistic ambiguity cards for every clause in the regulation.
Each card is a multi-paragraph block containing verbatim OJ text plus
variant readings. The total corpus is large (~280 cards across GDPR +
CRA); feeding all of them to a per-domain prompt produces a §6
section > 160 KB. We therefore expose an optional ``domain_id``
filter that retains only cards relevant to the requested AEGIS
sub-domain set.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_CLAUSE_ID = r"(?:[A-Za-z][A-Za-z0-9_]*-C[LP]\d+[A-Za-z0-9_-]*|[A-Za-z][A-Za-z0-9_]*-CL\d+[A-Za-z0-9_-]*|C\d+[A-Za-z0-9_-]*)"
_MARKER_PATTERNS = (
    re.compile(rf"(?im)^\s*\*\*Clause:\s*(?P<id>{_CLAUSE_ID})\*\*.*$"),
    re.compile(rf"(?im)^\s*#{{2,6}}\s+Clause\s+(?P<id>{_CLAUSE_ID})\b.*$"),
    re.compile(
        r"(?im)^\s*#{2,6}\s+(?:\d+(?:\.\d+)?\s+)?(?P<id>[A-Za-z][A-Za-z0-9_]*-CL\d+[A-Za-z0-9_-]*)\b.*$"
    ),
    re.compile(rf"(?im)^\s*[-*]\s+\*\*(?P<id>{_CLAUSE_ID})\*\*\s*:.*$"),
)
_RESOLUTION_HEADING_RE = re.compile(
    r"(?ims)^\s*#{1,6}\s+resolution[^\n]*\n(?P<body>.*?)(?=^\s*#{1,6}\s|\Z)"
)
_RESOLUTION_LINE_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?resolution(?:\*\*)?\s*:\s*(?P<body>.+)$"
)
_READING_LINE_RE = re.compile(
    r"(?im)^\s*(?P<body>(?:R\d+\s+is\s+(?:the\s+)?(?:literal|chosen|adopted)\s+reading|.*reading chosen:).+)$"
)

# Hard-coded map: domain_id → list of ``(regulation, clause_id_prefix,
# article_ref_token, locus_only)`` tuples used to keep only clauses
# relevant to the domain. ``clause_id_prefix`` is matched
# case-insensitively at the start of the clause id (``None`` = any prefix);
# ``article_ref_token`` is matched as a case-insensitive substring of the
# card body. ``locus_only`` marks entries that should be matched purely by
# the article-ref token (used when the clause-id prefix matches many
# clauses but only a few of them cite the relevant article).
#
# Curation strategy (CORR-023): for each domain we list one rule per
# applicable regulation, with ``prefix=None`` and ``article_ref_tokens``
# taken from the corresponding ``DOMAIN_ARTICLES`` entry. The article-token
# match is robust to the corpus's mixed CL/CP/AIA-/heading conventions
# (the ambiguity loader recognises GDPR-CL*, GDPR-CP*, CRA-CL*, NIS2-CL*;
# DORA and AI_Act files have no clause markers in a parseable form and
# therefore contribute 0 ambiguity entries regardless of this filter).
# D-10 and D-04 retain their original clause-ID entries (already validated
# against the corpus); D-01 retains its prefix+token form. D-02/03/05/06/
# 07/08/09 use the article-token form curated in CORR-023.
_DOMAIN_CLAUSE_FILTER: dict[str, list[tuple[str, str | None, list[str], bool]]] = {
    "D-10": [
        # GDPR: Art. 30 records, Art. 5(2) accountability, Art. 31 supervisory
        # cooperation, Art. 32 security of processing, Art. 35 DPIA.
        ("GDPR", "GDPR-CL07", [], False),  # Art. 5(2) — accountability / demonstrability
        ("GDPR", "GDPR-CP12", [], False),  # Art. 30(1)/(2) — records of processing
        ("GDPR", "GDPR-CP13", [], False),  # Art. 30(5) — 250-employee exception
        ("GDPR", "GDPR-CP14", [], False),  # Art. 31 — supervisory cooperation
        ("GDPR", "GDPR-CP15", [], False),  # Art. 32(1) — security of processing
        ("GDPR", "GDPR-CP16", [], False),  # Art. 32(2) — risk assessment
        # CRA: manufacturer documentation + monitoring/testing duties
        ("CRA", "CRA-CL21", [], False),  # Art. 13(4) sentence 1 — risk assessment in tech docs
        ("CRA", "CRA-CL26", [], False),  # Art. 13(7) — systematically document
        ("CRA", "CRA-CL27", [], False),  # Art. 13(8) sentence 1 — vuln handling during support
        ("CRA", "CRA-CL36", [], False),  # Art. 13(12) sentence 1 — tech docs + conformity
        ("CRA", "CRA-CL38", [], False),  # Art. 13(13) — 10-year retention
        ("CRA", "CRA-CL43", [], False),  # Art. 13(18) — Annex II info accessible 10 years
        ("CRA", "CRA-CL46", [], False),  # Art. 13(21) — corrective measures
        ("CRA", "CRA-CL47", [], False),  # Art. 13(22) — MSA cooperation
        ("CRA", "CRA-CL57", [], False),  # 10-year documentation retention (consolidated)
        # CRA Annex I: monitoring + logging + testing properties
        ("CRA", "CRA-CL133", [], False),  # Annex I Part I (2)(d) — access control / IAM
        ("CRA", "CRA-CL141", [], False),  # Annex I Part I (2)(l) — logging + monitoring
        ("CRA", "CRA-CL143", [], False),  # Annex I Part II (1) — SBOM + identify/document
        ("CRA", "CRA-CL145", [], False),  # Annex I Part II (3) — effective and regular tests
        # CRA Annex VII: technical documentation clauses (all relevant)
        ("CRA", "CRA-CL160", [], False),
        ("CRA", "CRA-CL161", [], False),
        ("CRA", "CRA-CL162", [], False),
        ("CRA", "CRA-CL163", [], False),
        ("CRA", "CRA-CL164", [], False),
        ("CRA", "CRA-CL165", [], False),
        ("CRA", "CRA-CL166", [], False),
        ("CRA", "CRA-CL167", [], False),
    ],
    "D-04": [
        # GDPR: breach notification
        ("GDPR", "GDPR-CP17", [], False),
        ("GDPR", "GDPR-CP18", [], False),
        ("GDPR", "GDPR-CP19", [], False),
        ("GDPR", "GDPR-CP20", [], False),
        # CRA: incident reporting Art. 14
        ("CRA", "CRA-CL", ["Art. 14"], False),
    ],
    "D-01": [
        ("GDPR", "GDPR-CP", ["Art. 32", "Art. 5"], False),
        ("CRA", "CRA-CL", ["Annex I Part I", "Art. 13(1)", "Art. 13(5)"], False),
    ],
    # ─── CORR-023 (article-token form, applicable regs only) ───────────
    "D-02": [
        # GDPR: testing (Art. 32(1)(d)) + DPIA review (Art. 35(11))
        ("GDPR", None, ["Art. 32", "Art. 35"], True),
        # CRA: vuln handling, patching, testing, disclosure
        (
            "CRA",
            None,
            [
                "Annex I Part I (2)(a)",
                "Annex I Part I (2)(c)",
                "Annex I Part II (1)",
                "Annex I Part II (2)",
                "Annex I Part II (3)",
                "Annex I Part II (4)",
                "Annex I Part II (5)",
                "Annex I Part II (6)",
                "Annex I Part II (7)",
                "Annex I Part II (8)",
                "Annex VII §3",
                "Annex VII §6",
                "Art. 13(3)",
                "Art. 13(7)",
                "Art. 13(8)",
                "Art. 13(9)",
                "Art. 13(17)",
                "Art. 13(18)",
            ],
            True,
        ),
        ("NIS2", None, ["Art. 21(2)(e)"], True),
    ],
    "D-03": [
        # GDPR: Art. 11/12 identity + Art. 28 processor + Art. 29 + Art. 32(4) + Art. 25
        (
            "GDPR",
            None,
            [
                "Art. 11",
                "Art. 12",
                "Art. 25",
                "Art. 28",
                "Art. 29",
                "Art. 32",
            ],
            True,
        ),
        (
            "CRA",
            None,
            [
                "Annex I Part I (2)(b)",
                "Annex I Part I (2)(d)",
                "Annex I Part I (2)(j)",
                "Annex II §3",
                "Art. 13(15)",
                "Art. 13(17)",
            ],
            True,
        ),
        ("NIS2", None, ["Art. 21(2)(i)", "Art. 21(2)(j)"], True),
    ],
    "D-05": [
        (
            "GDPR",
            None,
            [
                "Art. 5(1)(c)",
                "Art. 5(1)(e)",
                "Art. 6(1)",
                "Art. 6(4)",
                "Art. 8",
                "Art. 9",
                "Art. 12(3)",
                "Art. 12(5)",
                "Art. 15(3)",
                "Art. 17",
                "Art. 19",
                "Art. 20",
                "Art. 25",
                "Art. 28(3)",
                "Art. 30(1)(f)",
                "Art. 35",
                "Art. 89(1)",
            ],
            True,
        ),
        (
            "CRA",
            None,
            [
                "Annex I Part I (2)(g)",
                "Annex I Part I (2)(m)",
                "Annex I Part II (7)",
                "Annex I Part II (8)",
                "Annex II §7",
                "Annex II §8",
                "Art. 3(23)",
                "Art. 13(2)",
                "Art. 13(3)",
                "Art. 13(8)",
                "Art. 13(9)",
                "Art. 13(18)",
                "Art. 13(19)",
            ],
            True,
        ),
    ],
    "D-06": [
        (
            "GDPR",
            None,
            [
                "Art. 3(2)",
                "Art. 27",
                "Art. 28",
                "Art. 46",
                "Art. 48",
            ],
            True,
        ),
        (
            "CRA",
            None,
            [
                "Annex I Part II (1)",
                "Annex II §9",
                "Annex VII §2",
                "Annex VII §8",
                "Art. 3(23)",
                "Art. 3(39)",
                "Art. 3(48)",
                "Art. 13(5)",
                "Art. 13(6)",
                "Art. 22",
                "Art. 23",
            ],
            True,
        ),
        (
            "NIS2",
            None,
            ["Art. 21(2)(d)", "Art. 21(3)", "Art. 22"],
            True,
        ),
    ],
    "D-07": [
        ("GDPR", None, ["Art. 25"], True),
        (
            "CRA",
            None,
            [
                "Annex I Part I (2)(b)",
                "Annex I Part I (2)(c)",
                "Annex I Part I (2)(j)",
                "Annex I Part I (2)(k)",
                "Annex I Part II (7)",
                "Annex I Part II (8)",
                "Annex VII §2",
                "Annex VII §3",
                "Art. 13(1)",
                "Art. 13(2)",
                "Art. 13(3)",
                "Art. 13(7)",
                "Art. 13(8)",
                "Art. 13(10)",
                "Art. 13(14)",
                "Art. 13(21)",
            ],
            True,
        ),
        ("NIS2", None, ["Art. 21(2)(e)"], True),
    ],
    "D-08": [
        ("GDPR", None, ["Art. 5(2)", "Art. 39"], True),
        (
            "CRA",
            None,
            ["Annex II §8", "Annex VII", "Art. 13(18)"],
            True,
        ),
        ("NIS2", None, ["Art. 20(2)", "Art. 21(2)(g)"], True),
    ],
    "D-09": [
        (
            "GDPR",
            None,
            [
                "Art. 5(2)",
                "Art. 24",
                "Art. 30",
                "Art. 35",
                "Art. 36",
                "Art. 37",
                "Art. 38",
                "Art. 39",
            ],
            True,
        ),
        (
            "CRA",
            None,
            [
                "Annex I Part I (2)",
                "Annex VII §1",
                "Annex VII §2",
                "Annex VII §3",
                "Annex VII §8",
                "Art. 13(2)",
                "Art. 13(3)",
                "Art. 13(4)",
                "Art. 13(8)",
                "Art. 13(12)",
                "Art. 13(13)",
                "Art. 13(19)",
                "Art. 24(1)",
                "Art. 28",
                "Art. 30",
                "Art. 31",
                "Art. 32",
            ],
            True,
        ),
        (
            "NIS2",
            None,
            [
                "Art. 20(1)",
                "Art. 21(2)(a)",
                "Art. 21(2)(f)",
                "Art. 21(2)(i)",
                "Art. 21(3)",
                "Art. 22(1)",
                "Art. 24",
            ],
            True,
        ),
    ],
}


def load_ambiguities_for_regs(
    regs: list[str],
    base_path: Path,
    domain_id: str | None = None,
) -> list[dict[str, str]]:
    """Load clause-level ambiguity entries from applicable regulation files.

    Args:
        regs: Applicable regulation short names.
        base_path: Root preprocessing directory containing ``Regulation`` data.
        domain_id: Optional AEGIS domain identifier (e.g. ``"D-10"``).
            When provided, entries are filtered to those whose clause
            id or article reference maps to a clause relevant to the
            domain (per :data:`_DOMAIN_CLAUSE_FILTER`). ``None`` returns
            the unfiltered set (legacy behaviour).

    Returns:
        Entries with ``id``, ``regulation``, ``description``, ``resolution``,
        and ``source_file``. Missing directories produce an empty list.
    """
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for raw_reg in regs:
        regulation = _normalise_regulation(raw_reg)
        regulation_path = _find_regulation_path(base_path, regulation)
        if regulation_path is None:
            continue
        ambiguity_path = regulation_path / "Ambiguity"
        for source_file in sorted(ambiguity_path.glob("*.md")):
            for entry in _parse_file(source_file, regulation):
                if domain_id and not _entry_matches_domain(entry, regulation, domain_id):
                    continue
                key = (entry["regulation"], entry["id"], entry["source_file"])
                if key in seen:
                    continue
                seen.add(key)
                entries.append(entry)

    entries.sort(key=lambda entry: (entry["regulation"], entry["id"], entry["source_file"]))
    logger.debug(
        "load_ambiguities_for_regs(domain=%s): %d entries", domain_id, len(entries)
    )
    return entries


def _parse_file(source_file: Path, regulation: str) -> list[dict[str, str]]:
    """Parse all clause markers in one Markdown file."""
    try:
        text = source_file.read_text(encoding="utf-8")
    except OSError:
        logger.debug("Could not read ambiguity file: %s", source_file, exc_info=True)
        return []

    markers = sorted(
        (match.start(), match.end(), match)
        for pattern in _MARKER_PATTERNS
        for match in pattern.finditer(text)
    )
    if not markers:
        return []

    entries: list[dict[str, str]] = []
    for index, (start, end, match) in enumerate(markers):
        next_start = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        marker_line = text[start:end].strip()
        body = text[end:next_start].strip()
        clause_id = match.group("id").strip()
        inline_description = _inline_description(marker_line, clause_id)
        description_parts = [part for part in (inline_description, body) if part]
        description = "\n\n".join(description_parts)
        entries.append(
            {
                "id": clause_id,
                "regulation": regulation,
                "description": description,
                "resolution": _extract_resolution(body),
                "source_file": str(source_file),
            }
        )
    return entries


def _inline_description(marker_line: str, clause_id: str) -> str:
    """Extract text following a clause marker when it is on the same line."""
    line = re.sub(r"^\s*#{2,6}\s*", "", marker_line)
    line = re.sub(r"^\s*[-*]\s+", "", line)
    line = re.sub(rf"^\*\*{re.escape(clause_id)}\*\*\s*:\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(rf"^\*\*Clause:\s*{re.escape(clause_id)}\*\*\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(
        rf"^(?:\d+(?:\.\d+)?\s+)?{re.escape(clause_id)}\s*", "", line, flags=re.IGNORECASE
    )
    line = re.sub(r"[\u2014\u2013]", " ", line).strip(" -:")
    return line.strip()


def _extract_resolution(text: str) -> str:
    """Extract an explicit resolution or selected reading from a clause block."""
    heading_match = _RESOLUTION_HEADING_RE.search(text)
    if heading_match:
        return heading_match.group("body").strip()
    line_match = _RESOLUTION_LINE_RE.search(text)
    if line_match:
        return line_match.group("body").strip()
    reading_matches = _READING_LINE_RE.findall(text)
    return "\n".join(match.strip() for match in reading_matches)


def _entry_matches_domain(
    entry: dict[str, str], regulation: str, domain_id: str
) -> bool:
    """Return ``True`` if ``entry`` is relevant to ``domain_id``.

    The check uses :data:`_DOMAIN_CLAUSE_FILTER`: a clause is kept
    when its regulation matches, its clause id starts with the
    configured prefix (or any prefix when ``None``), AND the article
    reference token (when configured) appears as a case-insensitive
    substring of the card body. When no filter is registered for the
    domain, the entry is kept (defensive fallback).
    """
    rules = _DOMAIN_CLAUSE_FILTER.get(domain_id)
    if not rules:
        return True

    clause_id = entry.get("id", "")
    body = entry.get("description", "") + "\n" + entry.get("resolution", "")
    body_lower = body.lower()

    for rule_reg, prefix, tokens, locus_only in rules:
        if rule_reg != regulation:
            continue
        if not locus_only and prefix and not clause_id.upper().startswith(prefix.upper()):
            continue
        if tokens and not any(token.lower() in body_lower for token in tokens):
            continue
        return True
    return False


def _normalise_regulation(reg: str) -> str:
    """Return the canonical regulation directory name."""
    value = str(reg or "").strip()
    if value.upper().startswith("REG-"):
        value = value[4:]
    compact = re.sub(r"[\s_-]+", "", value).lower()
    aliases = {
        "aiact": "AI_Act",
        "ai": "AI_Act",
        "nis2": "NIS2",
        "gdpr": "GDPR",
        "cra": "CRA",
        "dora": "DORA",
    }
    if compact in aliases:
        return aliases[compact]
    return re.sub(r"[\s-]+", "_", value).strip("_")


def _find_regulation_path(base_path: Path, regulation: str) -> Path | None:
    """Find a regulation directory while tolerating case-only differences."""
    direct_candidates = (base_path / regulation, base_path / "Regulation" / regulation)
    for direct in direct_candidates:
        if direct.is_dir():
            return direct
    try:
        for parent in (base_path, base_path / "Regulation"):
            for candidate in parent.iterdir():
                if candidate.is_dir() and candidate.name.casefold() == regulation.casefold():
                    return candidate
    except OSError:
        return None
    return None


__all__ = ["load_ambiguities_for_regs"]
