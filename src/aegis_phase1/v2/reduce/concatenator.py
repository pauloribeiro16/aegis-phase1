"""concatenator — flatten MAP-stage domain results into a sub-domain dict.

After the MAP stage, results are organised by domain (D-XX). The
REDUCE stage works on the sub-domain level (D-XX.Y). The concatenator
is a pure projection: it walks ``state.domain_results`` and produces a
flat mapping keyed by sub-domain ID, plus a per-domain view carrying
the LLM-adapted narrative (so downstream renderers like ``doc_04b``
can display an Adapted Objective section per domain).

References:
    - contracts/SPRINT002_003_map_reduce_output.md (Sprint 003 — REDUCE step 1)
"""

from __future__ import annotations

import logging
from typing import Any

from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)


def concatenate(state: V2State) -> dict[str, Any]:
    """Flatten ``state.domain_results`` into a sub-domain-level dict.

    Iterates over every domain result and lifts each entry in
    ``domain_result["subdomains"]`` to the top level, keyed by the
    sub-domain ID (``D-XX.Y``). If a sub-domain appears under multiple
    domains (defensive case), the last occurrence wins and a warning is
    logged.

    Args:
        state: The full v2 pipeline state. Must contain a populated
            ``domain_results`` mapping (i.e. be at least at stage
            ``MAPPED``).

    Returns:
        A dictionary with two keys:

        * ``subdomains`` — mapping from sub-domain ID (e.g. ``"D-01.1"``)
          to the raw sub-domain dict produced by the MAP stage. Missing
          entries default to ``{}`` so downstream stages can safely
          ``.get()``.
        * ``adapted_objectives`` — mapping from domain ID (``"D-XX"``)
          to a per-domain dict carrying the LLM-adapted narrative,
          ``key_changes`` bullets, and confidence. This is the
          propagated view consumed by ``doc_04b`` for the
          Adapted Objective section and by the human review loop.
    """
    domain_results: dict[str, Any] = state.get("domain_results", {}) or {}

    subdomains: dict[str, dict[str, Any]] = {}
    adapted_objectives: dict[str, dict[str, Any]] = {}

    for domain_id, domain_result in domain_results.items():
        if not domain_result:
            continue
        domain_subdomains = (domain_result or {}).get("subdomains", []) or []
        for entry in domain_subdomains:
            sub_id = (
                entry.get("subdomain_id")
                or entry.get("id")
                or entry.get("document_id")
                or ""
            )
            if not sub_id:
                logger.debug(
                    "Skipping subdomain without ID in domain %s", domain_id
                )
                continue
            if sub_id in subdomains:
                logger.warning(
                    "Subdomain %s appears in multiple domains; overwriting", sub_id
                )
            subdomains[sub_id] = entry

        adapted_objectives[domain_id] = {
            "domain_id": domain_id,
            "adapted_objective": domain_result.get("adapted_objective", ""),
            "key_changes": list(domain_result.get("key_changes", []) or []),
            "confidence": domain_result.get("confidence", "UNKNOWN"),
            "llm_status": domain_result.get("llm_status", "UNKNOWN"),
            "domain_name": domain_result.get("domain_name", domain_id),
        }

    logger.info(
        "concatenate: %d domains -> %d subdomains, %d adapted_objectives",
        len(domain_results),
        len(subdomains),
        len(adapted_objectives),
    )
    return {
        "subdomains": subdomains,
        "adapted_objectives": adapted_objectives,
    }


__all__ = ["concatenate"]
