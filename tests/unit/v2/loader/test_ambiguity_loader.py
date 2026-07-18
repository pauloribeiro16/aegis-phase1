"""Tests for the regulation ambiguity loader."""

from pathlib import Path

from aegis_phase1.v2.loader.ambiguity_loader import load_ambiguities_for_regs

PREPROCESSING = Path(
    "/home/epmq-cyber/Área de Trabalho/projects/Methodology-main/" "00_METHODOLOGY/PREPROCESSING"
)


def test_load_ambiguities_for_gdpr() -> None:
    entries = load_ambiguities_for_regs(["GDPR"], PREPROCESSING)

    assert isinstance(entries, list)
    if entries:
        assert {"id", "regulation", "description", "resolution", "source_file"} <= set(entries[0])
        assert entries[0]["regulation"] == "GDPR"


def test_load_ambiguities_empty_for_unknown_reg() -> None:
    assert load_ambiguities_for_regs(["FAKE_REG"], PREPROCESSING) == []
