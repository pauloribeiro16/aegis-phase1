"""Document evaluator for Phase 1 output documents.

Hybrid approach:
- Rule-based: detect empty fields, placeholders [N], [X]%, incomplete sections
- LLM-based: semantic inconsistencies, ID format mismatches, contradictions

Returns a prioritized list of Issues that can be patched section-by-section.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from aegis_phase1.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Issue:
    """A single issue found in a filled document."""

    section: str
    issue_type: (
        str  # "empty_field" | "placeholder" | "inconsistent" | "missing_section" | "contradiction"
    )
    severity: str  # "low" | "medium" | "high"
    location: str  # ex: "line 3, field 'Sector'"
    description: str
    suggested_fix: str
    context: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


SECTION_HEADER_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"\[(?:N|X|Y|NN|\?|\.+|\.\.\.)\]")
EMPTY_FIELD_RE = re.compile(r"^[-*]\s+\*\*([^*]+):\*\*\s*$", re.MULTILINE)
INCOMPLETE_BULLET_RE = re.compile(r"^[-*]\s+\*\*([^*]+):\*\*\s+\[", re.MULTILINE)


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split a Markdown document into (header, body) pairs."""
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_header = ""
    current_body: list[str] = []

    for line in lines:
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", line)
        if m:
            if current_header or current_body:
                sections.append((current_header, "\n".join(current_body).strip()))
            current_header = m.group(2)
            current_body = []
        else:
            current_body.append(line)

    if current_header or current_body:
        sections.append((current_header, "\n".join(current_body).strip()))

    return sections


def _rule_based_scan(filled: str, template: str) -> list[Issue]:
    """Apply rule-based checks: empty fields, placeholders, incomplete bullets."""
    issues: list[Issue] = []
    sections = _split_into_sections(filled)

    for header, body in sections:
        if not body:
            issues.append(
                Issue(
                    section=header or "(unnamed)",
                    issue_type="missing_section",
                    severity="high",
                    location=f"section '{header}'",
                    description=f"Section '{header}' has no content",
                    suggested_fix="Fill this section with content from the state",
                )
            )
            continue

        for m in EMPTY_FIELD_RE.finditer(body):
            field_name = m.group(1)
            line_start = body[: m.start()].count("\n") + 1
            issues.append(
                Issue(
                    section=header or "(unnamed)",
                    issue_type="empty_field",
                    severity="high",
                    location=f"line {line_start}, field '{field_name}'",
                    description=f"Field '{field_name}' is empty (no value after '**Field:**')",
                    suggested_fix=f"Fill field '{field_name}' with the corresponding value from state",
                )
            )

        for m in PLACEHOLDER_RE.finditer(body):
            line_start = body[: m.start()].count("\n") + 1
            placeholder = m.group(0)
            issues.append(
                Issue(
                    section=header or "(unnamed)",
                    issue_type="placeholder",
                    severity="medium",
                    location=f"line {line_start}",
                    description=f"Unfilled placeholder '{placeholder}' found",
                    suggested_fix=f"Replace '{placeholder}' with actual value",
                )
            )

    return issues


def _detect_id_inconsistencies(filled: str) -> list[Issue]:
    """Detect inconsistent Sub-Domain ID formats (SD-* vs D-XX.Y vs D-XX.X.Y)."""
    issues: list[Issue] = []
    sd_style = set(re.findall(r"\bSD-[A-Z_]+\b", filled))
    d_style = set(re.findall(r"\bD-\d+\.\d+(?:\.\d+)?\b", filled))

    if sd_style and d_style:
        sections = _split_into_sections(filled)
        for header, body in sections:
            if re.search(r"\bSD-[A-Z_]+\b", body) and re.search(r"\bD-\d+\.\d+", body):
                issues.append(
                    Issue(
                        section=header or "(unnamed)",
                        issue_type="inconsistent",
                        severity="medium",
                        location=f"section '{header}'",
                        description=(
                            f"Mixed Sub-Domain ID formats found: {len(sd_style)} SD-* style, "
                            f"{len(d_style)} D-XX.Y style. Pick one."
                        ),
                        suggested_fix=(
                            f"Normalize all Sub-Domain IDs to one format. "
                            f"Found SD-* examples: {list(sd_style)[:3]}. "
                            f"Found D-XX.Y examples: {list(d_style)[:3]}."
                        ),
                    )
                )
                break

    return issues


def _detect_contradictions(filled: str) -> list[Issue]:
    """Detect self-contradictory statements in the same document."""
    issues: list[Issue] = []

    coverage_matches = re.findall(
        r"(?:coverage|covered|coverage %)[:\s]*([0-9]+\.?[0-9]*)\s*%",
        filled,
        re.IGNORECASE,
    )
    if len(coverage_matches) >= 2:
        nums = [float(m) for m in coverage_matches]
        if max(nums) - min(nums) > 5.0:
            sections = _split_into_sections(filled)
            sections_with_coverage = [
                (h, b) for h, b in sections if re.search(r"coverage", b, re.IGNORECASE)
            ]
            for header, _body in sections_with_coverage:
                issues.append(
                    Issue(
                        section=header or "(unnamed)",
                        issue_type="contradiction",
                        severity="high",
                        location=f"section '{header}'",
                        description=(
                            f"Conflicting coverage percentages found: {nums}. "
                            f"Verify which is correct."
                        ),
                        suggested_fix=(
                            "Reconcile coverage values. Use the computed value from "
                            "coverage_summary.coverage_pct, not a template default."
                        ),
                    )
                )

    return issues


