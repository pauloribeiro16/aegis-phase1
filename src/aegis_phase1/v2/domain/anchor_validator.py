"""anchor_validator — Extract and validate OJ legal anchors cited in LLM output.

Prevents factual hallucinations like 'Annex II' when the source has only
'Annex I' by comparing output anchors against source anchors.

Public API:
    extract_anchors(text: str) -> set[str]
    extract_anchors_with_context(text: str) -> dict[str, list[str]]
    normalize_anchor(anchor: str) -> str
    validate_output_citations(output: str, source_anchors: set[str] | dict[str, list[str]]) -> tuple[bool, list[str]]
"""

from __future__ import annotations

import re

# Anchors recognized in regulatory text:
#   - Art. 30(3) GDPR
#   - Art. 5(2)
#   - Annex VII §5-§8
#   - Annex I Part II (3)
#   - Annex II  (rare, but possible)
# Negative lookahead ``(?!\w)`` avoids \b failing between ``)`` and a non-word
# delimiter like space or comma (which would prevent ``(N)`` capture).
_ART_RE = re.compile(
    r"\bArt\.\s*(\d+(?:\([^)]+\))?(?:\s*[a-z])?)(?!\w)",
    re.IGNORECASE,
)
# En-dash is intentional in OJ section ranges (e.g. §5-§8 vs §5--§8).
_ANNEX_RE = re.compile(
    r"\bAnnex\s+([IVX]+)(?:\s+(?:Part\s+[IVX]+|§\s*\d+(?:[–-]\s*§?\d+)?))?(?!\w)",  # noqa: RUF001
    re.IGNORECASE,
)
# Standalone §N (e.g. §5, §5-§8) — these are sub-sections.
# En-dash matches both en-dash and hyphen-minus in OJ section ranges.
_SECTION_RE = re.compile(r"§\s*(\d+)(?:[–-]\s*§?\s*(\d+))?")  # noqa: RUF001


def normalize_anchor(anchor: str) -> str:
    """Normalize an anchor for comparison.

    Examples:
        'Art. 30(3)' → 'art:30(3)'
        'art. 30' → 'art:30'
        'Annex VII' → 'annex:vii'
        'annex i part ii (3)' → 'annex:i part ii (3)'
        '§5' → 'section:5'
    """
    a = anchor.strip().lower()
    a = re.sub(r"\s+", " ", a)
    # Translate OJ-specific tokens into the canonical ``kind:value`` form used
    # by :func:`extract_anchors`. This keeps ``validate_output_citations``
    # comparisons aligned with the normalised form on the source side.
    a = re.sub(r"\bart\.\s*", "art:", a)
    a = re.sub(r"\bannex\s+", "annex:", a)
    a = re.sub(r"§\s*", "section:", a)
    return a


def extract_anchors(text: str) -> set[str]:
    """Extract all OJ anchors from text.

    Returns normalized anchor strings: {'art:30(3)', 'art:5(2)', 'annex:vii', 'section:5', ...}
    """
    if not text:
        return set()
    anchors: set[str] = set()
    for m in _ART_RE.finditer(text):
        anchors.add(f"art:{m.group(1).lower()}")
    for m in _ANNEX_RE.finditer(text):
        anchors.add(f"annex:{m.group(1).lower()}")
    for m in _SECTION_RE.finditer(text):
        start = m.group(1)
        end = m.group(2)
        if end:
            anchors.add(f"section:{start}-{end}")
            # Also add the endpoints individually so partial-range matches
            # (e.g. ``§5`` when source has ``§5-§8``) validate correctly.
            anchors.add(f"section:{start}")
            anchors.add(f"section:{end}")
        else:
            anchors.add(f"section:{start}")
    return anchors


def extract_anchors_with_context(text: str) -> dict[str, list[str]]:
    """Extract anchors with their surrounding regulation context.

    Returns {'GDPR': ['art:30(3)', 'art:5(2)'], 'CRA': ['annex:vii', ...]}.

    Looks for patterns like "Art. 30(3) GDPR" or "Annex VII CRA" to associate
    anchors with regulations. Falls back to 'unknown' when no regulation context.
    """
    result: dict[str, list[str]] = {}
    # Pattern: <anchor> <REGULATION>. En-dash is intentional in section ranges.
    pattern = re.compile(
        r"\b(Art\.\s*\d+(?:\([^)]+\))?(?:\s*[a-z])?|Annex\s+[IVX]+(?:\s+Part\s+[IVX]+)?(?:\s+§\s*\d+(?:[–-]\s*§?\d+)?)?|§\s*\d+(?:[–-]\s*§?\d+)?)\s+(GDPR|NIS\s?2|CRA|DORA|AI\s+Act|AI_Act)\b",  # noqa: RUF001
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        anchor_str = m.group(1)
        reg_str = m.group(2).upper().replace(" ", "_").replace("NIS_2", "NIS2").replace("AI_ACT", "AI_Act")
        # Normalize the anchor
        anchors = extract_anchors(anchor_str)
        result.setdefault(reg_str, []).extend(anchors)
    return result


def validate_output_citations(
    output: str,
    source_anchors: set[str] | dict[str, list[str]],
) -> tuple[bool, list[str]]:
    """Validate that every anchor cited in output exists in source.

    Args:
        output: LLM-generated text
        source_anchors: Either a flat set of normalized anchors OR
            a dict mapping regulation code to list of anchors.

    Returns:
        (ok, unknown_anchors) where unknown_anchors is the list of
        anchors cited in output but NOT present in source_anchors.

    Logic:
        - Extract anchors from output.
        - For each output anchor, check if it (or a prefix match) exists in source.
        - For dict source, also enforce that the output anchor is associated
          with the same regulation as in source.
    """
    output_anchors_with_reg = extract_anchors_with_context(output)
    output_anchors = set()
    for anchors in output_anchors_with_reg.values():
        output_anchors.update(anchors)
    # Also extract bare anchors without regulation context
    output_anchors.update(extract_anchors(output))

    if isinstance(source_anchors, dict):
        # Build per-regulation allowed anchors
        flat: set[str] = set()
        for reg_anchors in source_anchors.values():
            flat.update(reg_anchors)
        # Filter output anchors to those NOT in flat set
        unknown = sorted(
            a for a in output_anchors
            if not _is_known_anchor(a, flat)
        )
    else:
        unknown = sorted(
            a for a in output_anchors
            if not _is_known_anchor(a, source_anchors)
        )

    return (len(unknown) == 0, unknown)


def _is_known_anchor(anchor: str, known: set[str]) -> bool:
    """Check if anchor is in known set, with prefix-matching tolerance.

    E.g., 'art:30(3)' matches 'art:30' (prefix).
    """
    if anchor in known:
        return True
    # Prefix match: 'art:30(3)' is a refinement of 'art:30'
    for k in known:
        if k.startswith(anchor + " ") or anchor.startswith(k + " "):
            return True
        # Handle 'art:30' prefix matching 'art:30(3)' (parent matches child)
        if anchor.startswith(k + "(") and k.split("(")[0] == anchor.split("(")[0]:
            return True
        if k.startswith(anchor + "(") and k.split("(")[0] == anchor.split("(")[0]:
            return True
    return False


__all__ = [
    "extract_anchors",
    "extract_anchors_with_context",
    "normalize_anchor",
    "validate_output_citations",
]
