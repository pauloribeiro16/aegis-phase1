"""CORR-048 — Langfuse metadata + tree + threading tests.

Pre-CORR-048:
  - Tags had corr-XXX in some runs
  - 4 subphase tags were hardcoded on every node (defeating filter)
  - _project_company_context ignored 4 CORR-047 fields

Post-CORR-048:
  - Tags are phase:phase1 + case:case1-tinytask (no internal IDs)
  - Each subphase node adds only its own stage tag
  - _project_company_context threads the 4 fields if available

These 5 tests cover the contract:
  (a) test_runner_metadata_has_no_corr_xxx_tags
  (b) test_graph_subphase_tags_are_per_node
  (c) test_project_company_context_threads_4_new_fields
  (d) test_project_company_context_backward_compat
  (e) test_invoker_truncates_large_prompts
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aegis_phase1.v2.domain.inputs import (
    _extract_corr047_fields,
    _project_company_context,
)
from aegis_phase1.v2.state import (
    ImplementationReadiness,
    RegulatoryClassification,
    RegulatoryInteractions,
    RoleMatrix,
    RoleMatrixEntry,
)

# ──────────────────────────────────────────────────────────────────
# (a) Runner metadata: no corr-XXX tags
# ──────────────────────────────────────────────────────────────────


def test_runner_metadata_has_no_corr_xxx_tags() -> None:
    """Tags in runner.py:cmd_run_all_traced must not contain corr-XXX.

    Internal ticket IDs (corr-044, corr-045, …) leaked into the
    public Langfuse UI. Post-CORR-048 only phase + case tags are
    added by the runner.
    """
    runner_path = Path("src/aegis_phase1/v2/runner.py")
    src = runner_path.read_text(encoding="utf-8")
    # Look for any "tags=" or "tags=[...]" assignment containing "corr-"
    import re
    matches = re.findall(r"tags\s*=\s*\[[^\]]*\]", src)
    assert matches, "runner.py has no tags=[...] assignment"
    for m in matches:
        assert "corr-" not in m, f"CORR-048 FAIL: tag list leaks corr-XXX: {m!r}"
    # Also check the actual call site
    assert "tags=[f\"phase:phase1\", f\"case:{case_name}\"]" in src or \
           "tags=[\"phase:phase1\", f\"case:{case_name}\"]" in src or \
           "tags=['phase:phase1', 'case:" in src or \
           'tags=[\n        f"phase:phase1",\n        f"case:' in src, \
           "CORR-048: expected phase+case tags in runner.py cmd_run_all_traced"


# ──────────────────────────────────────────────────────────────────
# (b) Graph: per-node stage tags (not hardcoded list)
# ──────────────────────────────────────────────────────────────────


def test_graph_subphase_tags_are_per_node() -> None:
    """The 4 subphase tags (subphase:map/1b/reduce/output) must NOT be
    hardcoded in run_phase1_graph. Each _make_subgraph_node call should
    add its own stage tag via metadata.langfuse_tags."""
    graph_path = Path("src/aegis_phase1/v2/graph.py")
    src = graph_path.read_text(encoding="utf-8")
    # The old hardcoded list:
    assert '"subphase:map",\n        "subphase:1b",\n        "subphase:reduce",\n        "subphase:output"' \
        not in src, "CORR-048 FAIL: 4 subphase tags still hardcoded in run_phase1_graph"
    # Each _make_subgraph_node call must include its own stage tag
    # in metadata.langfuse_tags. We look for the stage:map / :1b / :reduce / :output strings.
    for stage in ("stage:map", "stage:1b", "stage:reduce", "stage:output"):
        assert stage in src, f"CORR-048: per-node stage tag {stage!r} not found in graph.py"


# ──────────────────────────────────────────────────────────────────
# (c) _project_company_context threads the 4 fields
# ──────────────────────────────────────────────────────────────────


def test_project_company_context_threads_4_new_fields() -> None:
    """When ctx has the 4 CORR-047 fields populated (Pydantic attrs),
    _project_company_context returns all 12 keys."""
    ctx = MagicMock(spec=[
        "company_name", "sector", "employees", "revenue", "scale",
        "security_fte", "tech_stack", "applicable_regs",
        "implementation_readiness", "regulatory_classification",
        "role_matrix", "regulatory_interactions",
    ])
    ctx.company_name = "TinyTask"
    ctx.sector = "SaaS"
    ctx.employees = 8
    ctx.revenue = 2_000_000
    ctx.scale = "MICRO"
    ctx.security_fte = 0.85
    ctx.tech_stack = ["AWS"]
    ctx.applicable_regs = ["GDPR", "CRA"]
    ctx.implementation_readiness = ImplementationReadiness(ciso="YES", backup="YES")
    ctx.regulatory_classification = RegulatoryClassification(
        cra_product_class="CLASS_I",
    )
    ctx.role_matrix = RoleMatrix(gdpr=RoleMatrixEntry(role="controller"))
    ctx.regulatory_interactions = RegulatoryInteractions()

    out = _project_company_context(ctx)
    # 8 base + 4 new = 12 keys
    assert len(out) == 12
    assert "implementation_readiness" in out
    assert "regulatory_classification" in out
    assert "role_matrix" in out
    assert "regulatory_interactions" in out
    # Each new field is serialised to dict (not the original Pydantic model)
    assert isinstance(out["implementation_readiness"], dict)
    assert isinstance(out["regulatory_classification"], dict)
    assert isinstance(out["role_matrix"], dict)
    assert isinstance(out["regulatory_interactions"], dict)
    # Values are preserved
    assert out["implementation_readiness"]["ciso"] == "YES"
    assert out["regulatory_classification"]["cra_product_class"] == "CLASS_I"


# ──────────────────────────────────────────────────────────────────
# (d) _project_company_context backward-compat (dict path)
# ──────────────────────────────────────────────────────────────────


def test_project_company_context_backward_compat() -> None:
    """When ctx is a plain dict (v1-compat shim) without the 4 fields,
    _project_company_context returns the original 8-key shape with no
    KeyError."""
    ctx = {
        "company_name": "X",
        "sector": "Tech",
        "employees": 1,
        "revenue": 0,
        "scale": "MICRO",
        "security_fte": 0.0,
        "tech_stack": [],
        "applicable_regs": [],
        # NB: no implementation_readiness / regulatory_classification /
        # role_matrix / regulatory_interactions
    }
    out = _project_company_context(ctx)
    assert len(out) == 8
    assert "implementation_readiness" not in out
    assert "regulatory_classification" not in out
    assert "role_matrix" not in out
    assert "regulatory_interactions" not in out


def test_extract_corr047_fields_dict_with_v2_company_profile() -> None:
    """State shim with v2_company_profile sub-dict is supported."""
    profile = MagicMock()
    profile.implementation_readiness = ImplementationReadiness(ciso="YES")
    profile.regulatory_classification = RegulatoryClassification(
        cra_product_class="CLASS_I"
    )
    profile.role_matrix = RoleMatrix()
    profile.regulatory_interactions = RegulatoryInteractions()
    ctx = {"v2_company_profile": profile}
    out = _extract_corr047_fields(ctx)
    assert "implementation_readiness" in out
    assert out["implementation_readiness"]["ciso"] == "YES"


def test_extract_corr047_fields_dict_direct_keys() -> None:
    """State shim with 4 direct keys is supported."""
    ctx = {
        "implementation_readiness": {"ciso": "NO", "dpo": "NO"},
        "regulatory_classification": {"cra_product_class": "CLASS_I"},
        "role_matrix": {"gdpr": {"role": "controller"}},
        "regulatory_interactions": {"temporal_conflicts": []},
    }
    out = _extract_corr047_fields(ctx)
    assert out["implementation_readiness"]["ciso"] == "NO"
    assert out["regulatory_classification"]["cra_product_class"] == "CLASS_I"
    assert out["role_matrix"]["gdpr"]["role"] == "controller"


# ──────────────────────────────────────────────────────────────────
# (e) Invoker truncates large prompts (> 10KB)
# ──────────────────────────────────────────────────────────────────


def test_invoker_raises_PromptTooLargeError_on_large_prompt() -> None:
    """CORR-102: when the rendered prompt exceeds the model's effective
    token cap, ``_attempt()`` raises :class:`PromptTooLargeError` instead
    of silently truncating (CORR-049 byte-based silent truncation is
    GONE).

    Calls ``_attempt()`` directly (bypassing ``invoke()``'s post-loop
    that has a pre-existing AttributeError on ``validation=None`` —
    out of CORR-102 scope).

    The test renders a 56K-token prompt (well above gemma4:e4b's
    8K-token native cap) and asserts the hard fail instead of any
    truncation. The exception carries the spec_id, model, sys/user
    tokens, and cap for downstream diagnosis.
    """
    from aegis_phase1.prompts_v2.factory import get_prompts_root
    from aegis_phase1.prompts_v2.invoker import (
        Phase1LLMInvoker,
        PromptTooLargeError,
    )
    from aegis_phase1.prompts_v2.llm_inventory import (
        get_invocation_pattern,
        get_stage,
    )
    from aegis_phase1.prompts_v2.loader import PromptLoader
    from aegis_phase1.prompts_v2.logging_helper import JSONLLogger
    prompt_loader = PromptLoader(root=get_prompts_root())
    invoker = Phase1LLMInvoker(
        prompt_loader=prompt_loader,
        catalog_loader=MagicMock(),
        llm_logger=MagicMock(spec=JSONLLogger),
        format_logger=MagicMock(spec=JSONLLogger),
        model="gemma4:e4b",  # 8K token native cap
        base_url="http://localhost:11434",
    )

    huge_inputs = {
        "case_id": "case1-tinytask",
        "tech_stack": [f"tech_{i:08d}" for i in range(60000)],
        "applicable_regs": ["GDPR", "CRA"],
    }

    # CORR-059: caplog fixture removed — has stash KeyError bug in
    # pytest 8.x/9.x. We don't need to assert on logs anyway; the
    # exception is the assertion target.
    with (
        patch("aegis_phase1.prompts_v2.invoker.probe_ollama", return_value=True),
        pytest.raises(PromptTooLargeError) as exc_info,
    ):
        invoker._attempt(
            spec_id="P1C-LLM-01-OVERLAP-CLASSIFICATION",
            inputs=huge_inputs,
            invocation_pattern=get_invocation_pattern(
                "P1C-LLM-01-OVERLAP-CLASSIFICATION"
            ),
            stage=get_stage("P1C-LLM-01-OVERLAP-CLASSIFICATION"),
            attempt=1,
        )

    # Error carries diagnostic context
    assert exc_info.value.spec_id == "P1C-LLM-01-OVERLAP-CLASSIFICATION"
    assert exc_info.value.model == "gemma4:e4b"
    # CORR-102: BASE is 100K tokens for all models (incl. gemma4:e4b).
    assert exc_info.value.cap == 100000
    assert exc_info.value.sys_tokens > 0
    assert exc_info.value.user_tokens > 0
    assert exc_info.value.sys_tokens + exc_info.value.user_tokens > 100000
    assert "gemma4:e4b" in str(exc_info.value)
    assert "P1C-LLM-01-OVERLAP-CLASSIFICATION" in str(exc_info.value)


# ──────────────────────────────────────────────────────────────────
# Bonus: helper unit test
# ──────────────────────────────────────────────────────────────────


def test_extract_corr047_fields_returns_empty_when_nothing_available() -> None:
    """When ctx is a plain dict without the 4 fields, helper returns {}."""
    out = _extract_corr047_fields({"company_name": "X"})
    assert out == {}
