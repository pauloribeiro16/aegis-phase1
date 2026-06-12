"""Prompts for SubPhase B: Regulatory Structure."""

import logging

logger = logging.getLogger(__name__)

CLAUSE_BATCH_ENRICHMENT_PROMPT = """You are a regulatory clause enrichment specialist for EU compliance.

Enrich ALL clauses of the following regulation with detailed metadata.

For each clause, provide:
- clauseId (as provided)
- articleReference (as provided)
- description (as provided)
- normativeStrength (MANDATORY_UNCONDITIONAL, MANDATORY_CONDITIONAL, or GUIDANCE)
- obligatedParty (list of: CONTROLLER, PROCESSOR, MANUFACTURER, IMPORTER, DISTRIBUTOR, ESSENTIAL_OR_IMPORTANT_ENTITY, FINANCIAL_ENTITY, PROVIDER, DEPLOYER)
- obligationType (CONTINUOUS, PERIODIC, TRIGGERED, or ONE_TIME)
- isAtomic (true if the clause is at atomic/granular level, false if it groups sub-requirements)

## Regulation: {regulation_id}
## Clauses:
{clauses_json}

## Company Context:
{company_context}

Return JSON: {{"enriched_clauses": [...]}}"""

# ─── Backward-compat aliases (used by legacy nodes) ─────────────────
APPLICABILITY_SYSTEM = (
    "You are a senior EU regulatory compliance analyst. Analyze applicability of each regulation."
)
APPLICABILITY_USER = """Analyze the following company profile and generate applicability rationale.

## Company Context:
{company_context}

## Deterministic Applicability Results:
{deterministic_result}

## Ontology Regulations:
{ontology_regulations}"""

CLAUSE_MAPPING_SYSTEM = "You are a clause mapping specialist for EU regulatory compliance."
CLAUSE_MAPPING_USER = """Map the following clause to the most appropriate subdomain.

## Clause:
{clause}

## Company Context:
{company_context}"""

NORMATIVE_SYSTEM = "You are a normative intensity analyst for EU regulatory compliance."
NORMATIVE_USER = """Analyze normative intensity data.

## Normative Intensity Statistics:
{normative_intensities}

## Clause Mappings:
{clause_mappings}"""