def _detect_old_dates(filled: str) -> list[Issue]:
    """Detect completion_date older than 1 day (suggests stale run)."""
    issues: list[Issue] = []
    from datetime import datetime, timedelta

    m = re.search(r"completion_date[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2})", filled)
    if m:
        try:
            d = datetime.fromisoformat(m.group(1))
            if d < datetime.now() - timedelta(days=1):
                sections = _split_into_sections(filled)
                for header, body in sections:
                    if "completion_date" in body.lower() or "matrix_id" in body.lower():
                        issues.append(
                            Issue(
                                section=header or "(unnamed)",
                                issue_type="stale_data",
                                severity="medium",
                                location="line with completion_date",
                                description=(
                                    f"completion_date is {m.group(1)} (more than 1 day old). "
                                    f"This is from a previous run."
                                ),
                                suggested_fix=(
                                    "Update completion_date to current timestamp and "
                                    "regenerate matrix_id with new timestamp."
                                ),
                            )
                        )
                        break
        except ValueError as e:
            logger.debug("Date parse in _detect_old_dates failed: %s", e)

    return issues


def _llm_based_scan(
    filled: str,
    template: str,
    state: dict,
    model: str = "gemma4:e4b",
) -> list[Issue]:
    """Use LLM to detect semantic issues that rules miss.

    Conservative: only adds issues, never removes rule-based ones.
    """
    from aegis_phase1.llm.base import create_llm_client

    if len(filled) > 20000:
        logger.debug("[evaluator] doc too long for LLM scan, skipping (%d chars)", len(filled))
        return []

    try:
        llm_config = state.get("case_config", {}).get("llm", {})
        client = create_llm_client(llm_config)
    except Exception:
        logger.warning("[evaluator] could not create LLM client, skipping LLM scan", exc_info=True)
        return []

    prompt = f"""You are auditing a filled regulatory document against its template.

TEMPLATE (expected structure):
{template[:8000]}

FILLED DOCUMENT (produced by pipeline):
{filled[:8000]}

Identify ONLY clear, concrete issues. Output a JSON array. If no issues, return [].

Each issue must have:
- "section": section header name
- "type": one of "empty_field" | "inconsistent" | "missing_section" | "contradiction" | "placeholder"
- "severity": "low" | "medium" | "high"
- "location": brief location hint
- "description": what is wrong
- "fix": concrete suggestion

Focus on:
1. Fields that exist in template but are absent/empty in filled
2. Sections that should exist per template but don't
3. Factual contradictions within the document
4. Mix of different ID formats (e.g., "SD-XYZ" vs "D-01.1")
5. Dates from previous runs (older than today)

OUTPUT (JSON array, no preamble):"""

    try:
        result = client.generate(
            prompt=prompt,
            system="You are a precise document auditor. Output only valid JSON.",
            task_name="doc_evaluation",
            temperature=0.0,
            num_predict=2000,
        )
    except Exception:
        logger.warning("[evaluator] LLM call failed", exc_info=True)
        return []

    if result.get("error"):
        return []

    raw = result.get("raw", "").strip()
    if not raw:
        return []

    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        return []

    try:
        llm_issues_raw = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        logger.warning("[evaluator] LLM returned invalid JSON: %s", raw[:200])
        return []

    issues: list[Issue] = []
    for it in llm_issues_raw:
        if not isinstance(it, dict):
            continue
        issues.append(
            Issue(
                section=it.get("section", "unknown"),
                issue_type=it.get("type", "inconsistent"),
                severity=it.get("severity", "medium"),
                location=it.get("location", ""),
                description=it.get("description", ""),
                suggested_fix=it.get("fix", ""),
            )
        )

    return issues


def evaluate_filled_doc(
    filled_path: Path,
    template_path: Path,
    state: dict | None = None,
    use_llm: bool = True,
) -> list[Issue]:
    """Evaluate a filled document and return prioritized list of issues.

    Args:
        filled_path: Path to the _filled.md document
        template_path: Path to the original template (.md)
        state: Optional phase state dict for LLM context
        use_llm: Whether to also run LLM-based scan

    Returns:
        List of Issues sorted by severity (high first).
    """
    filled = filled_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")

    logger.info("[evaluator] scanning %s (%d chars)", filled_path.name, len(filled))

    issues: list[Issue] = []
    issues.extend(_rule_based_scan(filled, template))
    issues.extend(_detect_id_inconsistencies(filled))
    issues.extend(_detect_contradictions(filled))
    issues.extend(_detect_old_dates(filled))

    if use_llm and state is not None:
        issues.extend(_llm_based_scan(filled, template, state))

    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: severity_order.get(i.severity, 3))

    logger.info(
        "[evaluator] %s: %d issues (high=%d, medium=%d, low=%d)",
        filled_path.name,
        len(issues),
        sum(1 for i in issues if i.severity == "high"),
        sum(1 for i in issues if i.severity == "medium"),
        sum(1 for i in issues if i.severity == "low"),
    )

    return issues


def group_issues_by_section(issues: list[Issue]) -> dict[str, list[Issue]]:
    """Group issues by their section for batched patching."""
    grouped: dict[str, list[Issue]] = {}
    for issue in issues:
        grouped.setdefault(issue.section, []).append(issue)
    return grouped
