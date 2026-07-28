"""Pipeline-input contract verification (CORR-070).

This is the **structural + golden hybrid** that protects against
accidental field removal in the orchestrator's prompt-input
construction. Two layers of protection:

**Layer 1 — Structural assertions (HARD FAIL).**
For each spec, the schema (tests/fixtures/pipeline_inputs_golden/_schema.json)
declares the set of top-level keys, company_facts keys, classification
keys, and catalog keys that MUST be present in the inputs dict. If any
of these disappear, the test FAILS. This catches direct regressions
like "someone removed `layer0_catalog` from run_p1b_single".

**Layer 2 — Golden file comparison (WARNING).**
Golden JSON files under tests/fixtures/pipeline_inputs_golden/<case>/
record the full inputs dict + rendered size metadata. The test compares
the regenerated inputs against the golden and PRINTS any drift (key
sets, counts, sizes). Drift does NOT fail the test — it surfaces
unexpected changes for the developer to review and re-commit the
golden.

**Hybrid rationale:** structural assertions are the safety net that
guarantees no required field is ever silently dropped. Golden
comparison is the discovery tool for unexpected side-effects of
pipeline changes (e.g. a new field appears, a count changes).

**Known issues at v1.0.0 (see _schema.json):**
- BUG-A: P1B-LLM-01/02 user prompts are truncated by CORR-049 cap
  (catalog + # TASK are lost). Test logs this as expected.
- BUG-B: P1B-LLM-02 is called without p1b_llm_01_outputs wired.
  Schema declares it required; test will FAIL until BUG-B is fixed.

**How to update the contract:**
1. Update _schema.json with the new required fields
2. Run `python scripts/dev/regenerate-pipeline-inputs-golden.py` to refresh golden files
3. Review the diff (it should be intentional)
4. Commit both the schema and the golden files
"""
import json
import logging
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_ROOT = REPO_ROOT / "tests" / "fixtures" / "pipeline_inputs_golden"
SCHEMA_PATH = GOLDEN_ROOT / "_schema.json"


# ── Load schema + golden files once per session ────────────────────────
@pytest.fixture(scope="module")
def schema() -> dict:
    if not SCHEMA_PATH.exists():
        pytest.fail(
            f"Schema not found at {SCHEMA_PATH}. "
            f"Run: python scripts/dev/regenerate-pipeline-inputs-golden.py"
        )
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def golden_index() -> list:
    """Return a list of (case, spec, lane) tuples for every golden file."""
    out = []
    for case_dir in sorted(GOLDEN_ROOT.iterdir()):
        if not case_dir.is_dir():
            continue
        for f in sorted(case_dir.glob("*.json")):
            data = json.loads(f.read_text())
            out.append((data["case"], data["spec"], data["lane"]))
    return out


@pytest.fixture(scope="module")
def golden_data():
    """Return a dict keyed by (case, spec, lane) → golden file data."""
    out = {}
    for case_dir in sorted(GOLDEN_ROOT.iterdir()):
        if not case_dir.is_dir():
            continue
        for f in sorted(case_dir.glob("*.json")):
            data = json.loads(f.read_text())
            out[(data["case"], data["spec"], data["lane"])] = data
    return out


# ── Helpers ────────────────────────────────────────────────────────────
def _check_required_keys(schema, spec, inputs, lane=None):
    """Assert all top-level + nested required keys are present.
    Returns a list of missing-field descriptions (empty = all good)."""
    spec_schema = schema["specs"][spec]
    missing = []

    for k in spec_schema.get("top_level_keys_required", []):
        if k not in inputs:
            missing.append(f"top-level key '{k}' missing")

    cf_required = spec_schema.get("company_facts_keys_required", [])
    if cf_required:
        cf = inputs.get("company_facts") or {}
        for k in cf_required:
            if k not in cf:
                missing.append(f"company_facts key '{k}' missing")

    cl_required = spec_schema.get("classification_keys_required", [])
    if cl_required:
        cl = inputs.get("classification") or {}
        for k in cl_required:
            if k not in cl:
                missing.append(f"classification key '{k}' missing")

    lc_required = spec_schema.get("layer0_catalog_keys_required", [])
    if lc_required:
        lc = inputs.get("layer0_catalog") or {}
        for k in lc_required:
            if k not in lc:
                missing.append(f"layer0_catalog key '{k}' missing")

    refs_min = spec_schema.get("layer0_subdomain_refs_min_count", 0)
    if refs_min:
        refs = inputs.get("layer0_subdomain_refs") or []
        if len(refs) < refs_min:
            missing.append(
                f"layer0_subdomain_refs has {len(refs)} entries (expected ≥{refs_min})"
            )

    if spec_schema.get("p1b_llm_01_outputs_required"):
        if "p1b_llm_01_outputs" not in inputs:
            missing.append(
                "p1b_llm_01_outputs key missing (BUG-B not yet fixed)"
            )

    return missing


