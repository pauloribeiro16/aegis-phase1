"""Tests for the quantization manifest sidecar (AEGIS-P1-CORR-111).

Behaviour contracts verified:

  Schema + dataclass
    1.  ``QuantManifest.validate()`` flags empty model, bad provider, bad
        pulled_at format, unknown provenance, and 'quantization=unknown'.
    2.  ``QuantManifest.validate()`` is silent on a clean record.
    3.  ``to_json`` / ``from_json`` round-trip preserves every field.
    4.  ``manifest_path`` produces ``<root>/<provider>/<model>@<quant>.json``.

  Path / IO
    5.  ``write_manifest`` creates the parent dirs and writes JSON.
    6.  ``load_manifest`` reads back exactly what was written.
    7.  When the same path exists, ``manifest_path`` appends -2, -3 to avoid
        clobbering.
    8.  ``find_manifest`` returns the newest matching record when multiple
        manifests exist for the same model (e.g. q4_K_M + q8_0).
    9.  Missing ``AEGIS_QUANT_MANIFEST_ROOT``/provider dir is a no-match, not
        a crash.

  Helpers
   10.  ``_normalize_quant_tag`` handles case-insensitive variants
        ('Q4_K_M', 'q4-k-m', ' q4 KM ') → 'q4_k_m'.
   11.  Unknown tags pass through unchanged.
   12.  ``detect_ollama_quantization`` never raises — missing binary, timeout,
        non-JSON output, non-zero exit, all return 'unknown'.
   13.  ``build_from_ollama_pull`` uses 'ollama-pull' provenance when the
        probe succeeds, 'provider_default' otherwise (per user decision
        2026-09-02: declare the provider default when nothing else is
        known).
   14.  ``frontmatter_comment`` escapes double-quotes and the ``--`` sequence
        to keep the HTML comment well-formed.
   15.  ``header_for_doc`` appends the unknown-quant caveat iff quant is
        'unknown' / 'provider_default'.

  Constraints
   16.  No third-party imports — stdlib only (no httpx, requests, etc.).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# Import under test — done after the contract pieces so the module can run
# without an ollama binary present.
from aegis_phase1.llm import quant_manifest as qm

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_manifest_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AEGIS_QUANT_MANIFEST_ROOT", str(tmp_path))
    # reload the module so DEFAULT_MANIFEST_ROOT points at our temp dir.
    monkeypatch.setattr(qm, "DEFAULT_MANIFEST_ROOT", str(tmp_path))
    # detect_ollama_quantization respects this — turn off for tests where we
    # don't want a subprocess call.
    return tmp_path


def _good_manifest(**overrides) -> qm.QuantManifest:
    base = {
        "model": "nemotron-3.5-lightning:30b",
        "provider": "ollama",
        "quantization": "q4_K_M",
        "quantization_provenance": "ollama-pull",
        "pulled_at": "2026-09-02T20:14:00Z",
        "source": "registry.ollama.ai/library/nemotron-3.5-lightning:30b",
        "size_bytes": 17_382_914_133,
        "digest_sha256": "f3a1c0b",
        "vllm_compat": False,
        "notes": "default Ollama tag",
    }
    base.update(overrides)
    return qm.QuantManifest(**base)


# ---------------------------------------------------------------------------
# Schema + dataclass
# ---------------------------------------------------------------------------


def test_validate_flags_bad_fields() -> None:
    m = qm.QuantManifest(
        model="",
        provider="alien",
        quantization="unknown",
        quantization_provenance="magical",
        pulled_at="not-a-timestamp",
        source="",
        size_bytes=-1,
    )
    issues = m.validate()
    assert any("model is empty" in i for i in issues)
    assert any("provider" in i for i in issues)
    assert any("quantization is 'unknown'" in i for i in issues)
    assert any("quantization_provenance" in i for i in issues)
    assert any("pulled_at" in i for i in issues)
    assert any("size_bytes" in i for i in issues)


def test_validate_clean_record() -> None:
    assert _good_manifest().validate() == []


def test_to_from_json_roundtrip() -> None:
    m = _good_manifest()
    raw = m.to_json()
    assert isinstance(raw, str)
    assert json.loads(raw)["model"] == m.model
    m2 = qm.QuantManifest.from_json(raw)
    assert m2 == m


def test_manifest_path_layout() -> None:
    m = _good_manifest()
    p = m.manifest_path(root="/tmp/whatever")
    assert p == Path("/tmp/whatever/ollama/nemotron-3.5-lightning:30b@q4_K_M.json")


# ---------------------------------------------------------------------------
# Path / IO
# ---------------------------------------------------------------------------


def test_write_then_load(tmp_manifest_root: Path) -> None:
    m = _good_manifest()
    p = qm.write_manifest(m)
    assert p.exists()
    loaded = qm.load_manifest(p)
    assert loaded == m
    # pulled_at should have been preserved
    assert loaded.pulled_at == "2026-09-02T20:14:00Z"


def test_write_auto_fills_pulled_at(tmp_manifest_root: Path) -> None:
    m = _good_manifest(pulled_at="")
    p = qm.write_manifest(m)
    loaded = qm.load_manifest(p)
    assert loaded.pulled_at  # ISO-8601 set automatically
    assert loaded.pulled_at.endswith("Z")


def test_manifest_path_avoids_clobbering(tmp_manifest_root: Path) -> None:
    m = _good_manifest()
    p1 = qm.write_manifest(m)
    p2 = qm.write_manifest(m)
    assert p1 != p2
    assert p1.exists() and p2.exists()
    assert p2.name.startswith("nemotron-3.5-lightning:30b@q4_K_M-2.json")


def test_find_manifest_returns_newest(tmp_manifest_root: Path) -> None:
    m_old = _good_manifest(
        quantization="q4_K_M",
        pulled_at="2026-09-01T08:00:00Z",
    )
    m_new = _good_manifest(
        quantization="q8_0",
        pulled_at="2026-09-02T20:00:00Z",
    )
    qm.write_manifest(m_old)
    qm.write_manifest(m_new)
    hit = qm.find_manifest(
        model="nemotron-3.5-lightning:30b", provider="ollama"
    )
    assert hit is not None
    assert hit.quantization == "q8_0"  # newest pulled_at wins


def test_find_manifest_quant_filter(tmp_manifest_root: Path) -> None:
    qm.write_manifest(_good_manifest(quantization="q4_K_M", pulled_at="2026-09-02T10:00:00Z"))
    qm.write_manifest(_good_manifest(quantization="q8_0",   pulled_at="2026-09-02T20:00:00Z"))
    hit = qm.find_manifest(
        model="nemotron-3.5-lightning:30b", provider="ollama", quantization="q4_K_M"
    )
    assert hit is not None
    assert hit.quantization == "q4_K_M"


def test_find_manifest_missing_dir_returns_none(tmp_manifest_root: Path) -> None:
    # No manifests dir exists → no hit, no crash
    assert qm.find_manifest(model="phantom", provider="ollama") is None


# ---------------------------------------------------------------------------
# Helpers — tag normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Q4_K_M", "q4_k_m"),
        ("q4-k-m", "q4_k_m"),
        # Two unambiguous shapes the normaliser fixes up (qq{N}{KM} family):
        ("q4KM", "q4_k_m"),
        ("Q4KM", "q4_k_m"),
        # Spaces/dashes collapse to single underscore; we don't infer digit↔letter joins.
        ("  q4  KM  ", "q4_km"),
        ("FP8", "fp8"),
        ("bf16", "bf16"),
        ("exl2@4bpw", "exl2@4bpw"),  # unknown tags pass through
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_normalize_quant_tag(raw, expected) -> None:
    assert qm._normalize_quant_tag(raw) == expected


def test_detect_via_blob_happy_path(tmp_path: Path) -> None:
    """Stage a fake Ollama cache on disk and read file_type from the
    config blob. No subprocesses — proves Path 3 (CORR-111 follow-up,
    2026-09-03)."""
    root = tmp_path
    manifest_dir = root / "manifests" / "registry.ollama.ai" / "library" / "qwen3.5"
    manifest_dir.mkdir(parents=True)
    # manifest references a config blob by sha256
    cfg_sha = "f" * 64  # 64 hex chars; sha length
    (root / "blobs").mkdir(parents=True)
    cfg_path = root / "blobs" / f"sha256-{cfg_sha}"
    cfg_path.write_text(json.dumps({
        "model_format": "gguf",
        "model_family": "qwen35",
        "file_type": "Q4_K_M",
    }))
    cfg_digest = f"sha256:{cfg_sha}"
    (manifest_dir / "27b").write_text(json.dumps({
        "config": {"digest": cfg_digest, "mediaType": "image.v1+json", "size": 1},
        "layers": [{"digest": "sha256:0" * 64, "size": 1}],
    }))
    # Tag in model name → match by wanted_tag
    assert qm.detect_ollama_quantization_via_blob("qwen3.5:27b", ollama_models_root=root) == "q4_k_m"


def test_detect_via_blob_no_manifest_dir(tmp_path: Path) -> None:
    """Bare-name match against a missing model → unknown, not error."""
    assert qm.detect_ollama_quantization_via_blob("ghost:99", ollama_models_root=tmp_path) == "unknown"


def test_detect_via_blob_missing_config_blob(tmp_manifest_root: Path) -> None:
    """Manifest present but its config blob is gone → unknown, not error."""
    root = tmp_path_for_blob_test(tmp_manifest_root)
    manifest_dir = root / "manifests" / "registry.ollama.ai" / "library" / "ghost"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "1b").write_text(json.dumps({
        "config": {"digest": "sha256:" + "0" * 64, "size": 1},
        "layers": [],
    }))
    assert qm.detect_ollama_quantization_via_blob("ghost:1b", ollama_models_root=root) == "unknown"


def test_detect_via_blob_no_file_type_field(tmp_manifest_root: Path) -> None:
    """Manifest + config blob exist but the config lacks file_type → unknown."""
    root = tmp_path_for_blob_test(tmp_manifest_root)
    manifest_dir = root / "manifests" / "registry.ollama.ai" / "library" / "naked"
    manifest_dir.mkdir(parents=True)
    cfg_sha = "a" * 64
    (root / "blobs").mkdir(parents=True)
    (root / "blobs" / f"sha256-{cfg_sha}").write_text(json.dumps({
        "model_format": "gguf",
        "model_family": "naked",
        # NO file_type
    }))
    (manifest_dir / "30b").write_text(json.dumps({
        "config": {"digest": f"sha256:{cfg_sha}", "size": 1},
        "layers": [],
    }))
    assert qm.detect_ollama_quantization_via_blob("naked:30b", ollama_models_root=root) == "unknown"


def tmp_path_for_blob_test(root: Path) -> Path:
    """Helper: a fresh tmp dir independent of the one in tmp_manifest_root."""
    import shutil
    d = root / "_blob_test_root"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir()
    return d


def test_detect_ollama_falls_back_to_blob_when_show_unavailable(tmp_manifest_root: Path) -> None:
    """When subprocess returns 'unknown' (e.g. no daemon), the function
    should attempt the blob path before giving up. Confirms the chain."""
    fake = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="could not connect",
    )
    # Stage a real blob so the fallback succeeds
    root = tmp_path_for_blob_test(tmp_manifest_root)
    manifest_dir = root / "manifests" / "registry.ollama.ai" / "library" / "miniglm"
    manifest_dir.mkdir(parents=True)
    cfg_sha = "b" * 64
    (root / "blobs").mkdir(parents=True)
    (root / "blobs" / f"sha256-{cfg_sha}").write_text(json.dumps({
        "file_type": "q4_k_m", "model_family": "miniglm",
    }))
    (manifest_dir / "latest").write_text(json.dumps({
        "config": {"digest": f"sha256:{cfg_sha}", "size": 1},
        "layers": [],
    }))
    with patch("subprocess.run", return_value=fake):
        assert qm.detect_ollama_quantization("miniglm:latest", ollama_models_root=root) == "q4_k_m"


# ---------------------------------------------------------------------------
# Helpers — provider probes
# ---------------------------------------------------------------------------


def test_detect_ollama_returns_unknown_on_missing_binary(tmp_manifest_root: Path) -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert qm.detect_ollama_quantization("anything") == "unknown"


def test_detect_ollama_returns_unknown_on_timeout(tmp_manifest_root: Path) -> None:
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ollama", 10)):
        assert qm.detect_ollama_quantization("anything") == "unknown"


def test_detect_ollama_returns_unknown_on_non_zero_exit(tmp_manifest_root: Path) -> None:
    fake = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="err")
    with patch("subprocess.run", return_value=fake):
        assert qm.detect_ollama_quantization("anything") == "unknown"


def test_detect_ollama_returns_unknown_on_non_json_stdout(tmp_manifest_root: Path) -> None:
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout="not-json", stderr="")
    with patch("subprocess.run", return_value=fake):
        assert qm.detect_ollama_quantization("anything") == "unknown"


def test_detect_ollama_parses_quantization_key(tmp_manifest_root: Path) -> None:
    payload = json.dumps({"model_info": {"general.quantization_version": "Q4_K_M"}})
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=payload, stderr="")
    with patch("subprocess.run", return_value=fake):
        assert qm.detect_ollama_quantization("x") == "q4_k_m"


def test_detect_ollama_parses_show_text(tmp_manifest_root: Path) -> None:
    """Cluster-shipped Ollama 0.31.1 has no ``--json`` — fall back to
    parsing the plain text output (CORR-111 lesson, 2026-09-03).
    """
    text = (
        "  Model\n"
        "    architecture        gemma4\n"
        "    parameters          31.3B\n"
        "    quantization        Q4_K_M\n"
        "    requires            0.20.0\n\n"
        "  Capabilities\n"
        "    completion\n"
    )
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=text, stderr="")
    with patch("subprocess.run", return_value=fake):
        assert qm.detect_ollama_quantization("gemma4:31b") == "q4_k_m"


def test_detect_ollama_text_no_quantization_section(tmp_manifest_root: Path) -> None:
    """No quantization line in the show output → unknown."""
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="  Model\n    architecture gemma4\n", stderr=""
    )
    with patch("subprocess.run", return_value=fake):
        assert qm.detect_ollama_quantization("gemma4:31b") == "unknown"


def test_detect_ollama_falls_back_to_text_when_json_fails(tmp_manifest_root: Path) -> None:
    """First call returns rc=0 but non-JSON text → second call parses text."""
    calls = {"n": 0}

    def fake_run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0,
                stdout="Model\n  architecture gemma4\n  parameters 31B\n",
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0,
            stdout="Model\n  quantization Q4_K_M\n",
            stderr="",
        )

    with patch("subprocess.run", side_effect=fake_run):
        assert qm.detect_ollama_quantization("gemma4:31b") == "q4_k_m"
        assert calls["n"] == 2


def test_parse_ollama_show_text_extracts_quant(tmp_manifest_root: Path) -> None:
    text = (
        "  Model\n"
        "    architecture        gemma4\n"
        "    quantization        q8_0\n"
        "    requires            0.20.0\n\n"
        "  Capabilities\n"
    )
    assert qm._parse_ollama_show_text(text) == "q8_0"


def test_parse_ollama_show_text_returns_empty_when_missing(tmp_manifest_root: Path) -> None:
    assert qm._parse_ollama_show_text("") == ""
    assert qm._parse_ollama_show_text("  Capabilities\n    completion\n") == ""


def test_build_from_ollama_pull_uses_probe_when_successful(tmp_manifest_root: Path) -> None:
    with patch.object(qm, "detect_ollama_quantization", return_value="q4_k_m"):
        m = qm.build_from_ollama_pull(model="qwen3.5:27b")
    assert m.quantization == "q4_k_m"
    assert m.quantization_provenance == "ollama-pull"


def test_build_from_ollama_pull_falls_back_to_provider_default(tmp_manifest_root: Path) -> None:
    with patch.object(qm, "detect_ollama_quantization", return_value="unknown"):
        m = qm.build_from_ollama_pull(model="qwen3.5:27b")
    assert m.quantization == "provider_default"
    assert m.quantization_provenance == "provider_default"


# ---------------------------------------------------------------------------
# Helpers — frontmatter + doc header
# ---------------------------------------------------------------------------


def test_frontmatter_comment_format(tmp_manifest_root: Path) -> None:
    s = qm.frontmatter_comment(
        model="qwen3.5:27b",
        provider="ollama",
        quant="q4_K_M",
        job=1862819,
        spec="P1B-LLM-01-INTERPRETATION",
    )
    assert s.startswith("<!-- aegis:")
    assert s.endswith("-->")
    assert 'model="qwen3.5:27b"' in s
    assert 'provider="ollama"' in s
    assert 'quant="q4_K_M"' in s
    assert 'job="1862819"' in s
    assert 'spec="P1B-LLM-01-INTERPRETATION"' in s
    # ts injected
    assert 'ts="' in s


def test_frontmatter_comment_escapes_quotes(tmp_manifest_root: Path) -> None:
    s = qm.frontmatter_comment(
        model='weird"model',
        provider="ollama",
        quant="q4_K_M",
        job=1,
        spec="X",
    )
    # Must not contain an unescaped " that would break out of the attribute
    assert 'model="weird&quot;model"' in s


def test_frontmatter_comment_blocks_double_dash_inside(tmp_manifest_root: Path) -> None:
    s = qm.frontmatter_comment(
        model="a--b",
        provider="ollama",
        quant="q4_K_M",
        job=1,
        spec="X",
    )
    # The '--' inside an HTML comment ends it; we must neutralise it. Only the
    # real terminator at the very end is allowed.
    assert s.rstrip().endswith("-->")
    inner = s.rstrip()[:-3]
    assert "-->" not in inner
    # The escape should have replaced '--' with U+2011 (non-breaking hyphen).
    assert "\u2011\u2011" in inner or "--" not in s.replace("-->", "")


@pytest.mark.parametrize(
    "quant,want_caveat",
    [
        ("q4_K_M", False),
        ("fp8", False),
        ("bf16", False),
        ("unknown", True),
        ("provider_default", True),
    ],
)
def test_header_for_doc_caveats(quant: str, want_caveat: bool) -> None:
    h = qm.header_for_doc(model="x", quant=quant, job=42)
    assert h.startswith(f"Model: x @ {quant} (job 42)")
    assert ("[" in h) == want_caveat


# ---------------------------------------------------------------------------
# Constraint — no third-party imports
# ---------------------------------------------------------------------------


def test_module_only_imports_stdlib() -> None:
    """Static guard: this module must depend only on stdlib (no httpx, etc.).

    The phase-1 policy (CORR-110) is 'no new project dependencies'. The
    manifest is intentionally pure-Python — verify via the AST that any new
    third-party import breaks this test loudly.
    """
    import ast

    src = Path(qm.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Modules under the aegis_phase1 package itself are fine; everything else
    # MUST be stdlib (we whitelist the stdlib names our module uses).
    stdlib_whitelist = {
        "os", "re", "json", "hashlib", "subprocess",
        "dataclasses", "datetime", "pathlib", "typing",
        "__future__",
    }

    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in stdlib_whitelist and not top.startswith("aegis_phase1"):
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in stdlib_whitelist and not module.startswith("aegis_phase1"):
                bad.append(node.module or "<unknown>")

    assert bad == [], f"third-party imports detected: {bad}"
