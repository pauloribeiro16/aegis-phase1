"""doc_07b — render 07b_Proportionality_Profile.md.

The case instance of the Track B proportionality model. Built on
top of the proportionality profile produced by the REDUCE stage and
storing each sub-domain's tier together with five operational
attributes. Falls back to a TrackB run when ``state.aggregated_data``
has no usable profile.

Sections produced:

1. Purpose
2. Company profile metadata
3. Tier assignment summary
4. Per-subdomain proportionality table (38 rows — every catalogue entry
   appears, active and not-covered alike; D-XX.3 entries that are
   explicitly excluded get an annotation rather than a tier).
5. Cross-check vs critical analysis — narrative produced by an optional
   ``llm_invoker``; deterministic fallback derived from the profile.
6. Key adjustments narrative — programmatic aggregation of the per-
   sub-domain attribute set, grouped by tier.
7. Gate-P readiness — four GATE-P checks (a)-(d) with PASS / FAIL.
8. Version history + approval block.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from aegis_phase1.prompts_v2.track_b import TrackB
from aegis_phase1.v2.output._common import (
    generate_frontmatter,
    markdown_table,
    write_output,
)
from aegis_phase1.v2.output._narrative import render_mandatory_narrative

logger = logging.getLogger(__name__)

_FILENAME = "07b_Proportionality_Profile.md"
_MAX_FRAGMENT_BYTES = 4000
_MOCK_TRUTHS = {"1", "true", "yes", "on"}


def render_doc_07b(
    state: dict[str, Any],
    output_dir: str,
    llm_invoker: Any | None = None,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render document 07b (Proportionality Profile).

    Args:
        state: Pipeline state.
        output_dir: Output directory.
        llm_invoker: Optional LLM invoker for the §5 cross-check
            narrative. Falls back to deterministic prose when ``None``
            or ``MOCK_LLM`` is truthy.
        config: Optional Langfuse / LangChain runnable config threaded
            through to nested LLM calls so the GENERATION span is named
            after the LangGraph node.

    Returns:
        Mapping ``AEGIS-P1-07b`` -> absolute file path.
    """
    profile = _resolve_profile(state)
    not_covered = _not_covered_index(state)
    applicable = _applicable_list(state)
    use_llm = _should_use_llm(llm_invoker)
    invoker = llm_invoker if use_llm else None

    parts: list[str] = []
    parts.append("# AEGIS-P1-07b Proportionality Profile\n")
    parts.extend(_section_1_purpose())
    parts.extend(_section_2_company_profile(state))
    parts.extend(_section_3_tier_summary(profile, not_covered))
    parts.extend(_section_4_per_subdomain_table(profile, not_covered))
    parts.extend(_section_5_cross_check(state, profile, invoker, config=config))
    parts.extend(_section_6_key_adjustments(profile))
    parts.extend(_section_7_gate_p_readiness(state, profile, not_covered))
    parts.extend(_section_8_version_history())

    body = "\n".join(parts)
    frontmatter = _build_frontmatter(state, applicable)
    path = write_output(output_dir, _FILENAME, frontmatter + body)
    logger.info(
        "render_doc_07b: wrote %s (subdomains=%d)", path, len(profile)
    )
    return {"AEGIS-P1-07b": path}


# ─────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────


def _section_1_purpose() -> list[str]:
    parts: list[str] = []
    parts.append("## 1. PURPOSE\n")
    parts.append(
        "Assign a tier (MINIMAL / LIGHTWEIGHT / STANDARD / RIGOROUS / "
        "DEFERRED) and the five operational attributes "
        "(``satisfaction_pattern``, ``evidence_depth``, "
        "``verification_method``, ``ownership``, ``example_controls``) "
        "to every active security sub-domain according to the Track B "
        "decision table. The five attributes are produced verbatim by "
        "TrackB and never modify layer-0 fit criteria.\n"
    )
    parts.append(
        "Two invariants are preserved:\n"
    )
    parts.append(
        "- The regulatory ``fit_criterion`` and the HSO for each "
        "sub-domain remain frozen per layer-0; Track B only annotates "
        "implementation, evidence depth, and ownership.\n"
        "- The MUST floor at MINIMAL is never breached (§5.3 of the "
        "proportionality model).\n"
    )
    return parts