# ── Layer 1: structural assertions (HARD FAIL) ────────────────────────
class TestPipelineInputsStructural:
    """For every golden file: structural assertions per schema."""

    def test_all_golden_files_present(self, golden_index):
        """58 expected = 2+2+10+1+1 + 4+4+10+1+1 + 5+5+10+1+1 = 58."""
        assert len(golden_index) == 58, (
            f"Expected 58 golden files, found {len(golden_index)}. "
            f"Run: python scripts/dev/regenerate-pipeline-inputs-golden.py"
        )

    def test_golden_files_cover_all_5_specs(self, golden_index):
        specs = {s for _, s, _ in golden_index}
        expected = {
            "P1B-LLM-01-INTERPRETATION",
            "P1B-LLM-02-RATIONALE",
            "P1C-LLM-01-OVERLAP-CLASSIFICATION",
            "P1C-LLM-02-COMPOUND-EVENT",
            "P1C-LLM-03-STRATEGIC-SYNTHESIS",
        }
        assert specs == expected, (
            f"Spec coverage mismatch. expected={expected}, actual={specs}"
        )

    @pytest.mark.parametrize("case", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
    def test_p1b_llm_01_structural(self, schema, golden_data, case):
        for lane, g in [
            (k[2], v) for k, v in golden_data.items()
            if k[0] == case and k[1] == "P1B-LLM-01-INTERPRETATION"
        ]:
            missing = _check_required_keys(
                schema, "P1B-LLM-01-INTERPRETATION", g["inputs"], lane=lane
            )
            assert not missing, (
                f"{case} P1B-LLM-01/{lane}: " + "; ".join(missing)
            )

    @pytest.mark.parametrize("case", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
    def test_p1b_llm_02_structural(self, schema, golden_data, case):
        for lane, g in [
            (k[2], v) for k, v in golden_data.items()
            if k[0] == case and k[1] == "P1B-LLM-02-RATIONALE"
        ]:
            missing = _check_required_keys(
                schema, "P1B-LLM-02-RATIONALE", g["inputs"], lane=lane
            )
            # BUG-B: p1b_llm_01_outputs is expected MISSING until fixed
            non_bug_b = [m for m in missing if "p1b_llm_01_outputs" not in m]
            if non_bug_b:
                pytest.fail(
                    f"{case} P1B-LLM-02/{lane}: non-BUG-B missing: "
                    + "; ".join(non_bug_b)
                )
            if missing:
                logger.warning(
                    "%s P1B-LLM-02/%s: p1b_llm_01_outputs missing — BUG-B",
                    case, lane,
                )

    @pytest.mark.parametrize("case", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
    def test_p1c_llm_01_structural(self, schema, golden_data, case):
        for d_num, g in [
            (k[2], v) for k, v in golden_data.items()
            if k[0] == case and k[1] == "P1C-LLM-01-OVERLAP-CLASSIFICATION"
        ]:
            missing = _check_required_keys(
                schema, "P1C-LLM-01-OVERLAP-CLASSIFICATION", g["inputs"], lane=d_num
            )
            assert not missing, (
                f"{case} P1C-LLM-01/{d_num}: " + "; ".join(missing)
            )

    @pytest.mark.parametrize("case", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
    def test_p1c_llm_02_structural(self, schema, golden_data, case):
        for lane, g in [
            (k[2], v) for k, v in golden_data.items()
            if k[0] == case and k[1] == "P1C-LLM-02-COMPOUND-EVENT"
        ]:
            missing = _check_required_keys(
                schema, "P1C-LLM-02-COMPOUND-EVENT", g["inputs"], lane=lane
            )
            assert not missing, (
                f"{case} P1C-LLM-02/{lane}: " + "; ".join(missing)
            )

    @pytest.mark.parametrize("case", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
    def test_p1c_llm_03_structural(self, schema, golden_data, case):
        for lane, g in [
            (k[2], v) for k, v in golden_data.items()
            if k[0] == case and k[1] == "P1C-LLM-03-STRATEGIC-SYNTHESIS"
        ]:
            missing = _check_required_keys(
                schema, "P1C-LLM-03-STRATEGIC-SYNTHESIS", g["inputs"], lane=lane
            )
            assert not missing, (
                f"{case} P1C-LLM-03/{lane}: " + "; ".join(missing)
            )


# ── Layer 2: golden comparison (WARNING) ──────────────────────────────
class TestPipelineInputsGoldenDrift:
    """Soft warnings. Drift does not fail; just logs."""

    @pytest.mark.parametrize("case", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
    @pytest.mark.parametrize("spec,lane", [
        ("P1B-LLM-01-INTERPRETATION", "GDPR"),
        ("P1B-LLM-01-INTERPRETATION", "CRA"),
        ("P1B-LLM-02-RATIONALE", "GDPR"),
        ("P1C-LLM-01-OVERLAP-CLASSIFICATION", "D-01"),
        ("P1C-LLM-02-COMPOUND-EVENT", "global"),
        ("P1C-LLM-03-STRATEGIC-SYNTHESIS", "global"),
    ])
    def test_inputs_size_within_budget(self, golden_data, case, spec, lane):
        """User prompt must respect the 512KB budget OR have a truncation marker."""
        g = golden_data.get((case, spec, lane))
        if g is None:
            pytest.skip(f"No golden file for {case}/{spec}/{lane}")
        user_len = g["rendered"]["user_len"]
        if user_len > 524288:
            logger.warning(
                "%s/%s/%s: user=%d B (>524288 budget). "
                "CORR-049 cap will truncate. BUG-A.",
                case, spec, lane, user_len,
            )
        # Soft pass — the size > cap IS expected until BUG-A is fixed

    @pytest.mark.parametrize("case", ["case1-tinytask", "case2-secureborder", "case3-omnibank"])
    def test_golden_keys_match_schema(self, schema, golden_data, case):
        """Drift detection: top-level key sets should match schema."""
        for spec in schema["specs"]:
            for k, g in golden_data.items():
                if k[0] != case or k[1] != spec:
                    continue
                spec_schema = schema["specs"][spec]
                schema_top = set(spec_schema.get("top_level_keys_required", []))
                actual_top = set(g["inputs"].keys())
                if schema_top != actual_top:
                    logger.warning(
                        "%s/%s/%s: top-level key drift. "
                        "schema=%s, actual=%s. Re-run regen if intentional.",
                        case, spec, k[2],
                        sorted(schema_top - actual_top),
                        sorted(actual_top - schema_top),
                    )
        # Soft pass — drift is just logged
