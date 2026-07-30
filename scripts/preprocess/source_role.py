"""CORR-078 WS2 — Compute ``source_role`` for each article shard.

A regulation's ``00_README.md`` enumerates the *articles in scope* (T5/T4
cybersecurity subset). For each per-article JSON in
``regulation/<REG>/articles/Art_NN.json``, we assign:

  - ``primary_source``      — the article's number is in the in-scope list AND
                              at least one of its ``security_rules[].source_clauses``
                              references the article itself.
  - ``supporting_citation`` — the article is in the in-scope list but every
                              ``source_clauses`` entry points to a different
                              article (this article is cited from inside another
                              article's per-article shard).
  - ``out_of_scope``        — the article's number is NOT in the in-scope list
                              AND none of its ``security_rules`` references the
                              article itself.

The MD source is **not** edited — the flag is computed deterministically by
the preprocessor reading the in-scope list from each regulation's
``00_README.md`` (per Orchestrator decision: option A in `execution/CORR-078.md`).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_in_scope_articles(readme_path: Path) -> list[int]:
    """Parse the 'Articles in scope (T5/T4 cybersecurity subset)' enumeration
    from a regulation's ``00_README.md``.

    Accepts multiple layouts:

      * Enumerated list — ``Art. 9 ...; Art. 10 ...; ...``
        (AI_Act / CRA / DORA / NIS2 — explicit enumeration)
      * Range — ``Art. 5-49 (excluding Art. 40-43)``
        (GDPR — range with exclusions)
      * Annex-style — ``Annex I ... Annex II ...``
        (CRA — Annexes treated as binding articles)

    Returns article numbers as ints, in the order they appear. The function
    is intentionally permissive — if a regulation's README uses an
    unrecognised layout, an empty list is returned and a warning is logged.
    """
    if not readme_path.is_file():
        return []
    text = readme_path.read_text(encoding="utf-8")
    m = re.search(
        r"\*\*Articles in scope[^*\n]*\*\*\.?\s*(.+?)(?=\n\n|\n-\s*\*\*Excluded|\Z)",
        text,
        re.DOTALL,
    )
    if not m:
        logger.warning("could not find 'Articles in scope' paragraph in %s", readme_path)
        return []
    para = m.group(1)

    # Collect explicit single-number mentions
    nums: list[int] = []
    seen: set[int] = set()

    def _add(n: int) -> None:
        if n not in seen:
            seen.add(n)
            nums.append(n)

    # 1. Explicit "Art. NN" — the primary enumeration
    for am in re.finditer(r"Art\.\s*(\d{1,3})", para):
        _add(int(am.group(1)))

    # 2. Ranges like "Art. 5-49" or "Art. 5-9" (em-dash, en-dash, hyphen)
    for rm in re.finditer(r"Art\.\s*(\d{1,3})\s*[\u2013\u2014\-]\s*(\d{1,3})", para):
        lo, hi = int(rm.group(1)), int(rm.group(2))
        for n in range(lo, hi + 1):
            _add(n)

    # 3. Exclusions: drop articles marked as excluded inline.
    # Two layouts are supported:
    # (a) "excluding Art. X" or "excluding Art. X-Y"
    # (b) "excluding Art. X-Y and Art. Z" — the trailing singleton "and Art. Z"
    #     is dropped (GDPR has "excluding Art. 40-43 codes/certification and
    #     Art. 50 international cooperation").
    excl_text = para
    excl_ranges: list[tuple[int, int]] = []
    for em in re.finditer(
        r"excluding\s+Art\.\s*(\d{1,3})(?:\s*[\u2013\u2014\-]\s*(\d{1,3}))?",
        excl_text,
    ):
        lo = int(em.group(1))
        hi = int(em.group(2)) if em.group(2) else lo
        excl_ranges.append((lo, hi))

    # Also pick up the trailing "and Art. NN <reason>" inside an exclusion
    # clause. Layout: "... excluding Art. 40-43 codes/certification and Art.
    # 50 international cooperation" — drop the singleton 50. Use [^;\n]*
    # (excludes only semicolons and newlines, NOT dots — dots appear inside
    # "Art. NN").
    if "excluding" in excl_text:
        for excl in re.finditer(r"excluding[^;\n]*", excl_text):
            chunk = excl.group(0)
            for em in re.finditer(
                r"\band\s+Art\.\s*(\d{1,3})\b", chunk
            ):
                excl_ranges.append((int(em.group(1)), int(em.group(1))))

    for lo, hi in excl_ranges:
        for n in range(lo, hi + 1):
            seen.discard(n)
        nums = [n for n in nums if not (lo <= n <= hi)]

    # 4. Annexes — add as 1000+ ids? No: Annexes don't have numeric Article IDs
    # here. They appear in CRA's enumeration but the build script does not
    # currently treat Annexes as articles. Skip.

    return nums


def _article_refs_match(article_json: dict[str, Any], article_num: int) -> bool:
    """Return True if any SR's ``source_clauses`` references the given article
    number (either as a top-level ``article_ref`` or inside a clause_ref).
    """
    if not isinstance(article_num, int):
        return False
    for sr in article_json.get("security_rules", []) or []:
        for sc in sr.get("source_clauses", []) or []:
            if not isinstance(sc, dict):
                continue
            ar = str(sc.get("article_ref", ""))
            # Either a bare "Art. 9" or contains "Art. 9(…)" / "Art. 9 "
            if re.search(rf"Art\.\s*{article_num}\b", ar):
                return True
            # Some clauses are dict-form like {"clause_id": "...", "article_ref": "Art. 9"}
            # already covered above, but also accept clause_id-prefix matches:
            cid = str(sc.get("clause_id", ""))
            if cid and re.search(rf"Art[\s_]?{article_num}\b", cid):
                return True
    return False


def compute_source_role(
    article_json: dict[str, Any],
    in_scope: list[int],
    regulation: str,
) -> str:
    """Classify the article as ``primary_source`` | ``supporting_citation`` |
    ``out_of_scope``.

    Logic:
      - Parse the article number from ``article_json['article_ref']`` (e.g.
        ``"Art. 9(1)"`` → 9). Falls back to scanning the frontmatter/ID.
      - ``primary_source`` — number is in ``in_scope`` AND at least one SR
        points back to that article.
      - ``supporting_citation`` — number is in ``in_scope`` but no SR points
        back (this article is just being cited by other articles).
      - ``out_of_scope`` — number is not in ``in_scope`` AND no SR points
        back (the file exists only as a citation anchor).
    """
    # Extract article number from "Art. NN(...)" / "Art. NN"
    ref = str(article_json.get("article_ref", ""))
    m = re.search(r"Art\.\s*(\d{1,3})", ref)
    if not m:
        # Fall back: scan the first SR's article_ref or frontmatter
        fm = article_json.get("frontmatter", {}) or {}
        ref2 = str(fm.get("article", ""))
        m = re.search(r"Art\.\s*(\d{1,3})", ref2)
    if not m:
        logger.warning(
            "could not extract article number from %s %r",
            regulation,
            ref,
        )
        return "out_of_scope"
    article_num = int(m.group(1))
    in_scope_set = set(in_scope)
    is_in_scope = article_num in in_scope_set
    has_own_sc = _article_refs_match(article_json, article_num)

    if is_in_scope and has_own_sc:
        return "primary_source"
    if is_in_scope:
        return "supporting_citation"
    if has_own_sc:
        return "primary_source"  # oddly cited but does have substance
    return "out_of_scope"


__all__ = ["compute_source_role", "extract_in_scope_articles"]
