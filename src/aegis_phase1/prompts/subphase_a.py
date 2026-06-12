"""Prompts for SubPhase A: Context Setup."""

import logging

logger = logging.getLogger(__name__)

STAKEHOLDER_PROMPT = """You are a regulatory compliance analyst specializing in organizational assessment.

Analyze the company intake form and identify ALL stakeholders relevant to regulatory compliance.

For each stakeholder, provide:
- stakeholderId (STK-INT-01, STK-INT-02 for internal; STK-EXT-01, STK-EXT-02 for external)
- name (role title if name not given)
- role
- department (if internal) or organization (if external)
- stakeholderType ("internal" or "external")
- accessLevel (if known)
- relationshipType (if external)

## Company Context:
{company_context}

## Intake Form:
{intake_form}

## Taxonomy Reference:
{taxonomy_reference}

Return JSON: {{"stakeholders": [...]}}"""

BUSINESS_GOALS_PROMPT = """You are a regulatory compliance analyst.

Identify business goals from the company's intake form that intersect with regulatory compliance.

For each goal, provide:
- goalId (BG-01, BG-02, etc.)
- description
- priority (HIGH, MEDIUM, LOW)
- strategicAlignment (how it relates to compliance requirements)

## Company Context:
{company_context}

## Intake Form:
{intake_form}

## Stakeholder Analysis:
{stakeholder_analysis}

Return JSON: {{"goals": [...], "summary": "..."}}"""

REGULATORY_INTERACTIONS_PROMPT = """You are a regulatory interaction analyst for EU compliance.

Enrich the following regulatory interactions with conflict descriptions and resolution principles.

For each interaction:
- interactionId
- interactionType (TEMPORAL_CONFLICT, REQUIREMENT_CONFLICT, TRIGGER_MISMATCH, NEGATIVE_ANALYSIS)
- involvedRegulations
- conflictDescription (detailed description of the conflict)
- resolutionPrinciple (how to resolve or manage the conflict)

## Company Context:
{company_context}

## Regulatory Interactions from CSV:
{interactions}

## Applicable Regulations:
{applicable_regulations}

Return JSON: {{"interactions": [...]}}"""

# ─── Backward-compat aliases (used by legacy nodes) ─────────────────
STAKEHOLDER_ANALYSIS_SYSTEM = (
    "You are a regulatory compliance analyst specializing in organizational assessment."
)
STAKEHOLDER_ANALYSIS_USER = STAKEHOLDER_PROMPT
BUSINESS_GOALS_SYSTEM = "You are a regulatory compliance analyst."
BUSINESS_GOALS_USER = BUSINESS_GOALS_PROMPT
CONTEXT_SUMMARY_SYSTEM = "You are a senior regulatory compliance analyst. Produce a comprehensive Company Context Assessment."
CONTEXT_SUMMARY_USER = """Based on the following analysis, produce a complete Company Context Assessment.

## Company Context (from ontology):
{company_context}

## Stakeholder Analysis:
{stakeholder_analysis}

## Business Goals Catalog:
{business_goals}

## Intake Form:
{intake_form}

## Taxonomy Reference:
{taxonomy_reference}

Produce the full assessment with regulatory applicability flags and architectural implications."""
