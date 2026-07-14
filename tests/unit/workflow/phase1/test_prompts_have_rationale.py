"""Verify subphase prompt files have rationale/justification/resolution in output schemas."""

from pathlib import Path

PROMPTS_DIR = Path("src/aegis_phase1/prompts")
DECISION_KEYWORDS = ["rationale", "justification", "resolution"]


def test_prompts_dir_exists():
    assert PROMPTS_DIR.is_dir(), f"{PROMPTS_DIR} not found"


def _prompt_has_decision_keyword(text: str) -> bool:
    return any(keyword in text.lower() for keyword in DECISION_KEYWORDS)


def test_subphase_a_prompt_has_rationale():
    path = PROMPTS_DIR / "subphase_a.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert _prompt_has_decision_keyword(text), (
        f"{path.name} missing rationale/justification/resolution"
    )


def test_subphase_b_prompt_has_rationale():
    path = PROMPTS_DIR / "subphase_b.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert _prompt_has_decision_keyword(text), (
        f"{path.name} missing rationale/justification/resolution"
    )


def test_subphase_c_prompt_has_rationale():
    path = PROMPTS_DIR / "subphase_c.py"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert _prompt_has_decision_keyword(text), (
        f"{path.name} missing rationale/justification/resolution"
    )
