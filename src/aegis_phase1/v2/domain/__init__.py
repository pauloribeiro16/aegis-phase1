"""domain — MAP stage per-domain processing for the v2 pipeline.

Public API:
    assemble_inputs(state, domain_id) -> dict[str, Any]
    render_prompt(inputs, feedback="") -> str
    load_prompt_spec() -> str
    OutputParser, ParseResult
    filter_context(state, domain_id) -> dict  (legacy v1)
    filter_articles(state, domain_id) -> list[dict]  (legacy v1)
    build_domain_prompt(state, domain_id) -> str  (legacy v1)
    DomainProcessor.process(domain_id, state) -> DomainResult  (Option C)
    OllamaUnreachable                              (fatal LLM error)
    MapPartialFailure                              (some domains failed)
"""

from aegis_phase1.v2.domain.article_filter import filter_articles
from aegis_phase1.v2.domain.context_filter import filter_context
from aegis_phase1.v2.domain.inputs import assemble_inputs
from aegis_phase1.v2.domain.parser import OutputParser, ParseResult
from aegis_phase1.v2.domain.processor import (
    DOMAIN_NAMES,
    DomainProcessor,
    MapPartialFailure,
    OllamaUnreachable,
)
from aegis_phase1.v2.domain.prompt import load_prompt_spec, render_prompt
from aegis_phase1.v2.domain.prompt_builder import build_domain_prompt

__all__ = [
    "DOMAIN_NAMES",
    "DomainProcessor",
    "MapPartialFailure",
    "OllamaUnreachable",
    "OutputParser",
    "ParseResult",
    "assemble_inputs",
    "build_domain_prompt",
    "filter_articles",
    "filter_context",
    "load_prompt_spec",
    "render_prompt",
]
