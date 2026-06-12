"""Prompts for SubPhase C: Analysis & Matrix."""

import logging

logger = logging.getLogger(__name__)

COMPLEMENTARITY_PROMPT = """You are a regulatory complementarity analyst for EU compliance.

Analyze overlapping subdomains where multiple regulations apply and identify:
1. Synergistic overlaps (regulations reinforce each other)
2. Structural tensions (permanent conflicting requirements)
3. Contextual tensions (same event triggers conflicting obligations)

For each complementarity analysis, provide:
- analysisId (CA-01, CA-02, etc.)
- sharedScope (float 0.0-1.0, proportion of shared regulatory scope)
- jaccardIndex (complementarity index, float 0.0-1.0)
- overlapType (SYNERGISTIC, STRUCTURAL_TENSION, CONTEXTUAL_TENSION, CUMULATIVE_REINFORCEMENT)
- structuralConnectedness (float 0.0-1.0)
- regulation1Id
- regulation2Id
- description
- justification

## Complementarity Data from CSV:
{complementarity_data}

## Applicable Regulations:
{applicable_regulations}

## Domain Coverage Entries:
{coverage_entries}

Return JSON: {{"complementarity_analyses": [...]}}"""

DOMAIN_ELABORATION_PROMPT = """You are a domain elaboration analyst for EU regulatory compliance.

For each domain where complementarity analysis identified overlaps, produce elaboration entries.

For each entry, provide:
- entryId (DE-01, DE-02, etc.)
- analysisId (link to complementarity analysis)
- subDomainId
- elaborationFactor (float, how much the domain needs elaboration, 0.0-1.0)
- dominantRegulation (which regulation dominates this subdomain)
- relationType (OVERLAP, CUMULATIVE_REINFORCEMENT, CONFLICT, GAP)
- normativeIntensity (float 0.0-1.0)
- weightedScore (float)
- notes
- rationale

## Domain Elaboration Data from CSV:
{elaboration_data}

## Complementarity Analyses:
{complementarity_analyses}

## Domain Coverage Entries:
{coverage_entries}

Return JSON: {{"domain_elaboration_entries": [...]}}"""

STRATEGIC_IMPLICATIONS_PROMPT = """You are a strategic compliance advisor for EU regulatory frameworks.

Based on the business goals and regulatory landscape, identify strategic implications.

For each implication, provide:
- implicationId (SI-01, SI-02, etc.)
- description
- businessImpact (HIGH, MEDIUM, LOW)
- complianceRisk (HIGH, MEDIUM, LOW)

## Business Goals:
{business_goals}

## Company Context:
{company_context}

## Compliance Context:
{compliance_context}

## Complementarity Analyses:
{complementarity_analyses}

## Domain Coverage Entries:
{coverage_entries}

Return JSON: {{"strategic_implications": [...]}}"""

# ─── Backward-compat aliases (used by legacy nodes) ─────────────────
COMPLEMENTARITY_SYSTEM = "You are a regulatory complementarity analyst for EU compliance."
COMPLEMENTARITY_USER = """Analyze overlapping subdomains and applicable regulations.

## Overlapping Subdomains:
{overlaps}

## Applicable Regulations:
{applicable_regulations}"""

STRATEGIC_SYSTEM = "You are a strategic compliance advisor for EU regulatory frameworks."
STRATEGIC_USER = """Based on complementarity analysis, company context, and coverage summary, generate strategic implications.

## Complementarity Analysis:
{complementarity}

## Company Context:
{company_context}

## Coverage Summary:
{coverage_summary}"""

STRATEGIC_IMPLICATIONS_SYSTEM = STRATEGIC_SYSTEM
STRATEGIC_IMPLICATIONS_USER = STRATEGIC_USER
