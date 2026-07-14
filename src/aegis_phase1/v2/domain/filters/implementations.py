"""implementations — Map tech stack to implementations."""

from __future__ import annotations
import logging
from typing import Any
from aegis_phase1.v2.state import V2State

logger = logging.getLogger(__name__)

M = {
    "aws": [
        {"name": "AWS Managed Security Services", "covers": ["D-01.1", "D-01.2", "D-01.3", "D-10.1", "D-10.2"], "adequacy": "ADEQUATE"},
        {"name": "AWS KMS", "covers": ["D-01.3"], "adequacy": "ADEQUATE"},
        {"name": "AWS S3", "covers": ["D-01.1", "D-10.2"], "adequacy": "ADEQUATE"},
        {"name": "AWS CloudWatch", "covers": ["D-10.1", "D-10.2"], "adequacy": "ADEQUATE"},
        {"name": "AWS GuardDuty", "covers": ["D-04.1", "D-10.1"], "adequacy": "ADEQUATE"},
    ],
    "firebase": [{"name": "Firebase Authentication", "covers": ["D-03.1", "D-03.2"], "adequacy": "PARTIAL"}],
    "auth0": [{"name": "Auth0", "covers": ["D-03.1", "D-03.2"], "adequacy": "ADEQUATE"}],
    "okta": [{"name": "Okta", "covers": ["D-03.1", "D-03.2"], "adequacy": "ADEQUATE"}],
    "github actions": [{"name": "GitHub Actions CI/CD", "covers": ["D-07.3"], "adequacy": "PARTIAL"}],
    "github": [{"name": "GitHub Security Features", "covers": ["D-07.3", "D-02.1"], "adequacy": "PARTIAL"}],
    "azure": [{"name": "Azure Security Center", "covers": ["D-01.1", "D-01.2", "D-10.1", "D-10.2"], "adequacy": "ADEQUATE"}],
    "gcp": [{"name": "Google Cloud Security", "covers": ["D-01.1", "D-01.2", "D-10.1"], "adequacy": "ADEQUATE"}],
    "stripe": [{"name": "Stripe (Payment Processor)", "covers": ["D-06.1"], "adequacy": "ADEQUATE"}],
    "kubernetes": [{"name": "Kubernetes", "covers": ["D-07.1", "D-07.3"], "adequacy": "PARTIAL"}],
    "terraform": [{"name": "Terraform IaC", "covers": ["D-07.4", "D-09.3"], "adequacy": "PARTIAL"}],
}


def filter_implementations(state: V2State, domain_id: str) -> list[dict[str, Any]]:
    ctx = state.get("company_context")
    if ctx is None:
        return []
    tech_stack = list(getattr(ctx, "tech_stack", []) or [])
    if not tech_stack:
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tech in tech_stack:
        norm = str(tech).strip().lower()
        if not norm:
            continue
        for key, impls in M.items():
            if key in norm:
                for impl in impls:
                    name = impl["name"]
                    if name in seen:
                        continue
                    seen.add(name)
                    out.append({
                        "name": name,
                        "covers": list(impl["covers"]),
                        "adequacy": str(impl["adequacy"]),
                    })
    out.sort(key=lambda i: i["name"])
    logger.debug("filter_implementations(%s): %d impls from %d tech", domain_id, len(out), len(tech_stack))
    return out


__all__ = ["filter_implementations"]