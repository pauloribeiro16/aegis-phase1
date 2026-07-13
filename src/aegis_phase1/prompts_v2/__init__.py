"""AEGIS Phase 1 v1.2 LLM Prompts integration.

Loads prompts from Methodology-main/00_METHODOLOGY/PROMPTS/ and provides
canonical invocation + validation infrastructure for the 5 Phase 1 LLMs:

    P1B-LLM-01-INTERPRETATION       (per_regulation)
    P1B-LLM-02-RATIONALE            (per_regulation)
    P1C-LLM-01-OVERLAP-CLASS        (per_domain_lane)
    P1C-LLM-02-COMPOUND-EVENT       (global_reduce)
    P1C-LLM-03-STRATEGIC-SYNTHESIS  (global_reduce)

Public API:
    PromptLoader     - loads PROMPTS/*.md + extracts YAML frontmatter
    CatalogLoader    - loads YAML catalogs + evaluates predicates
    Phase1LLMInvoker - single LLM call with parse retry + schema validation
    Phase1Validator  - post-generation deterministic validation
    JSONLLogger      - structured logging (JSONL + stdout)
    RobustParser     - multi-strategy JSON parser (handles gemma4:e2b format issues)
    TrackB           - deterministic tier assignment per proportionality_model.md section 5
"""

from aegis_phase1.prompts_v2.catalog import CatalogLoader
from aegis_phase1.prompts_v2.factory import (
    get_invoker,
    get_layer0_root,
    get_logs_dir,
    get_prompts_root,
    get_validator,
)
from aegis_phase1.prompts_v2.invoker import Phase1LLMInvoker
from aegis_phase1.prompts_v2.llm_inventory import (
    LLM_SPECS,
    get_invocation_pattern,
    list_specs,
)
from aegis_phase1.prompts_v2.loader import PromptLoader
from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
from aegis_phase1.prompts_v2.phase1_executor import (
    DOMAINS,
    SPEC_COMPOUND,
    SPEC_INTERPRETATION,
    SPEC_OVERLAP,
    SPEC_RATIONALE,
    SPEC_STRATEGIC,
    Phase1Executor,
    invoker_to_executor,
)
from aegis_phase1.prompts_v2.robust_parser import RobustParser
from aegis_phase1.prompts_v2.track_b import TrackB
from aegis_phase1.prompts_v2.validator import Phase1Validator

__all__ = [
    "DOMAINS",
    "LLM_SPECS",
    "SPEC_COMPOUND",
    "SPEC_INTERPRETATION",
    "SPEC_OVERLAP",
    "SPEC_RATIONALE",
    "SPEC_STRATEGIC",
    "CatalogLoader",
    "JSONLLogger",
    "Phase1Executor",
    "Phase1LLMInvoker",
    "Phase1Validator",
    "PromptLoader",
    "RobustParser",
    "TrackB",
    "get_invocation_pattern",
    "get_invoker",
    "get_layer0_root",
    "get_logs_dir",
    "get_prompts_root",
    "get_validator",
    "invoker_to_executor",
    "list_specs",
]