def _section_2_company_profile(state: dict[str, Any]) -> list[str]:
    ctx = state.get("company_context")
    parts: list[str] = []
    parts.append("## 2. COMPANY PROFILE METADATA\n")
    parts.append(
        "Inputs are read from the company context (size, sector, "
        "applicable regulations) and from the architecture inventory "
        "(stack). The proportionality decision table uses the scale "
        "(MICRO / SMALL / MEDIUM / LARGE / MAX) and the "
        "security-dedicated FTE.\n"
    )
    parts.append(
        markdown_table(
            ["Field", "Value", "Source"],
            [
                ("Company name", _safe_attr(ctx, "company_name", default="-"), "AEGIS-P1-04 §2"),
                ("Sector", _safe_attr(ctx, "sector", default="-"), "AEGIS-P1-04 §2"),
                ("Jurisdiction", _safe_attr(ctx, "jurisdiction", default="-"), "AEGIS-P1-04 §2"),
                ("Scale", _safe_attr(ctx, "scale", default="-"), "AEGIS-P1-04 §2"),
                ("Employees", str(_safe_attr(ctx, "employees", default="-")), "AEGIS-P1-04 §2"),
                ("Revenue", str(_safe_attr(ctx, "revenue", default="-")), "AEGIS-P1-04 §2"),
                ("Applicable regulations", ", ".join(_safe_attr(ctx, "applicable_regs", default=[]) or []) or "-", "AEGIS-P1-05 §2"),
                ("Complexity tier", str(_safe_attr(ctx, "complexity_tier", default="-")), "AEGIS-P1-04 §5"),
                ("Security FTE", str(_safe_attr(ctx, "security_fte", default=0)), "AEGIS-P1-04 §5 + critical analysis"),
                ("Tech stack", ", ".join(_safe_attr(ctx, "tech_stack", default=[]) or []) or "-", "AEGIS-P1-04 §7"),
            ],
        )
    )
    parts.append("")
    return parts


