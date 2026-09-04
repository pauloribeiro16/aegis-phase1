"""Unit tests for scripts/kg_etl/config.py and driver.py."""

from unittest.mock import MagicMock, patch

import pytest

from scripts.kg_etl.config import (
    CANONICAL_BOLT_PORT,
    CANONICAL_HTTP_PORT,
    PROHIBITED_PORTS,
    get_neo4j_config,
    validate_port_safety,
)
from scripts.kg_etl.driver import create_neo4j_driver, run_unwind_batch


def test_default_config_uses_canonical_ports(monkeypatch):
    monkeypatch.delenv("NEO4J_BOLT_URL", raising=False)
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_HTTP_URL", raising=False)

    cfg = get_neo4j_config()
    assert f":{CANONICAL_BOLT_PORT}" in cfg.bolt_url
    assert f":{CANONICAL_HTTP_PORT}" in cfg.http_url


def test_validate_port_safety_rejects_prohibited_ports():
    for p in PROHIBITED_PORTS:
        with pytest.raises(ValueError, match="Prohibited port"):
            validate_port_safety(f"bolt://localhost:{p}")
        with pytest.raises(ValueError, match="Prohibited port"):
            validate_port_safety(f"http://localhost:{p}")


def test_custom_safe_ports_allowed(monkeypatch):
    monkeypatch.setenv("NEO4J_BOLT_URL", "bolt://my-cluster:7688")
    monkeypatch.setenv("NEO4J_HTTP_URL", "http://my-cluster:7475")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")

    cfg = get_neo4j_config()
    assert cfg.bolt_url == "bolt://my-cluster:7688"
    assert cfg.http_url == "http://my-cluster:7475"
    assert cfg.password == "secret"


def test_create_neo4j_driver():
    with patch("scripts.kg_etl.driver.GraphDatabase.driver") as mock_drv:
        cfg = get_neo4j_config()
        create_neo4j_driver(cfg)
        assert mock_drv.called
        call_args = mock_drv.call_args
        assert call_args[0][0] == cfg.bolt_url


def test_run_unwind_batch():
    mock_session = MagicMock()
    rows = [{"id": i} for i in range(120)]
    processed = run_unwind_batch(mock_session, "UNWIND $rows AS r RETURN r", rows, batch_size=50)
    assert processed == 120
    assert mock_session.run.call_count == 3  # 50 + 50 + 20
