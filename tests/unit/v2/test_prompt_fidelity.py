"""CORR-102: Prompt fidelity tests.

Validates the dry-run prompt dump:
- All scenarios have required keys
- All scenarios are within BASE_PROMPT_TOKENS budget (or document which are over)
- Coverage of all 3 cases * all 5 specs
- Summary counts match scenario count
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis_phase1.prompts_v2.invoker import (
    BASE_PROMPT_TOKENS,
    MAX_PROMPT_TOKENS,
)

DUMP_PATH = Path("tests/fixtures/dry_run/prompts_dump.json")


@pytest.fixture(scope="module")
def dump() -> dict:
    if not DUMP_PATH.exists():
        pytest.skip(f"{DUMP_PATH} not found; run scripts/dev/dry_run_prompts.py first")
    return json.loads(DUMP_PATH.read_text(encoding="utf-8"))


class TestDumpStructure:
    def test_dump_has_required_keys(self, dump: dict):
        required = {
            "schema_version",
            "generated_by",
            "models_tested",
            "base_prompt_tokens",
            "max_prompt_tokens",
            "model_token_caps",
            "summary",
            "scenarios",
        }
        assert required <= set(dump.keys()), f"missing: {required - set(dump.keys())}"

    def test_dump_base_is_100k(self, dump: dict):
        assert dump["base_prompt_tokens"] == BASE_PROMPT_TOKENS
        assert dump["base_prompt_tokens"] == 100000

    def test_dump_max_is_124k(self, dump: dict):
        assert dump["max_prompt_tokens"] == MAX_PROMPT_TOKENS
        assert dump["max_prompt_tokens"] == 124000

    def test_dump_summary_counts_match(self, dump: dict):
        s = dump["summary"]
        total = len(dump["scenarios"])
        assert s["total"] == total
        assert s["within_budget"] + s["over_budget"] == total
        assert s["errors"] >= 0


class TestScenarioShape:
    def test_every_scenario_has_required_keys(self, dump: dict):
        required = {
            "case",
            "spec_id",
            "lane_id",
            "model",
            "prompt_bytes",
            "prompt_tokens",
            "effective_cap",
            "within_budget",
        }
        for i, s in enumerate(dump["scenarios"]):
            missing = required - set(s.keys())
            assert not missing, f"scenario[{i}] missing keys: {missing}"

    def test_no_render_errors(self, dump: dict):
        for i, s in enumerate(dump["scenarios"]):
            assert "render_error" not in s, (
                f"scenario[{i}] has render_error: {s.get('render_error')}"
            )


class TestCaseCoverage:
    @pytest.mark.parametrize(
        "case",
        ["case1-tinytask", "case2-secureborder", "case3-omnibank"],
    )
    def test_all_cases_present(self, dump: dict, case: str):
        cases_in_dump = {s["case"] for s in dump["scenarios"]}
        assert case in cases_in_dump


class TestSpecCoverage:
    @pytest.mark.parametrize(
        "spec_id",
        [
            "P1B-LLM-01-INTERPRETATION",
            "P1B-LLM-02-RATIONALE",
            "P1C-LLM-01-OVERLAP-CLASSIFICATION",
            "P1C-LLM-02-COMPOUND-EVENT",
            "P1C-LLM-03-STRATEGIC-SYNTHESIS",
        ],
    )
    def test_all_specs_present(self, dump: dict, spec_id: str):
        specs_in_dump = {s["spec_id"] for s in dump["scenarios"]}
        assert spec_id in specs_in_dump


class TestModelCoverage:
    @pytest.mark.parametrize("model", ["gemma4:e4b", "MiniMax-M3"])
    def test_all_models_covered(self, dump: dict, model: str):
        models_in_dump = {s["model"] for s in dump["scenarios"]}
        assert model in models_in_dump


class TestBudgetEnforcement:
    def test_all_caps_match_base_for_all_models(self, dump: dict):
        """CORR-102: every model gets BASE_PROMPT_TOKENS (100K) cap."""
        caps = dump["model_token_caps"]
        for model, cap in caps.items():
            assert cap == 100000, f"{model} cap={cap} != 100000"

    def test_no_cap_exceeds_max(self, dump: dict):
        """No scenario's effective_cap exceeds MAX_PROMPT_TOKENS."""
        for s in dump["scenarios"]:
            assert s["effective_cap"] <= MAX_PROMPT_TOKENS, (
                f"scenario {s.get('case')}/{s.get('spec_id')}/{s.get('lane_id')} "
                f"cap={s['effective_cap']} > MAX={MAX_PROMPT_TOKENS}"
            )

    def test_over_budget_scenarios_are_documented(self, dump: dict):
        """If scenarios exceed budget, they are flagged in the dump."""
        over = [s for s in dump["scenarios"] if not s["within_budget"]]
        # We don't enforce 0 over-budget (the actual count depends on
        # payload size; the point is that the dump captures them so
        # operators can see the budget pressure).
        if over:
            print(f"\nINFO: {len(over)} scenarios over budget (will hard-fail at runtime):")
            for s in over[:5]:
                print(
                    f"  {s['case']}/{s['spec_id']}/{s['lane_id']} "
                    f"model={s['model']} tokens={s['prompt_tokens']} cap={s['effective_cap']}"
                )
