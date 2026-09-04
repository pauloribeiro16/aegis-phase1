"""Test KG-12 objective: decoupling of runtime pipeline from Neo4j/ETL.

Invariant:
The pipeline in src/aegis_phase1/v2/ must NOT import neo4j or any scripts/kg_etl module.
Cluster runs (e.g. Deucalion) need no Neo4j instance or dependencies.
"""

import re
from pathlib import Path


def test_no_neo4j_in_pipeline_v2():
    v2_dir = Path(__file__).resolve().parents[3] / "src" / "aegis_phase1" / "v2"
    assert v2_dir.is_dir(), f"v2 directory not found at {v2_dir}"

    forbidden_patterns = [
        re.compile(r"^\s*import\s+neo4j\b", re.MULTILINE),
        re.compile(r"^\s*from\s+neo4j\b", re.MULTILINE),
        re.compile(r"^\s*import\s+scripts\.kg_etl\b", re.MULTILINE),
        re.compile(r"^\s*from\s+scripts\.kg_etl\b", re.MULTILINE),
        re.compile(r"^\s*import\s+kg_etl\b", re.MULTILINE),
        re.compile(r"^\s*from\s+kg_etl\b", re.MULTILINE),
    ]

    violations = []
    py_files = list(v2_dir.rglob("*.py"))
    assert len(py_files) > 0, "No python files found in v2"

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            matches = pat.findall(content)
            if matches:
                violations.append(
                    f"{py_file.relative_to(v2_dir.parent.parent)}: matches pattern '{pat.pattern}'"
                )

    assert not violations, (
        "KG-12 Violation: src/aegis_phase1/v2/ imports neo4j or kg_etl:\n" + "\n".join(violations)
    )
