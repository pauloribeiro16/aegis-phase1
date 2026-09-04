"""Unit tests for scripts/kg_etl/schema.py."""

from unittest.mock import MagicMock

from scripts.kg_etl.schema import (
    SCHEMA_CYPHER_PATH,
    apply_schema,
    load_schema_statements,
)


def test_schema_file_exists():
    assert SCHEMA_CYPHER_PATH.is_file()


def test_load_schema_statements_parses_cleanly():
    statements = load_schema_statements()
    assert len(statements) > 50, f"Expected >50 DDL statements, got {len(statements)}"

    # Check for fixes to Errata 1 (composite keys on run-derived nodes)
    sda_constraint = [s for s in statements if "sda_pk" in s]
    assert sda_constraint, "sda_pk constraint missing"
    assert "(n.run_id, n.sub_domain_id)" in sda_constraint[0]

    pa_constraint = [s for s in statements if "pa_pk" in s]
    assert "(n.run_id, n.pair_id)" in pa_constraint[0]

    # Check for fixes to Errata 2 (SecurityObjective lookup index instead of unique constraint)
    so_index = [s for s in statements if "so_reg" in s]
    assert so_index, "so_reg index missing"
    assert "CREATE INDEX so_reg" in so_index[0]
    assert "ON (n.regulation_code)" in so_index[0]
    assert "UNIQUE" not in so_index[0]


def test_apply_schema_executes_on_session():
    mock_session = MagicMock()
    count = apply_schema(mock_session)
    assert count > 50
    assert mock_session.run.call_count == count