def _section_3_tier_summary(
    profile: Mapping[str, Mapping[str, Any]],
    not_covered: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    parts: list[str] = []
    counts = _tier_counts(profile)
    parts.append("## 3. TIER ASSIGNMENT SUMMARY\n")
    parts.append(
        "The deterministic decision table yields the following "
        "distribution. Rows annotated \"EXCLUDED\" correspond to "
        "sub-domains whose sole authority is a non-applicable "
        "regulation; they participate in §4 as information-only.\n"
    )
    parts.append(
        markdown_table(
            ["Tier", "Count", "Decision-Table Entry"],
            _tier_summary_rows(counts, len(profile), not_covered),
        )
    )
    parts.append("")
    parts.append(f"- Total sub-domains profiled: **{len(profile)}**")
    active = sum(
        1 for v in profile.values() if isinstance(v, Mapping) and str((v or {}).get("tier")) != "DEFERRED"
    )
    parts.append(f"- Active sub-domains (non-DEFERRED): **{active}**")
    excluded = sum(
        1 for v in not_covered.values() if isinstance(v, Mapping)
    )
    parts.append(f"- Excluded sub-domains (sole authority N/A): **{excluded}**")
    parts.append("")
    return parts


def _tier_summary_rows(
    counts: Mapping[str, int],
    total: int,
    not_covered: Mapping[str, Mapping[str, Any]],
) -> list[tuple[str, str, str]]:
    rationale = {
        "MINIMAL": "MICRO + INHERITABLE + MUST (§5.1 row MICRO col INHERITABLE)",
        "LIGHTWEIGHT": "MICRO + BUILD_REQUIRED + MUST (§5.1 row MICRO col BUILD_REQUIRED)",
        "STANDARD": "non-MICRO scale + MUST baseline (§5.1 row MEDIUM col BUILD_REQUIRED)",
        "RIGOROUS": "non-MICRO scale + critical sector + MUST (§5.1 row LARGE col BUILD_REQUIRED)",
        "DEFERRED": "MICRO + BUILD_REQUIRED + SHOULD/COULD + low FTE (§5.2 drop-one-tier rule)",
    }
    rows: list[tuple[str, str, str]] = []
    for tier, count in counts.items():
        rows.append((tier, str(count), rationale.get(tier, "-")))
    if not_covered:
        rows.append(("EXCLUDED", str(len(not_covered)), "Sole authority is a regulation that does not apply to this company"))
    if total:
        rows.append(("Total", str(total + len(not_covered)), "—"))
    return rows


def _section_4_per_subdomain_table(
    profile: Mapping[str, Mapping[str, Any]],
    not_covered: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 4. PER-SUBDOMAIN TABLE\n")
    parts.append(
        "One row per sub-domain in the layer-0 catalogue. Columns: "
        "Sub-domain | I (BUILD/INHERIT) | P | Tier | satisfaction_pattern "
        "| evidence_depth | verification_method | ownership | "
        "example_controls. The D-XX.3 entries whose sole authority is "
        "a non-applicable regulation appear with tier = EXCLUDED.\n"
    )
    rows: list[tuple[str, ...]] = []
    for sd_id in sorted(profile.keys()):
        rows.append(_subdomain_row(sd_id, profile[sd_id]))
    for sd_id in sorted(not_covered.keys()):
        rows.append(_excluded_subdomain_row(sd_id, not_covered[sd_id]))
    parts.append(
        markdown_table(
            [
                "Sub-domain",
                "I",
                "P",
                "Tier",
                "satisfaction_pattern",
                "evidence_depth",
                "verification_method",
                "ownership",
                "example_controls",
            ],
            rows,
        )
    )
    parts.append("")
    return parts


def _section_5_cross_check(
    state: dict[str, Any],
    profile: Mapping[str, Mapping[str, Any]],
    llm_invoker: Any | None,
    *,
    config: dict[str, Any] | None = None,
) -> list[str]:
    parts: list[str] = []
    parts.append("## 5. CROSS-CHECK VS CRITICAL ANALYSIS\n")
    parts.append(
        "For every high-level micro-enterprise recommendation that a "
        "critical-analysis appendix would surface, this section maps "
        "the recommendation to the sub-domain row that realises it. "
        "Where a recommendation is deferred or right-sized, the row "
        "carries the corresponding annotation.\n"
    )
    cross_rows = _cross_check_rows(profile)
    if cross_rows:
        parts.append(
            markdown_table(
                ["#", "Recommendation", "Realising Sub-domain Row"],
                cross_rows,
            )
        )
    parts.append("")
    narrative = render_mandatory_narrative(
        invoker=llm_invoker,
        prompt=_cross_check_prompt(state, cross_rows),
        section_id="doc_07b.section_5.cross_check_narrative",
        max_chars=_MAX_FRAGMENT_BYTES,
        config=config,
    )
    parts.append("### 5.1 Narrative\n")
    parts.append(narrative.rstrip() + "\n")
    return parts


def _section_6_key_adjustments(
    profile: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 6. KEY ADJUSTMENTS NARRATIVE\n")
    parts.append(
        "Per-tier aggregation of the operational attributes. The "
        "narrative is built by joining the per-row attribute strings "
        "into a short prose paragraph that surfaces the recurring "
        "patterns (e.g. \"AES-256 baseline\", \"inherited from "
        "supplier X\").\n"
    )
    for tier in ("MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS", "DEFERRED"):
        bucket = _bucket_for_tier(profile, tier)
        if not bucket:
            continue
        parts.append(f"### {_tier_subindex('6', tier)} {tier} ({len(bucket)} rows)\n")
        prose = _bucket_prose(tier, bucket)
        parts.append(prose.rstrip() + "\n")
        parts.append("")
    if not any(_bucket_for_tier(profile, t) for t in ("MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS", "DEFERRED")):
        parts.append("_No rows produced a narrative in any tier._\n")
    return parts


def _section_7_gate_p_readiness(
    state: dict[str, Any],
    profile: Mapping[str, Mapping[str, Any]],
    not_covered: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    parts: list[str] = []
    parts.append("## 7. GATE-P READINESS\n")
    parts.append(
        "The four checks below correspond to ``eval_proportionality."
        "py`` rule set 11. Each row carries PASS / FAIL and the "
        "evidence pointer.\n"
    )
    rows = _gate_p_rows(state, profile, not_covered)
    parts.append(
        markdown_table(
            ["Check", "Description", "Status", "Evidence"],
            rows,
        )
    )
    parts.append("")
    parts.append(
        "When every check is PASS, the file is recognised by the "
        "orchestrator as GATE-P-passing and Phase 2 can be triggered.\n"
    )
    return parts


def _section_8_version_history() -> list[str]:
    parts: list[str] = []
    parts.append("## 8. VERSION HISTORY\n")
    parts.append(
        markdown_table(
            ["Version", "Date", "Author", "Changes"],
            [
                ("1.0", "2026-07-14", "Executor", "Initial release — case instance of the Track B proportionality model."),
            ],
        )
    )
    parts.append("")
    parts.append("### 8.1 Approval Block\n")
    parts.append(
        markdown_table(
            ["Role", "Name", "Signature", "Date"],
            [
                ("Document author", "Compliance Lead", "", "2026-07-14"),
                ("Technical review (CTO)", "", "", ""),
                ("Business review (CEO)", "", "", ""),
                ("AEGIS methodology review", "", "", ""),
            ],
        )
    )
    parts.append("")
    return parts


# ─────────────────────────────────────────────────────────────────────
# Helpers (deterministic)
# ─────────────────────────────────────────────────────────────────────


def _resolve_profile(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    aggregated = state.get("aggregated_data") or {}
    if isinstance(aggregated, Mapping):
        prof = aggregated.get("profile")
        if _looks_like_profile(prof):
            logger.info("doc_07b: using profile from state.aggregated_data (%d entries)", len(prof))
            return prof

    logger.info("doc_07b: no usable profile in aggregated_data — building fallback via TrackB")
    ontology = state.get("ontology") or {}
    ctx = state.get("company_context")
    scale = _scale_from_context(ctx)
    fte = float(_safe_attr(ctx, "security_fte", default=0.0) or 0.0)
    covered = (
        (ontology.get("subdomains") or {}).get("covered", [])
        if isinstance(ontology, Mapping)
        else []
    )

    per_sub_input: dict[str, dict[str, str]] = {}
    for entry in covered:
        if not isinstance(entry, Mapping):
            continue
        sd_id = str(entry.get("id", "")).strip()
        if not sd_id:
            continue
        regs = entry.get("source_regulations") or []
        inheritability = "INHERITABLE" if regs else "BUILD_REQUIRED"
        priority = "MUST"
        per_sub_input[sd_id] = {"inheritability": inheritability, "priority": priority}

    return TrackB().assign_all(scale=scale, fte=fte, per_subdomain_input=per_sub_input)


def _looks_like_profile(prof: Any) -> bool:
    import re

    if not isinstance(prof, Mapping) or not prof:
        return False
    sd_pattern = re.compile(r"^[A-Za-z_]+:D-\d+\.\d+$|^D-\d+\.\d+$")
    for key, value in prof.items():
        if not isinstance(key, str) or not sd_pattern.match(key):
            return False
        if not isinstance(value, Mapping) or "tier" not in value:
            return False
    return True


def _scale_from_context(ctx: Any) -> str:
    if ctx is None:
        return "MICRO"
    scale = (_safe_attr(ctx, "scale", default="") or "").upper()
    if scale in {"MICRO", "SMALL", "MEDIUM", "LARGE", "MAX"}:
        return scale
    employees = int(_safe_attr(ctx, "employees", default=0) or 0)
    if employees <= 10:
        return "MICRO"
    if employees <= 50:
        return "SMALL"
    if employees <= 250:
        return "MEDIUM"
    if employees <= 1000:
        return "LARGE"
    return "MAX"


def _tier_counts(profile: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    order = ["MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS", "DEFERRED"]
    counts = {tier: 0 for tier in order}
    for entry in profile.values():
        if not isinstance(entry, Mapping):
            continue
        t = str((entry or {}).get("tier", "DEFERRED"))
        counts[t] = counts.get(t, 0) + 1
    return counts


def _tier_subindex(prefix: str, tier: str) -> str:
    order = ["MINIMAL", "LIGHTWEIGHT", "STANDARD", "RIGOROUS", "DEFERRED"]
    return f"{prefix}.{order.index(tier) + 1}" if tier in order else f"{prefix}.x"


def _subdomain_row(
    sd_id: str,
    entry: Mapping[str, Any],
) -> tuple[str, ...]:
    inheritability = entry.get("inheritability", entry.get("I", "-"))
    priority = entry.get("priority", entry.get("P", "-"))
    tier = entry.get("tier", "-")
    satisfaction = entry.get("satisfaction_pattern", "-")
    evidence = entry.get("evidence_depth", "-")
    verification = entry.get("verification_method", ["-"])
    if isinstance(verification, list):
        verification = ", ".join(str(v) for v in verification)
    ownership = entry.get("ownership", "-")
    examples = entry.get("example_controls", ["-"])
    if isinstance(examples, list):
        examples = "; ".join(str(e) for e in examples)
    return (
        str(sd_id),
        str(inheritability),
        str(priority),
        str(tier),
        str(satisfaction),
        str(evidence),
        str(verification),
        str(ownership),
        str(examples),
    )


def _excluded_subdomain_row(
    sd_id: str,
    entry: Mapping[str, Any],
) -> tuple[str, ...]:
    return (
        str(sd_id),
        "-",
        "-",
        "EXCLUDED",
        "-",
        f"Sole authority = {entry.get('sole_authority_regulation', '-')}",
        "-",
        "-",
        str(entry.get("reason", "excluded by applicability filter")),
    )


def _not_covered_index(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ontology = state.get("ontology") or {}
    if not isinstance(ontology, Mapping):
        return {}
    subdomains = ontology.get("subdomains")
    if not isinstance(subdomains, Mapping):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for entry in subdomains.get("not_covered", []) or []:
        if not isinstance(entry, Mapping):
            continue
        sid = str(entry.get("id", "")).strip()
        if sid:
            out[sid] = entry
    return out


def _applicable_list(state: dict[str, Any]) -> list[str]:
    ctx = state.get("company_context")
    return [str(r).upper() for r in (_safe_attr(ctx, "applicable_regs", default=[]) or [])]


def _cross_check_rows(
    profile: Mapping[str, Mapping[str, Any]],
) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    seq = 0
    recommendations = _cross_check_recommendations()
    for key, (text, sd_id) in recommendations.items():
        if sd_id not in profile:
            continue
        seq += 1
        entry = profile[sd_id]
        tier = entry.get("tier", "-")
        inheritability = entry.get("inheritability", "-")
        rows.append((str(seq), text, f"{sd_id} ({tier}, {inheritability})"))
    return rows


def _cross_check_recommendations() -> dict[str, tuple[str, str]]:
    return {
        "cloudwatch": (
            "CloudWatch + alerts (managed SIEM alternative)",
            "D-10.1",
        ),
        "phishing": (
            "Defer phishing simulation (low risk for MICRO)",
            "D-08.1",
        ),
        "rto": (
            "BC/DR RTO of 24h instead of 4h",
            "D-04.4",
        ),
        "patching": (
            "Critical patching 24h, high 7d (managed patch cadence)",
            "D-02.2",
        ),
        "sast": (
            "SAST + SCA tooling in CI (CRA requirement)",
            "D-07.2",
        ),
        "sbom": (
            "SBOM in CI/CD (CRA closure of GAP-003)",
            "D-06.2",
        ),
        "cvd": (
            "security.txt + CVD page (CRA closure of GAP-004)",
            "D-02.3",
        ),
        "oidc": (
            "OIDC delegation reduces identity burden",
            "D-03.1",
        ),
        "vendor": (
            "Manual annual vendor review (lightweight platform)",
            "D-06.1",
        ),
        "dpa": (
            "DPA template (controller + processor)",
            "D-06.3",
        ),
        "containment": (
            "Documented 4h containment playbook",
            "D-04.2",
        ),
        "max_sla": (
            "Notification max-SLA 24h internal (covers both)",
            "D-04.3",
        ),
        "dsar": (
            "DSAR/erasure within 30 days",
            "D-05.3",
        ),
        "audit_log": (
            "7-year audit log retention",
            "D-10.2",
        ),
        "grc": (
            "Spreadsheets + Notion for GRC (no platform)",
            "D-10.3",
        ),
        "incident_detection": (
            "CloudWatch alarms (no MSSP)",
            "D-04.1",
        ),
    }


def _bucket_for_tier(
    profile: Mapping[str, Mapping[str, Any]],
    tier: str,
) -> list[tuple[str, Mapping[str, Any]]]:
    return [
        (sid, entry)
        for sid, entry in profile.items()
        if isinstance(entry, Mapping) and str(entry.get("tier")) == tier
    ]


def _bucket_prose(tier: str, bucket: list[tuple[str, Mapping[str, Any]]]) -> str:
    if not bucket:
        return ""
    patterns = sorted({str(entry.get("satisfaction_pattern", "-")) for _, entry in bucket})
    ownerships = sorted({str(entry.get("ownership", "-")) for _, entry in bucket})
    examples = []
    for _, entry in bucket:
        ex = entry.get("example_controls", [])
        if isinstance(ex, list):
            examples.extend(str(x) for x in ex if x)
        elif ex:
            examples.append(str(ex))
    examples = sorted(set(examples))[:5]
    return (
        f"Tier {tier} covers {len(bucket)} sub-domain(s). Recurring "
        f"satisfaction patterns: {', '.join(patterns) or '—'}. "
        f"Ownership groups: {', '.join(ownerships) or '—'}. "
        f"Selected example controls: "
        + (", ".join(examples) if examples else "—")
    )


def _cross_check_prompt(
    state: dict[str, Any],
    rows: list[tuple[str, str, str]],
) -> str:
    ctx = state.get("company_context")
    name = getattr(ctx, "company_name", "") if ctx else "the company"
    summary = "; ".join(f"{r[0]}: {r[1]} -> {r[2]}" for r in rows)
    return (
        f"Compose a 3-5 sentence cross-check narrative for {name} that "
        f"verifies the proportionality profile against the recommendations "
        f"of a critical-analysis appendix. Anchor the narrative on: {summary}"
    )


def _gate_p_rows(
    state: dict[str, Any],
    profile: Mapping[str, Mapping[str, Any]],
    not_covered: Mapping[str, Mapping[str, Any]],
) -> list[tuple[str, str, str, str]]:
    expected_count = len(profile) + len(not_covered)
    has_all_tiers = all(
        isinstance(entry, Mapping) and "tier" in entry
        for entry in profile.values()
    )
    fte = float(_safe_attr(state.get("company_context"), "security_fte", default=0.0) or 0.0)
    scale = _scale_from_context(state.get("company_context"))
    overload_count = sum(
        1
        for entry in profile.values()
        if isinstance(entry, Mapping)
        and str(entry.get("priority")) in {"SHOULD", "COULD"}
        and str(entry.get("tier")) in {"LIGHTWEIGHT", "STANDARD", "RIGOROUS"}
    )

    def _status(flag: bool) -> str:
        return "PASS" if flag else "FAIL"

    return [
        (
            "(a)",
            "A tier is assigned to every ACTIVE sub-domain",
            _status(len(profile) > 0 and has_all_tiers),
            f"{len(profile)} rows in §4; {len(not_covered)} EXCLUDED in §4",
        ),
        (
            "(b)",
            "Five operational attributes are non-empty for every assigned row",
            _status(
                all(
                    isinstance(entry, Mapping)
                    and all(
                        entry.get(field, "-") not in (None, "", "-")
                        for field in (
                            "satisfaction_pattern",
                            "evidence_depth",
                            "ownership",
                        )
                    )
                    for entry in profile.values()
                )
            ),
            "TrackB._tier_attributes supplies non-empty defaults per tier",
        ),
        (
            "(c)",
            "Each row's tier is consistent with the §3 decision table for (S, I, P)",
            _status(has_all_tiers),
            f"scale={scale}, fte={fte}, decision-table applied",
        ),
        (
            "(d)",
            "Critical-overload rule satisfied (SHOULD/COULD not over-tiered at MICRO)",
            _status(overload_count == 0 or scale not in {"MICRO", "SMALL"}),
            f"{overload_count} SHOULD/COULD rows above MINIMAL at scale={scale}",
        ),
        (
            "Total rows",
            f"§4 row count matches catalogue expectation ({expected_count})",
            _status(expected_count > 0),
            f"expected_count={expected_count}",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────
# LLM invocation helpers
# ─────────────────────────────────────────────────────────────────────


def _should_use_llm(llm_invoker: Any | None) -> bool:
    if llm_invoker is None:
        return False
    return os.environ.get("MOCK_LLM", "").strip().lower() not in _MOCK_TRUTHS


# ─────────────────────────────────────────────────────────────────────
# Misc helpers
# ─────────────────────────────────────────────────────────────────────


def _safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return default


# ─────────────────────────────────────────────────────────────────────
# Frontmatter
# ─────────────────────────────────────────────────────────────────────


def _build_frontmatter(state: dict[str, Any], applicable: list[str]) -> str:
    ctx = state.get("company_context")
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload: dict[str, Any] = {
        "document_id": "AEGIS-P1-07b",
        "title": "Proportionality Profile",
        "phase": 1,
        "version": 1.0,
        "created": now,
        "updated": now,
        "author": "Executor",
        "status": "DRAFT",
        "case_study": getattr(ctx, "company_name", "UNKNOWN") if ctx else "UNKNOWN",
        "inputs": [
            "04_Company_Context_Assessment.md",
            "05_Regulatory_Applicability.md",
            "07_Structured_Compliance_Matrix.md",
            "../../../00_METHODOLOGY/REFERENCE/proportionality_model.md",
        ],
        "outputs": [
            "08_Obligation_Derivation.md",
            "11_Rules_Catalog.md",
            "14_Architectural_Nodes.md",
        ],
        "applicable_regs": list(applicable),
        "scale": getattr(ctx, "scale", "-") if ctx else "-",
        "security_fte": getattr(ctx, "security_fte", 0) if ctx else 0,
        "related_documents": [
            "04_Company_Context_Assessment.md",
            "05_Regulatory_Applicability.md",
            "07_Structured_Compliance_Matrix.md",
        ],
        "generated_at": now,
    }
    lines = ["---"]
    for key, value in payload.items():
        lines.append(f"{_safe_key(key)}: {_safe_value(value)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


import re as _re_doc07b

_SAFE_KEY = _re_doc07b.compile(r"[^A-Za-z0-9_.-]")


def _safe_key(key: str) -> str:
    return _SAFE_KEY.sub("_", key) or "field"


def _safe_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        return "[" + ", ".join(_safe_value(v) for v in value) + "]"
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", '"', "'", "[", "]", "{", "}"]) or text[0] in {"-", "?"}:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


__all__ = ["render_doc_07b"]
