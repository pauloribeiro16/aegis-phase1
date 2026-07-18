"""Load regulation article content from the preprocessing source tree.

Per-article split files (e.g. ``Art_13.md``) carry a NIST-derived
security-objective + security-rule table grouped by article. Each row
in the SO table and each YAML security-rule record carries a
``sub_domain:`` field; this loader can optionally filter those rows to
a specific sub-domain set (e.g. ``["D-10.1", "D-10.2", "D-10.3"]``)
to keep the per-domain prompt section small. When no sub-domain filter
is provided the file content is returned as-is.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from aegis_phase1.v2.loader import _parse_yaml_frontmatter, _strip_frontmatter

logger = logging.getLogger(__name__)

DOMAIN_ARTICLES: dict[str, dict[str, list[str]]] = {
    "D-01": {
        "GDPR": ["Art. 32"],
        "CRA": ["Annex I Part I (2)(e)"],
        "NIS2": [],
        "DORA": [],
        "AI_Act": [],
    },
    "D-02": {
        "GDPR": ["Art. 32(1)(d)", "Art. 35(11)"],
        "CRA": [
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
            "Annex II §2",
            "Annex VII §3",
            "Annex VII §6",
            "Annex VIII Part II (8)",
            "Art. 13(3)",
            "Art. 13(7)",
            "Art. 13(8)",
            "Art. 13(9)",
            "Art. 13(17)",
            "Art. 13(18)",
        ],
        "NIS2": ["Art. 21(2)(e)"],
        "DORA": [
            "Art. 7(2)",
            "Art. 8(2)",
            "Art. 9(4)(b)",
            "Art. 9(4)(f)",
            "Art. 24(1)",
            "Art. 25(1)",
            "Art. 26(1)",
        ],
        "AI_Act": [
            "Art. 9(2)",
            "Art. 9(6)",
            "Art. 9(7)",
            "Art. 15(1)",
            "Art. 15(4)",
            "Art. 15(5)",
            "Art. 60",
        ],
    },
    "D-03": {
        "GDPR": [
            "Art. 5(1)(c)",
            "Art. 11(2)",
            "Art. 12(6)",
            "Art. 25(1)",
            "Art. 25(2)",
            "Art. 28(3)(a)",
            "Art. 28(3)(b)",
            "Art. 28(3)(g)",
            "Art. 29",
            "Art. 32(4)",
        ],
        "CRA": [
            "Annex I Part I (2)(b)",
            "Annex I Part I (2)(d)",
            "Annex I Part I (2)(j)",
            "Annex II §3",
            "Art. 13(15)",
            "Art. 13(17)",
        ],
        "NIS2": ["Art. 21(2)(i)", "Art. 21(2)(j)"],
        "DORA": ["Art. 9(4)(c)", "Art. 9(4)(d)"],
        "AI_Act": [],
    },
    "D-04": {
        "GDPR": ["Art. 33", "Art. 34"],
        "CRA": ["Art. 14"],
        "NIS2": [],
        "DORA": [],
        "AI_Act": [],
    },
    "D-05": {
        "GDPR": [
            "Art. 5(1)(c)",
            "Art. 5(1)(e)",
            "Art. 6(1)(a)",
            "Art. 6(1)(b)",
            "Art. 6(4)",
            "Art. 8(1)",
            "Art. 9(1)",
            "Art. 9(2)",
            "Art. 12(3)",
            "Art. 12(5)",
            "Art. 15(3)",
            "Art. 17(1)",
            "Art. 17(3)",
            "Art. 19",
            "Art. 20(1)",
            "Art. 20(2)",
            "Art. 20(3)",
            "Art. 20(4)",
            "Art. 25(1)",
            "Art. 25(2)",
            "Art. 28(3)(g)",
            "Art. 30(1)(f)",
            "Art. 35",
            "Art. 35(7)",
            "Art. 89(1)",
        ],
        "CRA": [
            "Annex I Part I (2)(g)",
            "Annex I Part I (2)(m)",
            "Annex I Part II (7)",
            "Annex I Part II (8)",
            "Annex II §7",
            "Annex II §8(d)",
            "Art. 3(23)",
            "Art. 13(2)",
            "Art. 13(3)",
            "Art. 13(8)",
            "Art. 13(9)",
            "Art. 13(18)",
            "Art. 13(19)",
        ],
        "NIS2": [],
        "DORA": [],
        "AI_Act": [
            "Art. 10(1)",
            "Art. 10(2)",
            "Art. 10(3)",
            "Art. 10(5)",
            "Art. 12(1)",
            "Art. 19(1)",
        ],
    },
    "D-06": {
        "GDPR": [
            "Art. 3(2)",
            "Art. 27(2)",
            "Art. 28(1)",
            "Art. 28(2)",
            "Art. 28(3)(a)",
            "Art. 28(3)(b)",
            "Art. 28(3)(e)",
            "Art. 28(3)(f)",
            "Art. 28(3)(g)",
            "Art. 28(3)(h)",
            "Art. 46",
            "Art. 48",
        ],
        "CRA": [
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
        "NIS2": ["Art. 21(2)(d)", "Art. 21(3)", "Art. 22"],
        "DORA": [
            "Art. 28(1)",
            "Art. 28(5)",
            "Art. 28(13)",
            "Art. 30(2)",
            "Art. 30(3)",
        ],
        "AI_Act": [],
    },
    "D-07": {
        "GDPR": ["Art. 25(1)", "Art. 25(2)"],
        "CRA": [
            "Annex I Part I",
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
        "NIS2": ["Art. 21(2)(e)"],
        "DORA": ["Art. 9(4)(b)", "Art. 9(4)(e)", "Art. 9(4)(f)"],
        "AI_Act": ["Art. 15(1)", "Art. 15(4)", "Art. 15(5)"],
    },
    "D-08": {
        "GDPR": ["Art. 5(2)", "Art. 39(1)(a)", "Art. 39(1)(b)"],
        "CRA": [
            "Annex I Part I",
            "Annex II §8",
            "Annex II §8(f)",
            "Annex VII",
            "Art. 13(18)",
        ],
        "NIS2": ["Art. 20(2)", "Art. 21(2)(g)"],
        "DORA": ["Art. 5(4)", "Art. 13(6)"],
        "AI_Act": ["Art. 14(1)", "Art. 14(4)", "Art. 26(2)"],
    },
    "D-09": {
        "GDPR": [
            "Art. 5(2)",
            "Art. 24(1)",
            "Art. 30(1)",
            "Art. 30(2)",
            "Art. 30(3)",
            "Art. 30(4)",
            "Art. 30(5)",
            "Art. 35(1)",
            "Art. 35(7)",
            "Art. 35(11)",
            "Art. 36(1)",
            "Art. 37",
            "Art. 38",
            "Art. 39",
        ],
        "CRA": [
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
        "NIS2": [
            "Art. 20(1)",
            "Art. 21(2)(a)",
            "Art. 21(2)(f)",
            "Art. 21(2)(i)",
            "Art. 21(3)",
            "Art. 22(1)",
            "Art. 24(1)",
            "Art. 24(2)",
            "Art. 24(3)",
        ],
        "DORA": [
            "Art. 5(2)",
            "Art. 6(1)",
            "Art. 6(4)",
            "Art. 7(1)",
            "Art. 7(2)",
            "Art. 9(4)(a)",
        ],
        "AI_Act": [
            "Art. 9(1)",
            "Art. 9(2)",
            "Art. 11(1)",
            "Art. 12(2)",
            "Art. 13(1)",
            "Art. 13(3)",
            "Art. 17(1)",
            "Art. 19(1)",
        ],
    },
    "D-10": {
        "GDPR": ["Art. 30(3)", "Art. 5(2)", "Art. 31"],
        "CRA": [
            "Annex VII §5-§8",
            "Annex VII §3",
            "Art. 13(4)",
            "Art. 13(22)",
            "Annex VII §6",
            "Annex I Part II (3)",
        ],
        "NIS2": [],
        "DORA": ["Art. 9(4)(a)"],
        "AI_Act": ["Art. 12(1)", "Art. 12(2)", "Art. 19(1)"],
    },
}

_ARTICLE_RE = re.compile(
    r"^\s*(?:art(?:icle)?)[\s._-]*(?P<number>\d+)" r"(?:\s*(?P<paragraph>(?:\([^)]*\))+))?",
    re.IGNORECASE,
)
_ANNEX_RE = re.compile(r"^\s*annex\s+(?P<annex>[A-Za-z0-9]+)(?P<rest>.*)$", re.IGNORECASE)

# Hard cap on per-article text after sub-domain filtering. The
# per-article split files can run to ~230 KB; even after filtering the
# surviving D-10 rows are projected to stay under this ceiling. The cap
# protects the §3 APPLICABLE ARTICLES section from re-bloating if the
# upstream corpus grows or a domain with many sub-domains is loaded.
_MAX_ARTICLE_TEXT_CHARS = 6000

# Regex matching the SO table row separator / header line; we use these
# to detect the table region in the per-article split.
_TABLE_HEADER_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")

# YAML record starts: each record begins with ``- sr_id:`` and ends at
# the next ``- sr_id:`` or the closing ``\`\`\``` fence.
_SR_ID_LINE_RE = re.compile(r"^\s*-\s+sr_id:\s*(\S+)\s*$")


def load_article(
    reg: str,
    article_ref: str,
    base_path: Path,
    applicable_subdomains: list[str] | None = None,
) -> dict[str, str] | None:
    """Load one article file for a regulation reference.

    Args:
        reg: Regulation short name, such as ``GDPR`` or ``AI Act``.
        article_ref: Article or annex reference, such as ``Art. 30(3)``.
        base_path: Root preprocessing directory containing ``Regulation`` data.
        applicable_subdomains: Optional list of sub-domain IDs (e.g.
            ``["D-10.1", "D-10.2", "D-10.3"]``). When provided, the
            per-article split file content is filtered to keep only
            SO/SR rows tagged with one of these sub-domains. ``None``
            returns the unfiltered file body (legacy behaviour).

    Returns:
        Article metadata and the filtered Markdown body, or ``None``
        when the reference has no matching source file.
    """
    regulation = _normalise_regulation(reg)
    reference = _normalise_article_reference(article_ref)
    if not regulation or not reference:
        return None

    regulation_path = _find_regulation_path(base_path, regulation)
    if regulation_path is None:
        logger.debug("Regulation path not found: %s", regulation)
        return None

    articles_path = regulation_path / "Articles"
    if not articles_path.is_dir():
        logger.debug("Article directory not found: %s", articles_path)
        return None

    source_file = _find_article_file(articles_path, reference)
    if source_file is None:
        logger.debug("Article file not found for %s %s", regulation, reference)
        return None

    try:
        raw_text = source_file.read_text(encoding="utf-8")
    except OSError:
        logger.debug("Could not read article file: %s", source_file, exc_info=True)
        return None

    title, body = _extract_title_and_body(raw_text)
    if applicable_subdomains:
        body = _filter_body_by_subdomains(body, applicable_subdomains)
        if not body.strip():
            logger.debug(
                "Sub-domain filter %s removed all content from %s",
                applicable_subdomains,
                source_file,
            )
            return None
    if len(body) > _MAX_ARTICLE_TEXT_CHARS:
        body = _truncate_at_record_boundary(body, _MAX_ARTICLE_TEXT_CHARS)
    return {
        "regulation": regulation,
        "article": reference,
        "title": title or reference,
        "text": body,
        "source_file": str(source_file),
    }


def load_articles_for_domain(
    domain_id: str,
    regs: list[str],
    base_path: Path,
    applicable_subdomains: list[str] | None = None,
) -> list[dict[str, str]]:
    """Load all mapped article references for a domain and applicable regulations.

    The domain catalog is the fallback mapping used when case ontology data is
    absent or incomplete. Missing source files are skipped independently.

    Args:
        domain_id: Domain identifier such as ``"D-10"``.
        regs: Applicable regulation short names.
        base_path: Root preprocessing directory.
        applicable_subdomains: Optional sub-domain filter (passed through
            to :func:`load_article`). When provided, each loaded article
            is filtered to those sub-domains.
    """
    domain_key = domain_id.strip().upper()
    domain_mapping = DOMAIN_ARTICLES.get(domain_key)
    if domain_mapping is None and "." in domain_key:
        domain_mapping = DOMAIN_ARTICLES.get(domain_key.split(".", 1)[0])
    if domain_mapping is None:
        domain_mapping = {}
    articles: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for raw_reg in regs:
        regulation = _normalise_regulation(raw_reg)
        for reference in domain_mapping.get(regulation, []):
            key = (regulation, reference)
            if key in seen:
                continue
            seen.add(key)
            article = load_article(
                regulation,
                reference,
                base_path,
                applicable_subdomains=applicable_subdomains,
            )
            if article is not None:
                articles.append(article)

    articles.sort(key=lambda article: (article["regulation"], article["article"]))
    logger.debug(
        "load_articles_for_domain(%s, subs=%s): %d articles",
        domain_id,
        applicable_subdomains,
        len(articles),
    )
    return articles


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


def _normalise_article_reference(article_ref: str) -> str:
    """Return a stable display form for an article or annex reference."""
    value = str(article_ref or "").strip()
    match = _ARTICLE_RE.match(value)
    if match:
        reference = f"Art. {match.group('number')}"
        paragraph = match.group("paragraph")
        if paragraph:
            reference += re.sub(r"\s+", "", paragraph)
        return reference
    return re.sub(r"\s+", " ", value)


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


def _find_article_file(articles_path: Path, reference: str) -> Path | None:
    """Find the most specific file matching an article or annex reference."""
    files = sorted(articles_path.glob("*.md"))
    by_key: dict[str, Path] = {}
    for filepath in files:
        by_key.setdefault(_filename_key(filepath.stem), filepath)

    if _ARTICLE_RE.match(reference):
        match = _ARTICLE_RE.match(reference)
        assert match is not None
        number = match.group("number")
        paragraph = match.group("paragraph")
        keys = []
        if paragraph:
            keys.append(f"art{number}{_filename_key(paragraph)}")
        keys.append(f"art{number}")
    else:
        keys = _annex_candidate_keys(reference)

    for key in keys:
        if key in by_key:
            return by_key[key]
    return None


def _annex_candidate_keys(reference: str) -> list[str]:
    """Build filename keys from most-specific to base annex names."""
    full_key = _filename_key(reference)
    match = _ANNEX_RE.match(reference)
    if not match:
        return [full_key]

    annex_key = "annex" + _filename_key(match.group("annex"))
    rest_key = _filename_key(match.group("rest"))
    keys = [full_key]
    if rest_key:
        numeric_parts = re.findall(r"\d+", match.group("rest"))
        keys.extend(annex_key + part for part in numeric_parts)
    keys.append(annex_key)
    return list(dict.fromkeys(keys))


def _filename_key(value: str) -> str:
    """Normalise punctuation and separators for filename comparison."""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _extract_title_and_body(raw_text: str) -> tuple[str, str]:
    """Extract the first level-one heading and retain the complete body."""
    frontmatter = _parse_yaml_frontmatter(raw_text)
    body = _strip_frontmatter(raw_text).strip()
    heading = re.search(r"(?m)^#\s+([^\n]+?)\s*$", body)
    title = heading.group(1).strip() if heading else str(frontmatter.get("title") or "").strip()
    if heading:
        body = (body[: heading.start()] + body[heading.end() :]).strip()
    return title, body


def _filter_body_by_subdomains(body: str, subdomains: list[str]) -> str:
    """Filter per-article split content to rows/records tagged with ``subdomains``.

    The corpus uses two row formats inside the same Markdown table —
    ``| SO-id | description | source clauses | sub-domain |`` and a
    compact ``| SO-id | sub-domain | art-ref | summary |`` variant —
    and a third format for the YAML security-rule records (``sub_domain:
    [D-XX.Y, ...]``). The filter keeps any row/record that mentions at
    least one of the target sub-domain IDs (as a literal substring of a
    ``D-XX.Y`` token). Lines outside tables and YAML blocks (the
    section headers, the empty placeholder line that follows the SO
    table, the ``### SO-CRA-NNN`` YAML section markers) are kept
    verbatim so the LLM still sees a coherent document structure.
    """
    if not subdomains:
        return body
    target_patterns = [s.strip() for s in subdomains if s and s.strip()]
    if not target_patterns:
        return body

    lines = body.splitlines()
    out: list[str] = []
    in_yaml = False
    open_fence: str | None = None
    block_kept_record = False
    current_record: list[str] = []
    current_record_has_target = False

    def flush_record() -> None:
        nonlocal current_record, current_record_has_target, block_kept_record
        if current_record and current_record_has_target:
            out.extend(current_record)
            block_kept_record = True
        current_record = []
        current_record_has_target = False

    def flush_block() -> None:
        nonlocal in_yaml, open_fence, block_kept_record
        flush_record()
        if open_fence is not None and block_kept_record:
            out.append(open_fence)
        in_yaml = False
        open_fence = None
        block_kept_record = False

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```") and not in_yaml:
            flush_record()
            in_yaml = True
            open_fence = line
            block_kept_record = False
            current_record = []
            current_record_has_target = False
            i += 1
            continue
        if stripped.startswith("```") and in_yaml:
            current_record.append(line)
            flush_block()
            i += 1
            continue
        if in_yaml:
            if _SR_ID_LINE_RE.match(line):
                flush_record()
                current_record = [line]
                current_record_has_target = _row_mentions_any(line, target_patterns)
            else:
                current_record.append(line)
                if _row_mentions_any(line, target_patterns):
                    current_record_has_target = True
            i += 1
            continue

        if _TABLE_HEADER_RE.match(line) and _looks_like_so_table(lines, i):
            flush_record()
            header_and_sep: list[str] = []
            j = i
            while j < n and _TABLE_HEADER_RE.match(lines[j]):
                if (
                    j == i
                    or _TABLE_SEPARATOR_RE.match(lines[j])
                    or _row_mentions_any(lines[j], target_patterns)
                ):
                    header_and_sep.append(lines[j])
                j += 1
            if len(header_and_sep) > 2:
                out.extend(header_and_sep)
                out.append("")
            i = j
            continue

        if _row_mentions_any(line, target_patterns):
            out.append(line)
        i += 1

    flush_record()
    return "\n".join(out).strip()


def _looks_like_so_table(lines: list[str], start: int) -> bool:
    """Heuristic: detect the SO table region by checking column headers.

    The SO table header is ``| SO ID | Description | Source clauses | Sub-domain |``;
    the compact summary variant omits the description column. Either way, a
    separator line ``|---|---|`` follows immediately. Detect either form.
    """
    if start + 1 >= len(lines):
        return False
    header = lines[start].lower()
    if "so id" not in header:
        return False
    return bool(_TABLE_SEPARATOR_RE.match(lines[start + 1]))


def _row_mentions_any(line: str, target_patterns: list[str]) -> bool:
    """Return ``True`` if the line contains any target ``D-XX.Y`` token.

    Word-boundary-aware to avoid spurious matches like ``D-100`` for
    a target ``D-10``. Uses a substring scan with boundary check on
    either side of the match.
    """
    for target in target_patterns:
        idx = 0
        while True:
            pos = line.find(target, idx)
            if pos < 0:
                break
            left_ok = pos == 0 or not line[pos - 1].isalnum()
            right_end = pos + len(target)
            right_ok = right_end >= len(line) or not line[right_end].isalnum()
            if left_ok and right_ok:
                return True
            idx = pos + 1
    return False


def _truncate_at_record_boundary(body: str, limit: int) -> str:
    r"""Trim ``body`` to ``limit`` chars without splitting inside a YAML record.

    The filter emits whole YAML record blocks for each matched record;
    chopping at an arbitrary character index can leave an open fence
    with no closing fence. We search backwards from the limit for the
    last close fence (a triple-backtick line without a language tag)
    and cut just after it, then append a truncation marker. If no
    close fence is found before the limit we fall back to a hard cut.
    """
    if len(body) <= limit:
        return body

    head = body[:limit]
    close_match = None
    for match in re.finditer(r"^```\s*$", head, flags=re.MULTILINE):
        close_match = match
    if close_match is None:
        return head.rstrip() + "\n_(truncated)_"
    cut = close_match.end()
    return head[:cut].rstrip() + "\n_(truncated)_"


__all__ = ["DOMAIN_ARTICLES", "load_article", "load_articles_for_domain"]
